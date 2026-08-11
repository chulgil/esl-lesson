"""어순 조립 레이스 — 칩 셔플·점수·랭킹 규칙 (docs/specs/scramble-race.md)."""

import random

from app.services.game import scramble as sc


def test_scramble_chips_differs_from_answer_but_same_words():
    words = "I met him at the station yesterday".split()
    rng = random.Random(42)
    chips = sc.scramble_chips(words, rng)
    assert chips != words  # 정답 어순 그대로 내지 않음
    assert sorted(chips) == sorted(words)  # 단어 구성은 동일

    # 전 단어 동일 등 섞기 불가능한 경우는 그대로 통과
    same = ["go", "go", "go"]
    assert sc.scramble_chips(same, rng) == same


def test_sentence_score_bonus_penalty_floor():
    fast = sc.sentence_score(elapsed=0.0, mistakes=0)
    slow = sc.sentence_score(elapsed=sc.SENTENCE_SECONDS, mistakes=0)
    assert fast == sc.BASE_SCORE + sc.TIME_BONUS_MAX + sc.PERFECT_BONUS  # 즉답+무실수
    assert slow == sc.BASE_SCORE + sc.PERFECT_BONUS  # 보너스 0 이어도 퍼펙트는 인정
    assert sc.sentence_score(10.0, mistakes=2) < sc.sentence_score(10.0, mistakes=0)
    # 실수가 아무리 많아도 완성하면 최소 점수 보장 (포기 방지)
    assert sc.sentence_score(30.0, mistakes=50) == sc.MIN_SENTENCE_SCORE


def test_build_rounds_filters_by_chip_range_and_scrambles():
    pool = [
        {"en": "Too short", "ko": "짧음"},  # 2칩 — 제외
        {"en": "This one has exactly six words", "ko": "여섯 단어"},
        {"en": "Another sentence with five words", "ko": "다섯 단어"},
    ]
    rounds = sc.build_rounds(pool, count=4, seed=7)
    assert len(rounds) == 4  # 부족하면 순환
    for r in rounds:
        assert sc.MIN_CHIPS <= len(r["answer"]) <= sc.MAX_CHIPS
        assert sorted(r["chips"]) == sorted(r["answer"])
        assert " ".join(r["answer"]) in {p["en"] for p in pool}


def test_rank_players_score_then_mistakes_then_time():
    def player(name, uid, score, mistakes, ms):
        p = sc.ScramblerState(user_id=uid, name=name)
        p.score, p.mistakes, p.total_ms = score, mistakes, ms
        return p

    name, uid = sc.rank_players([player("a", 1, 900, 5, 9000), player("b", 2, 800, 0, 100)])
    assert (name, uid) == ("a", 1)  # 점수 우선
    name, _ = sc.rank_players([player("a", 1, 900, 5, 900), player("b", 2, 900, 2, 9000)])
    assert name == "b"  # 같은 점수면 실수 적은 쪽
    name, uid = sc.rank_players([player("a", 1, 900, 2, 5000), player("b", 2, 900, 2, 5000)])
    assert (name, uid) == (None, None)  # 완전 동률 = 무승부
    assert sc.rank_players([player("솔로", 1, 900, 0, 100)]) == (None, None)


# --- 오답 → 원탭 학습 (플로우) ---

import asyncio  # noqa: E402

import pytest  # noqa: E402

from app.models import User  # noqa: E402
from tests.test_game_manager import Collector, seed_user_and_words, wired_db  # noqa: E402, F401

_seed_batch = 0


async def seed_scramble_sentences(db, count=6):
    """seed_items 는 단어 1개짜리 en_text — 칩 범위(4~12단어)용 문장을 별도 시딩."""
    from sqlalchemy import select

    from app.models import (
        Content,
        ContentSubscription,
        ItemOccurrence,
        LearningItem,
        User,
    )

    global _seed_batch
    _seed_batch += 1
    content = Content(source="manual", title="sc-seed", status="ready", visibility="public")
    db.add(content)
    await db.flush()
    items = []
    for i in range(count):
        item = LearningItem(
            item_type="sentence",
            en_text=f"this is scramble sentence number {_seed_batch}{i}",
            ko_text=f"어순 문장 {_seed_batch}{i}",
            normalized_key=f"sc-sent-{_seed_batch}-{i}",
            review_status="approved",
        )
        db.add(item)
        await db.flush()
        db.add(ItemOccurrence(item_id=item.id, content_id=content.id))
        items.append(item)
    for user_id in (await db.execute(select(User.id))).scalars().all():
        db.add(ContentSubscription(content_id=content.id, user_id=user_id))
    await db.commit()
    return items


@pytest.fixture
def fast_scramble(monkeypatch):
    monkeypatch.setattr(sc, "SENTENCE_COUNT", 2)
    monkeypatch.setattr(sc, "SENTENCE_SECONDS", 0.5)
    monkeypatch.setattr(sc, "COUNTDOWN_SECONDS", 0.0)
    monkeypatch.setattr(sc, "TICK", 0.02)


