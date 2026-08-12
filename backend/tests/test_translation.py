"""채팅 자동번역 엔진 체인 — 캐시·한도·DeepL/Haiku 폴백 (services/translation.py)."""

from types import SimpleNamespace

from sqlalchemy import func, select

from app.core.config import get_settings
from app.models import ChatTranslation, TranslationUsage
from app.services import translation
from app.services.langs import normalize_text_key


def settings_of(primary="ko", learning=None):
    return SimpleNamespace(primary_lang=primary, learning_langs=learning or ["en"])


# --- 번역 방향 결정 --------------------------------------------------------------


async def test_direction_primary_to_learning(db_session, monkeypatch):
    """모국어(primary) 문장 → 학습언어(learning_langs[0])로 번역."""

    async def fake_chain(text, target):
        assert target == "en"
        return "hello", "haiku"

    monkeypatch.setattr(translation, "_translate_via_chain", fake_chain)
    result = await translation.translate_chat(db_session, 1, "안녕", settings_of())
    assert result == {"lang": "en", "text": "hello"}


async def test_direction_learning_to_primary(db_session, monkeypatch):
    """학습언어로 쓴 문장 → 모국어(primary)로 번역."""

    async def fake_chain(text, target):
        assert target == "ko"
        return "안녕", "haiku"

    monkeypatch.setattr(translation, "_translate_via_chain", fake_chain)
    result = await translation.translate_chat(db_session, 1, "hello", settings_of())
    assert result == {"lang": "ko", "text": "안녕"}


async def test_same_source_and_target_returns_none(db_session, monkeypatch):
    """감지 언어가 이미 타깃과 같으면(모국어=학습언어 오설정 등) 번역 없이 None."""
    called = False

    async def fake_chain(text, target):
        nonlocal called
        called = True
        return "x", "haiku"

    monkeypatch.setattr(translation, "_translate_via_chain", fake_chain)
    result = await translation.translate_chat(
        db_session, 1, "hello", settings_of(primary="en", learning=["en"])
    )
    assert result is None
    assert called is False


async def test_defaults_when_settings_none(db_session, monkeypatch):
    """설정 미존재(신규 유저) — 기본 primary=ko, learning=[en]."""

    async def fake_chain(text, target):
        assert target == "en"
        return "hi", "haiku"

    monkeypatch.setattr(translation, "_translate_via_chain", fake_chain)
    result = await translation.translate_chat(db_session, 1, "안녕하세요", None)
    assert result == {"lang": "en", "text": "hi"}


# --- 캐시 ------------------------------------------------------------------------


async def test_cache_hit_skips_engine_and_usage(db_session, monkeypatch):
    db_session.add(
        ChatTranslation(
            text_key="hello world",
            source_lang="en",
            target_lang="ko",
            text="안녕 세상",
            engine="haiku",
        )
    )
    await db_session.commit()

    async def boom(text, target):
        raise AssertionError("engine should not be called on cache hit")

    monkeypatch.setattr(translation, "_translate_via_chain", boom)
    result = await translation.translate_chat(db_session, 1, "Hello World", settings_of())

    assert result == {"lang": "ko", "text": "안녕 세상"}
    usage_count = (await db_session.execute(select(func.count(TranslationUsage.id)))).scalar_one()
    assert usage_count == 0  # 캐시 히트는 사용량 미기록


# --- 한도 게이트 -------------------------------------------------------------------


async def test_monthly_budget_exceeded_returns_none(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "translate_monthly_budget_chars", 10)
    db_session.add(TranslationUsage(user_id=1, chars=10, engine="haiku"))
    await db_session.commit()

    called = False

    async def fake_chain(text, target):
        nonlocal called
        called = True
        return "x", "haiku"

    monkeypatch.setattr(translation, "_translate_via_chain", fake_chain)
    result = await translation.translate_chat(db_session, 1, "hello", settings_of())
    assert result is None
    assert called is False


