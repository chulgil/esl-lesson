"""받아쓰기 배틀 — 채점·점수·랭킹 규칙 (docs/specs/dictation-battle.md)."""

from app.services.game import dictation as dt


def test_word_accuracy_ignores_case_and_punctuation():
    assert dt.word_accuracy("I met him, yesterday!", "i met him yesterday") == 1.0
    assert dt.word_accuracy("I met him yesterday", "i met her yesterday") < 1.0
    assert dt.word_accuracy("Hello world", "") == 0.0
    assert dt.word_accuracy("", "anything") == 0.0


def test_sentence_score_accuracy_gate_for_bonus():
    perfect_fast = dt.sentence_score(1.0, 0.0)
    assert perfect_fast > dt.BASE_MAX  # 정확 100% + 시간 보너스
    sloppy_fast = dt.sentence_score(0.5, 0.0)
    assert sloppy_fast == 50  # 정확도 90% 미만 — 보너스 없음
    assert dt.sentence_score(1.0, dt.SENTENCE_SECONDS) == dt.BASE_MAX


def test_rank_players_score_accuracy_time():
    def player(name, uid, score, acc, ms):
        p = dt.DictatorState(user_id=uid, name=name)
        p.score, p.accuracy_sum, p.total_ms = score, acc, ms
        return p

    name, uid = dt.rank_players([player("a", 1, 500, 4.0, 900), player("b", 2, 400, 5.0, 100)])
    assert (name, uid) == ("a", 1)
    name, _ = dt.rank_players([player("a", 1, 500, 4.0, 900), player("b", 2, 500, 5.0, 9000)])
    assert name == "b"  # 동점이면 정확도
    assert dt.rank_players([player("솔로", 1, 500, 5.0, 1)]) == (None, None)


# --- 오답 → 원탭 학습 (플로우) ---

import asyncio  # noqa: E402

import pytest  # noqa: E402

from app.models import User  # noqa: E402
from app.services.game.manager import WordPoolError  # noqa: E402
from tests.test_game_manager import Collector, seed_user_and_words, wired_db  # noqa: E402, F401

_seed_batch = 0


async def seed_dictation_sentences(db, count=6, lang="en"):
    """유튜브 구간이 있는 문장 시딩 — 받아쓰기 풀 요건 (video_id + start_ms).

    lang: 게임 언어 분리 필터 테스트용 (chat-language-rooms.md §게임 언어 분리).
    """
    from sqlalchemy import select

    from app.models import (
        Content,
        ContentSubscription,
        ItemOccurrence,
        LearningItem,
        TranscriptSegment,
    )

    global _seed_batch
    _seed_batch += 1
    content = Content(
        source="youtube",
        title="dt-seed",
        status="ready",
        visibility="public",
        youtube_video_id=f"vid{_seed_batch:08d}",
        lang=lang,
    )
    db.add(content)
    await db.flush()
    items = []
    for i in range(count):
        segment = TranscriptSegment(
            content_id=content.id,
            seq=i,
            start_ms=i * 4000,
            end_ms=i * 4000 + 3000,
            en_text=f"dictation line {_seed_batch}{i}",
        )
        db.add(segment)
        item = LearningItem(
            item_type="sentence",
            en_text=f"they said dictation line {_seed_batch}{i}",
            ko_text=f"받아쓰기 문장 {_seed_batch}{i}",
            normalized_key=f"dt-sent-{_seed_batch}-{i}",
            review_status="approved",
        )
        db.add(item)
        await db.flush()
        db.add(ItemOccurrence(item_id=item.id, content_id=content.id, segment_id=segment.id))
        items.append(item)
    for user_id in (await db.execute(select(User.id))).scalars().all():
        db.add(ContentSubscription(content_id=content.id, user_id=user_id))
    await db.commit()
    return items


@pytest.fixture
def fast_dictation(monkeypatch):
    monkeypatch.setattr(dt, "SENTENCE_COUNT", 2)
    monkeypatch.setattr(dt, "SENTENCE_SECONDS", 0.5)
    monkeypatch.setattr(dt, "REVEAL_SECONDS", 0.05)
    monkeypatch.setattr(dt, "COUNTDOWN_SECONDS", 0.0)
    monkeypatch.setattr(dt, "TICK", 0.02)


async def _wait_for(collector, msg_type, timeout=3.0):
    for _ in range(int(timeout / 0.02)):
        found = [m for m in collector.messages if m["t"] == msg_type]
        if found:
            return found
        await asyncio.sleep(0.02)
    raise AssertionError(f"{msg_type} not received")


async def test_missed_sentences_sent_as_review(wired_db, fast_dictation):  # noqa: F811
    """부정확 제출·미제출 문장은 종료 시 dt.review 로 본인에게 전달."""
    user = await seed_user_and_words(wired_db)
    await seed_dictation_sentences(wired_db)
    manager = dt.DictationManager()
    sender = Collector()

    session = await manager.solo(user.id, user.name, sender)
    await _wait_for(sender, "dt.sentence")
    await manager.submit(user.id, idx=0, text="totally wrong words")  # 부정확 제출
    await asyncio.wait_for(session.task, timeout=5)  # 2번째 문장은 미제출

    review = next(m for m in sender.messages if m["t"] == "dt.review")
    assert [i["item_id"] for i in review["items"]] == [r["item_id"] for r in session.rounds]
    assert all(i["en"] and i["ko"] for i in review["items"])
    types = [m["t"] for m in sender.messages]
    assert types.index("dt.review") < types.index("dt.end")


