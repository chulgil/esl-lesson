"""친구 게임 초대 — 프레즌스 + 초대 릴레이 + 오프라인 푸시 폴백 (P2 경쟁 루프)."""

from sqlalchemy import select

from app.models import PushSubscription, User
from app.models.friend import Friendship
from app.services import push
from app.services.friends import are_friends
from app.services.game.invites import GAME_LABELS, GAMES, InviteHub, invite_push_payload
from tests.test_game_manager import Collector


async def test_invite_relayed_to_online_friend():
    hub = InviteHub()
    a, b = Collector(), Collector()
    hub.attach(1, "철수", a)
    hub.attach(2, "영희", b)

    ok = await hub.invite(1, to_user_id=2, game="typing", code="AB12CD")
    assert ok is True
    msg = next(m for m in b.messages if m["t"] == "iv.invited")
    assert msg["from"] == "철수" and msg["game"] == "typing" and msg["code"] == "AB12CD"


async def test_invite_offline_returns_false():
    hub = InviteHub()
    a = Collector()
    hub.attach(1, "철수", a)
    ok = await hub.invite(1, to_user_id=99, game="quiz", code="XXYYZZ")
    assert ok is False


async def test_presence_tracks_multiple_sockets():
    """페이지마다 소켓이 따로 열려도 하나라도 살아 있으면 온라인."""
    hub = InviteHub()
    s1, s2 = Collector(), Collector()
    hub.attach(1, "철수", s1)
    hub.attach(1, "철수", s2)
    hub.detach(1, s1)
    assert hub.online(1) is True
    hub.detach(1, s2)
    assert hub.online(1) is False


def test_invite_push_payload_uses_korean_labels():
    """푸시 본문은 게임 한글 이름, 클릭 URL 은 대기실 자동 입장(?join=)."""
    assert set(GAMES) == set(GAME_LABELS)  # 새 게임 추가 시 라벨 누락 방지
    payload = invite_push_payload("철수", "dictation", "AB12CD")
    assert "받아쓰기 배틀" in payload["body"]
    assert "철수" in payload["body"]
    assert payload["url"] == "/game/dictation?join=AB12CD"
    assert payload["tag"] == "game-invite"


async def make_users(db, *names):
    users = [User(google_sub=f"g-{n}", email=f"{n}@example.com", name=n) for n in names]
    db.add_all(users)
    await db.commit()
    return users


async def test_are_friends_requires_accepted(db_session):
    a, b, c = await make_users(db_session, "a", "b", "c")
    db_session.add(Friendship(requester_id=a.id, addressee_id=b.id, status="accepted"))
    db_session.add(Friendship(requester_id=c.id, addressee_id=a.id, status="pending"))
    await db_session.commit()

    assert await are_friends(db_session, a.id, b.id) is True
    assert await are_friends(db_session, b.id, a.id) is True  # 방향 무관
    assert await are_friends(db_session, a.id, c.id) is False  # pending 은 친구 아님
    assert await are_friends(db_session, b.id, c.id) is False


async def test_send_to_user_delivers_and_prunes_dead_subs(db_session, vapid_keys, monkeypatch):
    """하나라도 전달되면 True, 만료 구독(404/410)은 삭제."""
    (user,) = await make_users(db_session, "u")
    db_session.add(PushSubscription(user_id=user.id, endpoint="https://dead", p256dh="k", auth="a"))
    db_session.add(
        PushSubscription(user_id=user.id, endpoint="https://alive", p256dh="k", auth="a")
    )
    await db_session.commit()

    async def fake_send_to(sub, payload, settings):
        return "ok" if sub.endpoint != "https://dead" else "gone"

    monkeypatch.setattr(push, "send_to", fake_send_to)

    ok = await push.send_to_user(db_session, user.id, {"title": "t"})
    assert ok is True
    remaining = (await db_session.execute(select(PushSubscription.endpoint))).scalars().all()
    assert remaining == ["https://alive"]


async def test_send_to_user_without_subs_returns_false(db_session, vapid_keys):
    (user,) = await make_users(db_session, "nosub")
    assert await push.send_to_user(db_session, user.id, {"title": "t"}) is False
