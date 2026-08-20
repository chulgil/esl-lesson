"""영문 타자연습 — 문장 동기 레이스(전원 완성 시 다음 문장), 1~4인."""

import asyncio
import time

import pytest

from app.models import TypingRace, User
from app.services.game import typing_race as tr
from app.services.game.manager import WordPoolError, review_items
from tests.test_game_manager import Collector, seed_user_and_words, wired_db  # noqa: F401


def test_review_items_dedupes_and_drops_missing_ids():
    entries = [
        {"item_id": 1, "en": "a", "ko": "가"},
        {"item_id": 1, "en": "a", "ko": "가"},  # 순환 풀에서 같은 문장 반복
        {"item_id": 2, "en": "b", "ko": "나"},
        {"en": "no id", "ko": "제외"},
    ]
    assert review_items(entries) == [
        {"item_id": 1, "en": "a", "ko": "가"},
        {"item_id": 2, "en": "b", "ko": "나"},
    ]


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
    # 방 게임은 종료 후에도 방·매핑이 유지된다 — 재대결 대기 (2026-08-20 다시하기)
    assert host.id in manager.by_user and not session.started


async def test_typo_and_timeout_sentences_sent_as_review(wired_db, fast_race):  # noqa: F811
    """오타 완성·시간초과 문장은 종료 시 tp.review 로 본인에게 전달."""
    user = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db)
    manager = tr.TypingRaceManager()
    sender = Collector()

    session = await manager.solo(user.id, user.name, sender)
    start = next(m for m in sender.messages if m["t"] == "tp.start")
    assert all("item_id" in s for s in start["sentences"])  # 풀에 학습 항목 연결

    await _wait_for(sender, "tp.sentence")
    first = session.sentences[0]["en"]
    await manager.done(user.id, idx=0, chars=len(first), errors=2)  # 오타 있는 완성
    await asyncio.wait_for(session.task, timeout=5)  # 2번째 문장은 시간초과

    review = next(m for m in sender.messages if m["t"] == "tp.review")
    assert review["items"] == review_items(session.sentences)
    types = [m["t"] for m in sender.messages]
    assert types.index("tp.review") < types.index("tp.end")


async def test_clean_race_sends_no_review(wired_db, fast_race):  # noqa: F811
    """무오타로 전부 완성하면 tp.review 를 보내지 않는다."""
    user = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db)
    manager = tr.TypingRaceManager()
    sender = Collector()

    session = await manager.solo(user.id, user.name, sender)
    for idx in range(2):
        for _ in range(100):
            if sum(1 for m in sender.messages if m["t"] == "tp.sentence") >= idx + 1:
                break
            await asyncio.sleep(0.02)
        await manager.done(user.id, idx=idx, chars=len(session.sentences[idx]["en"]), errors=0)
    await asyncio.wait_for(session.task, timeout=5)

    assert not any(m["t"] == "tp.review" for m in sender.messages)
    assert any(m["t"] == "tp.end" for m in sender.messages)


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


async def test_reconnect_during_race_keeps_session(wired_db, fast_race):  # noqa: F811
    """대전 도중 WS 끊김 → 재연결 시 세션 복귀해야 한다 (버그: detach 가 매치 진행 중에도
    by_user 를 즉시 지워 재접속을 막았다)."""
    host = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db)
    guest = User(google_sub="g-rc", email="rc@example.com", name="RC")
    wired_db.add(guest)
    await wired_db.commit()

    manager = tr.TypingRaceManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(host.id, host.name, s1)
    await manager.join(guest.id, guest.name, s2, code)
    await manager.begin(host.id)
    session = manager.sessions[manager.by_user[host.id]]
    await _wait_for(s2, "tp.sentence")

    await manager.detach(guest.id)  # WS 끊김 — 매치는 진행 중
    assert guest.id in manager.by_user  # 세션 매핑이 유지돼야 재접속 가능
    assert session.match_id in manager.sessions

    s2b = Collector()
    resumed = await manager.attach(guest.id, s2b)
    assert resumed is session
    racer = next(p for p in session.players if p.user_id == guest.id)
    assert racer.send is s2b
    assert any(m["t"] == "tp.start" for m in s2b.messages)  # 현재 상태 재전송
    assert any(m["t"] == "tp.sentence" for m in s2b.messages)

    session.task.cancel()


