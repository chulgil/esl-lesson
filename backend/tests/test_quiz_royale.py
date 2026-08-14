"""스피드 퀴즈 로얄 — 문제 생성/점수/순위 순수 로직 + 매니저 흐름 (docs/proposal/quiz-royale.md)."""

import asyncio
import random

import pytest

from app.models import QuizRoyaleMatch, User
from app.services.game import quiz_royale as qr
from app.services.game.manager import WordPoolError
from tests.test_game_manager import (  # noqa: F401
    Collector,
    seed_user_and_words,
    seed_words_for,
    wired_db,
)


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
        # 오답 복습용 학습 항목 — 출제 단어와 일치 (프롬프트=한쪽, 정답=다른쪽)
        assert {q.prompt, q.answer} == {q.en, q.ko}
        assert q.item_id == int(q.en.removeprefix("word"))


def test_build_questions_prefers_priority_items():
    """P0-A 게임-복습 편입: due·최근 오답 항목이 출제에 우선 포함된다."""
    rng = random.Random(7)
    priority = {1, 5, 9, 13, 17}
    questions = qr.build_questions(_pool(), rounds=10, rng=rng, priority=priority)
    picked = {q.item_id for q in questions}
    assert priority <= picked  # 우선 항목 전부 출제
    assert len(questions) == 10  # 나머지는 일반 풀로 채움


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


async def test_wrong_answers_sent_as_review(wired_db, fast_rounds):  # noqa: F811
    """오답·미제출 문항은 종료 시 qr.review 로 본인에게만 전달 (원탭 학습 추가용)."""
    user = await seed_user_and_words(wired_db)
    manager = qr.QuizRoyaleManager()
    sender = Collector()

    session = await manager.solo(user.id, user.name, sender, bot_level=5, bots=1)
    for _ in range(50):
        if any(m["t"] == "qr.round" for m in sender.messages):
            break
        await asyncio.sleep(0.02)

    # 1라운드 오답 제출, 2라운드 미제출
    q0 = session.questions[0]
    wrong = next(c for c in q0.choices if c != q0.answer)
    await manager.answer(user.id, wrong)
    await asyncio.wait_for(session.task, timeout=5)

    review = next(m for m in sender.messages if m["t"] == "qr.review")
    items = review["items"]
    assert [i["item_id"] for i in items] == [q.item_id for q in session.questions]
    assert all(i["en"] and i["ko"] for i in items)
    # qr.end 이전에 도착 — 결과 화면에서 바로 사용 가능
    types = [m["t"] for m in sender.messages]
    assert types.index("qr.review") < types.index("qr.end")


async def test_all_correct_sends_no_review(wired_db, fast_rounds):  # noqa: F811
    """전부 정답이면 qr.review 를 보내지 않는다."""
    user = await seed_user_and_words(wired_db)
    manager = qr.QuizRoyaleManager()
    sender = Collector()

    session = await manager.solo(user.id, user.name, sender, bot_level=5, bots=1)
    for round_no in (1, 2):
        for _ in range(50):
            if any(m["t"] == "qr.round" and m["no"] == round_no for m in sender.messages):
                break
            await asyncio.sleep(0.02)
        await manager.answer(user.id, session.questions[round_no - 1].answer)
    await asyncio.wait_for(session.task, timeout=5)

    assert not any(m["t"] == "qr.review" for m in sender.messages)
    assert any(m["t"] == "qr.end" for m in sender.messages)


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


async def test_reconnect_during_round_keeps_session(wired_db, fast_rounds):  # noqa: F811
    """대전 도중 WS 끊김 → 재연결 시 세션 복귀해야 한다 (버그: detach 가 매치 진행 중에도
    by_user 를 즉시 지워 재접속을 막았다)."""
    p1 = await seed_user_and_words(wired_db)
    p2 = User(google_sub="g-recon", email="recon@example.com", name="RC")
    wired_db.add(p2)
    await wired_db.commit()

    manager = qr.QuizRoyaleManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(p1.id, p1.name, s1)
    await manager.join(p2.id, p2.name, s2, code)
    await manager.start(p1.id)
    session = manager.sessions[manager.by_user[p1.id]]
    for _ in range(50):
        if any(m["t"] == "qr.round" for m in s2.messages):
            break
        await asyncio.sleep(0.02)

    await manager.detach(p2.id)  # WS 끊김 — 매치는 진행 중
    assert p2.id in manager.by_user  # 세션 매핑이 유지돼야 재접속 가능
    assert session.match_id in manager.sessions  # 세션 자체도 살아있어야 함

    s2b = Collector()
    resumed = await manager.attach(p2.id, s2b)
    assert resumed is session
    idx = manager._index_of(session, p2.id)
    assert session.players[idx].send is s2b
    assert any(m["t"] == "qr.round" for m in s2b.messages)  # 현재 라운드 재전송

    session.task.cancel()


