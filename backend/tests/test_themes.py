"""테마 엔타이틀먼트 — 카탈로그·지급·회수·권한 격리·탈퇴 연쇄 (docs/specs/theme-mall.md)."""

from sqlalchemy import func, select

from app.core.security import SESSION_COOKIE, create_session_token
from app.models import Notification, ThemeGrant
from tests.test_friends import make_user
from tests.test_study import login


async def themes_by_key(client) -> dict:
    data = (await client.get("/api/themes")).json()
    return {item["key"]: item for item in data["items"]}


async def test_free_all_allowed_cat_locked_by_default(client, db_session):
    """free 테마는 전원 사용 가능, 제한 테마(cat)는 grant 없이는 잠김."""
    await login(client, db_session)
    by_key = await themes_by_key(client)
    assert set(by_key) == {"note", "candy", "lego", "excel", "cat"}
    for key in ("note", "candy", "lego", "excel"):
        assert by_key[key] == {"key": key, "access": "free", "allowed": True}
    assert by_key["cat"] == {"key": "cat", "access": "restricted", "allowed": False}


async def test_grant_unlocks_cat_and_notifies(admin_client, db_session):
    user = await make_user(db_session, "kitty@example.com", "냥집사")
    await db_session.commit()

    # 이메일은 대소문자 무관 조회 (저장은 소문자 원본)
    res = await admin_client.post(
        "/api/admin/themes/cat/grants",
        json={"email": "Kitty@Example.com", "note": "여름 이벤트"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "kitty@example.com"
    assert body["note"] == "여름 이벤트"

    # 보유자 목록·테마별 보유자 수에 반영
    grants = (await admin_client.get("/api/admin/themes/cat/grants")).json()["items"]
    assert [(g["email"], g["nickname"], g["note"]) for g in grants] == [
        ("kitty@example.com", "냥집사", "여름 이벤트")
    ]
    stats = (await admin_client.get("/api/admin/themes")).json()["items"]
    assert {s["key"]: s["grants"] for s in stats}["cat"] == 1

    # 지급 알림 적재 — payload 는 지급 시점 스냅샷
    notif = (
        await db_session.execute(select(Notification).where(Notification.user_id == user.id))
    ).scalar_one()
    assert notif.type == "theme_granted"
    assert notif.payload == {"theme_key": "cat", "note": "여름 이벤트"}

    # 당사자에게 cat 허용
    admin_client.cookies.set(SESSION_COOKIE, create_session_token(user))
    by_key = await themes_by_key(admin_client)
    assert by_key["cat"]["allowed"] is True


async def test_grant_validations(admin_client, db_session):
    await make_user(db_session, "kitty@example.com", "냥집사")
    await db_session.commit()

    # 미존재 유저 404
    res = await admin_client.post(
        "/api/admin/themes/cat/grants", json={"email": "ghost@example.com"}
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "user_not_found"

    # 중복 지급 409
    first = await admin_client.post(
        "/api/admin/themes/cat/grants", json={"email": "kitty@example.com"}
    )
    assert first.status_code == 200
    dup = await admin_client.post(
        "/api/admin/themes/cat/grants", json={"email": "kitty@example.com"}
    )
    assert dup.status_code == 409
    assert dup.json()["detail"] == "already_granted"

    # free 테마는 전원 사용 가능이라 지급 자체가 무의미 — 422
    free = await admin_client.post(
        "/api/admin/themes/note/grants", json={"email": "kitty@example.com"}
    )
    assert free.status_code == 422
    assert free.json()["detail"] == "theme_not_restricted"

    # 카탈로그에 없는 키 404
    unknown = await admin_client.post(
        "/api/admin/themes/neon/grants", json={"email": "kitty@example.com"}
    )
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "theme_not_found"


async def test_revoke_locks_again(admin_client, db_session):
    user = await make_user(db_session, "kitty@example.com", "냥집사")
    await db_session.commit()
    grant_id = (
        await admin_client.post("/api/admin/themes/cat/grants", json={"email": "kitty@example.com"})
    ).json()["id"]

    res = await admin_client.delete(f"/api/admin/themes/grants/{grant_id}")
    assert res.status_code == 204
    # 이미 회수된 grant 재회수는 404
    assert (await admin_client.delete(f"/api/admin/themes/grants/{grant_id}")).status_code == 404

    admin_client.cookies.set(SESSION_COOKIE, create_session_token(user))
    by_key = await themes_by_key(admin_client)
    assert by_key["cat"]["allowed"] is False


async def test_admin_api_forbidden_for_learner(client, db_session):
    await login(client, db_session)
    assert (await client.get("/api/admin/themes")).status_code == 403
    res = await client.post("/api/admin/themes/cat/grants", json={"email": "x@example.com"})
    assert res.status_code == 403


async def test_account_delete_cascades_grants(client, db_session):
    """sqlite 테스트는 FK cascade 미작동 — delete_me 의 명시 삭제 목록 검증."""
    me = await login(client, db_session)
    db_session.add(ThemeGrant(user_id=me.id, theme_key="cat"))
    await db_session.commit()

    assert (await client.delete("/api/me")).status_code == 204
    remaining = (
        await db_session.execute(
            select(func.count(ThemeGrant.id)).where(ThemeGrant.user_id == me.id)
        )
    ).scalar_one()
    assert remaining == 0


async def test_admin_allowed_all_without_grant(admin_client):
    """관리자는 grant 없이 전 테마 허용 — 백오피스 운영 확인용."""
    by_key = await themes_by_key(admin_client)
    assert all(item["allowed"] for item in by_key.values())


async def test_access_toggle_restricts_and_frees(admin_client, db_session):
    """관리자가 테마 정책을 전환 — free→restricted 잠금, restricted→free 전원 해제."""
    user = await make_user(db_session, "kitty@example.com", "냥집사")
    await db_session.commit()

    # candy 를 제한으로 전환 → grant 없는 유저는 잠김
    res = await admin_client.patch("/api/admin/themes/candy", json={"access": "restricted"})
    assert res.status_code == 200
    assert res.json() == {"key": "candy", "access": "restricted"}
    # 제한 전환 후엔 지급도 가능해진다
    grant = await admin_client.post(
        "/api/admin/themes/candy/grants", json={"email": "kitty@example.com"}
    )
    assert grant.status_code == 200

    # cat 을 무료로 전환 → grant 없이도 전원 허용
    res = await admin_client.patch("/api/admin/themes/cat", json={"access": "free"})
    assert res.status_code == 200

    admin_client.cookies.set(SESSION_COOKIE, create_session_token(user))
    by_key = await themes_by_key(admin_client)
    assert by_key["candy"] == {"key": "candy", "access": "restricted", "allowed": True}
    assert by_key["cat"] == {"key": "cat", "access": "free", "allowed": True}


async def test_access_toggle_locks_out_ungranted(admin_client, db_session):
    """제한 전환된 테마는 grant 없는 유저에게 잠긴다 (클라 가드가 note 복귀)."""
    user = await make_user(db_session, "plain@example.com", "일반인")
    await db_session.commit()
    await admin_client.patch("/api/admin/themes/excel", json={"access": "restricted"})

    admin_client.cookies.set(SESSION_COOKIE, create_session_token(user))
    by_key = await themes_by_key(admin_client)
    assert by_key["excel"] == {"key": "excel", "access": "restricted", "allowed": False}


async def test_access_toggle_validations(admin_client, client, db_session):
    # note 는 잠금 해제 복귀(fallback) 테마 — 제한 전환 금지
    res = await admin_client.patch("/api/admin/themes/note", json={"access": "restricted"})
    assert res.status_code == 422
    assert res.json()["detail"] == "fallback_theme_locked"

    # 카탈로그에 없는 키 404
    res = await admin_client.patch("/api/admin/themes/neon", json={"access": "restricted"})
    assert res.status_code == 404
    assert res.json()["detail"] == "theme_not_found"

    # 관리자 전용
    await login(client, db_session)
    res = await client.patch("/api/admin/themes/candy", json={"access": "restricted"})
    assert res.status_code == 403