async def test_host_leaving_waiting_room_notifies_remaining_players(wired_db):  # noqa: F811
    """대기방에서 호스트가 나가 세션이 삭제되면 남은 플레이어에게 알려야 한다 (버그 2:
    기존엔 아무 브로드캐스트 없이 세션만 삭제돼 화면이 멈췄다)."""
    host = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db)
    guest = User(google_sub="g-hl", email="hl@example.com", name="HL")
    wired_db.add(guest)
    await wired_db.commit()

    manager = tr.TypingRaceManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(host.id, host.name, s1)
    await manager.join(guest.id, guest.name, s2, code)

    await manager.detach(host.id)  # 호스트 이탈 — 대기방(시작 전)

    assert any(m.get("code") == "room_closed" for m in s2.messages)
    assert guest.id not in manager.by_user  # 세션 정리됨
    assert not manager.sessions


# --- 재대결·출제 히스토리 (2026-08-20 다시하기 목표) ---


async def test_room_rematch_keeps_players_and_new_match(wired_db, monkeypatch):  # noqa: F811
    """레이스 종료 후 방이 유지되고, 방장 begin 으로 새 매치가 시작된다 —
    다시하기 = 재입장 없이 같은 멤버로 다음 판."""
    monkeypatch.setattr(tr, "COUNTDOWN_SECONDS", 0.0)
    host = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db)
    guest = User(google_sub="g-rm", email="rm@example.com", name="RM")
    wired_db.add(guest)
    await wired_db.commit()

    manager = tr.TypingRaceManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(host.id, host.name, s1)
    await manager.join(guest.id, guest.name, s2, code)
    await manager.begin(host.id)
    session = manager.sessions[manager.by_user[host.id]]
    session.task.cancel()
    first_match_id = session.match_id
    session.players[0].chars = 42
    session.players[0].sentences = 1
    session.players[0].wrong = [0]
    await manager._finish(session, aborted=False)

    # 방 유지 — 세션·매핑·방 코드가 남고 대기 상태로 복귀
    assert manager.by_user.get(host.id) is not None
    assert manager.by_user.get(guest.id) is not None
    assert not session.started
    assert manager.rooms.get(code) is not None

    await manager.begin(host.id)
    assert session.started
    assert session.match_id != first_match_id  # 새 매치 행
    for p in session.players:
        assert p.chars == 0 and p.sentences == 0 and p.wrong == []
    assert len([m for m in s2.messages if m["t"] == "tp.start"]) >= 2  # 첫 판 + 재대결
    session.task.cancel()
    manager._cleanup(session)


async def test_solo_finish_still_cleans_up(wired_db, monkeypatch):  # noqa: F811
    """솔로는 종전대로 종료 시 정리 — 한 번 더는 새 솔로 생성."""
    monkeypatch.setattr(tr, "COUNTDOWN_SECONDS", 0.0)
    user = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db)
    manager = tr.TypingRaceManager()
    session = await manager.solo(user.id, user.name, Collector())
    session.task.cancel()

    await manager._finish(session, aborted=False)
    assert user.id not in manager.by_user
    assert session.match_id not in manager.sessions


async def test_sentences_exclude_recently_served(wired_db, monkeypatch):  # noqa: F811
    """연달아 하면 직전 판 문장이 반복되지 않는다 (풀이 충분할 때)."""
    monkeypatch.setattr(tr, "SENTENCE_COUNT", 4)
    monkeypatch.setattr(tr, "COUNTDOWN_SECONDS", 0.0)
    user = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db, count=8)
    manager = tr.TypingRaceManager()

    first = await manager.solo(user.id, user.name, Collector())
    first.task.cancel()
    first_ids = {s["item_id"] for s in first.sentences}
    await manager._finish(first, aborted=False)

    second = await manager.solo(user.id, user.name, Collector())
    second.task.cancel()
    second_ids = {s["item_id"] for s in second.sentences}
    await manager._finish(second, aborted=False)

    assert first_ids and first_ids.isdisjoint(second_ids)  # 8문장 풀 — 4+4 겹침 없음


# --- 게임 언어 분리 (docs/specs/chat-language-rooms.md §게임 언어 분리) ---

_lang_batch = 0