async def test_host_leaving_waiting_room_notifies_remaining_players(wired_db):  # noqa: F811
    """대기방에서 호스트가 나가 세션이 삭제되면 남은 플레이어에게 알려야 한다 (버그 2:
    기존엔 아무 브로드캐스트 없이 세션만 삭제돼 화면이 멈췄다)."""
    p1 = await seed_user_and_words(wired_db)
    p2 = User(google_sub="g-hl", email="hl@example.com", name="HL")
    wired_db.add(p2)
    await wired_db.commit()

    manager = qr.QuizRoyaleManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(p1.id, p1.name, s1)
    await manager.join(p2.id, p2.name, s2, code)

    await manager.detach(p1.id)  # 호스트 이탈 — 대기방(시작 전)

    assert any(m.get("code") == "room_closed" for m in s2.messages)
    assert p2.id not in manager.by_user  # 세션 정리됨
    assert not manager.sessions


# --- 게임 언어 분리 (docs/specs/chat-language-rooms.md §게임 언어 분리) ---


async def test_solo_rejects_invalid_lang(wired_db):  # noqa: F811
    user = await seed_user_and_words(wired_db)
    manager = qr.QuizRoyaleManager()
    with pytest.raises(WordPoolError, match="invalid_lang"):
        await manager.solo(user.id, user.name, Collector(), bot_level=1, bots=1, lang="fr")


async def test_solo_meaning_pool_filtered_by_lang(wired_db, fast_rounds):  # noqa: F811
    """en 콘텐츠와 ja 콘텐츠가 섞여 있어도 출제가 lang 콘텐츠에서만 나온다."""
    user = await seed_user_and_words(wired_db, count=20, lang="en")
    ja_items = await seed_words_for(wired_db, user, "ja", count=20)
    ja_ids = {i.id for i in ja_items}

    manager = qr.QuizRoyaleManager()
    session = await manager.solo(user.id, user.name, Collector(), bot_level=1, bots=1, lang="ja")
    assert session.questions  # 출제 완료
    assert all(q.item_id in ja_ids for q in session.questions)
    session.task.cancel()


async def test_nuance_questions_filtered_by_lang(db_session, monkeypatch):
    """뉘앙스(odd-one-out) 변형도 lang 콘텐츠 안에서만 후보를 뽑는다."""
    import random

    from app.services.game import quiz_royale as qr_mod

    user = await seed_user_and_words(db_session, count=25, lang="en")
    ja_items = await seed_words_for(db_session, user, "ja", count=25)

    monkeypatch.setattr(qr_mod.embeddings, "enabled", lambda db: True)

    async def fake_similar(db, item_id, k=2):
        others = [i for i in ja_items if i.id != item_id]
        return [{"id": p.id, "en_text": p.en_text} for p in others[:2]]

    monkeypatch.setattr(qr_mod.embeddings, "similar_items", fake_similar)

    rng = random.Random(1)
    questions = await qr_mod.build_nuance_questions(
        db_session, user.id, rounds=3, rng=rng, lang="ja"
    )
    assert len(questions) == 3
    ja_texts = {i.en_text for i in ja_items}
    for q in questions:
        assert set(q.choices) <= ja_texts


async def test_room_lang_stored_and_broadcast(wired_db, fast_rounds):  # noqa: F811
    """방장이 고른 lang 이 qr.room 으로 전파되고, 참가자 풀도 그 lang."""
    p1 = await seed_user_and_words(wired_db, count=20, lang="en")
    ja_items = await seed_words_for(wired_db, p1, "ja", count=20)
    ja_ids = {i.id for i in ja_items}
    p2 = User(google_sub="g-qrlang", email="qrlang@example.com", name="QL")
    wired_db.add(p2)
    await wired_db.commit()

    manager = qr.QuizRoyaleManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(p1.id, p1.name, s1, lang="ja")
    room = next(m for m in s1.messages if m["t"] == "qr.room")
    assert room["lang"] == "ja"

    await manager.join(p2.id, p2.name, s2, code)
    await manager.start(p1.id)
    session = manager.sessions[manager.by_user[p1.id]]
    assert all(q.item_id in ja_ids for q in session.questions)
    session.task.cancel()
