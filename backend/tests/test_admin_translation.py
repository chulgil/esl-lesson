"""백오피스 번역 사용량 대시보드 (docs/specs/chat-translation.md)."""

from app.core.config import get_settings
from app.models import TranslationUsage
from tests.test_study import login


async def test_admin_only(client, db_session):
    await login(client, db_session)
    res = await client.get("/api/admin/translation-usage")
    assert res.status_code == 403


async def test_translation_usage_aggregates_month_and_engine(admin_client, db_session):
    db_session.add_all(
        [
            TranslationUsage(user_id=1, chars=100, engine="deepl"),
            TranslationUsage(user_id=1, chars=50, engine="deepl"),
            TranslationUsage(user_id=2, chars=30, engine="haiku"),
        ]
    )
    await db_session.commit()

    res = await admin_client.get("/api/admin/translation-usage")
    assert res.status_code == 200
    body = res.json()
    assert body["month_chars"] == 180
    assert body["budget_chars"] == get_settings().translate_monthly_budget_chars
    assert body["by_engine"] == {"deepl": 2, "haiku": 1}
    assert body["today_calls"] == 3


async def test_translation_usage_empty_state(admin_client, db_session):
    res = await admin_client.get("/api/admin/translation-usage")
    assert res.status_code == 200
    body = res.json()
    assert body["month_chars"] == 0
    assert body["by_engine"] == {"deepl": 0, "haiku": 0}
    assert body["today_calls"] == 0


async def test_translation_usage_excludes_last_month(admin_client, db_session):
    from datetime import UTC, datetime

    # 과거(다른 달) 사용량은 이번 달 합계·오늘 호출 수 어디에도 잡히면 안 된다.
    # created_at 은 서버 기본값을 쓰는 컬럼이라 직접 값을 지정해 과거로 고정한다.
    db_session.add(
        TranslationUsage(
            user_id=1, chars=999, engine="deepl", created_at=datetime(2020, 1, 1, tzinfo=UTC)
        )
    )
    db_session.add(TranslationUsage(user_id=1, chars=10, engine="haiku"))  # 이번 달(지금)
    await db_session.commit()

    res = await admin_client.get("/api/admin/translation-usage")
    body = res.json()
    assert body["month_chars"] == 10
    assert body["by_engine"] == {"deepl": 0, "haiku": 1}
    assert body["today_calls"] == 1
