"""임베딩 서비스 + 유사단어 선지 배치 (docs/proposal/word-insight.md P2)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import get_settings
from app.services import embeddings, quiz


def _item(i, en, ko, t="word"):
    return SimpleNamespace(
        id=i, en_text=en, ko_text=ko, item_type=t, pattern_template=None, occurrences=[]
    )


async def test_embed_texts_restores_input_order():
    """Voyage 응답이 순서 뒤섞여 와도 index 로 입력 순서 복원."""
    payload = {
        "data": [
            {"index": 1, "embedding": [0.2] * 4},
            {"index": 0, "embedding": [0.1] * 4},
        ]
    }
    res = MagicMock()
    res.json.return_value = payload
    res.raise_for_status.return_value = None
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.post = AsyncMock(return_value=res)

    with patch.object(embeddings.httpx, "AsyncClient", return_value=client):
        out = await embeddings.embed_texts(["a", "b"])

    assert out == [[0.1] * 4, [0.2] * 4]
    body = client.post.await_args.kwargs["json"]
    assert body["output_dimension"] == embeddings.EMBEDDING_DIM
    assert body["input"] == ["a", "b"]


async def test_enabled_requires_key_and_postgres(db_session):
    """키 없음 → 비활성. 키 있어도 sqlite(테스트 DB) → 비활성 (안전 스킵)."""
    settings = get_settings()
    original = settings.voyage_embedding_secret
    try:
        settings.voyage_embedding_secret = ""
        assert embeddings.enabled(db_session) is False
        settings.voyage_embedding_secret = "test-key"
        assert embeddings.enabled(db_session) is False  # sqlite 라서
    finally:
        settings.voyage_embedding_secret = original


def test_distractors_prefer_similar_words():
    """유사단어 최대 2개 우선 + 나머지 랜덤 (2+1 배합), 정답/중복 제외."""
    pool = [_item(i, f"w{i}", f"뜻{i}") for i in range(10)]
    target = pool[0]
    similar = [
        {"en_text": "w0", "ko_text": "뜻0"},  # 정답과 동일 — 제외돼야 함
        {"en_text": "near1", "ko_text": "비슷1"},
        {"en_text": "near2", "ko_text": "비슷2"},
        {"en_text": "near3", "ko_text": "비슷3"},  # 2개 상한 초과 — 미사용
    ]
    picked = quiz._distractors(target, pool, "ko_text", similar)
    assert len(picked) == 3
    assert picked[0] == "비슷1" and picked[1] == "비슷2"
    assert "비슷3" not in picked and "뜻0" not in picked


async def test_wrong_answer_reports_close_match(client, db_session):
    """오답이 임베딩 유사단어면 close_match(아깝다) 반환, 무관 오답은 null."""
    from tests.test_study import login, seed_items

    await login(client, db_session)
    await seed_items(db_session, count=1)
    res = await client.get("/api/study/queue")
    q = res.json()["questions"][0]
    field = "ko_text" if q["quiz_mode"] == "choice_en2ko" else "en_text"
    fake = [{"id": 777, "en_text": "villain", "ko_text": "악당", "distance": 0.1}]

    with (
        patch.object(embeddings, "enabled", return_value=True),
        patch.object(embeddings, "similar_items", new=AsyncMock(return_value=fake)),
    ):
        wrong_similar = await client.post(
            "/api/study/answer",
            json={
                "card_id": q["card_id"],
                "quiz_mode": q["quiz_mode"],
                "answer": fake[0][field],
                "duration_ms": 1000,
            },
        )
    body = wrong_similar.json()
    assert body["correct"] is False
    assert body["close_match"] == {
        "item_id": 777,
        "en_text": "villain",
        "ko_text": "악당",
    }

    # 무관 오답 → close_match 없음 (두 번째 문항이 없으므로 같은 카드 재채점은 하지 않고
    # 새 카드로 확인)
    await seed_items(db_session, count=1)
    res2 = await client.get("/api/study/queue")
    q2 = res2.json()["questions"][0]
    with (
        patch.object(embeddings, "enabled", return_value=True),
        patch.object(embeddings, "similar_items", new=AsyncMock(return_value=fake)),
    ):
        wrong_random = await client.post(
            "/api/study/answer",
            json={
                "card_id": q2["card_id"],
                "quiz_mode": q2["quiz_mode"],
                "answer": "totally-unrelated",
                "duration_ms": 1000,
            },
        )
    body2 = wrong_random.json()
    assert body2["correct"] is False
    assert body2["close_match"] is None


def test_build_question_uses_similar_choices():
    pool = [_item(i, f"w{i}", f"뜻{i}") for i in range(8)]
    similar = [
        {"en_text": "near1", "ko_text": "비슷1"},
        {"en_text": "near2", "ko_text": "비슷2"},
    ]
    q = quiz.build_question(pool[0], pool, similar)
    joined = set(q["choices"])
    assert {"비슷1", "비슷2"} <= joined or {"near1", "near2"} <= joined  # 방향에 따라 en/ko
