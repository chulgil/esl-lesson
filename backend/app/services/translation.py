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
from app.services.langs import DEEPL_CODES, LANG_LABELS, detect_lang, normalize_text_key

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
    cfg = get_settings()
    if cfg.deepl_api_key:
        try:
            translated = await _call_deepl(text, target, cfg.deepl_api_key)
            if translated:
                return translated, "deepl"
        except Exception:  # noqa: BLE001 — 실패는 폴백으로, 채팅은 계속 진행
            logger.warning("deepl translate failed, falling back to haiku text=%r", text[:40])
    try:
        translated = await _call_haiku(text, target)
        if translated:
            return translated, "haiku"
    except Exception:  # noqa: BLE001
        logger.exception("haiku translate failed text=%r", text[:40])
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


async def _call_haiku(text: str, target: str) -> str | None:
    cfg = get_settings()
    if not cfg.anthropic_api_key:
        return None
    client = _haiku_client()
    res = await client.messages.create(
        model=cfg.anthropic_translate_model,
        max_tokens=1000,
        system=f"자연스러운 대화체로 {LANG_LABELS[target]}로 번역하고 번역문만 출력한다.",
        messages=[{"role": "user", "content": text}],
    )
    out = _first_text(res).strip()
    return out or None
