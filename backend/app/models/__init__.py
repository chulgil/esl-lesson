"""SQLAlchemy 모델. 스키마 정의: docs/architecture/database.md"""

from app.models.base import Base
from app.models.card import ReviewCard, ReviewLog
from app.models.content import Content, ContentSubscription, ExtractionJob, TranscriptSegment
from app.models.game import GameMatch, QuizRoyaleMatch
from app.models.item import ItemOccurrence, LearningItem, WordInsight
from app.models.user import User, UserSettings

__all__ = [
    "Base",
    "Content",
    "ContentSubscription",
    "ExtractionJob",
    "GameMatch",
    "QuizRoyaleMatch",
    "ItemOccurrence",
    "LearningItem",
    "ReviewCard",
    "ReviewLog",
    "TranscriptSegment",
    "User",
    "UserSettings",
    "WordInsight",
]
