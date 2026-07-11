"""매치 매니저: 세션 생성/입력/저장 (전송 계층은 페이크 sender)."""

import pytest
from sqlalchemy import select

import app.core.db as core_db
from app.models import GameMatch, LearningItem, ReviewCard, User
from app.services.game.manager import GameManager, load_word_pool


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
    return db_session


class Collector:
    def __init__(self):
        self.messages = []

    async def __call__(self, message: dict):
        self.messages.append(message)

    def types(self):
        return [m["t"] for m in self.messages]


async def seed_user_and_words(db, count=45):
    user = User(google_sub="g-p1", email="p1@example.com", name="P1")
    db.add(user)
    await db.flush()
    for i in range(count):
        item = LearningItem(
            item_type="word",
            en_text=f"gameword{i}",
            ko_text=f"뜻{i}",
            normalized_key=f"gameword{i}",
            review_status="approved",
        )
        db.add(item)
        await db.flush()
        db.add(
            ReviewCard(
                user_id=user.id,
                item_id=item.id,
                state="new",
                due_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )
        )
    await db.commit()
    return user


async def test_word_pool_prefers_learned_and_pads(wired_db):
    user = await seed_user_and_words(wired_db, count=10)  # 학습 10 < 최소 40 → 전역 보충
    pool = await load_word_pool(user.id, "en")
    assert len(pool) == 10  # 전역 풀도 같은 10개뿐 (dedup 확인)
    assert all(answer == display for _, answer, display in pool)
    ko_pool = await load_word_pool(user.id, "ko2en")
    assert all(display.startswith("뜻") for _, _, display in ko_pool)


async def test_pve_session_flow_and_result_saved(wired_db):
    user = await seed_user_and_words(wired_db)
    gm = GameManager()
    sender = Collector()

    session = await gm.join_pve(user.id, user.name, "en", bot_level=2, send=sender)
    session.task.cancel()  # 실시간 루프 대신 수동 진행

    assert "match.found" in sender.types()
    assert gm.by_user[user.id] == session.match_id
    row = await wired_db.get(GameMatch, session.match_id)
    assert row.mode == "pve" and row.bot_level == 2

    # 브릭 스폰까지 수동 틱 → 정답 제출
    while not session.match.board1.bricks:
        session.match.tick(0.1)
    text = session.match.board1.bricks[0].text
    await gm.handle_input(user.id, text, seq=7)
    clear = next(m for m in sender.messages if m["t"] == "clear.result")
    assert clear["ok"] is True and clear["seq"] == 7

    # 강제 종료 → 결과 저장 + match.end
    session.match.board2.add_garbage(12)
    session.match.tick(0.1)
    assert session.match.finished and session.match.winner == 1
    await gm._finish(session)

    row = await wired_db.get(GameMatch, session.match_id)
    await wired_db.refresh(row)
    assert row.status == "finished"
    assert row.winner_id == user.id
    assert row.stats["p1"]["cleared"] == 1
    end = next(m for m in sender.messages if m["t"] == "match.end")
    assert end["winner"] == "win"
    assert user.id not in gm.by_user  # 세션 정리됨


async def test_room_create_and_join(wired_db):
    p1 = await seed_user_and_words(wired_db)
    p2 = User(google_sub="g-p2", email="p2@example.com", name="P2")
    wired_db.add(p2)
    await wired_db.commit()

    gm = GameManager()
    s1, s2 = Collector(), Collector()
    code = await gm.create_room(p1.id, p1.name, "en", s1)
    assert any(m["t"] == "room.created" for m in s1.messages)

    await gm.join_room(p2.id, p2.name, code, s2)
    assert any(m["t"] == "match.found" for m in s1.messages)
    assert any(m["t"] == "match.found" for m in s2.messages)
    session = gm.sessions[gm.by_user[p1.id]]
    session.task.cancel()
    assert session.match.board1.word_queue == session.match.board2.word_queue  # 공정성

    # 없는 방 (진행 중 매치 가드에 걸리지 않도록 먼저 종료)
    session.match.forfeit(1)
    s3 = Collector()
    await gm.join_room(p2.id, p2.name, "ZZZZZZ", s3)
    assert any(m.get("code") == "room_not_found" for m in s3.messages)


async def test_pvp_queue_matches_two_players(wired_db):
    p1 = await seed_user_and_words(wired_db)
    p2 = User(google_sub="g-p2", email="p2@example.com", name="P2")
    wired_db.add(p2)
    await wired_db.commit()

    gm = GameManager()
    s1, s2 = Collector(), Collector()
    await gm.join_pvp_queue(p1.id, p1.name, "en", s1)
    assert s1.types() == ["queue.waiting"]
    await gm.join_pvp_queue(p2.id, p2.name, "en", s2)
    assert any(m["t"] == "match.found" for m in s1.messages)
    assert any(m["t"] == "match.found" for m in s2.messages)
    session = gm.sessions[gm.by_user[p1.id]]
    session.task.cancel()

    matches = (await wired_db.execute(select(GameMatch))).scalars().all()
    assert any(m.mode == "pvp" and m.player2_id == p2.id for m in matches)


async def test_pve_rejects_when_no_words_visible(wired_db):
    """가시 단어가 부족하면 크래시 대신 시작 전 안내 (words_insufficient)."""
    import pytest

    from app.models import User
    from app.services.game.manager import GameManager, WordPoolError

    user = User(google_sub="g-empty", email="empty@example.com", name="E")
    wired_db.add(user)
    await wired_db.commit()

    gm = GameManager()
    with pytest.raises(WordPoolError):
        await gm.join_pve(user.id, user.name, "en", bot_level=1, send=Collector())