async def test_perfect_dictation_sends_no_review(wired_db, fast_dictation):  # noqa: F811
    """전부 정확히 받아쓰면 dt.review 를 보내지 않는다."""
    user = await seed_user_and_words(wired_db)
    await seed_dictation_sentences(wired_db)
    manager = dt.DictationManager()
    sender = Collector()

    session = await manager.solo(user.id, user.name, sender)
    for idx in range(2):
        for _ in range(100):
            if sum(1 for m in sender.messages if m["t"] == "dt.sentence") >= idx + 1:
                break
            await asyncio.sleep(0.02)
        await manager.submit(user.id, idx=idx, text=session.rounds[idx]["en"])
    await asyncio.wait_for(session.task, timeout=5)

    assert not any(m["t"] == "dt.review" for m in sender.messages)
    assert any(m["t"] == "dt.end" for m in sender.messages)


async def test_reconnect_during_battle_keeps_session(wired_db, fast_dictation):  # noqa: F811
    """대전 도중 WS 끊김 → 재연결 시 세션 복귀해야 한다 (버그: detach 가 매치 진행 중에도
    by_user 를 즉시 지워 재접속을 막았다)."""
    host = await seed_user_and_words(wired_db)
    await seed_dictation_sentences(wired_db)
    guest = User(google_sub="g-rc", email="rc@example.com", name="RC")
    wired_db.add(guest)
    await wired_db.commit()

    manager = dt.DictationManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(host.id, host.name, s1)
    await manager.join(guest.id, guest.name, s2, code)
    await manager.begin(host.id)
    session = manager.sessions[manager.by_user[host.id]]
    await _wait_for(s2, "dt.sentence")

    await manager.detach(guest.id)  # WS 끊김 — 매치는 진행 중
    assert guest.id in manager.by_user  # 세션 매핑이 유지돼야 재접속 가능
    assert session.match_id in manager.sessions

    s2b = Collector()
    resumed = await manager.attach(guest.id, s2b)
    assert resumed is session
    player = next(p for p in session.players if p.user_id == guest.id)
    assert player.send is s2b
    assert any(m["t"] == "dt.start" for m in s2b.messages)  # 현재 상태 재전송
    assert any(m["t"] == "dt.sentence" for m in s2b.messages)

    session.task.cancel()


async def test_host_leaving_waiting_room_notifies_remaining_players(wired_db):  # noqa: F811
    """대기방에서 호스트가 나가 세션이 삭제되면 남은 플레이어에게 알려야 한다 (버그 2:
    기존엔 아무 브로드캐스트 없이 세션만 삭제돼 화면이 멈췄다)."""
    host = await seed_user_and_words(wired_db)
    await seed_dictation_sentences(wired_db)
    guest = User(google_sub="g-hl", email="hl@example.com", name="HL")
    wired_db.add(guest)
    await wired_db.commit()

    manager = dt.DictationManager()
    s1, s2 = Collector(), Collector()
    code = await manager.create(host.id, host.name, s1)
    await manager.join(guest.id, guest.name, s2, code)

    await manager.detach(host.id)  # 호스트 이탈 — 대기방(시작 전)

    assert any(m.get("code") == "room_closed" for m in s2.messages)
    assert guest.id not in manager.by_user  # 세션 정리됨
    assert not manager.sessions


# --- 게임 언어 분리 (docs/specs/chat-language-rooms.md §게임 언어 분리) ---


async def test_load_dictation_pool_filters_by_lang(wired_db):  # noqa: F811
    """en 콘텐츠와 ja 콘텐츠가 섞여 있어도 lang 별로 분리된 풀만 나온다."""
    user = await seed_user_and_words(wired_db)
    en_items = await seed_dictation_sentences(wired_db, count=6, lang="en")
    ja_items = await seed_dictation_sentences(wired_db, count=6, lang="ja")

    en_pool = await dt.load_dictation_pool(user.id, lang="en")
    ja_pool = await dt.load_dictation_pool(user.id, lang="ja")

    assert {p["item_id"] for p in en_pool} == {i.id for i in en_items}
    assert {p["item_id"] for p in ja_pool} == {i.id for i in ja_items}


async def test_solo_rejects_invalid_lang(wired_db):  # noqa: F811
    user = await seed_user_and_words(wired_db)
    await seed_dictation_sentences(wired_db)
    manager = dt.DictationManager()
    with pytest.raises(WordPoolError, match="invalid_lang"):
        await manager.solo(user.id, user.name, Collector(), lang="fr")


async def test_room_lang_stored_and_broadcast(wired_db, fast_dictation):  # noqa: F811
    """방장이 고른 lang 이 dt.room·dt.start 로 전파된다."""
    host = await seed_user_and_words(wired_db)
    await seed_dictation_sentences(wired_db, count=6, lang="ja")

    manager = dt.DictationManager()
    s1 = Collector()
    code = await manager.create(host.id, host.name, s1, lang="ja")
    room = next(m for m in s1.messages if m["t"] == "dt.room")
    assert room["lang"] == "ja"

    guest = User(google_sub="g-dtlang", email="dtlang@example.com", name="DL")
    wired_db.add(guest)
    await wired_db.commit()
    s2 = Collector()
    await manager.join(guest.id, guest.name, s2, code)
    await manager.begin(host.id)
    session = manager.sessions[manager.by_user[host.id]]

    start = next(m for m in s1.messages if m["t"] == "dt.start")
    assert start["lang"] == "ja"

    session.task.cancel()
