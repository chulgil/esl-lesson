"""어휘망 그래프 — 내 카드 노드 + 근접 엣지 + 덱 밖 추천 (docs/proposal/word-insight.md P3)."""

from unittest.mock import AsyncMock, patch

from app.services import embeddings, vocab_network
from tests.test_study import login, seed_items


def _row(src, dst, distance, en="w", ko="뜻"):
    return {"src": src, "dst": dst, "en_text": en, "ko_text": ko, "distance": distance}


def test_build_network_edges_dedup_and_threshold():
    """양방향 중복 쌍은 한 엣지(최소 거리)로, 임계 초과는 제외."""
    rows = [
        _row(1, 2, 0.20),
        _row(2, 1, 0.23),  # 같은 쌍 역방향 — 하나로 합쳐야 함
        _row(1, 3, 0.90),  # 임계(0.55) 초과 — 제외
    ]
    edges, suggestions = vocab_network.build_network({1, 2, 3}, rows)
    assert edges == [{"source": 1, "target": 2, "distance": 0.20}]
    assert suggestions == []


def test_build_network_edge_cap_per_node():
    """한 노드의 엣지는 가까운 순으로 상한(max_edges_per_node)까지만."""
    rows = [_row(1, dst, 0.1 + dst * 0.01) for dst in range(2, 9)]
    edges, _ = vocab_network.build_network(set(range(1, 9)), rows, max_edges_per_node=3)
    assert len(edges) == 3
    assert [e["target"] for e in edges] == [2, 3, 4]  # 가까운 순


def test_build_network_suggestions_ranked_and_capped():
    """덱 밖 이웃은 dst 별 최소 거리로 집계, 가까운 순 정렬 + 상한."""
    rows = [
        _row(1, 10, 0.30, en="ten"),
        _row(2, 10, 0.25, en="ten"),  # 같은 후보 — 더 가까운 src 채택
        _row(1, 11, 0.40, en="eleven"),
        _row(2, 12, 0.45, en="twelve"),
        _row(1, 13, 0.70, en="far"),  # 임계 초과 — 제외
    ]
    edges, suggestions = vocab_network.build_network({1, 2}, rows, max_suggestions=2)
    assert edges == []
    assert [s["item_id"] for s in suggestions] == [10, 11]
    assert suggestions[0]["near_item_id"] == 2
    assert suggestions[0]["distance"] == 0.25


async def test_network_endpoint_nodes_without_embeddings(client, db_session):
    """sqlite(임베딩 비활성): 내 word/idiom 카드만 노드로, 엣지/추천 없음.
    sentence 카드와 suspend 카드는 제외."""
    await login(client, db_session)
    words = await seed_items(db_session, count=2)
    sentences = await seed_items(db_session, count=1, item_type="sentence")
    for item in [*words, *sentences]:
        await client.post("/api/cards", json={"item_id": item.id})
    suspended = await client.post("/api/cards", json={"item_id": words[1].id})
    # words[1] 은 위에서 이미 추가됨 → 기존 카드 반환. suspend 처리
    await client.post(f"/api/cards/{suspended.json()['card_id']}/suspend", json={"suspended": True})

    res = await client.get("/api/study/network")
    assert res.status_code == 200
    body = res.json()
    assert [n["item_id"] for n in body["nodes"]] == [words[0].id]
    assert body["nodes"][0]["en"] == words[0].en_text
    assert body["nodes"][0]["state"] == "new"
    assert body["edges"] == []
    assert body["suggestions"] == []
    assert body["embeddings_enabled"] is False


async def test_network_endpoint_requires_auth(client):
    res = await client.get("/api/study/network")
    assert res.status_code == 401


async def test_network_excludes_unsubscribed_content_words(client, db_session):
    """구독 해제 → 노드 소멸(카드는 보존), 재담기 → 그대로 복귀 (content-governance.md)."""
    from sqlalchemy import select

    from app.models import ItemOccurrence, ReviewCard

    user = await login(client, db_session)
    words = await seed_items(db_session, count=1)
    await client.post("/api/cards", json={"item_id": words[0].id})
    content_id = (
        await db_session.execute(
            select(ItemOccurrence.content_id).where(ItemOccurrence.item_id == words[0].id)
        )
    ).scalar_one()

    nodes = (await client.get("/api/study/network")).json()["nodes"]
    assert [n["item_id"] for n in nodes] == [words[0].id]

    # 빼기: 노드에서 사라지지만 카드 행은 남는다
    assert (await client.delete(f"/api/my/contents/{content_id}")).status_code == 204
    assert (await client.get("/api/study/network")).json()["nodes"] == []
    card = (
        await db_session.execute(select(ReviewCard).where(ReviewCard.user_id == user.id))
    ).scalar_one()
    assert card.item_id == words[0].id

    # 재담기: 같은 카드로 복귀
    assert (await client.post(f"/api/my/contents/{content_id}/subscribe")).status_code == 202
    nodes = (await client.get("/api/study/network")).json()["nodes"]
    assert [n["item_id"] for n in nodes] == [words[0].id]


