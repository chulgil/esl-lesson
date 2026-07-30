"""SQLAlchemy 모델. 스키마 정의: docs/architecture/database.md"""

from app.models.base import Base
from app.models.card import ReviewCard, ReviewLog
from app.models.chat import ChatMessage, ChatRead, Conversation
from app.models.content import (
    Content,
    ContentPermission,
    ContentSubscription,
    ExtractionJob,
    TranscriptSegment,
)
from app.models.friend import Friendship
from app.models.game import (
    DailyPuzzlePlay,
    DictationRace,
    GameMatch,
    QuizRoyaleMatch,
    QuizRoyalePlayer,
    ScrambleRace,
    TypingRace,
)
from app.models.item import ItemOccurrence, LearningItem, WordInsight
from app.models.notification import Notification
from app.models.push import PushSubscription
from app.models.retention import QuestCompletion, StreakSaverUse
from app.models.theme import ThemeGrant, ThemeRewardRule, ThemeSetting
from app.models.user import User, UserSettings

__all__ = [
    "Base",
    "ChatMessage",
    "ChatRead",
    "Conversation",
    "DailyPuzzlePlay",
    "DictationRace",
    "Content",
    "ContentPermission",
    "ContentSubscription",
    "ExtractionJob",
    "Friendship",
    "GameMatch",
    "QuizRoyaleMatch",
    "QuizRoyalePlayer",
    "ScrambleRace",
    "TypingRace",
    "ItemOccurrence",
    "LearningItem",
    "Notification",
    "PushSubscription",
    "QuestCompletion",
    "ReviewCard",
    "ReviewLog",
    "StreakSaverUse",
    "ThemeGrant",
    "ThemeRewardRule",
    "ThemeSetting",
    "TranscriptSegment",
    "User",
    "UserSettings",
    "WordInsight",
]
