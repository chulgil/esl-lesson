"""언어 학습 대화방 — 방 CRUD·랜덤 매칭·방 기준 번역·레거시 위임
(docs/specs/chat-language-rooms.md)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import Conversation, Friendship
from app.services import chat as chat_service
from app.services import chat_match
from app.services import translation as translation_service
from tests.test_chat import login, make_friends, send_body, two_friends
from tests.test_my_contents import login_as


@pytest.fixture(autouse=True)
def _fresh_state():
    chat_service.reset_caches()
    chat_match.reset()
    yield
    chat_service.reset_caches()
    chat_match.reset()


async def stub_translation(monkeypatch, mapping):
    """test_chat_translation.py 와 동일 패턴 — 엔진 체인을 대체해 실호출 금지."""

    async def fake_chain(text, target):
        return mapping.get(text)

    monkeypatch.setattr(translation_service, "_translate_via_chain", fake_chain)


# --- 방 get-or-create + 언어쌍 유니크 ---------------------------------------------


async def test_create_room_get_or_create_returns_existing(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    body = {"peer_id": b.id, "source_lang": "ko", "target_lang": "en"}

    first = await client.post("/api/chat/rooms", json=body)
    assert first.status_code == 201
    assert first.json()["created"] is True

    again = await client.post("/api/chat/rooms", json=body)
    assert again.status_code == 201
    assert again.json()["created"] is False
    assert again.json()["room"]["id"] == first.json()["room"]["id"]

    count = (await db_session.execute(select(func.count(Conversation.id)))).scalar_one()
    assert count == 1


async def test_reversed_lang_pair_is_a_separate_room(client, db_session):
    """한→영 과 영→한 은 별개 방 (스펙 결정 #1)."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    ko_en = (
        await client.post(
            "/api/chat/rooms", json={"peer_id": b.id, "source_lang": "ko", "target_lang": "en"}
        )
    ).json()["room"]
    en_ko = (
        await client.post(
            "/api/chat/rooms", json={"peer_id": b.id, "source_lang": "en", "target_lang": "ko"}
        )
    ).json()["room"]

    assert ko_en["id"] != en_ko["id"]
    count = (await db_session.execute(select(func.count(Conversation.id)))).scalar_one()
    assert count == 2


async def test_room_creation_requires_friend_and_valid_lang_pair(client, db_session):
    a = await login_as(client, db_session, "room-a@example.com")
    stranger = await login_as(client, db_session, "room-x@example.com")
    await login(client, db_session, a)

    not_friend = await client.post(
        "/api/chat/rooms", json={"peer_id": stranger.id, "source_lang": "ko", "target_lang": "en"}
    )
    assert not_friend.status_code == 404

    b = await login_as(client, db_session, "room-b@example.com")
    await make_friends(db_session, a, b)
    await login(client, db_session, a)

    same_lang = await client.post(
        "/api/chat/rooms", json={"peer_id": b.id, "source_lang": "ko", "target_lang": "ko"}
    )
    assert same_lang.status_code == 422

    bad_lang = await client.post(
        "/api/chat/rooms", json={"peer_id": b.id, "source_lang": "ko", "target_lang": "fr"}
    )
    assert bad_lang.status_code == 422

    self_room = await client.post(
        "/api/chat/rooms", json={"peer_id": a.id, "source_lang": "ko", "target_lang": "en"}
    )
    assert self_room.status_code == 400