async def seed_lang_sentences(db, lang, count=6):
    """lang 콘텐츠의 문장 시딩. test_study.seed_items 는 lang 파라미터가 없어
    (그 파일은 소유 범위 밖) 로컬로 별도 시딩한다."""
    from sqlalchemy import select

    from app.models import Content, ContentSubscription, ItemOccurrence, LearningItem, User

    global _lang_batch
    _lang_batch += 1
    batch = _lang_batch
    content = Content(
        source="manual",
        title=f"lang-seed-{lang}-{batch}",
        status="ready",
        visibility="public",
        lang=lang,
    )
    db.add(content)
    await db.flush()
    items = []
    for i in range(count):
        item = LearningItem(
            item_type="sentence",
            en_text=f"{lang} sentence {batch} number {i}",
            ko_text=f"{lang} 문장 {batch} {i}",
            normalized_key=f"lang-sent-{lang}-{batch}-{i}",
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


async def test_load_sentence_pool_filters_by_lang(wired_db):  # noqa: F811
    """en 콘텐츠와 ja 콘텐츠가 섞여 있어도 lang 별로 분리된 풀만 나온다."""
    user = await seed_user_and_words(wired_db)
    en_items = await seed_lang_sentences(wired_db, "en", count=6)
    ja_items = await seed_lang_sentences(wired_db, "ja", count=6)

    en_pool = await tr.load_sentence_pool(user.id, lang="en")
    ja_pool = await tr.load_sentence_pool(user.id, lang="ja")

    assert {p["item_id"] for p in en_pool} == {i.id for i in en_items}
    assert {p["item_id"] for p in ja_pool} == {i.id for i in ja_items}


async def test_solo_rejects_invalid_lang(wired_db):  # noqa: F811
    user = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db)
    manager = tr.TypingRaceManager()
    with pytest.raises(WordPoolError, match="invalid_lang"):
        await manager.solo(user.id, user.name, Collector(), lang="fr")


async def test_room_lang_stored_and_broadcast_through_start(wired_db, fast_race):  # noqa: F811
    """방장이 고른 lang 이 tp.room·tp.start 로 전파되고, 참가자 풀도 같은 lang."""
    host = await seed_user_and_words(wired_db)
    await seed_lang_sentences(wired_db, "ja", count=6)
    guest = User(google_sub="g-lang", email="lang@example.com", name="LG")
    wired_db.add(guest)
    await wired_db.commit()

    manager = tr.TypingRaceManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(host.id, host.name, s1, lang="ja")
    room = next(m for m in s1.messages if m["t"] == "tp.room")
    assert room["lang"] == "ja"

    await manager.join(guest.id, guest.name, s2, code)
    await manager.begin(host.id)
    session = manager.sessions[manager.by_user[host.id]]
    start = next(m for m in s1.messages if m["t"] == "tp.start")
    assert start["lang"] == "ja"
    assert all(s["en"].startswith("ja sentence") for s in start["sentences"])

    session.task.cancel()


# --- 명시적 퇴장·잔여시간 (2026-08-20 교차 리뷰) ---


async def test_leave_on_result_screen_drops_player_and_blocks_ghost(wired_db, monkeypatch):  # noqa: F811
    """결과 화면을 떠난 사람은 방에서 빠지고, 다른 페이지에서 WS 를 열어도
    재대결에 유령 참가자로 편입되지 않는다 (버그 A)."""
    monkeypatch.setattr(tr, "COUNTDOWN_SECONDS", 0.0)
    host = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db)
    stay = User(google_sub="g-tgh1", email="tgh1@example.com", name="ST")
    gone = User(google_sub="g-tgh2", email="tgh2@example.com", name="GO")
    wired_db.add_all([stay, gone])
    await wired_db.commit()

    manager = tr.TypingRaceManager()
    s1, s2, s3 = Collector(), Collector(), Collector()
    code = await manager.create(host.id, host.name, s1)
    await manager.join(stay.id, stay.name, s2, code)
    await manager.join(gone.id, gone.name, s3, code)
    await manager.begin(host.id)
    session = manager.sessions[manager.by_user[host.id]]
    session.task.cancel()
    await manager._finish(session, aborted=False)
    assert session.completed

    await manager.leave(gone.id)  # 결과 화면 이탈 (tp.leave)
    assert gone.id not in manager.by_user
    assert all(p.user_id != gone.id for p in session.players)
    assert await manager.attach(gone.id, Collector()) is None

    await manager.begin(host.id)  # 방장 다시하기
    assert session.started
    assert all(p.user_id != gone.id for p in session.players)
    session.task.cancel()
    manager._cleanup(session)


async def test_attach_sentence_includes_server_remaining(wired_db, monkeypatch):  # noqa: F811
    """진행 중 재접속의 문장 재전송에 서버 기준 잔여시간이 실린다 — 없으면
    클라가 전체 시간으로 타이머를 되감는다 (버그 B)."""
    monkeypatch.setattr(tr, "COUNTDOWN_SECONDS", 0.0)
    user = await seed_user_and_words(wired_db)
    await seed_sentences(wired_db)
    manager = tr.TypingRaceManager()
    session = await manager.solo(user.id, user.name, Collector())
    session.task.cancel()
    session.round_no = 0
    session.round_started = time.monotonic() - 3.0

    resumed = Collector()
    assert await manager.attach(user.id, resumed) is session
    msgs = [m for m in resumed.messages if m["t"] == "tp.sentence"]
    assert msgs
    assert 0 < msgs[-1]["remaining"] < tr.SENTENCE_SECONDS
    manager._cleanup(session)
