"""리스닝 빙고 규칙·세션 검증 (docs/specs/listening-bingo.md)."""

import asyncio

import pytest

from app.models import BingoMatch
from app.services.game import bingo as bg
from app.services.game.manager import WordPoolError
from tests.test_game_manager import Collector, seed_user_and_words, wired_db  # noqa: F401


def _pool(n=40):
    return [(i, f"word{i:02d}", f"뜻{i:02d}") for i in range(1, n + 1)]


# --- 순수 규칙 ---


def test_pick_board_words_priority_then_media_first():
    """보드 선정 — due·오답 우선, 그다음 원어민 구간 보유, 결정적."""
    pool = _pool()
    priority = {3, 7, 11}
    media_ids = {2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32}
    b1 = bg.pick_board_words(pool, seed=42, priority=priority, media_ids=media_ids)
    b2 = bg.pick_board_words(pool, seed=42, priority=priority, media_ids=media_ids)
    assert b1 == b2  # 결정적
    assert len(b1) == bg.BOARD_CELLS
    ids = [w[0] for w in b1]
    assert set(ids[:3]) == priority  # 복습 우선 항목이 맨 앞
    assert all(i in media_ids for i in ids[3:])  # 나머지는 media 보유 우선


def test_has_bingo_lines():
    arrangement = list(range(1, 17))  # 배치 = item_id 1..16
    assert not bg.has_bingo(arrangement, set())
    assert bg.has_bingo(arrangement, {1, 2, 3, 4})  # 첫 행
    assert bg.has_bingo(arrangement, {1, 5, 9, 13})  # 첫 열
    assert bg.has_bingo(arrangement, {1, 6, 11, 16})  # 대각
    assert not bg.has_bingo(arrangement, {1, 2, 3, 5})  # 3개 + 다른 줄


# --- 세션 흐름 (DB 연동) ---


async def _start_solo(db):
    user = await seed_user_and_words(db)
    manager = bg.BingoManager()
    sender = Collector()
    session = await manager.solo(user.id, user.name, sender)
    session.task.cancel()  # 실시간 루프 대신 수동 진행
    return user, manager, sender, session


async def test_solo_start_board_and_words(wired_db):  # noqa: F811
    user, manager, sender, session = await _start_solo(wired_db)
    start = next(m for m in sender.messages if m["t"] == "bg.start")
    assert len(start["board"]) == bg.BOARD_CELLS
    assert start["total"] == bg.BOARD_CELLS
    # 보드 배치와 호출 순서는 같은 16단어의 순열
    assert {c["item_id"] for c in start["board"]} == set(session.call_order)
    row = await wired_db.get(BingoMatch, session.match_id)
    assert row.mode == "solo" and row.status == "playing"
    session.players[0].send = None
    manager._cleanup(session)


async def test_tap_correct_fills_and_wrong_counts(wired_db):  # noqa: F811
    user, manager, sender, session = await _start_solo(wired_db)
    session.round_no = 0
    player = session.players[0]
    current = session.call_order[0]
    wrong_id = next(i for i in session.words if i != current)

    await manager.tap(user.id, no=0, item_id=wrong_id)
    assert player.wrong == 1 and current not in player.filled
    await manager.tap(user.id, no=0, item_id=current)
    assert current in player.filled and player.done_current
    ok = [m for m in sender.messages if m["t"] == "bg.tap_result"]
    assert [m["ok"] for m in ok] == [False, True]
    # 정답 후 재탭은 무시
    await manager.tap(user.id, no=0, item_id=current)
    assert player.wrong == 1
    manager._cleanup(session)


