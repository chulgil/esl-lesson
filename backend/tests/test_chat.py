"""친구 1:1 채팅 — 대화 정규화·멱등 전송·커서·읽음·권한·캐시·푸시 (docs/specs/chat.md)."""

import json

import pytest
from sqlalchemy import func, select

from app.models import ChatMessage, Conversation, Friendship, LearningItem
from app.services import chat as chat_service
from app.services.game.invites import invite_hub
from tests.test_friends import make_user
from tests.test_my_contents import login_as
from tests.test_study import seed_items


@pytest.fixture(autouse=True)
def _fresh_caches():
    chat_service.reset_caches()
    yield
    chat_service.reset_caches()


async def make_friends(db, a, b):
    row = Friendship(requester_id=a.id, addressee_id=b.id, status="accepted")
    db.add(row)
    await db.commit()
    return row


async def two_friends(client, db):
    a = await login_as(client, db, "a@example.com")
    b = await login_as(client, db, "b@example.com")
    await make_friends(db, a, b)
    return a, b


def send_body(to_id, body="hello", cid="cid-00000001", item_id=None):
    payload = {"to_user_id": to_id, "body": body, "client_msg_id": cid}
    if item_id is not None:
        payload["item_id"] = item_id
    return payload


async def login(client, db, user):
    """이미 만든 사용자로 세션 전환."""
    from app.core.security import SESSION_COOKIE, create_session_token

    client.cookies.set(SESSION_COOKIE, create_session_token(user))


# --- 대화 정규화·멱등 -----------------------------------------------------------


async def test_conversation_normalized_one_row_per_pair(client, db_session):
    a, b = await two_friends(client, db_session)

    await login(client, db_session, a)
    r1 = await client.post("/api/chat/messages", json=send_body(b.id, "from a", "cid-aaaaaaaa"))
    assert r1.status_code == 201

    await login(client, db_session, b)
    r2 = await client.post("/api/chat/messages", json=send_body(a.id, "from b", "cid-bbbbbbbb"))
    assert r2.status_code == 201

    convs = (await db_session.execute(select(func.count(Conversation.id)))).scalar_one()
    assert convs == 1
    assert r1.json()["conversation_id"] == r2.json()["conversation_id"]


