"""대화방 공지 — 제목+내용 고정 공지 (docs/specs/chat-notice.md)."""

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
    assert res.json() == {"title": None, "text": None}


# --- PUT → GET 반영, 교체 -----------------------------------------------------------


async def test_put_then_get_reflects_title_and_text(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    put = await client.put(
        f"/api/chat/with/{b.id}/notice",
        json={"title": "8월 목표", "text": "매일 30분씩 복습하기"},
    )
    assert put.status_code == 200
    body = put.json()
    assert body["title"] == "8월 목표"
    assert body["text"] == "매일 30분씩 복습하기"
    assert body["updated_by_name"] == a.nickname
    assert body["updated_at"] is not None

    got = await client.get(f"/api/chat/with/{b.id}/notice")
    assert got.json() == body


async def test_put_title_only_is_allowed(client, db_session):
    """내용 없는 한 줄 공지 — 제목만으로도 성립한다."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    put = await client.put(f"/api/chat/with/{b.id}/notice", json={"title": "내일 쉬어요"})
    assert put.status_code == 200
    assert put.json()["title"] == "내일 쉬어요"
    assert put.json()["text"] == ""


async def test_put_replaces_keeps_single_row(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    await client.put(f"/api/chat/with/{b.id}/notice", json={"title": "초안", "text": "본문"})
    await login(client, db_session, b)
    replaced = await client.put(
        f"/api/chat/with/{a.id}/notice", json={"title": "수정된 공지", "text": "새 본문"}
    )
    assert replaced.json()["title"] == "수정된 공지"
    assert replaced.json()["updated_by_name"] == b.nickname

    rows = (
        (await db_session.execute(select(SharedGoal).where(SharedGoal.kind == "notice")))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].title == "수정된 공지"
    assert rows[0].text == "새 본문"


# --- DELETE 멱등 -------------------------------------------------------------------


async def test_delete_then_get_null_and_idempotent(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.put(f"/api/chat/with/{b.id}/notice", json={"title": "지울 공지"})

    res = await client.delete(f"/api/chat/with/{b.id}/notice")
    assert res.status_code == 204

    got = await client.get(f"/api/chat/with/{b.id}/notice")
    assert got.json() == {"title": None, "text": None}

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


async def test_put_rejects_blank_title(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    res = await client.put(f"/api/chat/with/{b.id}/notice", json={"title": "   ", "text": "본문"})
    assert res.status_code == 422
    assert res.json()["detail"] == "invalid_title"


async def test_put_rejects_multiline_title(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    res = await client.put(f"/api/chat/with/{b.id}/notice", json={"title": "첫줄\n둘째줄"})
    assert res.status_code == 422
    assert res.json()["detail"] == "invalid_title"


async def test_put_rejects_title_over_80_chars(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    res = await client.put(f"/api/chat/with/{b.id}/notice", json={"title": "가" * 81})
    assert res.status_code == 422
    assert res.json()["detail"] == "title_too_long"


async def test_put_rejects_text_over_500_chars(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    res = await client.put(
        f"/api/chat/with/{b.id}/notice", json={"title": "제목", "text": "가" * 501}
    )
    assert res.status_code == 422
    assert res.json()["detail"] == "text_too_long"


# --- 권한 ----------------------------------------------------------------------------


async def test_put_requires_friend_when_no_conversation(client, db_session):
    a = await login_as(client, db_session, "n-a2@example.com")
    stranger = await login_as(client, db_session, "n-x2@example.com")
    await login(client, db_session, a)

    res = await client.put(f"/api/chat/with/{stranger.id}/notice", json={"title": "공지"})
    assert res.status_code == 404


async def test_unfriend_blocks_put_and_delete_but_keeps_view(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.put(f"/api/chat/with/{b.id}/notice", json={"title": "남는 공지", "text": "본문"})

    row = (await db_session.execute(select(Friendship))).scalar_one()
    await db_session.delete(row)
    await db_session.commit()

    view = await client.get(f"/api/chat/with/{b.id}/notice")
    assert view.status_code == 200
    assert view.json()["title"] == "남는 공지"

    put = await client.put(f"/api/chat/with/{b.id}/notice", json={"title": "바꿔치기"})
    assert put.status_code == 403
    assert put.json()["detail"] == "not_friends"

    deleted = await client.delete(f"/api/chat/with/{b.id}/notice")
    assert deleted.status_code == 403
    assert deleted.json()["detail"] == "not_friends"


# --- 시스템 줄 적재 + WS 푸시 ---------------------------------------------------------


async def test_put_records_system_line_with_title_preview(client, db_session, monkeypatch):
    a, b = await two_friends(client, db_session)
    pushed = await _fake_deliver(monkeypatch)
    await login(client, db_session, a)

    await client.put(
        f"/api/chat/with/{b.id}/notice",
        json={"title": "매일 10문제", "text": "본문은 스냅샷에 안 들어간다"},
    )

    rows = (await db_session.execute(select(ChatMessage))).scalars().all()
    assert len(rows) == 1
    assert rows[0].kind == "notice_set"
    assert rows[0].body == "매일 10문제"  # 제목이 곧 미리보기
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


async def test_delete_records_system_line_kind_notice_clear(client, db_session, monkeypatch):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.put(f"/api/chat/with/{b.id}/notice", json={"title": "내릴 공지"})

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


# --- 레거시 행 (제목 없던 시절 데이터) ------------------------------------------------


async def test_legacy_notice_without_title_still_readable(client, db_session):
    """title 컬럼 도입(2026-08-13) 이전 행 — 내용만 있어도 조회는 성립한다."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.put(f"/api/chat/with/{b.id}/notice", json={"title": "임시"})
    row = (
        await db_session.execute(select(SharedGoal).where(SharedGoal.kind == "notice"))
    ).scalar_one()
    row.title = None
    row.text = "구버전 공지 본문"
    await db_session.commit()

    got = await client.get(f"/api/chat/with/{b.id}/notice")
    assert got.json()["title"] is None
    assert got.json()["text"] == "구버전 공지 본문"


# --- 기존 메시지 조회 API 가 kind 를 포함 --------------------------------------------


async def test_messages_endpoint_includes_kind_field(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.put(f"/api/chat/with/{b.id}/notice", json={"title": "공지 확인용"})

    res = await client.get(f"/api/chat/with/{b.id}/messages")
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "notice_set"


# --- my-phrases 는 시스템 줄을 수집하지 않는다 -----------------------------------------


async def test_my_phrases_does_not_collect_notice_system_lines(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    text = "오늘 회의 있어요"
    await client.put(f"/api/chat/with/{b.id}/notice", json={"title": text})
    await client.put(f"/api/chat/with/{b.id}/notice", json={"title": text})  # 빈도 2회 조건도 충족
    await seed_translation(db_session, text, "We have a meeting today")

    res = await client.get("/api/study/my-phrases")
    assert res.status_code == 200
    assert res.json()["total"] == 0


# --- 체크리스트 (chat-notice.md §공지 체크리스트) ----------------------------------


async def test_notice_check_toggle_and_validation(client, db_session, monkeypatch):
    """체크 항목 토글 — 해당 줄만 변경, 일반 줄·범위 밖 422, WS 재조회 푸시."""
    pushed = await _fake_deliver(monkeypatch)
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    text = "[] 단어 10개\n일반 메모 줄\n[x] 예습"
    res = await client.put(
        f"/api/chat/with/{b.id}/notice", json={"title": "스터디 규칙", "text": text}
    )
    assert res.status_code == 200
    pushed.clear()

    # 0번 줄 체크
    res = await client.patch(
        f"/api/chat/with/{b.id}/notice/check", json={"line_index": 0, "checked": True}
    )
    assert res.status_code == 200
    assert res.json()["text"] == "[x] 단어 10개\n일반 메모 줄\n[x] 예습"
    # WS chat.notice 양쪽 푸시, 시스템 줄 없음
    assert [m["t"] for _, m in pushed] == ["chat.notice", "chat.notice"]

    # 2번 줄 해제 — 다른 줄 불변
    res = await client.patch(
        f"/api/chat/with/{b.id}/notice/check", json={"line_index": 2, "checked": False}
    )
    assert res.json()["text"] == "[x] 단어 10개\n일반 메모 줄\n[] 예습"

    # 일반 줄·범위 밖 → not_check_line
    for idx in (1, 99, -1):
        res = await client.patch(
            f"/api/chat/with/{b.id}/notice/check",
            json={"line_index": idx, "checked": True},
        )
        assert res.status_code == 422
        assert res.json()["detail"] == "not_check_line"

    # 상대도 토글 가능 (공동 편집)
    await login(client, db_session, b)
    res = await client.patch(
        f"/api/chat/with/{a.id}/notice/check", json={"line_index": 2, "checked": True}
    )
    assert res.status_code == 200
    assert res.json()["text"].endswith("[x] 예습")
