"""어휘망 그래프 — 임베딩 근접 관계로 내 어휘를 연결 (docs/proposal/word-insight.md P3).

- 이웃 검색은 postgres 전용 raw SQL (embeddings.py 와 동일한 이유로 ORM 미사용).
- 그래프 조립(build_network)은 순수 함수 — sqlite 테스트에서 단독 검증한다.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

NEIGHBOR_K = 6
# voyage-3.5-lite 코사인 거리 기준 — 실데이터 관측 후 조정 여지 있음
EDGE_MAX_DISTANCE = 0.55
MAX_EDGES_PER_NODE = 4
MAX_SUGGESTIONS = 12


async def neighbor_rows(db: AsyncSession, item_ids: list[int], k: int = NEIGHBOR_K) -> list[dict]:
    """내 항목 각각의 임베딩 최근접 k개 (word/idiom, 비거절).

    LATERAL 안의 ORDER BY+LIMIT 이 행별 HNSW 스캔을 태운다.
    dst 는 승인 항목 또는 내 항목(개인 콘텐츠의 pending 포함) 만 허용.
    """
    rows = await db.execute(
        text(
            "SELECT a.item_id AS src, nb.id AS dst, nb.en_text, nb.ko_text, nb.distance "
            "FROM item_embeddings a "
            "JOIN LATERAL ("
            "  SELECT li.id, li.en_text, li.ko_text, "
            "         e.embedding <=> a.embedding AS distance "
            "  FROM item_embeddings e "
            "  JOIN learning_items li ON li.id = e.item_id "
            "  WHERE e.item_id != a.item_id "
            "    AND li.item_type IN ('word', 'idiom') "
            "    AND (li.review_status = 'approved' OR li.id = ANY(:ids)) "
            "  ORDER BY e.embedding <=> a.embedding "
            "  LIMIT :k"
            ") nb ON true "
            "WHERE a.item_id = ANY(:ids)"
        ),
        {"ids": item_ids, "k": k},
    )
    return [
        {
            "src": r.src,
            "dst": r.dst,
            "en_text": r.en_text,
            "ko_text": r.ko_text,
            "distance": float(r.distance),
        }
        for r in rows
    ]


def build_network(
    my_ids: set[int],
    rows: list[dict],
    *,
    edge_max_distance: float = EDGE_MAX_DISTANCE,
    max_edges_per_node: int = MAX_EDGES_PER_NODE,
    max_suggestions: int = MAX_SUGGESTIONS,
) -> tuple[list[dict], list[dict]]:
    """이웃 행을 (내 항목 간 엣지, 덱 밖 추천) 으로 조립한다.

    - 엣지: 양방향 중복 쌍은 최소 거리 하나로, 가까운 순으로 노드당 상한 적용
    - 추천: dst 별 최소 거리로 집계, 가까운 순 정렬 + 상한 (가시성 필터는 호출부)
    """
    pair_best: dict[tuple[int, int], float] = {}
    candidates: dict[int, dict] = {}
    for row in rows:
        src, dst, dist = row["src"], row["dst"], float(row["distance"])
        if src not in my_ids or dist > edge_max_distance:
            continue
        if dst in my_ids:
            key = (min(src, dst), max(src, dst))
            if key not in pair_best or dist < pair_best[key]:
                pair_best[key] = dist
        else:
            cur = candidates.get(dst)
            if cur is None or dist < cur["distance"]:
                candidates[dst] = {
                    "item_id": dst,
                    "en": row["en_text"],
                    "ko": row["ko_text"],
                    "distance": dist,
                    "near_item_id": src,
                }

    degree: dict[int, int] = {}
    edges: list[dict] = []
    for (a, b), dist in sorted(pair_best.items(), key=lambda kv: kv[1]):
        if degree.get(a, 0) >= max_edges_per_node or degree.get(b, 0) >= max_edges_per_node:
            continue
        edges.append({"source": a, "target": b, "distance": dist})
        degree[a] = degree.get(a, 0) + 1
        degree[b] = degree.get(b, 0) + 1

    suggestions = sorted(candidates.values(), key=lambda s: s["distance"])[:max_suggestions]
    return edges, suggestions