async def test_tap_rejected_outside_round_window(wired_db):  # noqa: F811
    """카운트다운(no=-1)·정답 공개 중 탭 무효 (2026-08-10 리뷰).

    round_no 는 카운트다운·reveal 동안 -1 — 기본값 no=-1 탭이 음수 인덱스로
    마지막 호출 단어를 선채움하고, 공개된 정답이 공짜 크레딧이 되던 구멍.
    """
    user, manager, sender, session = await _start_solo(wired_db)
    player = session.players[0]
    last_word = session.call_order[-1]
    assert session.round_no == -1  # 카운트다운 상태
    await manager.tap(user.id, no=-1, item_id=last_word)
    assert last_word not in player.filled  # 선채움 차단

    current = session.call_order[0]
    session.round_no = -1  # _run 이 reveal 직전 라운드를 마감한 상태
    await manager.tap(user.id, no=0, item_id=current)
    assert current not in player.filled  # 공개 후 크레딧 차단
    manager._cleanup(session)


async def test_finish_ranks_and_sends_missed_review(wired_db):  # noqa: F811
    user, manager, sender, session = await _start_solo(wired_db)
    player = session.players[0]
    # 첫 행 4개를 채워 빙고, 2개는 놓침 처리
    player.arrangement = list(session.words)
    filled4 = player.arrangement[:4]
    player.filled = set(filled4)
    player.bingo_round = 5
    player.missed = [player.arrangement[4], player.arrangement[5]]
    await manager._finish(session, aborted=False)

    end = next(m for m in sender.messages if m["t"] == "bg.end")
    assert end["winner"] is None  # 솔로는 승자 없음 (기록만)
    assert end["results"][0]["filled"] == 4
    assert end["results"][0]["bingo_round"] == 5
    review = next(m for m in sender.messages if m["t"] == "bg.review")
    assert {i["item_id"] for i in review["items"]} == set(player.missed)
    types = [m["t"] for m in sender.messages]
    assert types.index("bg.review") < types.index("bg.end")

    row = await wired_db.get(BingoMatch, session.match_id)
    await wired_db.refresh(row)
    assert row.status == "finished"
    assert row.stats["p1"]["filled"] == 4


async def test_winner_by_bingo_round_then_filled(wired_db):  # noqa: F811
    user, manager, sender, session = await _start_solo(wired_db)
    p1 = session.players[0]
    p2 = bg.BingoPlayer(user_id=99999, name="P2", send=Collector())
    session.players.append(p2)
    ids = list(session.words)
    p1.arrangement = ids
    p2.arrangement = ids
    p1.bingo_round, p1.filled = 7, set(ids[:6])
    p2.bingo_round, p2.filled = 7, set(ids[:5])  # 같은 라운드 빙고, 채운 칸 적음
    await manager._finish(session, aborted=False)
    end = next(m for m in sender.messages if m["t"] == "bg.end")
    assert end["winner"] == user.name  # 같은 빙고 라운드 → 채운 칸 多 승


async def test_room_create_join_and_full(wired_db):  # noqa: F811
    user = await seed_user_and_words(wired_db)
    from app.models import User

    manager = bg.BingoManager()
    s1 = Collector()
    code = await manager.create(user.id, user.name, s1)
    assert any(m["t"] == "bg.room" for m in s1.messages)

    guests = []
    for i in range(4):
        guest = User(google_sub=f"g-bg{i}", email=f"bg{i}@example.com", name=f"G{i}")
        wired_db.add(guest)
        await wired_db.commit()
        sender = Collector()
        await manager.join(guest.id, guest.name, sender, code)
        guests.append((guest, sender))
    # 4번째 게스트(5인째)는 정원 초과
    assert any(m.get("code") == "room_full" for m in guests[3][1].messages)
    session = manager.sessions[manager.by_user[user.id]]
    assert len(session.players) == bg.MAX_PLAYERS


async def test_solo_requires_16_words(wired_db):  # noqa: F811
    from app.models import User

    user = User(google_sub="g-bg-few", email="few@example.com", name="F")
    wired_db.add(user)
    await wired_db.commit()
    manager = bg.BingoManager()
    with pytest.raises(WordPoolError):
        await manager.solo(user.id, user.name, Collector())


