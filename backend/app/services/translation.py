"""채팅 자동번역 엔진 체인 — 캐시 → DeepL Free → Haiku 폴백 (docs/specs/chat-translation.md).

비용 방어 2층: 문장 단위 공유 캐시(ChatTranslation)가 1층, 월 예산 하드캡과
사용자 일일 한도가 2층. 캐시 미스가 한도를 넘으면 번역 없이 None 을 반환해
우아하게 중단한다 — 채팅 전송·조회 자체는 항상 정상 동작한다.

엔진은 DeepL Free 우선, 미설정이거나 실패하면 Haiku 로 폴백한다. 둘 다
실패하면 None. 커밋은 호출자 책임 — 이 모듈은 flush 까지만 한다.
"""

import logging
from datetime import UTC, datetime, timedelta, timezone

import httpx
from anthropic import AsyncAnthropic
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.translation import ChatTranslation, TranslationUsage
from app.models.user import UserSettings
from app.services.langs import (
    DEEPL_CODES,
    LANG_LABELS,
    detect_lang,
    has_translatable_text,
    normalize_text_key,
)

logger = logging.getLogger(__name__)

DEEPL_URL = "https://api-free.deepl.com/v2/translate"
KST = timezone(timedelta(hours=9))


def current_month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def current_day_start_kst(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.astimezone(KST).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def _target_lang(text: str, settings: UserSettings | None) -> str | None:
    """번역 방향 결정 — 모국어면 학습언어로, 그 외(=학습언어로 씀)는 모국어로."""
    primary = settings.primary_lang if settings and settings.primary_lang else "ko"
    learning = settings.learning_langs if settings and settings.learning_langs else ["en"]
    src = detect_lang(text)
    target = learning[0] if src == primary else primary
    return None if src == target else target


async def _within_budget(db: AsyncSession, user_id: int) -> bool:
    cfg = get_settings()
    now = datetime.now(UTC)
    month_chars = (
        await db.execute(
            select(func.coalesce(func.sum(TranslationUsage.chars), 0)).where(
                TranslationUsage.created_at >= current_month_start(now)
            )
        )
    ).scalar_one()
    if month_chars >= cfg.translate_monthly_budget_chars:
        return False

    today_calls = (
        await db.execute(
            select(func.count(TranslationUsage.id)).where(
                TranslationUsage.user_id == user_id,
                TranslationUsage.created_at >= current_day_start_kst(now),
            )
        )
    ).scalar_one()
    return today_calls < cfg.translate_user_daily_limit


async def translate_chat(
    db: AsyncSession, user_id: int, text: str, settings: UserSettings | None
) -> dict | None:
    """캐시 → 한도 게이트 → 엔진 체인. 성공 시 {"lang": ..., "text": ...}, 아니면 None."""
    # 이모티콘·초성 전용 메시지는 번역 대상 아님 (2026-08-12 실측 — 음차 오염 방지)
    if not has_translatable_text(text):
        return None
    target = _target_lang(text, settings)
    if target is None:
        return None

    key = normalize_text_key(text)
    cached = (
        await db.execute(
            select(ChatTranslation.text).where(
                ChatTranslation.text_key == key, ChatTranslation.target_lang == target
            )
        )
    ).scalar_one_or_none()
    if cached is not None:
        return {"lang": target, "text": cached}

    if not await _within_budget(db, user_id):
        return None

    src = detect_lang(text)
    chain_result = await _translate_via_chain(text, target)
    if chain_result is None:
        return None
    translated, engine = chain_result

    try:
        # SAVEPOINT — 동시 요청의 캐시 삽입 경합(uq_chat_translations_key_lang)이
        # 이번 호출만 롤백하게 격리 (theme_rewards.py 의 병렬 grant 경합 픽스와 동일 패턴,
        # 2026-08-11). 없으면 이 실패가 같은 루프에서 앞서 flush 된 다른 문장의
        # 번역 캐시까지 통째로 날린다.
        async with db.begin_nested():
            db.add(
                ChatTranslation(
                    text_key=key,
                    source_lang=src,
                    target_lang=target,
                    text=translated,
                    engine=engine,
                )
            )
            await db.flush()
    except IntegrityError:
        existing = (
            await db.execute(
                select(ChatTranslation.text).where(
                    ChatTranslation.text_key == key, ChatTranslation.target_lang == target
                )
            )
        ).scalar_one()
        return {"lang": target, "text": existing}

    db.add(TranslationUsage(user_id=user_id, chars=len(text), engine=engine))
    await db.flush()
    return {"lang": target, "text": translated}


async def _translate_via_chain(text: str, target: str) -> tuple[str, str] | None:
    """Haiku(원어민 캐주얼 프롬프트) 우선, DeepL 폴백.

    2026-08-12 실측 감사(프로덕션 196건): DeepL 이 문맥 없는 채팅 단문에서
    의미 반전 오역("어디 안 가요"→"Where are you going?")·의성어 음차·직역을
    냈다. 이 번역은 '내가 쓰는 말' 학습 재료가 되므로 품질 우선 — LLM 이
    화용을 이해해 자연스럽다. 비용은 캐시+하드캡으로 방어(개인 사용 규모에서
    사실상 0), DeepL 은 무료 폴백으로 유지.
    """
    cfg = get_settings()
    try:
        translated = await _call_haiku(text, target)
        if translated:
            return translated, "haiku"
    except Exception:  # noqa: BLE001 — 실패는 폴백으로, 채팅은 계속 진행
        logger.warning("haiku translate failed, falling back to deepl text=%r", text[:40])
    if cfg.deepl_api_key:
        try:
            translated = await _call_deepl(text, target, cfg.deepl_api_key)
            if translated:
                return translated, "deepl"
        except Exception:  # noqa: BLE001
            logger.exception("deepl translate failed text=%r", text[:40])
    return None


async def _call_deepl(text: str, target: str, api_key: str) -> str | None:
    async with httpx.AsyncClient(timeout=8.0) as client:
        res = await client.post(
            DEEPL_URL,
            headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
            json={"text": [text], "target_lang": DEEPL_CODES[target]},
        )
        res.raise_for_status()
        data = res.json()
    translations = data.get("translations") or []
    return translations[0]["text"] if translations else None


def _haiku_client() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=get_settings().anthropic_api_key, timeout=10, max_retries=1)


