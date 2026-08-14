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


async def seed_user_and_words(db, count=45, lang="en"):
    """가시성 규칙 대응: 게임 풀도 담긴(구독) 콘텐츠 출처가 필요 (content-governance.md).

    lang: 게임 언어 분리 필터 테스트용 (chat-language-rooms.md §게임 언어 분리) — 기본값
    "en" 은 Content.lang 기본값과 같아 기존 호출부(lang 미지정)는 그대로 동작한다.
    """
    from app.models import Content, ContentSubscription, ItemOccurrence

    user = User(google_sub="g-p1", email="p1@example.com", name="P1")
    db.add(user)
    await db.flush()
    content = Content(
        source="manual", title="게임 소재", visibility="public", status="ready", lang=lang
    )
    db.add(content)
    await db.flush()
    db.add(ContentSubscription(content_id=content.id, user_id=user.id))
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
        db.add(ItemOccurrence(item_id=item.id, content_id=content.id))
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


_extra_batch = 0


async def seed_words_for(db, user, lang, count=20):
    """기존 user 에게 다른 lang 콘텐츠의 word 항목을 추가 구독시킨다 — 언어별 풀 분리
    테스트에서 같은 사용자가 여러 언어를 학습 중인 상황을 재현
    (chat-language-rooms.md §게임 언어 분리)."""
    from app.models import Content, ContentSubscription, ItemOccurrence

    global _extra_batch
    _extra_batch += 1
    batch = _extra_batch
    content = Content(
        source="manual",
        title=f"게임 소재-{lang}-{batch}",
        visibility="public",
        status="ready",
        lang=lang,
    )
    db.add(content)
    await db.flush()
    db.add(ContentSubscription(content_id=content.id, user_id=user.id))
    items = []
    for i in range(count):
        item = LearningItem(
            item_type="word",
            en_text=f"{lang}word{batch}n{i}",
            ko_text=f"{lang}뜻{batch}n{i}",
            normalized_key=f"{lang}word{batch}n{i}",
            review_status="approved",
        )
        db.add(item)
        await db.flush()
        db.add(ItemOccurrence(item_id=item.id, content_id=content.id))
        items.append(item)
    await db.commit()
    return items


async def test_word_pool_carries_en_and_ko(wired_db):
    user = await seed_user_and_words(wired_db, count=10)  # 학습 10 < 최소 40 → 전역 보충
    pool = await load_word_pool(user.id)
    assert len(pool) == 10  # 전역 풀도 같은 10개뿐 (dedup 확인)
    # (id, en, ko) — 방향은 스폰 시 레벨 구간으로 결정
    assert all(en.startswith("gameword") and ko.startswith("뜻") for _, en, ko in pool)


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
    text = session.match.board1.bricks[0].answer
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


async def test_pve_disconnect_forfeit_is_aborted_not_loss(wired_db, monkeypatch):
    """PvE 에서 사람이 이탈해 몰수되면 패 대신 aborted — 전적에 안 잡힘 (2026-07-14 버그)."""
    import app.services.game.manager as manager_mod
    from app.services.game.manager import GameManager

    monkeypatch.setattr(manager_mod, "RECONNECT_GRACE_SECONDS", 0.0)
    user = await seed_user_and_words(wired_db)
    gm = GameManager()
    session = await gm.join_pve(user.id, user.name, "en", bot_level=2, send=Collector())
    session.task.cancel()

    gm.detach(user.id)  # 이탈 → 유예 0초 → 다음 스텝에서 몰수
    await gm._step(session, 0.1)
    assert session.match.finished
    await gm._finish(session, aborted=session.abandoned)

    row = await wired_db.get(GameMatch, session.match_id)
    await wired_db.refresh(row)
    assert row.status == "aborted"  # 패(finished+winner=bot)가 아니라 기록 제외


async def test_pve_word_queue_prioritizes_due_cards(wired_db):
    """P0-A 게임-복습 편입: due 도래 카드가 게임 큐 앞에 온다 (effectiveness-audit 4차)."""
    from datetime import UTC, datetime, timedelta

    user = await seed_user_and_words(wired_db)
    cards = (
        (await wired_db.execute(select(ReviewCard).where(ReviewCard.user_id == user.id)))
        .scalars()
        .all()
    )
    due_ids = {c.item_id for c in cards[:5]}
    for card in cards:
        if card.item_id not in due_ids:
            card.due_at = datetime.now(UTC) + timedelta(days=3)  # 나머지는 미래 due
    await wired_db.commit()

    gm = GameManager()
    session = await gm.join_pve(user.id, user.name, "en", bot_level=1, send=Collector())
    session.task.cancel()
    assert {w[0] for w in session.match.board1.word_queue[:5]} == due_ids
    # 공정성: 봇 보드도 같은 큐
    assert session.match.board1.word_queue == session.match.board2.word_queue
    session.match.forfeit(1)


async def test_match_review_returns_uncleared_words(wired_db):
    """종료 시 못 지운 브릭이 match.review 로 온다 — 원탭 학습 추가 (P0-A)."""
    user = await seed_user_and_words(wired_db)
    gm = GameManager()
    sender = Collector()
    session = await gm.join_pve(user.id, user.name, "en", bot_level=1, send=sender)
    session.task.cancel()
    while len(session.match.board1.bricks) < 2:
        session.match.tick(0.1)
    remaining_ids = {b.word_id for b in session.match.board1.bricks if not b.is_garbage}
    session.match.board2.add_garbage(12)  # 봇 KO → 종료
    session.match.tick(0.1)
    assert session.match.finished
    await gm._finish(session)

    review = next(m for m in sender.messages if m["t"] == "match.review")
    assert {i["item_id"] for i in review["items"]} == remaining_ids
    types = sender.types()
    assert types.index("match.review") < types.index("match.end")  # 결과 화면에서 바로 담기


