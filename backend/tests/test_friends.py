"""친구 시스템 — 요청/수락/목록 + 학습 중(관전 가능) 표시."""

from app.services.game.spectate import spectate_hub
from tests.test_game_manager import Collector
from tests.test_study import login


async def make_user(db, email, name):
    from app.models import User

    user = User(google_sub=f"g-{email}", email=email, name=name)
    db.add(user)
    await db.flush()
    return user


async def test_friend_request_accept_flow(client, db_session):
    me = await login(client, db_session)
    friend = await make_user(db_session, "friend@example.com", "친구")
    await db_session.commit()

    # 요청 → 상대 수락 대기
    res = await client.post("/api/friends/requests", json={"email": "friend@example.com"})
    assert res.status_code == 200
    req_id = res.json()["id"]

    lst = (await client.get("/api/friends")).json()
    assert lst["friends"] == []
    assert [o["name"] for o in lst["outgoing"]] == ["친구"]

    # 상대 계정으로 수락
    from app.core.security import SESSION_COOKIE, create_session_token

    client.cookies.set(SESSION_COOKIE, create_session_token(friend))
    incoming = (await client.get("/api/friends")).json()
    assert [i["name"] for i in incoming["incoming"]] == [me.name]
    accept = await client.post(f"/api/friends/requests/{req_id}/accept")
    assert accept.status_code == 200

    # 양쪽 모두 친구 목록에 등장
    mine = (await client.get("/api/friends")).json()
    assert [f["name"] for f in mine["friends"]] == [me.name]

    client.cookies.set(SESSION_COOKIE, create_session_token(me))
    theirs = (await client.get("/api/friends")).json()
    assert [f["name"] for f in theirs["friends"]] == ["친구"]


async def test_friend_request_validations(client, db_session):
    me = await login(client, db_session)
    await make_user(db_session, "friend@example.com", "친구")
    await db_session.commit()

    missing = await client.post("/api/friends/requests", json={"email": "ghost@example.com"})
    assert missing.status_code == 404

    selfreq = await client.post("/api/friends/requests", json={"email": me.email})
    assert selfreq.status_code == 400

    first = await client.post("/api/friends/requests", json={"email": "friend@example.com"})
    assert first.status_code == 200
    dup = await client.post("/api/friends/requests", json={"email": "friend@example.com"})
    assert dup.status_code == 409


async def test_friends_list_shows_studying_with_watch_code(client, db_session):
    """학습 중(관전 허용) 친구는 studying=true + 관전 코드 노출 (수락제는 별도 유지)."""
    me = await login(client, db_session)
    friend = await make_user(db_session, "friend@example.com", "친구")
    await db_session.commit()

    res = await client.post("/api/friends/requests", json={"email": "friend@example.com"})
    req_id = res.json()["id"]
    from app.core.security import SESSION_COOKIE, create_session_token

    client.cookies.set(SESSION_COOKIE, create_session_token(friend))
    await client.post(f"/api/friends/requests/{req_id}/accept")

    # 친구가 학습 관전 호스팅 시작
    code = await spectate_hub.host(friend.id, friend.name, Collector())

    client.cookies.set(SESSION_COOKIE, create_session_token(me))
    lst = (await client.get("/api/friends")).json()
    entry = lst["friends"][0]
    assert entry["studying"] is True and entry["watch_code"] == code

    await spectate_hub.detach(friend.id)
    lst2 = (await client.get("/api/friends")).json()
    assert lst2["friends"][0]["studying"] is False
    assert lst2["friends"][0]["watch_code"] is None


async def test_friend_decline_and_remove(client, db_session):
    me = await login(client, db_session)
    friend = await make_user(db_session, "friend@example.com", "친구")
    await db_session.commit()
    res = await client.post("/api/friends/requests", json={"email": "friend@example.com"})
    req_id = res.json()["id"]

    from app.core.security import SESSION_COOKIE, create_session_token

    client.cookies.set(SESSION_COOKIE, create_session_token(friend))
    decline = await client.delete(f"/api/friends/requests/{req_id}")
    assert decline.status_code == 204
    assert (await client.get("/api/friends")).json()["incoming"] == []

    # 재요청 → 수락 → 삭제
    client.cookies.set(SESSION_COOKIE, create_session_token(me))
    req2 = (
        await client.post("/api/friends/requests", json={"email": "friend@example.com"})
    ).json()["id"]
    client.cookies.set(SESSION_COOKIE, create_session_token(friend))
    await client.post(f"/api/friends/requests/{req2}/accept")
    removed = await client.delete(f"/api/friends/{me.id}")
    assert removed.status_code == 204
    assert (await client.get("/api/friends")).json()["friends"] == []
