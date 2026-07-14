"""스피드 퀴즈 로얄 — 문제 생성/점수/순위 순수 로직 + 매니저 흐름 (docs/proposal/quiz-royale.md)."""

import asyncio
import random

import pytest

from app.models import QuizRoyaleMatch, User
from app.services.game import quiz_royale as qr
from app.services.game.manager import WordPoolError
from tests.test_game_manager import Collector, seed_user_and_words, wired_db  # noqa: F401


def _pool(n=30):
    return [(i, f"word{i}", f"뜻{i}") for i in range(n)]


def test_build_questions_choices_and_answer():
    rng = random.Random(7)
    questions = qr.build_questions(_pool(), rounds=10, rng=rng)
    assert len(questions) == 10
    prompts = {q.prompt for q in questions}
    assert len(prompts) == 10  # 문제 중복 없음
    for q in questions:
        assert len(q.choices) == 4
        assert q.answer in q.choices
        assert len(set(q.choices)) == 4  # 선지 중복 없음


def test_score_for_speed_bonus():
    assert qr.score_for(0.0, limit=10.0) == 100
    assert qr.score_for(10.0, limit=10.0) == 50
    assert 50 < qr.score_for(5.0, limit=10.0) <= 75


def test_ranking_ties_share_rank():
    players = [
        qr.QuizPlayer(user_id=1, name="a", score=100),
        qr.QuizPlayer(user_id=2, name="b", score=100),
        qr.QuizPlayer(user_id=None, name="bot", score=40),
    ]
    ranks = qr.ranking(players)
    assert [(r["rank"], r["name"]) for r in ranks] == [(1, "a"), (1, "b"), (3, "bot")]
    assert ranks[2]["is_bot"] is True


@pytest.fixture
def fast_rounds(monkeypatch):
    monkeypatch.setattr(qr, "ROUND_SECONDS", 0.4)
    monkeypatch.setattr(qr, "REVEAL_SECONDS", 0.05)
    monkeypatch.setattr(qr, "ROUNDS", 2)
    monkeypatch.setattr(qr, "TICK", 0.02)


async def test_solo_match_with_bot_runs_to_end(wired_db, fast_rounds):  # noqa: F811
    """솔로+봇: 라운드 진행 → 정답 제출 → 종료·저장까지 전체 흐름."""
    user = await seed_user_and_words(wired_db)
    manager = qr.QuizRoyaleManager()
    sender = Collector()

    session = await manager.solo(user.id, user.name, sender, bot_level=5, bots=1)
    assert len(session.players) == 2
    assert any(m["t"] == "qr.room" for m in sender.messages)

    # 첫 라운드 출제를 기다렸다 정답 제출
    for _ in range(50):
        if any(m["t"] == "qr.round" for m in sender.messages):
            break
        await asyncio.sleep(0.02)
    round_msg = next(m for m in sender.messages if m["t"] == "qr.round")
    assert round_msg["total"] == 2 and len(round_msg["choices"]) == 4
    answer = session.questions[0].answer
    await manager.answer(user.id, answer)

    await asyncio.wait_for(session.task, timeout=5)
    end = next(m for m in sender.messages if m["t"] == "qr.end")
    my_rank = next(r for r in end["ranking"] if r["name"] == user.name)
    assert my_rank["score"] >= 50  # 1라운드 정답 점수 반영

    row = await wired_db.get(QuizRoyaleMatch, session.match_id)
    await wired_db.refresh(row)
    assert row.status == "finished"
    saved = {p["name"]: p for p in row.players["players"]}
    assert saved[user.name]["score"] == my_rank["score"]
    assert user.id not in manager.by_user  # 세션 정리


async def test_room_create_join_start_and_wrong_answer(wired_db, fast_rounds):  # noqa: F811
    """방: 생성/입장 브로드캐스트, 호스트만 시작, 오답 0점."""
    p1 = await seed_user_and_words(wired_db)
    p2 = User(google_sub="g-q2", email="q2@example.com", name="Q2")
    wired_db.add(p2)
    await wired_db.commit()

    manager = qr.QuizRoyaleManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(p1.id, p1.name, s1)
    assert any(m["t"] == "qr.room" and m["code"] == code for m in s1.messages)

    await manager.join(p2.id, p2.name, s2, code)
    assert any(m["t"] == "qr.room" and len(m["players"]) == 2 for m in s1.messages)

    await manager.start(p2.id)  # 호스트 아님 — 무시
    session = manager.sessions[manager.by_user[p1.id]]
    assert session.started is False

    await manager.start(p1.id)
    assert session.started is True
    for _ in range(50):
        if any(m["t"] == "qr.round" for m in s2.messages):
            break
        await asyncio.sleep(0.02)

    correct = session.questions[0].answer
    wrong = next(c for c in session.questions[0].choices if c != correct)
    await manager.answer(p1.id, correct)
    await manager.answer(p2.id, wrong)
    await asyncio.wait_for(session.task, timeout=5)

    end = next(m for m in s1.messages if m["t"] == "qr.end")
    scores = {r["name"]: r["score"] for r in end["ranking"]}
    assert scores[p1.name] >= 50 and scores[p2.name] == 0


async def test_join_full_room_and_missing_room(wired_db):  # noqa: F811
    p1 = await seed_user_and_words(wired_db)
    manager = qr.QuizRoyaleManager()
    code = await manager.create(p1.id, p1.name, Collector())

    users = []
    for i in range(4):
        u = User(google_sub=f"g-f{i}", email=f"f{i}@example.com", name=f"F{i}")
        wired_db.add(u)
        users.append(u)
    await wired_db.commit()

    for u in users[:3]:
        await manager.join(u.id, u.name, Collector(), code)
    full = Collector()
    await manager.join(users[3].id, users[3].name, full, code)
    assert any(m.get("code") == "room_full" for m in full.messages)

    ghost = Collector()
    await manager.join(users[3].id, users[3].name, ghost, "XXXXXX")
    assert any(m.get("code") == "room_not_found" for m in ghost.messages)


async def test_solo_requires_word_pool(wired_db):  # noqa: F811
    user = User(google_sub="g-nopool", email="nopool@example.com", name="N")
    wired_db.add(user)
    await wired_db.commit()
    manager = qr.QuizRoyaleManager()
    with pytest.raises(WordPoolError):
        await manager.solo(user.id, user.name, Collector(), bot_level=1, bots=1)
