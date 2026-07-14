"""영문 타자연습 — 문장 동기 레이스(전원 완성 시 다음 문장), 1~4인."""

import asyncio

import pytest

from app.models import TypingRace, User
from app.services.game import typing_race as tr
from app.services.game.manager import WordPoolError
from tests.test_game_manager import Collector, seed_user_and_words, wired_db  # noqa: F401


def test_wpm_and_accuracy():
    # 300자 정타 / 60초 = 60 WPM (5자=1단어)
    assert tr.wpm_for(chars=300, seconds=60.0) == 60.0
    assert tr.wpm_for(chars=0, seconds=60.0) == 0.0
    assert tr.accuracy_for(chars=95, errors=5) == 0.95
    assert tr.accuracy_for(chars=0, errors=0) == 1.0


def test_pick_sentences_cycles_when_short():
    pool = ["One sentence here.", "Another line to type."]
    picked = tr.pick_sentences(pool, count=5, seed=7)
    assert len(picked) == 5
    assert set(picked) <= set(pool)  # 부족하면 순환


def test_rank_players_ordering_and_draw():
    def racer(name, uid, sentences, chars, ms):
        r = tr.RacerState(user_id=uid, name=name)
        r.sentences, r.chars, r.total_ms = sentences, chars, ms
        return r

    # 완성 문장 多 우선 → 정타 → 시간
    name, uid = tr.rank_players([racer("a", 1, 3, 90, 9000), racer("b", 2, 2, 99, 1000)])
    assert (name, uid) == ("a", 1)
    name, _ = tr.rank_players([racer("a", 1, 3, 90, 9000), racer("b", 2, 3, 90, 5000)])
    assert name == "b"  # 같은 문장·정타면 빠른 쪽
    name, uid = tr.rank_players([racer("a", 1, 3, 90, 5000), racer("b", 2, 3, 90, 5000)])
    assert (name, uid) == (None, None)  # 완전 동률 = 무승부


async def seed_sentences(db, count=8):
    from tests.test_study import seed_items

    return await seed_items(db, count=count, item_type="sentence")


@pytest.fixture
def fast_race(monkeypatch):
    monkeypatch.setattr(tr, "SENTENCE_COUNT", 2)
    monkeypatch.setattr(tr, "SENTENCE_SECONDS", 0.5)
    monkeypatch.setattr(tr, "COUNTDOWN_SECONDS", 0.0)
    monkeypatch.setattr(tr, "TICK", 0.02)


async def _wait_for(collector, msg_type, timeout=3.0):
    for _ in range(int(timeout / 0.02)):
        found = [m for m in collector.messages if m["t"] == msg_type]
        if found:
            return found
        await asyncio.sleep(0.02)
    raise AssertionError(f"{msg_type} not received")


async def test_solo_advances_when_i_finish(wired_db, fast_race):  # noqa: F811
    """솔로: 내가 완성하면 바로 다음 문장 — 종료 시 기록 저장."""
    user = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db)
    manager = tr.TypingRaceManager()
    sender = Collector()

    session = await manager.solo(user.id, user.name, sender)
    start = next(m for m in sender.messages if m["t"] == "tp.start")
    assert start["total"] == 2 and start["players"] == [user.name]
    assert "en" in start["sentences"][0] and "ko" in start["sentences"][0]  # 뜻 힌트

    await _wait_for(sender, "tp.sentence")
    first = session.sentences[0]["en"]
    await manager.done(user.id, idx=0, chars=len(first), errors=1)
    # 전원(=나) 완성 → 두 번째 문장 방송
    for _ in range(100):
        if sum(1 for m in sender.messages if m["t"] == "tp.sentence") >= 2:
            break
        await asyncio.sleep(0.02)
    assert sum(1 for m in sender.messages if m["t"] == "tp.sentence") >= 2

    await asyncio.wait_for(session.task, timeout=5)
    end = next(m for m in sender.messages if m["t"] == "tp.end")
    me = end["results"][0]
    assert me["sentences"] == 1 and me["chars"] == len(first)

    row = await wired_db.get(TypingRace, session.match_id)
    await wired_db.refresh(row)
    assert row.status == "finished" and row.mode == "solo"


async def test_race_four_players_sync_and_winner(wired_db, fast_race):  # noqa: F811
    """4인: 방 입장 → 호스트 시작 → 전원 완성 시 진행, 정타 우위 승자, 실시간 진행 중계."""
    host = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db)
    others = []
    for i in range(3):
        u = User(google_sub=f"g-r{i}", email=f"r{i}@example.com", name=f"R{i}")
        wired_db.add(u)
        others.append(u)
    await wired_db.commit()

    manager = tr.TypingRaceManager()
    senders = [Collector() for _ in range(4)]
    code = await manager.create(host.id, host.name, senders[0])
    for u, s in zip(others, senders[1:], strict=True):
        await manager.join(u.id, u.name, s, code)
    room = [m for m in senders[0].messages if m["t"] == "tp.room"][-1]
    assert len(room["players"]) == 4

    await manager.begin(host.id)
    session = manager.sessions[manager.by_user[host.id]]
    await _wait_for(senders[3], "tp.sentence")
    sentence = session.sentences[0]["en"]

    # 실시간 진행 — 다른 플레이어에게 tp.typing (WPM 포함) 전파
    await manager.typing(host.id, idx=0, chars=3)
    typing_msg = (await _wait_for(senders[1], "tp.typing"))[0]
    assert typing_msg["name"] == host.name and typing_msg["chars"] == 3
    assert "wpm" in typing_msg

    # 호스트만 완성 보고 → 나머지는 문장 제한시간까지 대기 후 강제 진행
    await manager.done(host.id, idx=0, chars=len(sentence), errors=0)
    await asyncio.wait_for(session.task, timeout=5)

    end = next(m for m in senders[0].messages if m["t"] == "tp.end")
    assert end["winner"] == host.name
    row = await wired_db.get(TypingRace, session.match_id)
    await wired_db.refresh(row)
    assert row.winner_id == host.id and row.status == "finished"
    assert host.id not in manager.by_user


async def test_room_full_and_missing(wired_db):  # noqa: F811
    host = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db)
    manager = tr.TypingRaceManager()
    code = await manager.create(host.id, host.name, Collector())

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
    await manager.join(999, "G", ghost, "XXXXXX")
    assert any(m.get("code") == "room_not_found" for m in ghost.messages)


async def test_solo_requires_sentences(wired_db):  # noqa: F811
    user = User(google_sub="g-nosent", email="nosent@example.com", name="N")
    wired_db.add(user)
    await wired_db.commit()
    manager = tr.TypingRaceManager()
    with pytest.raises(WordPoolError):
        await manager.solo(user.id, user.name, Collector())
