"""단어 임베딩 — Voyage API + pgvector halfvec (docs/proposal/word-insight.md P2).

- 저장/검색은 postgres 전용 raw SQL (halfvec 1024 + HNSW cosine).
  sqlite(테스트)나 키 미설정 환경에서는 전체 기능이 조용히 스킵된다 (폴백: 랜덤 선지).
- ORM 모델을 두지 않는 이유: pgvector 타입은 sqlite 폴백이 없어 테스트 스키마가 깨짐.
"""

import logging

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

logger = logging.getLogger(__name__)

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
EMBEDDING_DIM = 1024
EMBED_BATCH_SIZE = 128


def enabled(db: AsyncSession) -> bool:
    """키가 있고 postgres 일 때만 동작 (그 외 조용히 스킵)."""
    if not get_settings().voyage_embedding_secret:
        return False
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


async def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Voyage 임베딩 호출. 응답의 index 로 입력 순서를 복원한다."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            VOYAGE_URL,
            headers={"Authorization": f"Bearer {settings.voyage_embedding_secret}"},
            json={
                "model": settings.voyage_embedding_model,
                "input": texts,
                "input_type": input_type,
                "output_dimension": EMBEDDING_DIM,
            },
        )
        res.raise_for_status()
        data = res.json()["data"]
    ordered = sorted(data, key=lambda d: d["index"])
    return [d["embedding"] for d in ordered]


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


async def upsert_embeddings(db: AsyncSession, pairs: list[tuple[int, list[float]]]) -> None:
    for item_id, vec in pairs:
        await db.execute(
            text(
                "INSERT INTO item_embeddings (item_id, embedding) "
                "VALUES (:id, CAST(:emb AS halfvec(1024))) "
                "ON CONFLICT (item_id) DO UPDATE SET embedding = EXCLUDED.embedding"
            ),
            {"id": item_id, "emb": _vec_literal(vec)},
        )


async def missing_item_ids(db: AsyncSession, item_ids: list[int]) -> list[int]:
    """임베딩이 아직 없는 항목만 추린다."""
    if not item_ids:
        return []
    rows = (
        await db.execute(
            text("SELECT item_id FROM item_embeddings WHERE item_id = ANY(:ids)"),
            {"ids": item_ids},
        )
    ).scalars()
    have = set(rows)
    return [i for i in item_ids if i not in have]


async def similar_items(db: AsyncSession, item_id: int, k: int = 5) -> list[dict]:
    """같은 타입(word/idiom) 승인 항목 중 임베딩 최근접 k개.

    쿼리 벡터를 상수로 넣어 HNSW 인덱스를 태운다 (0.8 iterative scan 으로
    타입/승인 필터가 걸려도 후보 고갈 없음).
    """
    row = (
        await db.execute(
            text("SELECT embedding::text FROM item_embeddings WHERE item_id = :id"),
            {"id": item_id},
        )
    ).scalar_one_or_none()
    if row is None:
        return []
    rows = await db.execute(
        text(
            "SELECT li.id, li.en_text, li.ko_text, "
            "       e.embedding <=> CAST(:q AS halfvec(1024)) AS distance "
            "FROM item_embeddings e "
            "JOIN learning_items li ON li.id = e.item_id "
            "WHERE e.item_id != :id AND li.review_status = 'approved' "
            "  AND li.item_type IN ('word', 'idiom') "
            "ORDER BY distance "
            "LIMIT :k"
        ),
        {"q": row, "id": item_id, "k": k},
    )
    return [
        {"id": r.id, "en_text": r.en_text, "ko_text": r.ko_text, "distance": float(r.distance)}
        for r in rows
    ]


async def drop_item_embedding(db: AsyncSession, item_id: int) -> None:
    """항목 텍스트 정정 시 stale 벡터 제거 — 다음 파이프라인 embed 단계가
    missing 으로 보고 자연 재생성한다 (2026-08-13 flow 감사 F3)."""
    if not enabled(db):
        return
    await db.execute(text("DELETE FROM item_embeddings WHERE item_id = :id"), {"id": item_id})


async def embed_items(db: AsyncSession, items: list) -> int:
    """(id, en_text) 를 가진 항목들을 배치 임베딩 후 저장. 저장 건수 반환."""
    if not items or not enabled(db):
        return 0
    total = 0
    for i in range(0, len(items), EMBED_BATCH_SIZE):
        batch = items[i : i + EMBED_BATCH_SIZE]
        vectors = await embed_texts([it.en_text for it in batch])
        await upsert_embeddings(db, [(it.id, v) for it, v in zip(batch, vectors, strict=True)])
        total += len(batch)
    return total
