"""학습 항목 가시성 규칙 (docs/specs/content-governance.md).

노출 = (a) 내가 담은 공용 콘텐츠의 approved 항목
     ∪ (b) 내가 담은 개인 콘텐츠의 항목 (rejected 제외)

2026-07-27 변경: 공용도 "담기(구독)" 를 전제로 한다. 이전에는 공용 콘텐츠가
전 회원에게 자동 편입됐다. 학습 큐·복습·게임·푸시가 모두 visible_item_clause
를 경유하므로 이 함수 하나가 규칙의 단일 지점이다.
"""

from sqlalchemy import and_, or_, select

from app.models import Content, ContentSubscription, ItemOccurrence, LearningItem


def subscribed_public_item_ids(user_id: int):
    """내가 담은 공용 콘텐츠의 항목."""
    return (
        select(ItemOccurrence.item_id)
        .join(Content, Content.id == ItemOccurrence.content_id)
        .where(
            Content.visibility == "public",
            Content.id.in_(subscribed_content_ids(user_id)),
        )
    )


def subscribed_content_ids(user_id: int):
    return select(ContentSubscription.content_id).where(ContentSubscription.user_id == user_id)


def my_private_item_ids(user_id: int):
    """내가 구독한 개인 콘텐츠의 항목 (같은 영상을 여러 사용자가 공유)."""
    return (
        select(ItemOccurrence.item_id)
        .join(Content, Content.id == ItemOccurrence.content_id)
        .where(
            Content.visibility == "private",
            Content.id.in_(subscribed_content_ids(user_id)),
        )
    )


def visible_item_clause(user_id: int):
    """LearningItem 쿼리에 붙이는 가시성 필터."""
    return or_(
        and_(
            LearningItem.review_status == "approved",
            LearningItem.id.in_(subscribed_public_item_ids(user_id)),
        ),
        and_(
            LearningItem.review_status != "rejected",
            LearningItem.id.in_(my_private_item_ids(user_id)),
        ),
    )
