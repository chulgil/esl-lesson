"""라이브러리 목록의 실시간 파생값 — 콘텐츠 난이도 + 내가 아는 표현 비율.

담기 전에 "내 수준의 영상인가"를 알려주는 값이라 저장 컬럼 없이 조회 시 계산한다
(docs/specs/content-governance.md). 목록 전체를 한 번에 집계해 콘텐츠당 N+1 을 막는다.
"""

from collections.abc import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ItemOccurrence, LearningItem, ReviewCard, TranscriptSegment

# DB 의 difficulty_hint 는 basic/intermediate/advanced, 노출 라벨은 업적 티어와 같은
# beginner/intermediate/advanced 를 쓴다 (프론트가 초급/중급/고급으로 표기)
HINT_SCORE = {"basic": 0.0, "intermediate": 1.0, "advanced": 2.0}
ADVANCED_MIN = 1.35
BEGINNER_MAX = 0.6
# 문장 길이 보정 (2026-08-10 프로드 실측 보정 — P0-2 보류분 착수):
# 추출 힌트에 basic 이 사실상 없어(전 항목 0건) 힌트 평균이 [1.0, 1.4] 로 압축되고
# BEGINNER_MAX 는 절대 발동하지 않는다 — Easy English 류 초급 회화가 중급으로 오분류.
# 초급 회화(문장당 3~7단어)와 강연(15~18단어)이 문장 길이로 깨끗이 갈리는 것을 실측.
SENTENCE_WPS_BEGINNER_MAX = 8.0  # 문장당 단어 수 — 이하 + 낮은 힌트 평균 = 초급
SENTENCE_WPS_ADVANCED_MIN = 17.0  # 이상(긴 원어민 발화) = 고급
HINT_BEGINNER_MAX_WITH_WPS = 1.12  # 문장 길이 신호가 있을 때의 초급 힌트 상한


def difficulty_label(
    hint_counts: dict[str, int], words_per_sentence: float | None = None
) -> str | None:
    """항목 난이도 분포의 가중 평균 (+ 문장 길이 신호) -> 라벨. 항목이 없으면 None.

    words_per_sentence 가 없으면(수기 등 세그먼트 없음) 기존 힌트-단독 기준 유지.
    """
    total = sum(hint_counts.values())
    if total == 0:
        return None
    score = sum(HINT_SCORE.get(hint, 1.0) * n for hint, n in hint_counts.items()) / total
    if words_per_sentence is not None:
        if score >= ADVANCED_MIN or words_per_sentence >= SENTENCE_WPS_ADVANCED_MIN:
            return "advanced"
        if score <= HINT_BEGINNER_MAX_WITH_WPS and words_per_sentence <= SENTENCE_WPS_BEGINNER_MAX:
            return "beginner"
        return "intermediate"
    if score >= ADVANCED_MIN:
        return "advanced"
    if score <= BEGINNER_MAX:
        return "beginner"
    return "intermediate"


async def _wps_by_content(db: AsyncSession, content_ids: Sequence[int]) -> dict[int, float]:
    """콘텐츠별 평균 문장 단어 수 — 공백 수 + 1 근사 (Postgres/SQLite 공용)."""
    text = func.trim(TranscriptSegment.en_text)
    words = func.length(text) - func.length(func.replace(text, " ", "")) + 1
    rows = (
        await db.execute(
            select(TranscriptSegment.content_id, func.avg(words))
            .where(
                TranscriptSegment.content_id.in_(content_ids),
                func.length(func.trim(TranscriptSegment.en_text)) > 0,
            )
            .group_by(TranscriptSegment.content_id)
        )
    ).all()
    return {content_id: float(avg) for content_id, avg in rows if avg is not None}


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
    wps = await _wps_by_content(db, content_ids)
    return {
        content_id: difficulty_label(counts.get(content_id, {}), wps.get(content_id))
        for content_id in content_ids
    }


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
