"""PvP 멀티플레이 통합 검증 — 실제 게임 루프 2인 대전 (docs/specs/word-tetris.md).

방 생성 → 입장 → 카운트다운 → 낙하/타이핑 → 콤보 공격 전달 → KO → 결과 저장까지
가속 상수로 실시간 루프를 그대로 돌려 검증한다.
"""

import asyncio

import pytest

import app.core.db as core_db
from app.models import GameMatch, LearningItem, User
from app.services.game import engine
from app.services.game import manager as manager_mod
from app.services.game.manager import GameManager, WordPoolError
from tests.test_game_manager import Collector


@pytest.fixture
async def wired_db(db_session, monkeypatch):
    class FakeFactory:
        def __call__(self):
            return FakeSessionCtx()

    class FakeSessionCtx:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(core_db, "_engine", object())
    monkeypatch.setattr(core_db, "_session_factory", FakeFactory())
    # 가속: 카운트다운 0.1s, 스폰 0.3s 간격, 재접속 유예 0.3s
    monkeypatch.setattr(manager_mod, "COUNTDOWN_SECONDS", 0.1)
    monkeypatch.setattr(manager_mod, "RECONNECT_GRACE_SECONDS", 0.3)
    monkeypatch.setattr(engine, "BASE_SPAWN_INTERVAL", 0.3)
    monkeypatch.setattr(engine, "MIN_SPAWN_INTERVAL", 0.2)
    return db_session


async def seed_two_players(db, words=15):
    p1 = User(google_sub="g-p1", email="p1@x.com", name="P1")
    p2 = User(google_sub="g-p2", email="p2@x.com", name="P2")
    db.add_all([p1, p2])
    await db.flush()
    from app.models import Content, ContentSubscription, ItemOccurrence

    content = Content(
        source="manual", title="풀", status="ready", visibility="public", created_by=p1.id
    )
    db.add(content)
    await db.flush()
    db.add(ContentSubscription(content_id=content.id, user_id=p1.id))
    for i in range(words):
        item = LearningItem(
            item_type="word",
            en_text=f"word{i:02d}",
            ko_text=f"뜻{i}",
            normalized_key=f"word{i:02d}",
            review_status="approved",
        )
        db.add(item)
        await db.flush()
        db.add(ItemOccurrence(item_id=item.id, content_id=content.id))
    await db.commit()
    return p1, p2


async def wait_until(predicate, timeout=8.0, interval=0.05):
    elapsed = 0.0
    while elapsed < timeout:
        if predicate():
            return True
        await asyncio.sleep(interval)
        elapsed += interval
    return False


async def test_full_pvp_room_match_end_to_end(wired_db):
    """친구 초대 방: 두 플레이어가 같은 단어로 대전하고 공격/승패/저장이 동작한다."""
    p1, p2 = await seed_two_players(wired_db)
    gm = GameManager()
    s1, s2 = Collector(), Collector()

    code = await gm.create_room(p1.id, "P1", "en", s1)
    await gm.join_room(p2.id, "P2", code, s2)

    # 1) 양쪽 모두 매치 성사 통지
    assert any(m["t"] == "match.found" for m in s1.messages)
    found2 = next(m for m in s2.messages if m["t"] == "match.found")
    assert found2["opponent"] == "P1" and found2["you"] == 2

    session = gm.sessions[gm.by_user[p1.id]]
    # 2) 실루프: 카운트다운 후 양쪽에 state 브로드캐스트
    assert await wait_until(
        lambda: (
            any(m["t"] == "state" for m in s1.messages)
            and any(m["t"] == "state" for m in s2.messages)
        )
    ), "state 브로드캐스트 없음"

    # 3) 공정성: 두 보드의 단어 큐 동일
    assert session.match.board1.word_queue == session.match.board2.word_queue

    # 4) P1 이 브릭 3개 타이핑 → 3콤보 공격이 P2 에 전달
    for _ in range(3):
        assert await wait_until(lambda: len(session.match.board1.bricks) > 0)
        text = session.match.board1.bricks[0].text
        await gm.handle_input(p1.id, text, seq=1)
    assert any(m["t"] == "clear.result" and m["ok"] for m in s1.messages)
    assert await wait_until(lambda: any(m["t"] == "attack.recv" for m in s2.messages)), (
        "공격 미전달"
    )
    assert session.match.board2.landed_count >= 1  # garbage 도착

    # 5) P2 보드를 KO 로 만들어 종료 → 양쪽 match.end + 승패
    session.match.board2.add_garbage(12)
    assert await wait_until(lambda: any(m["t"] == "match.end" for m in s1.messages))
    end1 = next(m for m in s1.messages if m["t"] == "match.end")
    end2 = next(m for m in s2.messages if m["t"] == "match.end")
    assert end1["winner"] == "win" and end2["winner"] == "lose"

    # 6) 결과 저장 + 세션 정리
    row = await wired_db.get(GameMatch, session.match_id)
    await wired_db.refresh(row)
    assert row.status == "finished"
    assert row.winner_id == p1.id
    assert row.player2_id == p2.id
    assert p1.id not in gm.by_user and p2.id not in gm.by_user