async def test_use_item_via_manager(wired_db):
    user = await seed_user_and_words(wired_db)
    gm = GameManager()
    sender = Collector()
    session = await gm.join_pve(user.id, user.name, "en", bot_level=2, send=sender)
    session.task.cancel()
    # 아이템 지급 후 사용
    session.match.board1.items.append("shield")
    await gm.handle_item(user.id, "shield")
    assert session.match.board1.shield_count == 1
    result = next(m for m in sender.messages if m["t"] == "item.result")
    assert result["ok"] is True and result["item"] == "shield"
    # 없는 아이템은 ok=false
    await gm.handle_item(user.id, "bomb")
    fail = [m for m in sender.messages if m["t"] == "item.result" and m.get("ok") is False]
    assert fail and fail[-1]["item"] == "bomb"
    session.match.forfeit(2)


# --- 게임 언어 분리 (docs/specs/chat-language-rooms.md §게임 언어 분리) ---


async def test_load_word_pool_filters_by_lang(wired_db):
    """en 콘텐츠와 ja 콘텐츠가 섞여 있어도 lang 별로 분리된 풀만 나온다."""
    user = await seed_user_and_words(wired_db, count=10, lang="en")
    ja_items = await seed_words_for(wired_db, user, "ja", count=10)

    en_pool = await load_word_pool(user.id, lang="en")
    ja_pool = await load_word_pool(user.id, lang="ja")

    assert len(en_pool) == 10
    assert all(en.startswith("gameword") for _, en, _ in en_pool)
    assert {i[0] for i in ja_pool} == {i.id for i in ja_items}
    assert all(en.startswith("jaword") for _, en, _ in ja_pool)


async def test_resolve_lang_prefers_explicit_then_settings(wired_db):
    from app.models.user import UserSettings
    from app.services.game.manager import resolve_lang

    user = await seed_user_and_words(wired_db, count=5)
    wired_db.add(UserSettings(user_id=user.id, learning_langs=["ja", "en"]))
    await wired_db.commit()

    assert await resolve_lang(user.id, "en") == "en"  # 명시값 우선
    assert await resolve_lang(user.id, None) == "ja"  # 생략 시 settings[0]

    no_settings = User(google_sub="g-nosettings", email="nosettings@example.com", name="NS")
    wired_db.add(no_settings)
    await wired_db.commit()
    assert await resolve_lang(no_settings.id, None) == "en"  # settings 없으면 기본값


async def test_pve_rejects_invalid_lang(wired_db):
    import pytest

    from app.services.game.manager import WordPoolError

    user = await seed_user_and_words(wired_db)
    gm = GameManager()
    with pytest.raises(WordPoolError, match="invalid_lang"):
        await gm.join_pve(user.id, user.name, "en", bot_level=1, send=Collector(), lang="fr")


async def test_room_lang_stored_and_propagated(wired_db):
    """방장이 고른 lang 이 room.created·match.found 로 전파되고, 참가자 풀도 그 lang."""
    p1 = await seed_user_and_words(wired_db, count=10, lang="ja")
    p2 = User(google_sub="g-langp2", email="langp2@example.com", name="P2")
    wired_db.add(p2)
    await wired_db.commit()

    gm = GameManager()
    s1, s2 = Collector(), Collector()
    code = await gm.create_room(p1.id, p1.name, "en", s1, lang="ja")
    created = next(m for m in s1.messages if m["t"] == "room.created")
    assert created["lang"] == "ja"

    await gm.join_room(p2.id, p2.name, code, s2)
    found = next(m for m in s1.messages if m["t"] == "match.found")
    assert found["lang"] == "ja"
    session = gm.sessions[gm.by_user[p1.id]]
    session.task.cancel()
    session.match.forfeit(1)


async def test_pvp_queue_matches_within_same_lang_only(wired_db):
    """언어가 다르면 매칭되지 않고, 같은 언어끼리만 성사된다."""
    p1 = await seed_user_and_words(wired_db, count=10, lang="en")
    p2 = User(google_sub="g-qja", email="qja@example.com", name="QJA")
    p3 = User(google_sub="g-qen", email="qen@example.com", name="QEN")
    wired_db.add_all([p2, p3])
    await wired_db.commit()

    gm = GameManager()
    s1, s2, s3 = Collector(), Collector(), Collector()
    await gm.join_pvp_queue(p1.id, p1.name, "en", s1, lang="en")
    await gm.join_pvp_queue(p2.id, p2.name, "en", s2, lang="ja")  # 다른 언어 — 미성사
    assert s1.types() == ["queue.waiting"]
    assert not any(m["t"] == "match.found" for m in s2.messages)

    await gm.join_pvp_queue(p3.id, p3.name, "en", s3, lang="en")  # 같은 언어 — 성사
    assert any(m["t"] == "match.found" for m in s1.messages)
    assert any(m["t"] == "match.found" for m in s3.messages)
    session = gm.sessions[gm.by_user[p1.id]]
    session.task.cancel()
    session.match.forfeit(1)