async def _wait_for(collector, msg_type, timeout=3.0):
    for _ in range(int(timeout / 0.02)):
        found = [m for m in collector.messages if m["t"] == msg_type]
        if found:
            return found
        await asyncio.sleep(0.02)
    raise AssertionError(f"{msg_type} not received")


async def test_mistake_and_timeout_rounds_sent_as_review(wired_db, fast_scramble):  # noqa: F811
    """실수 있는 완성·시간초과 문장은 종료 시 sc.review 로 본인에게 전달."""
    user = await seed_user_and_words(wired_db)
    await seed_scramble_sentences(wired_db)
    manager = sc.ScrambleManager()
    sender = Collector()

    session = await manager.solo(user.id, user.name, sender)
    start = next(m for m in sender.messages if m["t"] == "sc.start")
    assert all("item_id" in r for r in start["rounds"])  # 라운드에 학습 항목 연결

    await _wait_for(sender, "sc.sentence")
    await manager.done(user.id, idx=0, mistakes=1)  # 실수 있는 완성
    await asyncio.wait_for(session.task, timeout=5)  # 2번째 문장은 시간초과

    review = next(m for m in sender.messages if m["t"] == "sc.review")
    assert [i["item_id"] for i in review["items"]] == [r["item_id"] for r in session.rounds]
    assert all(i["en"] and i["ko"] for i in review["items"])
    types = [m["t"] for m in sender.messages]
    assert types.index("sc.review") < types.index("sc.end")


async def test_perfect_race_sends_no_review(wired_db, fast_scramble):  # noqa: F811
    """무실수로 전부 완성하면 sc.review 를 보내지 않는다."""
    user = await seed_user_and_words(wired_db)
    await seed_scramble_sentences(wired_db)
    manager = sc.ScrambleManager()
    sender = Collector()

    session = await manager.solo(user.id, user.name, sender)
    for idx in range(2):
        for _ in range(100):
            if sum(1 for m in sender.messages if m["t"] == "sc.sentence") >= idx + 1:
                break
            await asyncio.sleep(0.02)
        await manager.done(user.id, idx=idx, mistakes=0)
    await asyncio.wait_for(session.task, timeout=5)

    assert not any(m["t"] == "sc.review" for m in sender.messages)
    assert any(m["t"] == "sc.end" for m in sender.messages)


async def test_reconnect_during_race_keeps_session(wired_db, fast_scramble):  # noqa: F811
    """대전 도중 WS 끊김 → 재연결 시 세션 복귀해야 한다 (버그: detach 가 매치 진행 중에도
    by_user 를 즉시 지워 재접속을 막았다)."""
    host = await seed_user_and_words(wired_db)
    await seed_scramble_sentences(wired_db)
    guest = User(google_sub="g-rc", email="rc@example.com", name="RC")
    wired_db.add(guest)
    await wired_db.commit()

    manager = sc.ScrambleManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(host.id, host.name, s1)
    await manager.join(guest.id, guest.name, s2, code)
    await manager.begin(host.id)
    session = manager.sessions[manager.by_user[host.id]]
    await _wait_for(s2, "sc.sentence")

    await manager.detach(guest.id)  # WS 끊김 — 매치는 진행 중
    assert guest.id in manager.by_user  # 세션 매핑이 유지돼야 재접속 가능
    assert session.match_id in manager.sessions

    s2b = Collector()
    resumed = await manager.attach(guest.id, s2b)
    assert resumed is session
    player = next(p for p in session.players if p.user_id == guest.id)
    assert player.send is s2b
    assert any(m["t"] == "sc.start" for m in s2b.messages)  # 현재 상태 재전송
    assert any(m["t"] == "sc.sentence" for m in s2b.messages)

    session.task.cancel()


async def test_host_leaving_waiting_room_notifies_remaining_players(wired_db):  # noqa: F811
    """대기방에서 호스트가 나가 세션이 삭제되면 남은 플레이어에게 알려야 한다 (버그 2:
    기존엔 아무 브로드캐스트 없이 세션만 삭제돼 화면이 멈췄다)."""
    host = await seed_user_and_words(wired_db)
    await seed_scramble_sentences(wired_db)
    guest = User(google_sub="g-hl", email="hl@example.com", name="HL")
    wired_db.add(guest)
    await wired_db.commit()

    manager = sc.ScrambleManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(host.id, host.name, s1)
    await manager.join(guest.id, guest.name, s2, code)

    await manager.detach(host.id)  # 호스트 이탈 — 대기방(시작 전)

    assert any(m.get("code") == "room_closed" for m in s2.messages)
    assert guest.id not in manager.by_user  # 세션 정리됨
    assert not manager.sessions