async def test_room_list_shows_peer_lang_pair_and_status(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    created = (
        await client.post(
            "/api/chat/rooms", json={"peer_id": b.id, "source_lang": "ko", "target_lang": "en"}
        )
    ).json()["room"]

    rooms = (await client.get("/api/chat/rooms")).json()
    assert isinstance(rooms, list)
    row = next(r for r in rooms if r["id"] == created["id"])
    assert row["peer"]["id"] == b.id
    assert row["peer"]["nickname"] == b.nickname
    assert row["source_lang"] == "ko" and row["target_lang"] == "en"
    assert row["origin"] == "friend" and row["status"] == "active"


async def test_room_get_requires_participant(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    room = (
        await client.post(
            "/api/chat/rooms", json={"peer_id": b.id, "source_lang": "ko", "target_lang": "en"}
        )
    ).json()["room"]

    outsider = await login_as(client, db_session, "room-out@example.com")
    assert outsider is not None
    res = await client.get(f"/api/chat/rooms/{room['id']}")
    assert res.status_code == 403

    missing = await client.get("/api/chat/rooms/999999")
    assert missing.status_code == 404


# --- 방 기준 번역 (뷰어 설정 무관) -------------------------------------------------


async def test_room_message_translation_target_is_room_lang(client, db_session, monkeypatch):
    """방 메시지 응답의 translation target = 방 target (뷰어 설정과 무관 — 어떤
    UserSettings 도 세팅하지 않는다)."""
    a, b = await two_friends(client, db_session)
    await stub_translation(monkeypatch, {"안녕하세요": ("Hello", "haiku")})
    await login(client, db_session, a)
    room = (
        await client.post(
            "/api/chat/rooms", json={"peer_id": b.id, "source_lang": "ko", "target_lang": "en"}
        )
    ).json()["room"]

    sent = await client.post(
        "/api/chat/messages",
        json={"room_id": room["id"], "body": "안녕하세요", "client_msg_id": "cid-room0001"},
    )
    assert sent.status_code == 201
    assert sent.json()["translation"] == {"lang": "en", "text": "Hello"}

    listed = (await client.get(f"/api/chat/rooms/{room['id']}/messages")).json()
    assert listed["room"]["id"] == room["id"]
    row = next(m for m in listed["items"] if m["body"] == "안녕하세요")
    assert row["translation"] == {"lang": "en", "text": "Hello"}


async def test_room_message_in_target_lang_has_null_translation(client, db_session, monkeypatch):
    """target 언어로 친 메시지는 translation null (스펙 필수 테스트 케이스)."""
    a, b = await two_friends(client, db_session)
    calls: list[str] = []

    async def fail_if_called(text, target):
        calls.append(text)
        return ("should-not-be-used", "haiku")

    monkeypatch.setattr(translation_service, "_translate_via_chain", fail_if_called)
    await login(client, db_session, a)
    room = (
        await client.post(
            "/api/chat/rooms", json={"peer_id": b.id, "source_lang": "ko", "target_lang": "en"}
        )
    ).json()["room"]

    sent = await client.post(
        "/api/chat/messages",
        json={"room_id": room["id"], "body": "hello there", "client_msg_id": "cid-room0002"},
    )
    assert sent.json()["translation"] is None
    assert calls == []  # 엔진 호출 자체가 없어야 한다

    listed = (await client.get(f"/api/chat/rooms/{room['id']}/messages")).json()
    row = next(m for m in listed["items"] if m["body"] == "hello there")
    assert row["translation"] is None


# --- 나가기 ----------------------------------------------------------------------


async def test_leave_room_blocks_send_allows_read_and_is_idempotent(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    room = (
        await client.post(
            "/api/chat/rooms", json={"peer_id": b.id, "source_lang": "ko", "target_lang": "en"}
        )
    ).json()["room"]
    await client.post(
        "/api/chat/messages",
        json={"room_id": room["id"], "body": "hi", "client_msg_id": "cid-leave001"},
    )

    leave = await client.post(f"/api/chat/rooms/{room['id']}/leave")
    assert leave.status_code == 204

    blocked = await client.post(
        "/api/chat/messages",
        json={"room_id": room["id"], "body": "after", "client_msg_id": "cid-leave002"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "room_closed"

    read_after = await client.get(f"/api/chat/rooms/{room['id']}/messages")
    assert read_after.status_code == 200

    again = await client.post(f"/api/chat/rooms/{room['id']}/leave")
    assert again.status_code == 204  # 멱등

    listed = (await client.get("/api/chat/rooms")).json()
    row = next(r for r in listed if r["id"] == room["id"])
    assert row["status"] == "closed"


# --- origin 접근 규칙 --------------------------------------------------------------


async def test_match_room_send_without_friendship(client, db_session):
    """match 방은 친구 아님에도 전송 가능 (스펙 필수 테스트 케이스)."""
    a = await login_as(client, db_session, "match-a@example.com")
    b = await login_as(client, db_session, "match-b@example.com")
    row = (await db_session.execute(select(Friendship))).scalars().all()
    assert row == []  # 친구 아님을 확인

    room, _created = await chat_service.get_or_create_room(
        db_session, a.id, b.id, "ko", "en", origin="match"
    )
    await login(client, db_session, a)
    sent = await client.post(
        "/api/chat/messages",
        json={"room_id": room.id, "body": "hi stranger", "client_msg_id": "cid-match0001"},
    )
    assert sent.status_code == 201


async def test_friend_room_blocks_send_after_unfriend(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    room = (
        await client.post(
            "/api/chat/rooms", json={"peer_id": b.id, "source_lang": "ko", "target_lang": "en"}
        )
    ).json()["room"]

    friendship = (await db_session.execute(select(Friendship))).scalar_one()
    await db_session.delete(friendship)
    await db_session.commit()

    blocked = await client.post(
        "/api/chat/messages",
        json={"room_id": room["id"], "body": "still here", "client_msg_id": "cid-unfr0001"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "not_friends"


# --- 레거시 to_user_id 위임 --------------------------------------------------------


async def test_legacy_send_delegates_to_oldest_active_room(client, db_session):
    a, b = await two_friends(client, db_session)
    room, _created = await chat_service.get_or_create_room(
        db_session, a.id, b.id, "ja", "ko", origin="friend"
    )

    await login(client, db_session, a)
    sent = await client.post("/api/chat/messages", json=send_body(b.id, "legacy hi", "cid-lg00001"))
    assert sent.status_code == 201
    assert sent.json()["conversation_id"] == room.id

    count = (await db_session.execute(select(func.count(Conversation.id)))).scalar_one()
    assert count == 1  # 새 ko/en 방을 만들지 않고 기존 활성 방에 위임


async def test_legacy_send_reopens_closed_room_when_none_active(client, db_session):
    a, b = await two_friends(client, db_session)
    room, _created = await chat_service.get_or_create_room(
        db_session, a.id, b.id, "ko", "en", origin="friend"
    )
    await chat_service.leave_room(db_session, room, a.id)

    await login(client, db_session, a)
    sent = await client.post("/api/chat/messages", json=send_body(b.id, "revive", "cid-lg00002"))
    assert sent.status_code == 201
    assert sent.json()["conversation_id"] == room.id  # 새로 만들지 않고 재오픈

    count = (await db_session.execute(select(func.count(Conversation.id)))).scalar_one()
    assert count == 1
    await db_session.refresh(room)
    assert room.status == "active"


# --- 랜덤 매칭 --------------------------------------------------------------------


async def test_match_pairs_same_lang_users(client, db_session):
    a = await login_as(client, db_session, "mq-a@example.com")
    b = await login_as(client, db_session, "mq-b@example.com")

    await login(client, db_session, a)
    waiting = await client.post("/api/chat/match", json={"source_lang": "ko", "target_lang": "en"})
    assert waiting.json() == {"waiting": True}
    assert (await client.get("/api/chat/match")).json()["waiting"] is True

    await login(client, db_session, b)
    matched = await client.post("/api/chat/match", json={"source_lang": "ko", "target_lang": "en"})
    assert matched.status_code == 200
    room = matched.json()["room"]
    assert room["origin"] == "match"

    # A 도 더 이상 대기 중이 아니다
    await login(client, db_session, a)
    assert (await client.get("/api/chat/match")).json()["waiting"] is False


async def test_match_different_lang_pairs_not_matched(client, db_session):
    a = await login_as(client, db_session, "mq-c@example.com")
    b = await login_as(client, db_session, "mq-d@example.com")

    await login(client, db_session, a)
    await client.post("/api/chat/match", json={"source_lang": "ko", "target_lang": "en"})
    await login(client, db_session, b)
    res = await client.post("/api/chat/match", json={"source_lang": "en", "target_lang": "ko"})
    assert res.json() == {"waiting": True}


async def test_match_cancel(client, db_session):
    a = await login_as(client, db_session, "mq-e@example.com")
    await login(client, db_session, a)
    await client.post("/api/chat/match", json={"source_lang": "ko", "target_lang": "en"})
    assert (await client.get("/api/chat/match")).json()["waiting"] is True

    cancelled = await client.delete("/api/chat/match")
    assert cancelled.status_code == 204
    assert (await client.get("/api/chat/match")).json()["waiting"] is False


async def test_match_excludes_recently_closed_pair_for_24h(client, db_session):
    a = await login_as(client, db_session, "mq-f@example.com")
    b = await login_as(client, db_session, "mq-g@example.com")
    room, _created = await chat_service.get_or_create_room(
        db_session, a.id, b.id, "ko", "en", origin="match"
    )
    await chat_service.leave_room(db_session, room, a.id)

    await login(client, db_session, a)
    first = await client.post("/api/chat/match", json={"source_lang": "ko", "target_lang": "en"})
    assert first.json() == {"waiting": True}
    await login(client, db_session, b)
    second = await client.post("/api/chat/match", json={"source_lang": "ko", "target_lang": "en"})
    assert second.json() == {"waiting": True}  # 24h 내 재매칭 회피

    # 종료 시각을 25시간 전으로 되돌리면 다시 매칭된다
    room.closed_at = datetime.now(UTC) - timedelta(hours=25)
    await db_session.commit()
    chat_match.reset()

    await login(client, db_session, a)
    await client.post("/api/chat/match", json={"source_lang": "ko", "target_lang": "en"})
    await login(client, db_session, b)
    rematched = await client.post(
        "/api/chat/match", json={"source_lang": "ko", "target_lang": "en"}
    )
    assert rematched.json()["room"]["id"] == room.id


async def test_match_validates_lang_pair(client, db_session):
    a = await login_as(client, db_session, "mq-h@example.com")
    await login(client, db_session, a)
    res = await client.post("/api/chat/match", json={"source_lang": "ko", "target_lang": "ko"})
    assert res.status_code == 422


# --- 일반 대화 방 (mode='plain', 스펙 §일반 대화 방) --------------------------------


async def test_plain_room_separate_from_learn_and_unique_per_pair(client, db_session):
    """같은 쌍에 학습 방과 일반 방이 공존하고, 일반 방은 쌍당 1개."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    learn = await client.post(
        "/api/chat/rooms", json={"peer_id": b.id, "source_lang": "ko", "target_lang": "en"}
    )
    plain = await client.post(
        "/api/chat/rooms",
        json={"peer_id": b.id, "source_lang": "ja", "target_lang": "ko", "mode": "plain"},
    )
    assert plain.status_code == 201
    assert plain.json()["created"] is True
    assert plain.json()["room"]["mode"] == "plain"
    assert learn.json()["room"]["id"] != plain.json()["room"]["id"]

    # 언어쌍을 다르게 보내도 일반 방은 ko→en 정규화 — 쌍당 1개로 수렴
    again = await client.post(
        "/api/chat/rooms",
        json={"peer_id": b.id, "source_lang": "ko", "target_lang": "ja", "mode": "plain"},
    )
    assert again.json()["created"] is False
    assert again.json()["room"]["id"] == plain.json()["room"]["id"]


async def test_plain_room_messages_have_no_translation(client, db_session, monkeypatch):
    """일반 방은 전송 응답·목록 조회 모두 translation 이 붙지 않는다."""
    await stub_translation(monkeypatch, {"밥 먹었어요?": ("Did you eat?", "haiku")})
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    room_id = (
        await client.post(
            "/api/chat/rooms",
            json={"peer_id": b.id, "source_lang": "ko", "target_lang": "en", "mode": "plain"},
        )
    ).json()["room"]["id"]

    sent = await client.post(
        "/api/chat/messages",
        json={"room_id": room_id, "body": "밥 먹었어요?", "client_msg_id": "plain-000001"},
    )
    assert sent.status_code == 201
    assert sent.json()["translation"] is None

    listed = await client.get(f"/api/chat/rooms/{room_id}/messages")
    assert listed.json()["items"][0]["translation"] is None
    assert listed.json()["room"]["mode"] == "plain"

    # 단건 번역 엔드포인트도 plain 방에서는 null
    mid = listed.json()["items"][0]["id"]
    single = await client.get(f"/api/chat/messages/{mid}/translation")
    assert single.json()["translation"] is None


async def test_plain_match_bucket_ignores_lang_pair(client, db_session):
    """일반 매칭은 언어쌍 무관 단일 버킷 — ja→ko 로 참가해도 ko→en 대기자와 성사."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    first = await client.post(
        "/api/chat/match", json={"source_lang": "ko", "target_lang": "en", "mode": "plain"}
    )
    assert first.json() == {"waiting": True}

    await login(client, db_session, b)
    second = await client.post(
        "/api/chat/match", json={"source_lang": "ja", "target_lang": "ko", "mode": "plain"}
    )
    room = second.json()["room"]
    assert room["mode"] == "plain"
    assert room["origin"] == "match"

    # 학습 매칭 대기자와는 섞이지 않는다
    await login(client, db_session, a)
    learn_wait = await client.post(
        "/api/chat/match", json={"source_lang": "ko", "target_lang": "en"}
    )
    assert learn_wait.json() == {"waiting": True}


async def test_plain_room_excluded_from_my_phrases(client, db_session, monkeypatch):
    """plain 방 발화는 내가 쓰는 말 수집 대상이 아니다 (스펙 §일반 대화 방)."""
    from app.models import ChatTranslation
    from app.services.langs import normalize_text_key

    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    room_id = (
        await client.post(
            "/api/chat/rooms",
            json={"peer_id": b.id, "source_lang": "ko", "target_lang": "en", "mode": "plain"},
        )
    ).json()["room"]["id"]
    # 번역 캐시가 있어도 (plain 방이라) 수집되면 안 된다
    db_session.add(
        ChatTranslation(
            text_key=normalize_text_key("일반 방에서 자주 하는 말"),
            source_lang="ko",
            target_lang="en",
            text="A phrase from the plain room",
            engine="seed",
        )
    )
    await db_session.commit()
    for i in range(2):
        await client.post(
            "/api/chat/messages",
            json={
                "room_id": room_id,
                "body": "일반 방에서 자주 하는 말",
                "client_msg_id": f"plain-mp-{i:06d}",
            },
        )

    summary = (await client.get("/api/study/my-phrases?lang=en")).json()
    assert summary["total"] == 0
