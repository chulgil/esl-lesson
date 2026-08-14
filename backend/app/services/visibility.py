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


def lang_item_clause(lang: str):
    """LearningItem 이 lang 콘텐츠(Content.lang==lang)에 속하는지 필터.

    게임 풀 언어 분리 (docs/specs/chat-language-rooms.md §게임 언어 분리) — 문장·단어
    게임의 출제 풀이 사용자가 고른 게임 언어의 콘텐츠에서만 뽑히도록 강제한다.

    다른 절과 동일하게 상관(exists) 대신 IN 서브쿼리를 쓴다 — 이 필터를 쓰는
    호출부가 이미 ItemOccurrence 를 join 하는 경우가 많아, exists() 상관 서브쿼리는
    SQLAlchemy 가 겹치는 FROM 을 자동 상관 제거해 "no FROM clauses" 오류를 낸다.
    """
    return LearningItem.id.in_(
        select(ItemOccurrence.item_id)
        .join(Content, Content.id == ItemOccurrence.content_id)
        .where(Content.lang == lang)
    )
