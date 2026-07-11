"""학습 항목 가시성 규칙 (docs/specs/content-pipeline.md 콘텐츠 가시성).

노출 = (a) 공용 콘텐츠 출처가 있는 approved 항목
     ∪ (b) 내 개인 콘텐츠 출처가 있는 항목 (rejected 제외 — 개인 등록분 자동 편입)
"""

from sqlalchemy import and_, or_, select

from app.models import Content, ItemOccurrence, LearningItem


def public_item_ids():
    return (
        select(ItemOccurrence.item_id)
        .join(Content, Content.id == ItemOccurrence.content_id)
        .where(Content.visibility == "public")
    )


def my_private_item_ids(user_id: int):
    return (
        select(ItemOccurrence.item_id)
        .join(Content, Content.id == ItemOccurrence.content_id)
        .where(Content.visibility == "private", Content.created_by == user_id)
    )


def visible_item_clause(user_id: int):
    """LearningItem 쿼리에 붙이는 가시성 필터."""
    return or_(
        and_(
            LearningItem.review_status == "approved",
            LearningItem.id.in_(public_item_ids()),
        ),
        and_(
            LearningItem.review_status != "rejected",
            LearningItem.id.in_(my_private_item_ids(user_id)),
        ),
    )