def _first_text(res) -> str:
    """응답에서 첫 텍스트 블록 추출 — thinking 블록이 선행될 수 있음 (claude-sonnet-5)."""
    for block in res.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise ValueError("no text block in response")


def _haiku_system(target: str) -> str:
    """원어민 채팅체 지시 — 직역·음차·과한 슬랭 방지.

    2026-08-12 실서버 검증 2회 반영: 1차 프롬프트는 오역은 줄였지만 존댓말
    원문에 10대 슬랭(rn·fr·yo)과 원문에 없는 이모지를 붙였고 "어디 안 가요"
    의문문 오역이 남았다. 어조 준수·슬랭 금지·평서/의문 구분을 명시하자
    전 케이스가 자연스러운 원어민 문장으로 나왔다 (실측 7문장).
    """
    style = (
        "미국인이 일상 문자에서 실제로 쓰는 자연스러운 영어"
        if target == "en"
        else f"원어민이 메신저에서 실제로 쓰는 자연스러운 {LANG_LABELS[target]} 대화체"
    )
    # 대상 언어권의 흔한 이름으로 — 양방향 (2026-08-12 요청: 한글 방향도 동일)
    name_examples = {
        "en": "예: 혜인님 → Hailey, 지영씨 → Jenny, 민준 → Mason",
        "ko": "예: Chris → 민준, Emily → 지은, Hailey → 혜린",
        "ja": "예: 혜인 → さくら, Chris → ゆうた",
    }[target]
    return (
        f"친구·동료 사이의 채팅 메시지를 {style}로 번역한다. "
        "한국어 채팅의 늘임말(요오·당·음)·초성(ㅋㅋ)·의성어의 뉘앙스를 이해하고 "
        "직역·음차 대신 의미와 말투를 옮긴다. "
        "준말·축약을 정확히 해석한다: 낼=내일, 넘=너무, 글고=그리고, 어케=어떻게. "
        "특히 '담에/다음에'는 반드시 next time 또는 sometime 으로 옮긴다 — "
        "절대 tomorrow 가 아니다 (2026-08-12 실사용 오역 제보). "
        "원문의 어조를 따른다 — 존댓말이면 정중하고 다정한 캐주얼로, 반말이면 편한 캐주얼로. "
        "과한 슬랭(rn, fr, yo 등)과 원문에 없는 이모지는 넣지 않는다. "
        "평서문을 의문문으로 바꾸지 않는다 (예: 어디 안 가요 = I am not going anywhere). "
        f"사람 이름(님·씨·야 호칭 포함)은 반드시 발음·성별을 고려해 {LANG_LABELS[target]}권에서 "
        f"흔한 이름으로 바꾼다 — 로마자·원어 표기를 그대로 두지 않는다 ({name_examples}). "
        "단, 직급·직함(팀장님·부장님·과장님 등)은 바꾸지 않고 그대로 옮긴다. "
        "같은 이름은 항상 같은 이름으로 옮긴다. 번역문만 출력한다."
    )


async def anonymize_names(text: str, lang: str) -> str:
    """학습자료용 실명 치환 — 문장 속 사람 이름을 같은 언어권의 다른 평범한
    이름으로 바꾼다 (2026-08-12 요청: 학습 카드에 지인 실명이 박제되지 않게).

    직급·직함(팀장님·부장님 등)은 그대로 둔다. 이름이 없으면 원문 그대로.
    실패·키 미설정 시 원문 반환 (학습자료 생성을 막지 않는다).
    """
    cfg = get_settings()
    if not cfg.anthropic_api_key:
        return text
    try:
        client = _haiku_client()
        res = await client.messages.create(
            model=cfg.anthropic_translate_model,
            max_tokens=1000,
            system=(
                f"문장 속 사람 이름(님·씨·야 호칭 포함)을 {LANG_LABELS.get(lang, '같은 언어')}권의 "
                "다른 평범한 이름으로 바꾼다 — 성별 유지. "
                "직급·직함(팀장님·부장님·과장님 등)은 바꾸지 않는다. "
                "이름이 없으면 원문을 그대로 출력한다. 그 외 어떤 것도 바꾸지 않는다. "
                "문장만 출력한다."
            ),
            messages=[{"role": "user", "content": text}],
        )
        out = _first_text(res).strip()
        return out or text
    except Exception:  # noqa: BLE001 — 익명화 실패는 원문으로 진행
        logger.warning("name anonymize failed text=%r", text[:40])
        return text


async def _call_haiku(text: str, target: str) -> str | None:
    cfg = get_settings()
    if not cfg.anthropic_api_key:
        return None
    client = _haiku_client()
    res = await client.messages.create(
        model=cfg.anthropic_translate_model,
        max_tokens=1000,
        system=_haiku_system(target),
        messages=[{"role": "user", "content": text}],
    )
    out = _first_text(res).strip()
    return out or None
