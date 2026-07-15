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


async def test_chat_and_cheer_relayed_to_room():
    """채팅·응원은 호스트+수락 관전자 전원에게 릴레이 (2026-07-15)."""
    hub = SpectateHub()
    host_s, w1, w2 = Collector(), Collector(), Collector()
    code = await hub.host(1, "학습자", host_s)
    await hub.request(2, "응원단", w1, code)
    await hub.allow(1, watcher_id=2, allow=True)
    await hub.request(3, "대기중", w2, code)  # 수락 안 됨

    await hub.chat(2, "  화이팅   화이팅  ")
    for col in (host_s, w1):
        assert any(
            m["t"] == "st.chat" and m["name"] == "응원단" and m["text"] == "화이팅 화이팅"
            for m in col.messages
        )
    assert not any(m["t"] == "st.chat" for m in w2.messages)  # 미수락자는 수신 불가

    await hub.cheer(2, "star")
    assert any(m["t"] == "st.cheer" and m["kind"] == "star" for m in host_s.messages)
    assert any(m["t"] == "st.cheer" for m in w1.messages)


async def test_chat_guards_membership_kind_and_rate():
    """미수락자·빈 텍스트·잘못된 kind·연속 도배는 무시."""
    hub = SpectateHub()
    host_s, pending, accepted = Collector(), Collector(), Collector()
    code = await hub.host(1, "학습자", host_s)
    await hub.request(2, "대기자", pending, code)

    await hub.chat(2, "수락 전 채팅")  # 미수락 — 무시
    await hub.cheer(2, "star")
    assert not any(m["t"] in ("st.chat", "st.cheer") for m in host_s.messages)

    await hub.request(3, "팬", accepted, code)
    await hub.allow(1, watcher_id=3, allow=True)
    await hub.chat(3, "   ")  # 빈 텍스트 — 무시
    await hub.cheer(3, "bomb")  # 허용 목록 밖 — 무시
    assert not any(m["t"] in ("st.chat", "st.cheer") for m in host_s.messages)

    await hub.chat(3, "첫 줄")
    await hub.chat(3, "도배 시도")  # 1초 이내 — 드롭
    chats = [m for m in host_s.messages if m["t"] == "st.chat"]
    assert [c["text"] for c in chats] == ["첫 줄"]

    long_text = "가" * 300
    hub._last_sent.clear()  # rate 초기화 후 길이 제한 확인
    await hub.chat(3, long_text)
    chats = [m for m in host_s.messages if m["t"] == "st.chat"]
    assert len(chats[-1]["text"]) == 100