async def test_run_loop_round_and_reveal(wired_db, monkeypatch):  # noqa: F811
    """루프 1라운드 실기 — bg.round(음성 페이로드) → 정답 탭 → bg.reveal."""
    monkeypatch.setattr(bg, "COUNTDOWN_SECONDS", 0.0)
    monkeypatch.setattr(bg, "ROUND_SECONDS", 0.5)
    monkeypatch.setattr(bg, "REVEAL_SECONDS", 0.0)
    user = await seed_user_and_words(wired_db)
    manager = bg.BingoManager()
    sender = Collector()
    session = await manager.solo(user.id, user.name, sender)
    try:
        await asyncio.sleep(0.15)  # 카운트다운 0 → 1라운드 진입
        rnd = next(m for m in sender.messages if m["t"] == "bg.round")
        assert rnd["no"] == 0 and rnd["tts"] == session.words[session.call_order[0]][0]
        await manager.tap(user.id, no=0, item_id=session.call_order[0])
        await asyncio.sleep(0.3)  # 전원 완료 → reveal
        reveal = next(m for m in sender.messages if m["t"] == "bg.reveal")
        assert reveal["en"] == session.words[session.call_order[0]][0]
    finally:
        if session.task:
            session.task.cancel()
        manager._cleanup(session)


async def test_reconnect_during_round_keeps_session(wired_db, monkeypatch):  # noqa: F811
    """대전 도중 WS 끊김 → 재연결 시 세션 복귀해야 한다 (버그: detach 가 매치 진행 중에도
    by_user 를 즉시 지워 재접속을 막았다)."""
    from app.models import User

    monkeypatch.setattr(bg, "COUNTDOWN_SECONDS", 0.0)
    monkeypatch.setattr(bg, "ROUND_SECONDS", 2.0)
    monkeypatch.setattr(bg, "REVEAL_SECONDS", 0.0)
    host = await seed_user_and_words(wired_db)
    guest = User(google_sub="g-rc", email="rc@example.com", name="RC")
    wired_db.add(guest)
    await wired_db.commit()

    manager = bg.BingoManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(host.id, host.name, s1)
    await manager.join(guest.id, guest.name, s2, code)
    await manager.begin(host.id)
    session = manager.sessions[manager.by_user[host.id]]
    for _ in range(100):
        if any(m["t"] == "bg.round" for m in s2.messages):
            break
        await asyncio.sleep(0.02)

    await manager.detach(guest.id)  # WS 끊김 — 매치는 진행 중
    assert guest.id in manager.by_user  # 세션 매핑이 유지돼야 재접속 가능
    assert session.match_id in manager.sessions

    s2b = Collector()
    resumed = await manager.attach(guest.id, s2b)
    assert resumed is session
    player = next(p for p in session.players if p.user_id == guest.id)
    assert player.send is s2b
    assert any(m["t"] == "bg.start" for m in s2b.messages)  # 현재 상태(내 보드) 재전송
    assert any(m["t"] == "bg.round" for m in s2b.messages)

    session.task.cancel()
    manager._cleanup(session)


async def test_host_leaving_waiting_room_notifies_remaining_players(wired_db):  # noqa: F811
    """대기방에서 호스트가 나가 세션이 삭제되면 남은 플레이어에게 알려야 한다 (버그 2:
    기존엔 아무 브로드캐스트 없이 세션만 삭제돼 화면이 멈췄다)."""
    from app.models import User

    host = await seed_user_and_words(wired_db)
    guest = User(google_sub="g-hl", email="hl@example.com", name="HL")
    wired_db.add(guest)
    await wired_db.commit()

    manager = bg.BingoManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(host.id, host.name, s1)
    await manager.join(guest.id, guest.name, s2, code)

    await manager.detach(host.id)  # 호스트 이탈 — 대기방(시작 전)

    assert any(m.get("code") == "room_closed" for m in s2.messages)
    assert guest.id not in manager.by_user  # 세션 정리됨
    assert not manager.sessions