async def test_send_is_idempotent_by_client_msg_id(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    first = await client.post("/api/chat/messages", json=send_body(b.id, "hi", "cid-dup00001"))
    dup = await client.post("/api/chat/messages", json=send_body(b.id, "hi", "cid-dup00001"))
    assert first.json()["id"] == dup.json()["id"]
    assert first.json()["created"] is True
    assert dup.json()["created"] is False
    count = (await db_session.execute(select(func.count(ChatMessage.id)))).scalar_one()
    assert count == 1


# --- 검증 ----------------------------------------------------------------------


async def test_send_validations(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    self_msg = await client.post("/api/chat/messages", json=send_body(a.id))
    assert self_msg.status_code == 400

    empty = await client.post("/api/chat/messages", json=send_body(b.id, "   ", "cid-empty001"))
    assert empty.status_code == 422

    # 친구 아닌 상대 — 404 (존재 비노출)
    stranger = await login_as(client, db_session, "x@example.com")
    await login(client, db_session, a)
    not_friend = await client.post("/api/chat/messages", json=send_body(stranger.id))
    assert not_friend.status_code == 404


async def test_unfriend_blocks_send_but_keeps_history(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.post("/api/chat/messages", json=send_body(b.id, "before", "cid-before01"))

    # 친구 삭제
    row = (await db_session.execute(select(Friendship))).scalar_one()
    await db_session.delete(row)
    await db_session.commit()

    blocked = await client.post("/api/chat/messages", json=send_body(b.id, "after", "cid-after001"))
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "not_friends"

    # 기록 조회는 여전히 허용 (기록 보존 원칙)
    history = await client.get(f"/api/chat/with/{b.id}/messages")
    assert history.status_code == 200
    assert [m["body"] for m in history.json()["items"]] == ["before"]


# --- 커서 페이지네이션 -----------------------------------------------------------


async def test_cursor_pagination_no_gap_no_overlap(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    for i in range(7):
        await client.post("/api/chat/messages", json=send_body(b.id, f"m{i}", f"cid-page{i:04d}"))

    latest = (await client.get(f"/api/chat/with/{b.id}/messages?limit=3")).json()["items"]
    assert [m["body"] for m in latest] == ["m4", "m5", "m6"]

    older = (
        await client.get(f"/api/chat/with/{b.id}/messages?before={latest[0]['id']}&limit=3")
    ).json()["items"]
    assert [m["body"] for m in older] == ["m1", "m2", "m3"]

    oldest = (
        await client.get(f"/api/chat/with/{b.id}/messages?before={older[0]['id']}&limit=3")
    ).json()["items"]
    assert [m["body"] for m in oldest] == ["m0"]


# --- 읽음·안읽음 -----------------------------------------------------------------


async def test_unread_counts_and_mark_read(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    for i in range(3):
        await client.post("/api/chat/messages", json=send_body(b.id, f"u{i}", f"cid-unrd{i:04d}"))

    await login(client, db_session, b)
    assert (await client.get("/api/chat/unread-total")).json()["total"] == 3
    convs = (await client.get("/api/chat/conversations")).json()["items"]
    assert convs[0]["unread"] == 3
    assert convs[0]["last_message"] == "u2"

    await client.post(f"/api/chat/with/{a.id}/read")
    assert (await client.get("/api/chat/unread-total")).json()["total"] == 0

    # 내가 보낸 메시지는 내 안읽음에 안 잡힌다
    await login(client, db_session, a)
    assert (await client.get("/api/chat/unread-total")).json()["total"] == 0


async def test_read_positions_exposed_for_receipt_render(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    sent = (
        await client.post("/api/chat/messages", json=send_body(b.id, "rcpt", "cid-rcpt0001"))
    ).json()

    await login(client, db_session, b)
    await client.post(f"/api/chat/with/{a.id}/read")

    await login(client, db_session, a)
    res = (await client.get(f"/api/chat/with/{b.id}/messages")).json()
    assert res["reads"][str(b.id)] >= sent["id"]  # 상대가 읽었음 → "1" 제거 가능


# --- 캐시 ----------------------------------------------------------------------


async def test_cache_returns_fresh_message_after_send(client, db_session):
    """레드-그린 필수: 전송 직후 최신 조회에 신규 메시지가 반영돼야 한다 (stale 금지)."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.post("/api/chat/messages", json=send_body(b.id, "warm", "cid-warm0001"))
    # 캐시 웜업 (콜드 스타트 로드)
    await client.get(f"/api/chat/with/{b.id}/messages")

    await client.post("/api/chat/messages", json=send_body(b.id, "fresh", "cid-fresh001"))
    bodies = [
        m["body"] for m in (await client.get(f"/api/chat/with/{b.id}/messages")).json()["items"]
    ]
    assert bodies == ["warm", "fresh"]


async def test_unread_cache_invalidated_on_send_and_read(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, b)
    assert (await client.get("/api/chat/unread-total")).json()["total"] == 0  # 캐시 채움

    await login(client, db_session, a)
    await client.post("/api/chat/messages", json=send_body(b.id, "ping", "cid-ping0001"))

    await login(client, db_session, b)
    # TTL 이 남아 있어도 전송이 무효화했으므로 즉시 1
    assert (await client.get("/api/chat/unread-total")).json()["total"] == 1


# --- 학습 카드 스냅샷 ------------------------------------------------------------


async def test_item_snapshot_survives_item_deletion(client, db_session):
    a, b = await two_friends(client, db_session)
    items = await seed_items(db_session, count=1)
    await login(client, db_session, a)

    sent = await client.post(
        "/api/chat/messages", json=send_body(b.id, "", "cid-card0001", item_id=items[0].id)
    )
    assert sent.status_code == 201
    ref = sent.json()["item_ref"]
    assert ref["en_text"] == items[0].en_text

    # 원본 항목 삭제 후에도 스냅샷 무결 (기록 보존)
    await db_session.delete(await db_session.get(LearningItem, items[0].id))
    await db_session.commit()
    chat_service.reset_caches()

    history = (await client.get(f"/api/chat/with/{b.id}/messages")).json()["items"]
    assert history[0]["item_ref"]["en_text"] == ref["en_text"]


async def test_item_snapshot_rejects_invisible_item(client, db_session):
    """남의 개인 항목은 카드로 첨부 불가 (위조·유출 방지)."""
    a, b = await two_friends(client, db_session)
    stranger = await login_as(client, db_session, "x@example.com")
    hidden = await seed_items(
        db_session, count=1, status="pending", visibility="private", owner=stranger.id
    )
    await login(client, db_session, a)
    res = await client.post(
        "/api/chat/messages", json=send_body(b.id, "", "cid-steal001", item_id=hidden[0].id)
    )
    assert res.status_code == 404


# --- WS 전달·푸시 ----------------------------------------------------------------


async def test_ws_delivery_to_online_recipient(client, db_session):
    a, b = await two_friends(client, db_session)
    received = []

    async def fake_send(message):
        received.append(message)

    invite_hub.attach(b.id, "B", fake_send)
    try:
        await login(client, db_session, a)
        await client.post("/api/chat/messages", json=send_body(b.id, "live", "cid-live0001"))
    finally:
        invite_hub.detach(b.id, fake_send)

    assert any(m["t"] == "chat.message" and m["body"] == "live" for m in received)


async def test_push_only_when_offline_with_throttle(client, db_session, monkeypatch):
    a, b = await two_friends(client, db_session)
    pushed = []

    async def fake_push(db, user_id, payload):
        pushed.append((user_id, payload))
        return True

    import app.api.chat as chat_api

    monkeypatch.setattr(chat_api.push_service, "send_to_user", fake_push)

    await login(client, db_session, a)
    # 오프라인 → 푸시 1회
    await client.post("/api/chat/messages", json=send_body(b.id, "off1", "cid-off10001"))
    # 5분 내 같은 대화 → 스로틀
    await client.post("/api/chat/messages", json=send_body(b.id, "off2", "cid-off20001"))
    assert len(pushed) == 1
    assert pushed[0][0] == b.id
    # 잠금화면 보호 — 발신자·본문은 어느 필드에도 실리지 않는다 (2026-08-04)
    text = json.dumps(pushed[0][1], ensure_ascii=False)
    assert "off1" not in text
    assert a.nickname not in text

    # 온라인이면 푸시 안 감
    async def noop(message):
        pass

    invite_hub.attach(b.id, "B", noop)
    try:
        await client.post("/api/chat/messages", json=send_body(b.id, "on1", "cid-on100001"))
    finally:
        invite_hub.detach(b.id, noop)
    assert len(pushed) == 1


async def test_push_falls_back_when_all_sockets_dead(client, db_session, monkeypatch):
    """좀비 소켓(등록됐지만 전송 실패)만 남은 수신자 — WS 전달 실패로 보고
    웹푸시 폴백이 발동해야 한다. 이전엔 소켓 존재만으로 delivered 처리되어
    알림이 통째로 유실됐다 (2026-07-28 사용자 보고)."""
    a, b = await two_friends(client, db_session)
    pushed = []

    async def fake_push(db, user_id, payload):
        pushed.append(user_id)
        return True

    import app.api.chat as chat_api

    monkeypatch.setattr(chat_api.push_service, "send_to_user", fake_push)

    async def dead_send(message):
        raise RuntimeError("socket closed")

    invite_hub.attach(b.id, "B", dead_send)
    try:
        await login(client, db_session, a)
        await client.post("/api/chat/messages", json=send_body(b.id, "zomb", "cid-zombie001"))
    finally:
        invite_hub.detach(b.id, dead_send)

    assert pushed == [b.id]


def test_chat_push_payload_is_content_free():
    """채팅 알림은 도착 사실만 — 발신자·본문 없이 이동 경로만 싣는다.

    실제 표시 문구는 서비스 워커가 수신자 테마 라벨로 갈아끼우고(위장 유지),
    여기 값은 구형 워커를 위한 안전 폴백이다."""
    payload = chat_service.chat_push_payload(sender_id=7, conversation_id=42)

    assert payload["kind"] == "chat"  # 워커가 "내용 없는 알림"으로 분기하는 표식
    # 방 기준 딥링크 — 상대 기준 레거시 경로는 복수 방을 구분하지 못한다
    # (docs/specs/chat-language-rooms.md 결정 #14)
    assert payload["url"] == "/chat/room/42"
    assert payload["tag"] == "chat-42"
    # 폴백 문구도 중립 — 구형 워커에서도 내용이 새지 않는다
    assert payload["title"] and payload["body"]


def test_other_notifications_keep_their_text():
    """숨김은 채팅만 — 게임 초대·복습 리마인더는 문구를 그대로 보여준다."""
    from app.services.game.invites import invite_push_payload
    from app.services.push import reminder_payload

    invite = invite_push_payload("민수", "tetris", "ABCD")
    assert "민수" in invite["body"]
    assert "kind" not in invite  # 채팅 표식이 없으니 워커가 문구를 그대로 표시

    reminder = reminder_payload(3)
    assert "3" in reminder["body"]
    assert "kind" not in reminder


# --- 프레즌스·입력중 -------------------------------------------------------------


async def test_presence_broadcast_reaches_online_friends_only(client, db_session):
    a, b = await two_friends(client, db_session)
    stranger = await login_as(client, db_session, "x@example.com")  # 친구 아님

    got_b, got_x = [], []

    async def send_b(message):
        got_b.append(message)

    async def send_x(message):
        got_x.append(message)

    invite_hub.attach(b.id, "B", send_b)
    invite_hub.attach(stranger.id, "X", send_x)
    try:
        await chat_service.broadcast_presence(db_session, a.id, True)
    finally:
        invite_hub.detach(b.id, send_b)
        invite_hub.detach(stranger.id, send_x)

    assert got_b == [{"t": "presence", "user_id": a.id, "online": True}]
    assert got_x == []  # 친구 아닌 접속자에게는 안 감


async def test_typing_throttle_and_friend_gate(client, db_session):
    a, b = await two_friends(client, db_session)
    got = []

    async def send_b(message):
        got.append(message)

    invite_hub.attach(b.id, "B", send_b)
    try:
        assert chat_service.typing_allowed(a.id, b.id) is True
        await chat_service.relay_typing(db_session, a.id, b.id)
        # 2초 스로틀 — 연타는 거부
        assert chat_service.typing_allowed(a.id, b.id) is False
    finally:
        invite_hub.detach(b.id, send_b)

    assert got == [{"t": "chat.typing", "from_user_id": a.id}]
    # 오프라인 상대 — 게이트에서 거부
    assert chat_service.typing_allowed(a.id, 99999) is False


async def test_conversations_list_shows_online_flag(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.post("/api/chat/messages", json=send_body(b.id, "hey", "cid-online01"))

    async def noop(message):
        pass

    convs = (await client.get("/api/chat/conversations")).json()["items"]
    assert convs[0]["online"] is False

    invite_hub.attach(b.id, "B", noop)
    try:
        convs = (await client.get("/api/chat/conversations")).json()["items"]
        assert convs[0]["online"] is True
    finally:
        invite_hub.detach(b.id, noop)


# --- 실명 비노출 (2026-07-27 결정) ------------------------------------------------


async def test_chat_responses_never_expose_real_name_or_google_avatar(client, db_session):
    """채팅 응답 어디에도 구글 실명·프로필 사진이 인용되면 안 된다.

    login_as 는 name=이메일로 만들므로, 실명을 뚜렷한 값으로 바꿔 검사한다.
    """
    a, b = await two_friends(client, db_session)
    b.name = "REAL-NAME-홍길동"
    b.avatar_url = "https://lh3.googleusercontent.com/real-photo"
    a.name = "REAL-NAME-김철수"
    await db_session.commit()

    await login(client, db_session, a)
    await client.post("/api/chat/messages", json=send_body(b.id, "hi", "cid-real0001"))

    for path in (
        "/api/chat/conversations",
        f"/api/chat/with/{b.id}/messages",
        "/api/chat/unread-total",
    ):
        raw = (await client.get(path)).text
        assert "REAL-NAME" not in raw, f"실명 노출: {path}"
        assert "googleusercontent" not in raw, f"구글 아바타 노출: {path}"
        assert "avatar_url" not in raw, f"아바타 필드 잔존: {path}"


# --- 이미지 전송 (docs/specs/chat.md) ---------------------------------------------


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "chat_upload_dir", str(tmp_path))
    return tmp_path


PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
)


async def upload_png(client):
    res = await client.post("/api/chat/uploads", files={"file": ("x.png", PNG_1PX, "image/png")})
    assert res.status_code == 201
    return res.json()["image_id"]


async def test_image_upload_send_and_view(client, db_session, upload_dir):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    image_id = await upload_png(client)

    sent = await client.post(
        "/api/chat/messages",
        json={
            "to_user_id": b.id,
            "body": "",
            "client_msg_id": "cid-img00001",
            "image_id": image_id,
        },
    )
    assert sent.status_code == 201
    assert sent.json()["image_url"] == f"/api/chat/uploads/{image_id}"

    # 참여자(수신자)는 열람 가능
    await login(client, db_session, b)
    view = await client.get(f"/api/chat/uploads/{image_id}")
    assert view.status_code == 200
    assert view.content == PNG_1PX
    # 목록 미리보기는 [사진]
    convs = (await client.get("/api/chat/conversations")).json()["items"]
    assert convs[0]["last_message"] == "[사진]"


async def test_image_denied_to_non_participant(client, db_session, upload_dir):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    image_id = await upload_png(client)
    await client.post(
        "/api/chat/messages",
        json={
            "to_user_id": b.id,
            "body": "",
            "client_msg_id": "cid-img00002",
            "image_id": image_id,
        },
    )

    outsider = await login_as(client, db_session, "x@example.com")
    assert outsider is not None
    res = await client.get(f"/api/chat/uploads/{image_id}")
    assert res.status_code == 404  # 존재 비노출


async def test_image_upload_validations(client, db_session, upload_dir):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    bad_type = await client.post(
        "/api/chat/uploads", files={"file": ("x.txt", b"hello", "text/plain")}
    )
    assert bad_type.status_code == 422

    # 경로 조작 형식의 image_id 거부
    traversal = await client.post(
        "/api/chat/messages",
        json={
            "to_user_id": b.id,
            "body": "",
            "client_msg_id": "cid-img00003",
            "image_id": "../../etc/passwd",
        },
    )
    assert traversal.status_code == 422

    # 업로드된 적 없는 image_id 거부
    ghost = await client.post(
        "/api/chat/messages",
        json={
            "to_user_id": b.id,
            "body": "",
            "client_msg_id": "cid-img00004",
            "image_id": "0" * 32 + ".png",
        },
    )
    assert ghost.status_code == 422


# --- 메시지 삭제 (2026-07-31) ---------------------------------------------------


async def test_delete_own_message_soft_deletes(client, db_session):
    """삭제 = soft delete — 행 보존 + 내용 소거 + deleted 표기, 멱등 204."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    sent = (
        await client.post("/api/chat/messages", json=send_body(b.id, "지울 메시지", "cid-del00001"))
    ).json()

    res = await client.delete(f"/api/chat/messages/{sent['id']}")
    assert res.status_code == 204
    # 멱등 — 이미 삭제된 메시지 재삭제도 204
    assert (await client.delete(f"/api/chat/messages/{sent['id']}")).status_code == 204

    listing = (await client.get(f"/api/chat/with/{b.id}/messages")).json()["items"]
    row = next(m for m in listing if m["id"] == sent["id"])
    assert row["deleted"] is True
    assert row["body"] == "" and row["item_ref"] is None and row["image_url"] is None

    # 행은 보존 (기록·커서 안정성) — 본문만 소거
    db_row = await db_session.get(ChatMessage, sent["id"])
    assert db_row is not None and db_row.deleted_at is not None
    assert db_row.body == ""


async def test_delete_requires_sender(client, db_session):
    """타인 메시지 삭제는 404 (존재 비노출) — 수신자도 불가."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    sent = (
        await client.post("/api/chat/messages", json=send_body(b.id, "a의 메시지", "cid-del00002"))
    ).json()

    await login(client, db_session, b)
    assert (await client.delete(f"/api/chat/messages/{sent['id']}")).status_code == 404
    assert (await client.delete("/api/chat/messages/999999")).status_code == 404


async def test_delete_updates_recent_cache(client, db_session):
    """인프로세스 최근 캐시도 삭제 반영 — 캐시 히트 조회에서 본문 잔존 금지."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    sent = (
        await client.post("/api/chat/messages", json=send_body(b.id, "캐시 확인", "cid-del00003"))
    ).json()
    # 캐시 웜업 (최신 50 요청 = 캐시 경로)
    await client.get(f"/api/chat/with/{b.id}/messages")
    await client.delete(f"/api/chat/messages/{sent['id']}")

    listing = (await client.get(f"/api/chat/with/{b.id}/messages")).json()["items"]
    row = next(m for m in listing if m["id"] == sent["id"])
    assert row["deleted"] is True and row["body"] == ""


async def test_deleted_last_message_preview(client, db_session):
    """대화 목록 미리보기 — 삭제된 마지막 메시지는 "삭제되었습니다".
    (재검토: body/첨부 소거 상태를 "[단어 카드]" 로 오표기하던 문제)"""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    body = send_body(b.id, "마지막 메시지", "cid-del00004")
    sent = (await client.post("/api/chat/messages", json=body)).json()
    await client.delete(f"/api/chat/messages/{sent['id']}")

    convs = (await client.get("/api/chat/conversations")).json()["items"]
    row = next(c for c in convs if c["user_id"] == b.id)
    assert row["last_message"] == "삭제되었습니다"


async def test_reply_to_message(client, db_session):
    """답장 — 같은 대화 원문만 인용 가능, 미리보기는 읽기 시점(삭제 반영)."""
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    orig = (
        await client.post("/api/chat/messages", json=send_body(b.id, "원문입니다", "cid-rep00001"))
    ).json()

    reply_body = {**send_body(b.id, "답글입니다", "cid-rep00002"), "reply_to_id": orig["id"]}
    reply = (await client.post("/api/chat/messages", json=reply_body)).json()
    assert reply["reply_to_id"] == orig["id"]
    assert reply["reply_to"]["preview"] == "원문입니다"
    assert reply["reply_to"]["sender_id"] == a.id

    # 목록 조회에도 인용 부착 (캐시 경로)
    listing = (await client.get(f"/api/chat/with/{b.id}/messages")).json()["items"]
    row = next(m for m in listing if m["id"] == reply["id"])
    assert row["reply_to"]["preview"] == "원문입니다"

    # 원문 삭제 → 인용 미리보기도 "삭제되었습니다" (읽기 시점 해석)
    await client.delete(f"/api/chat/messages/{orig['id']}")
    listing = (await client.get(f"/api/chat/with/{b.id}/messages")).json()["items"]
    row = next(m for m in listing if m["id"] == reply["id"])
    assert row["reply_to"]["deleted"] is True
    assert row["reply_to"]["preview"] == "삭제되었습니다"

    # 다른 대화의 메시지 인용 시도 = 404 (정보 유출 차단)
    c = await make_user(db_session, "third@example.com", "제3자")
    await make_friends(db_session, a, c)
    bad = {**send_body(c.id, "크로스", "cid-rep00003"), "reply_to_id": orig["id"]}
    assert (await client.post("/api/chat/messages", json=bad)).status_code == 404