async def test_daily_user_limit_exceeded_returns_none(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "translate_user_daily_limit", 2)
    db_session.add_all(
        [
            TranslationUsage(user_id=1, chars=5, engine="haiku"),
            TranslationUsage(user_id=1, chars=5, engine="haiku"),
        ]
    )
    await db_session.commit()

    called = False

    async def fake_chain(text, target):
        nonlocal called
        called = True
        return "x", "haiku"

    monkeypatch.setattr(translation, "_translate_via_chain", fake_chain)
    result = await translation.translate_chat(db_session, 1, "hello", settings_of())
    assert result is None
    assert called is False

    # 다른 사용자는 한도 영향 없음 (사용자별 한도)
    monkeypatch.setattr(translation, "_translate_via_chain", fake_chain)
    result2 = await translation.translate_chat(db_session, 2, "hello", settings_of())
    assert called is True
    assert result2 == {"lang": "ko", "text": "x"}


# --- 엔진 체인: DeepL → Haiku 폴백 -------------------------------------------------


async def test_deepl_used_when_configured(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "deepl_api_key", "test-key")

    async def fake_deepl(text, target, api_key):
        assert api_key == "test-key"
        return "hi"

    async def boom_haiku(text, target):
        raise AssertionError("haiku should not be called when deepl succeeds")

    monkeypatch.setattr(translation, "_call_deepl", fake_deepl)
    monkeypatch.setattr(translation, "_call_haiku", boom_haiku)

    result = await translation.translate_chat(db_session, 7, "안녕", settings_of())
    assert result == {"lang": "en", "text": "hi"}

    row = (await db_session.execute(select(ChatTranslation))).scalar_one()
    assert row.engine == "deepl"
    usage = (await db_session.execute(select(TranslationUsage))).scalar_one()
    assert usage.engine == "deepl" and usage.user_id == 7 and usage.chars == len("안녕")


async def test_deepl_failure_falls_back_to_haiku(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "deepl_api_key", "test-key")

    async def failing_deepl(text, target, api_key):
        raise RuntimeError("deepl down")

    async def fake_haiku(text, target):
        return "hi"

    monkeypatch.setattr(translation, "_call_deepl", failing_deepl)
    monkeypatch.setattr(translation, "_call_haiku", fake_haiku)

    result = await translation.translate_chat(db_session, 1, "안녕", settings_of())
    assert result == {"lang": "en", "text": "hi"}
    row = (await db_session.execute(select(ChatTranslation))).scalar_one()
    assert row.engine == "haiku"


async def test_no_deepl_key_goes_straight_to_haiku(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "deepl_api_key", "")

    async def boom_deepl(text, target, api_key):
        raise AssertionError("deepl should not be called without a key")

    async def fake_haiku(text, target):
        return "hi"

    monkeypatch.setattr(translation, "_call_deepl", boom_deepl)
    monkeypatch.setattr(translation, "_call_haiku", fake_haiku)

    result = await translation.translate_chat(db_session, 1, "안녕", settings_of())
    assert result == {"lang": "en", "text": "hi"}


async def test_both_engines_fail_returns_none(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "deepl_api_key", "")

    async def failing_haiku(text, target):
        raise RuntimeError("haiku down")

    monkeypatch.setattr(translation, "_call_haiku", failing_haiku)
    result = await translation.translate_chat(db_session, 1, "안녕", settings_of())
    assert result is None
    count = (await db_session.execute(select(func.count(ChatTranslation.id)))).scalar_one()
    assert count == 0


# --- 동시 삽입 경합 (SAVEPOINT 격리) -----------------------------------------------


async def test_concurrent_cache_insert_returns_existing_row(db_session, monkeypatch):
    """다른 요청이 flush 직전에 같은 (text_key,target_lang) 행을 이미 커밋 완료한
    경합 상황 — theme_rewards.py 의 동시 grant 픽스와 동일 패턴으로 검증."""

    async def racy_chain(text, target):
        # 우리 flush 직전에 경쟁 요청이 같은 캐시 행을 커밋 완료한 상황 재현
        db_session.add(
            ChatTranslation(
                text_key=normalize_text_key(text),
                source_lang="ko",
                target_lang=target,
                text="경쟁 번역",
                engine="haiku",
            )
        )
        await db_session.commit()
        return "내 번역", "haiku"

    monkeypatch.setattr(translation, "_translate_via_chain", racy_chain)
    result = await translation.translate_chat(db_session, 1, "안녕", settings_of())
    assert result == {"lang": "en", "text": "경쟁 번역"}

    count = (await db_session.execute(select(func.count(ChatTranslation.id)))).scalar_one()
    assert count == 1  # 경합해도 캐시 행은 1개만
