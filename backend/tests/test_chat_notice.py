"""대화방 공지 — 자유 텍스트 고정 공지 (docs/specs/chat-notice.md)."""

import pytest
from sqlalchemy import select

import app.api.chat as chat_api
from app.models import ChatMessage, Friendship, SharedGoal
from app.services import chat as chat_service
from tests.test_chat import login, two_friends
from tests.test_my_contents import login_as
from tests.test_my_phrases import seed_translation


@pytest.fixture(autouse=True)
def _fresh_caches():
    chat_service.reset_caches()
    yield
    chat_service.reset_caches()


async def _fake_deliver(monkeypatch):
    pushed: list[tuple[int, dict]] = []

    async def fake(user_id, message):
        pushed.append((user_id, message))
        return True

    monkeypatch.setattr(chat_api.chat, "deliver_ws", fake)
    return pushed


# --- 조회: 대화 없음 ---------------------------------------------------------------


async def test_get_notice_requires_friend_when_no_conversation(client, db_session):
    a = await login_as(client, db_session, "n-a@example.com")
    stranger = await login_as(client, db_session, "n-x@example.com")
    await login(client, db_session, a)

    res = await client.get(f"/api/chat/with/{stranger.id}/notice")
    assert res.status_code == 404


async def test_get_notice_null_before_any_set(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    res = await client.get(f"/api/chat/with/{b.id}/notice")
    assert res.status_code == 200
    assert res.json() == {"text": None}


# --- PUT → GET 반영, 교체 -----------------------------------------------------------


async def test_put_then_get_reflects_text(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    put = await client.put(f"/api/chat/with/{b.id}/notice", json={"text": "8월엔 매일 30분"})
    assert put.status_code == 200
    body = put.json()
    assert body["text"] == "8월엔 매일 30분"
    assert body["updated_by_name"] == a.nickname
    assert body["updated_at"] is not None

    got = await client.get(f"/api/chat/with/{b.id}/notice")
    assert got.json() == body


async def test_put_replaces_keeps_single_row(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    await client.put(f"/api/chat/with/{b.id}/notice", json={"text": "초안"})
    await login(client, db_session, b)
    replaced = await client.put(f"/api/chat/with/{a.id}/notice", json={"text": "수정된 공지"})
    assert replaced.json()["text"] == "수정된 공지"
    assert replaced.json()["updated_by_name"] == b.nickname

    rows = (
        (await db_session.execute(select(SharedGoal).where(SharedGoal.kind == "notice")))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].text == "수정된 공지"


# --- DELETE 멱등 -------------------------------------------------------------------


async def test_delete_then_get_null_and_idempotent(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.put(f"/api/chat/with/{b.id}/notice", json={"text": "지울 공지"})

    res = await client.delete(f"/api/chat/with/{b.id}/notice")
    assert res.status_code == 204

    got = await client.get(f"/api/chat/with/{b.id}/notice")
    assert got.json() == {"text": None}

    again = await client.delete(f"/api/chat/with/{b.id}/notice")
    assert again.status_code == 204


async def test_delete_noop_when_never_set_does_not_push(client, db_session, monkeypatch):
    a, b = await two_friends(client, db_session)
    pushed = await _fake_deliver(monkeypatch)
    await login(client, db_session, a)

    res = await client.delete(f"/api/chat/with/{b.id}/notice")
    assert res.status_code == 204
    assert pushed == []

    rows = (await db_session.execute(select(ChatMessage))).scalars().all()
    assert rows == []


# --- 422 검증 ------------------------------------------------------------------------


async def test_put_rejects_blank_text(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    res = await client.put(f"/api/chat/with/{b.id}/notice", json={"text": "   "})
    assert res.status_code == 422
    assert res.json()["detail"] == "invalid_text"


async def test_put_rejects_text_over_500_chars(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    res = await client.put(f"/api/chat/with/{b.id}/notice", json={"text": "가" * 501})
    assert res.status_code == 422
    assert res.json()["detail"] == "text_too_long"


# --- 권한 ----------------------------------------------------------------------------


async def test_put_requires_friend_when_no_conversation(client, db_session):
    a = await login_as(client, db_session, "n-a2@example.com")
    stranger = await login_as(client, db_session, "n-x2@example.com")
    await login(client, db_session, a)

    res = await client.put(f"/api/chat/with/{stranger.id}/notice", json={"text": "공지"})
    assert res.status_code == 404


async def test_unfriend_blocks_put_and_delete_but_keeps_view(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.put(f"/api/chat/with/{b.id}/notice", json={"text": "남는 공지"})

    row = (await db_session.execute(select(Friendship))).scalar_one()
    await db_session.delete(row)
    await db_session.commit()

    view = await client.get(f"/api/chat/with/{b.id}/notice")
    assert view.status_code == 200
    assert view.json()["text"] == "남는 공지"

    put = await client.put(f"/api/chat/with/{b.id}/notice", json={"text": "바꿔치기"})
    assert put.status_code == 403
    assert put.json()["detail"] == "not_friends"

    deleted = await client.delete(f"/api/chat/with/{b.id}/notice")
    assert deleted.status_code == 403
    assert deleted.json()["detail"] == "not_friends"


# --- 시스템 줄 적재 + WS 푸시 ---------------------------------------------------------


async def test_put_records_system_line_and_pushes_both(client, db_session, monkeypatch):
    a, b = await two_friends(client, db_session)
    pushed = await _fake_deliver(monkeypatch)
    await login(client, db_session, a)

    await client.put(f"/api/chat/with/{b.id}/notice", json={"text": "매일 10문제\n둘째줄"})

    rows = (await db_session.execute(select(ChatMessage))).scalars().all()
    assert len(rows) == 1
    assert rows[0].kind == "notice_set"
    assert rows[0].body == "매일 10문제"  # 첫 줄만 스냅샷
    assert rows[0].sender_id == a.id

    receivers = {uid for uid, _ in pushed}
    assert receivers == {a.id, b.id}
    kinds = {msg["t"] for _, msg in pushed}
    assert kinds == {"chat.message", "chat.notice"}
    system_events = [msg for _, msg in pushed if msg["t"] == "chat.message"]
    assert all(e["kind"] == "notice_set" for e in system_events)
    assert all(e["from_name"] == a.nickname for e in system_events)
    notice_sync_events = [msg for _, msg in pushed if msg["t"] == "chat.notice"]
    assert all("conversation_id" in e for e in notice_sync_events)


async def test_put_preview_truncated_to_80_chars(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    long_text = "가" * 200
    await client.put(f"/api/chat/with/{b.id}/notice", json={"text": long_text})

    row = (await db_session.execute(select(ChatMessage))).scalar_one()
    assert row.body == "가" * 80


async def test_delete_records_system_line_kind_notice_clear(client, db_session, monkeypatch):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.put(f"/api/chat/with/{b.id}/notice", json={"text": "내릴 공지"})

    pushed = await _fake_deliver(monkeypatch)
    await client.delete(f"/api/chat/with/{b.id}/notice")

    rows = (await db_session.execute(select(ChatMessage).order_by(ChatMessage.id))).scalars().all()
    assert rows[-1].kind == "notice_clear"
    assert rows[-1].body == ""
    assert rows[-1].sender_id == a.id

    receivers = {uid for uid, _ in pushed}
    assert receivers == {a.id, b.id}
    system_events = [msg for _, msg in pushed if msg["t"] == "chat.message"]
    assert all(e["kind"] == "notice_clear" for e in system_events)


# --- 기존 메시지 조회 API 가 kind 를 포함 --------------------------------------------


async def test_messages_endpoint_includes_kind_field(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.put(f"/api/chat/with/{b.id}/notice", json={"text": "공지 확인용"})

    res = await client.get(f"/api/chat/with/{b.id}/messages")
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "notice_set"


# --- my-phrases 는 시스템 줄을 수집하지 않는다 -----------------------------------------


async def test_my_phrases_does_not_collect_notice_system_lines(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    text = "오늘 회의 있어요"
    await client.put(f"/api/chat/with/{b.id}/notice", json={"text": text})
    await client.put(f"/api/chat/with/{b.id}/notice", json={"text": text})  # 빈도 2회 조건도 충족
    await seed_translation(db_session, text, "We have a meeting today")

    res = await client.get("/api/study/my-phrases")
    assert res.status_code == 200
    assert res.json()["total"] == 0