async def test_disconnect_forfeits_after_grace(wired_db):
    """이탈 유예(재접속 grace) 초과 시 몰수패 — 상대 승리."""
    p1, p2 = await seed_two_players(wired_db)
    gm = GameManager()
    s1, s2 = Collector(), Collector()
    code = await gm.create_room(p1.id, "P1", "en", s1)
    await gm.join_room(p2.id, "P2", code, s2)
    session = gm.sessions[gm.by_user[p1.id]]
    assert await wait_until(lambda: session.started and any(m["t"] == "state" for m in s2.messages))

    gm.detach(p2.id)  # P2 연결 끊김
    # 몰수 → 종료 통지까지 (finished 플래그 직후 next() 는 레이스 — 메시지 도착을 기다린다)
    assert await wait_until(
        lambda: any(m["t"] == "match.end" for m in s1.messages), timeout=5.0
    ), "몰수 처리 안 됨"
    assert session.match.winner == 1
    end1 = next(m for m in s1.messages if m["t"] == "match.end")
    assert end1["winner"] == "win"


async def test_reconnect_within_grace_resumes(wired_db):
    """유예 내 재접속: 몰수 없이 상태를 다시 받는다."""
    p1, p2 = await seed_two_players(wired_db)
    gm = GameManager()
    s1, s2 = Collector(), Collector()
    code = await gm.create_room(p1.id, "P1", "en", s1)
    await gm.join_room(p2.id, "P2", code, s2)
    session = gm.sessions[gm.by_user[p1.id]]
    assert await wait_until(lambda: session.started)

    gm.detach(p2.id)
    s2b = Collector()
    resumed = await gm.attach(p2.id, s2b)  # 즉시 재접속 (유예 내)
    assert resumed is not None
    rejoin = next(m for m in s2b.messages if m["t"] == "match.found")
    assert rejoin.get("rejoined") is True
    assert await wait_until(lambda: any(m["t"] == "state" for m in s2b.messages))
    assert not session.match.finished
    session.match.forfeit(2)  # 정리


async def test_cannot_join_second_match_while_playing(wired_db):
    """진행 중 매치가 있으면 새 매치 진입 차단 (already_in_match)."""
    p1, p2 = await seed_two_players(wired_db)
    gm = GameManager()
    s1, s2 = Collector(), Collector()
    code = await gm.create_room(p1.id, "P1", "en", s1)
    await gm.join_room(p2.id, "P2", code, s2)
    session = gm.sessions[gm.by_user[p1.id]]
    assert await wait_until(lambda: session.started)

    with pytest.raises(WordPoolError, match="already_in_match"):
        await gm.join_pve(p1.id, "P1", "en", 1, s1)
    with pytest.raises(WordPoolError, match="already_in_match"):
        await gm.create_room(p2.id, "P2", "en", s2)
    session.match.forfeit(2)  # 정리
