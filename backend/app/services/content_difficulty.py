"""라이브러리 목록의 실시간 파생값 — 콘텐츠 난이도 + 내가 아는 표현 비율.

담기 전에 "내 수준의 영상인가"를 알려주는 값이라 저장 컬럼 없이 조회 시 계산한다
(docs/specs/content-governance.md). 목록 전체를 한 번에 집계해 콘텐츠당 N+1 을 막는다.
"""

from collections.abc import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ItemOccurrence, LearningItem, ReviewCard

# DB 의 difficulty_hint 는 basic/intermediate/advanced, 노출 라벨은 업적 티어와 같은
# beginner/intermediate/advanced 를 쓴다 (프론트가 초급/중급/고급으로 표기)
HINT_SCORE = {"basic": 0.0, "intermediate": 1.0, "advanced": 2.0}
ADVANCED_MIN = 1.35
BEGINNER_MAX = 0.6


def difficulty_label(hint_counts: dict[str, int]) -> str | None:
    """항목 난이도 분포의 가중 평균 -> 라벨. 항목이 없으면 판단 불가(None)."""
    total = sum(hint_counts.values())
    if total == 0:
        return None
    score = sum(HINT_SCORE.get(hint, 1.0) * n for hint, n in hint_counts.items()) / total
    if score >= ADVANCED_MIN:
        return "advanced"
    if score <= BEGINNER_MAX:
        return "beginner"
    return "intermediate"


async def difficulty_by_content(
    db: AsyncSession, content_ids: Sequence[int]
) -> dict[int, str | None]:
    if not content_ids:
        return {}
    rows = (
        await db.execute(
            select(
                ItemOccurrence.content_id,
                LearningItem.difficulty_hint,
                func.count(func.distinct(ItemOccurrence.item_id)),
            )
            .join(LearningItem, LearningItem.id == ItemOccurrence.item_id)
            .where(ItemOccurrence.content_id.in_(content_ids))
            .group_by(ItemOccurrence.content_id, LearningItem.difficulty_hint)
        )
    ).all()
    counts: dict[int, dict[str, int]] = {}
    for content_id, hint, n in rows:
        counts.setdefault(content_id, {})[hint] = n
    return {content_id: difficulty_label(counts.get(content_id, {})) for content_id in content_ids}


async def known_ratio_by_content(
    db: AsyncSession,
    user_id: int,
    content_ids: Sequence[int],
    item_counts: dict[int, int],
) -> dict[int, int | None]:
    """이미 내 카드가 있는 항목의 비율(0~100). 분모는 목록의 학습 항목 수와 같다."""
    if not content_ids:
        return {}
    known = dict(
        (
            await db.execute(
                select(
                    ItemOccurrence.content_id,
                    func.count(func.distinct(ItemOccurrence.item_id)),
                )
                .join(
                    ReviewCard,
                    and_(
                        ReviewCard.item_id == ItemOccurrence.item_id,
                        ReviewCard.user_id == user_id,
                    ),
                )
                .where(ItemOccurrence.content_id.in_(content_ids))
                .group_by(ItemOccurrence.content_id)
            )
        ).all()
    )
    return {
        content_id: (
            round(known.get(content_id, 0) * 100 / item_counts[content_id])
            if item_counts.get(content_id)
            else None
        )
        for content_id in content_ids
    }
