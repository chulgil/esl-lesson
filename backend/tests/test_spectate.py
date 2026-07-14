"""학습 관전 릴레이 — 승인제 (허락한 관전자만 스트림 수신)."""

from app.services.game.spectate import SpectateHub
from tests.test_game_manager import Collector


async def test_spectate_requires_host_approval():
    hub = SpectateHub()
    host_s, watcher_s = Collector(), Collector()

    code = await hub.host(1, "학습자", host_s)
    assert any(m["t"] == "st.hosting" and m["code"] == code for m in host_s.messages)

    # 요청 → 호스트에게 수락 프롬프트, 관전자는 아직 아무것도 못 봄
    await hub.request(2, "관전자", watcher_s, code)
    assert any(m["t"] == "st.request" and m["name"] == "관전자" for m in host_s.messages)
    await hub.event(1, {"phase": "question", "prompt": "apple"})
    assert not any(m["t"] == "st.event" for m in watcher_s.messages)

    # 수락 → 최근 상태 즉시 수신 + 이후 이벤트 스트림
    await hub.allow(1, watcher_id=2, allow=True)
    assert any(m["t"] == "st.approved" for m in watcher_s.messages)
    assert any(
        m["t"] == "st.event" and m["payload"]["prompt"] == "apple" for m in watcher_s.messages
    )
    await hub.event(1, {"phase": "feedback", "correct": True})
    assert any(
        m["t"] == "st.event" and m["payload"]["phase"] == "feedback" for m in watcher_s.messages
    )


async def test_spectate_deny_and_wrong_code():
    hub = SpectateHub()
    host_s, w1, w2 = Collector(), Collector(), Collector()
    code = await hub.host(1, "학습자", host_s)

    await hub.request(2, "거절될사람", w1, code)
    await hub.allow(1, watcher_id=2, allow=False)
    assert any(m["t"] == "st.denied" for m in w1.messages)
    await hub.event(1, {"phase": "question"})
    assert not any(m["t"] == "st.event" for m in w1.messages)

    await hub.request(3, "길잃음", w2, "ZZZZZZ")
    assert any(m.get("code") == "room_not_found" for m in w2.messages)


async def test_spectate_host_detach_notifies_watchers():
    hub = SpectateHub()
    host_s, watcher_s = Collector(), Collector()
    code = await hub.host(1, "학습자", host_s)
    await hub.request(2, "관전자", watcher_s, code)
    await hub.allow(1, watcher_id=2, allow=True)

    await hub.detach(1)  # 학습 종료/이탈
    assert any(m["t"] == "st.end" for m in watcher_s.messages)
    assert hub.rooms == {} and hub.by_host == {}


async def test_spectate_rehost_replaces_room():
    """학습자가 새 세션을 시작하면 이전 코드는 무효."""
    hub = SpectateHub()
    host_s = Collector()
    code1 = await hub.host(1, "학습자", host_s)
    code2 = await hub.host(1, "학습자", host_s)
    assert code1 != code2
    assert code1 not in hub.rooms and code2 in hub.rooms
