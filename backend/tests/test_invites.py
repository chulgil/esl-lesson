"""친구 게임 초대 — 프레즌스 + 초대 릴레이 (P2 경쟁 루프)."""

from app.services.game.invites import InviteHub
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
