"""알림 센터 — 적재·조회·읽음·본인 격리·탈퇴 연쇄 삭제 (docs/specs/notifications.md)."""

from sqlalchemy import func, select

from app.core.security import SESSION_COOKIE, create_session_token
from app.models import Notification
from app.services.notifications import notify
from tests.test_friends import make_user
from tests.test_study import login


async def test_friend_request_notifies_target(client, db_session):
    me = await login(client, db_session)
    friend = await make_user(db_session, "friend@example.com", "친구")
    await db_session.commit()

    res = await client.post("/api/friends/requests", json={"email": "friend@example.com"})
    req_id = res.json()["id"]

    # 수신자 계정으로 확인 — payload 는 요청 시점 닉네임 스냅샷
    client.cookies.set(SESSION_COOKIE, create_session_token(friend))
    data = (await client.get("/api/notifications")).json()
    assert data["unread"] == 1
    item = data["items"][0]
    assert item["type"] == "friend_request"
    assert item["payload"] == {"from_name": me.nickname, "request_id": req_id}
    assert item["read_at"] is None and item["created_at"] is not None


async def test_accept_notifies_requester(client, db_session):
    me = await login(client, db_session)
    friend = await make_user(db_session, "friend@example.com", "친구")
    await db_session.commit()
    res = await client.post("/api/friends/requests", json={"email": "friend@example.com"})
    req_id = res.json()["id"]

    client.cookies.set(SESSION_COOKIE, create_session_token(friend))
    accept = await client.post(f"/api/friends/requests/{req_id}/accept")
    assert accept.status_code == 200

    # 수락 알림은 요청자(me)에게 — 내가 보낸 friend_request 는 내 목록에 없음
    client.cookies.set(SESSION_COOKIE, create_session_token(me))
    data = (await client.get("/api/notifications")).json()
    assert [n["type"] for n in data["items"]] == ["friend_accepted"]
    assert data["items"][0]["payload"] == {"from_name": friend.nickname}
    assert data["unread"] == 1


async def test_list_scopes_to_me_id_desc_with_unread(client, db_session):
    me = await login(client, db_session)
    other = await make_user(db_session, "other@example.com", "남")
    await notify(db_session, me.id, "friend_request", {"from_name": "a", "request_id": 1})
    await notify(db_session, me.id, "friend_accepted", {"from_name": "b"})
    await notify(db_session, other.id, "friend_accepted", {"from_name": "c"})
    await db_session.commit()

    data = (await client.get("/api/notifications")).json()
    # 내 것만 + 최신(id DESC) 순 — 타인(other) 알림 미포함
    assert [n["payload"]["from_name"] for n in data["items"]] == ["b", "a"]
    ids = [n["id"] for n in data["items"]]
    assert ids == sorted(ids, reverse=True)
    assert data["unread"] == 2


async def test_read_marks_selected_ids_only(client, db_session):
    me = await login(client, db_session)
    await notify(db_session, me.id, "friend_accepted", {"from_name": "a"})
    await notify(db_session, me.id, "friend_accepted", {"from_name": "b"})
    await db_session.commit()
    first_id = (await client.get("/api/notifications")).json()["items"][-1]["id"]

    res = await client.post("/api/notifications/read", json={"ids": [first_id]})
    assert res.json() == {"ok": True}

    data = (await client.get("/api/notifications")).json()
    assert data["unread"] == 1
    by_id = {n["id"]: n for n in data["items"]}
    assert by_id[first_id]["read_at"] is not None


async def test_read_all(client, db_session):
    me = await login(client, db_session)
    await notify(db_session, me.id, "friend_accepted", {"from_name": "a"})
    await notify(db_session, me.id, "friend_accepted", {"from_name": "b"})
    await db_session.commit()

    await client.post("/api/notifications/read", json={"all": True})
    data = (await client.get("/api/notifications")).json()
    assert data["unread"] == 0
    assert all(n["read_at"] is not None for n in data["items"])


async def test_read_ignores_foreign_ids(client, db_session):
    await login(client, db_session)
    other = await make_user(db_session, "other@example.com", "남")
    await notify(db_session, other.id, "friend_accepted", {"from_name": "x"})
    await db_session.commit()
    foreign_id = (
        await db_session.execute(select(Notification.id).where(Notification.user_id == other.id))
    ).scalar_one()

    await client.post("/api/notifications/read", json={"ids": [foreign_id]})
    # identity map 우회 컬럼 조회 — 타인 알림은 여전히 안읽음이어야 한다
    read_at = (
        await db_session.execute(select(Notification.read_at).where(Notification.id == foreign_id))
    ).scalar_one()
    assert read_at is None


async def test_account_delete_cascades_notifications(client, db_session):
    me = await login(client, db_session)
    await notify(db_session, me.id, "friend_accepted", {"from_name": "a"})
    await db_session.commit()

    res = await client.delete("/api/me")
    assert res.status_code == 204
    remaining = (
        await db_session.execute(
            select(func.count(Notification.id)).where(Notification.user_id == me.id)
        )
    ).scalar_one()
    assert remaining == 0
