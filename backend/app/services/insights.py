"""단어 인사이트 — 뉘앙스/유사단어/예문 lazy 생성 (docs/proposal/word-insight.md P1).

최초 조회 시 LLM 1회 생성 후 word_insights 에 영구 캐시(전역 공유).
예문은 사용자가 본 영상 문맥(occurrence)을 1순위로 재사용해 환각을 줄인다.
"""

import json
import logging

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ItemOccurrence, LearningItem, WordInsight

logger = logging.getLogger(__name__)

MAX_CONTEXTS = 2

PROMPT = """당신은 영어 어휘 코치다. 아래 표현의 학습 카드 정보를 JSON 하나로만 답하라.

표현: {en_text}
뜻: {ko_text}
유형: {item_type}
{context_block}
JSON 스키마 (모든 한국어 필드는 자연스러운 한국어로):
{{"ipa": "IPA 발음 기호",
 "pos": "품사(영어 약어)",
 "nuance_ko": "뉘앙스·격식 한 줄 (구어/문어, 톤)",
 "examples": [{{"en": "예문", "ko": "번역"}}, {{"en": "예문", "ko": "번역"}}],
 "collocations": ["자주 붙는 표현 3개"],
 "synonyms": [{{"word": "유의어", "ko": "뜻", "diff_ko": "언제 이 단어를 쓰는지 한 줄"}}],
 "confusables": [{{"word": "혼동어", "ko": "뜻", "diff_ko": "혼동 포인트 한 줄"}}]}}

규칙: synonyms 2-3개, confusables 1-2개. 실제 사용 문맥이 주어지면 첫 예문으로
자연스럽게 재사용. JSON 외 다른 텍스트 금지."""


def _parse_json(text: str) -> dict:
    """모델 응답에서 JSON 만 추출 — ```펜스/설명 텍스트 허용."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


async def _contexts(db: AsyncSession, item_id: int) -> list[str]:
    rows = (
        await db.execute(
            select(ItemOccurrence.context_en)
            .where(ItemOccurrence.item_id == item_id, ItemOccurrence.context_en.is_not(None))
            .limit(MAX_CONTEXTS)
        )
    ).scalars()
    return [r for r in rows if r]


def _first_text(res) -> str:
    """텍스트 블록만 추출 — thinking 등 비텍스트 블록 선행 대응 (extraction 과 동일 패턴)."""
    for block in res.content:
        text = getattr(block, "text", None)
        if text:
            return text
    raise ValueError("no text block in insight response")


# 한국어 페이로드(예문 2+유의어 3+혼동어 2)가 1000 토큰을 넘어 JSON 이 잘리면
# 파싱 실패 → 502 가 특정 단어에서 일관 재현 (2026-07-15 delegate 실측 대응)
TOKEN_BUDGETS = (2000, 4000)


async def _generate(item: LearningItem, contexts: list[str]) -> dict:
    settings = get_settings()
    context_block = (
        "실제 사용 문맥:\n" + "\n".join(f"- {c}" for c in contexts) + "\n" if contexts else ""
    )
    client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60, max_retries=2)
    prompt = PROMPT.format(
        en_text=item.en_text,
        ko_text=item.ko_text,
        item_type=item.item_type,
        context_block=context_block,
    )
    for max_tokens in TOKEN_BUDGETS:
        res = await client.messages.create(
            model=settings.anthropic_insight_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if res.stop_reason != "max_tokens":
            break
        logger.warning("insight truncated at %s tokens item=%s — retrying", max_tokens, item.id)
    else:
        raise ValueError("insight response truncated at max budget")

    payload = _parse_json(_first_text(res))
    if not isinstance(payload.get("examples"), list) or not payload["examples"]:
        raise ValueError("insight payload missing examples")
    return payload


async def get_or_generate(db: AsyncSession, item_id: int) -> dict | None:
    """캐시 반환, 없으면 생성+저장. 항목이 없으면 None."""
    cached = (
        await db.execute(select(WordInsight).where(WordInsight.item_id == item_id))
    ).scalar_one_or_none()
    if cached is not None:
        return cached.payload

    item = await db.get(LearningItem, item_id)
    if item is None:
        return None

    contexts = await _contexts(db, item_id)
    payload = await _generate(item, contexts)
    db.add(
        WordInsight(item_id=item_id, payload=payload, model=get_settings().anthropic_insight_model)
    )
    try:
        await db.commit()
    except IntegrityError:
        # 동시 생성 경합 — 먼저 저장된 쪽을 채택
        await db.rollback()
        winner = (
            await db.execute(select(WordInsight).where(WordInsight.item_id == item_id))
        ).scalar_one()
        return winner.payload
    return payload