async def test_network_endpoint_edges_and_visible_suggestions(client, db_session):
    """임베딩 활성(mock): 내 항목 간 엣지 + 덱 밖 추천(가시성 통과분만)."""
    await login(client, db_session)
    words = await seed_items(db_session, count=2)
    ghosts = await seed_items(db_session, count=1)  # 승인+공용 — 추천 노출
    hidden = await seed_items(db_session, count=1, status="pending")  # 미승인 — 제외
    for item in words:
        await client.post("/api/cards", json={"item_id": item.id})

    rows = [
        _row(words[0].id, words[1].id, 0.2),
        _row(words[0].id, ghosts[0].id, 0.3, en=ghosts[0].en_text, ko=ghosts[0].ko_text),
        _row(words[1].id, hidden[0].id, 0.1, en=hidden[0].en_text, ko=hidden[0].ko_text),
    ]
    with (
        patch.object(embeddings, "enabled", return_value=True),
        patch.object(vocab_network, "neighbor_rows", new=AsyncMock(return_value=rows)),
    ):
        res = await client.get("/api/study/network")

    body = res.json()
    assert body["embeddings_enabled"] is True
    assert body["edges"] == [{"source": words[0].id, "target": words[1].id, "distance": 0.2}]
    assert [s["item_id"] for s in body["suggestions"]] == [ghosts[0].id]
    assert body["suggestions"][0]["en"] == ghosts[0].en_text


async def test_network_endpoint_lang_filter_and_counts(client, db_session):
    """언어별 복수 네트워크 분리 (word-insight.md §어휘망 언어별 분리, 2026-08-14).

    lang 파라미터가 콘텐츠 언어로 노드를 가르고, counts 는 언어 무관 전체
    집계(칩 노출 판단용)로 항상 함께 온다."""
    await login(client, db_session)
    en_words = await seed_items(db_session, count=2, lang="en")
    ja_words = await seed_items(db_session, count=1, lang="ja")
    for item in [*en_words, *ja_words]:
        await client.post("/api/cards", json={"item_id": item.id})

    en_res = (await client.get("/api/study/network?lang=en")).json()
    assert sorted(n["item_id"] for n in en_res["nodes"]) == sorted(i.id for i in en_words)
    assert en_res["lang"] == "en"
    assert en_res["counts"] == {"en": 2, "ja": 1}

    ja_res = (await client.get("/api/study/network?lang=ja")).json()
    assert [n["item_id"] for n in ja_res["nodes"]] == [ja_words[0].id]
    assert ja_res["lang"] == "ja"
    assert ja_res["counts"] == {"en": 2, "ja": 1}


async def test_network_endpoint_lang_defaults_to_learning_langs(client, db_session):
    """lang 생략 시 settings.learning_langs[0] (my-phrases.md 와 동일한 _resolve_lang)."""
    user = await login(client, db_session)
    from app.models import UserSettings

    # upsert_google_user 가 로그인 시 기본 UserSettings 를 이미 만들어 둔다 —
    # 새 행을 add 하면 UNIQUE(user_id) 충돌이라 기존 행을 조회해 갱신한다.
    settings = await db_session.get(UserSettings, user.id)
    settings.learning_langs = ["ja"]
    await db_session.commit()

    ja_words = await seed_items(db_session, count=1, lang="ja")
    en_words = await seed_items(db_session, count=1, lang="en")
    for item in [*ja_words, *en_words]:
        await client.post("/api/cards", json={"item_id": item.id})

    res = (await client.get("/api/study/network")).json()
    assert res["lang"] == "ja"
    assert [n["item_id"] for n in res["nodes"]] == [ja_words[0].id]


async def test_network_endpoint_invalid_lang_rejected(client, db_session):
    await login(client, db_session)
    res = await client.get("/api/study/network?lang=fr")
    assert res.status_code == 422
