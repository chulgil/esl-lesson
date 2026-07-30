"""테마 엔타이틀먼트 — 카탈로그·지급·회수·권한 격리·탈퇴 연쇄 (docs/specs/theme-mall.md)."""

from sqlalchemy import func, select

from app.core.security import SESSION_COOKIE, create_session_token
from app.models import Notification, ThemeGrant
from tests.test_friends import make_user
from tests.test_study import login


async def themes_by_key(client) -> dict:
    data = (await client.get("/api/themes")).json()
    return {item["key"]: item for item in data["items"]}


async def test_only_note_free_by_default(client, db_session):
    """기본 무료는 note 하나 — 나머지는 미션 달성/지급으로만 열린다 (2026-07-30 전환)."""
    await login(client, db_session)
    by_key = await themes_by_key(client)
    assert set(by_key) == {"note", "candy", "lego", "excel", "cat"}
    assert by_key["note"]["access"] == "free" and by_key["note"]["allowed"] is True
    for key in ("candy", "lego", "excel", "cat"):
        assert by_key[key]["access"] == "restricted"
        assert by_key[key]["allowed"] is False


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
    assert by_key["candy"]["access"] == "restricted" and by_key["candy"]["allowed"] is True
    assert by_key["cat"]["access"] == "free" and by_key["cat"]["allowed"] is True


async def test_access_toggle_locks_out_ungranted(admin_client, db_session):
    """제한 전환된 테마는 grant 없는 유저에게 잠긴다 (클라 가드가 note 복귀)."""
    user = await make_user(db_session, "plain@example.com", "일반인")
    await db_session.commit()
    await admin_client.patch("/api/admin/themes/excel", json={"access": "restricted"})

    admin_client.cookies.set(SESSION_COOKIE, create_session_token(user))
    by_key = await themes_by_key(admin_client)
    assert by_key["excel"]["access"] == "restricted" and by_key["excel"]["allowed"] is False


async def test_reward_rule_crud_and_validations(admin_client):
    """업적 보상 규칙 — 백오피스에서 업적→테마 매핑 관리."""
    # 생성
    res = await admin_client.post(
        "/api/admin/themes/rewards",
        json={"achievement_key": "first_friend", "theme_key": "candy"},
    )
    assert res.status_code == 200
    rule_id = res.json()["id"]

    # 목록 — 업적 카탈로그 동봉 (폼 셀렉트용)
    listing = (await admin_client.get("/api/admin/themes/rewards")).json()
    assert [(r["achievement_key"], r["theme_key"]) for r in listing["items"]] == [
        ("first_friend", "candy")
    ]
    assert any(a["key"] == "first_game" for a in listing["achievements"])

    # 중복 409 / 미존재 업적 404 / free 테마 422
    dup = await admin_client.post(
        "/api/admin/themes/rewards",
        json={"achievement_key": "first_friend", "theme_key": "candy"},
    )
    assert dup.status_code == 409
    unknown = await admin_client.post(
        "/api/admin/themes/rewards",
        json={"achievement_key": "ghost_key", "theme_key": "candy"},
    )
    assert unknown.status_code == 404
    free = await admin_client.post(
        "/api/admin/themes/rewards",
        json={"achievement_key": "first_win", "theme_key": "note"},
    )
    assert free.status_code == 422

    # 삭제 — 규칙 삭제는 기존 지급에 영향 없음 (별도 테스트에서 검증)
    assert (await admin_client.delete(f"/api/admin/themes/rewards/{rule_id}")).status_code == 204
    assert (await admin_client.delete(f"/api/admin/themes/rewards/{rule_id}")).status_code == 404


async def test_achievement_grants_theme_and_keeps_it(client, admin_client, db_session):
    """첫 친구 달성 → candy 자동 지급 + 알림 + 이력(note). 규칙이 바뀌어도 보유 유지."""
    from app.models import ThemeRewardRule

    db_session.add(ThemeRewardRule(achievement_key="first_friend", theme_key="candy"))
    await db_session.commit()

    admin_cookie = admin_client.cookies.get(SESSION_COOKIE)
    me = await login(client, db_session)
    # 달성 전: candy 잠김
    by_key = await themes_by_key(client)
    assert by_key["candy"]["allowed"] is False

    # 수락된 친구 생성 → 첫 친구 달성
    friend = await make_user(db_session, "pal@example.com", "친구")
    from app.models.friend import Friendship

    db_session.add(Friendship(requester_id=me.id, addressee_id=friend.id, status="accepted"))
    await db_session.commit()

    # 테마 조회 시 보상 엔진이 소급 지급 — AppNav 가드 경로에서 잠김 오판 없음
    by_key = await themes_by_key(client)
    assert by_key["candy"]["allowed"] is True

    grant = (
        await db_session.execute(select(ThemeGrant).where(ThemeGrant.theme_key == "candy"))
    ).scalar_one()
    assert grant.user_id == me.id
    assert "첫 친구" in (grant.note or "")  # 이력: 어떤 업적으로 받았는지
    notif = (
        await db_session.execute(select(Notification).where(Notification.type == "theme_granted"))
    ).scalar_one()
    assert notif.payload["theme_key"] == "candy"

    # 재조회 멱등 — 중복 지급 없음
    await themes_by_key(client)
    count = (
        await db_session.execute(
            select(func.count(ThemeGrant.id)).where(ThemeGrant.theme_key == "candy")
        )
    ).scalar_one()
    assert count == 1

    # 달성 스펙(규칙)이 삭제돼도 이미 받은 테마는 유지
    # admin_client 는 client 와 동일 인스턴스(쿠키만 admin) — login 이 덮었으니 복원
    admin_client.cookies.set(SESSION_COOKIE, admin_cookie)
    rules = (await admin_client.get("/api/admin/themes/rewards")).json()["items"]
    await admin_client.delete(f"/api/admin/themes/rewards/{rules[0]['id']}")
    admin_client.cookies.set(SESSION_COOKIE, create_session_token(me))
    by_key = await themes_by_key(client)
    assert by_key["candy"]["allowed"] is True


async def test_themes_unlock_hint_from_rules(client, db_session):
    """잠긴 테마에 해금 업적 힌트 — 설정 화면 배지 문구용."""
    from app.models import ThemeRewardRule

    db_session.add(ThemeRewardRule(achievement_key="first_game", theme_key="lego"))
    await db_session.commit()
    await login(client, db_session)
    by_key = await themes_by_key(client)
    assert by_key["lego"]["unlock"] == "첫 게임"
    # unlock_key — 설정 화면이 업적 진행률과 조인하는 키
    assert by_key["lego"]["unlock_key"] == "first_game"
    assert by_key["cat"]["unlock"] is None


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
