"""SQLAlchemy 모델. 스키마 정의: docs/architecture/database.md"""

from app.models.base import Base
from app.models.card import ReviewCard, ReviewLog
from app.models.chat import ChatMessage, ChatRead, Conversation
from app.models.content import (
    Content,
    ContentPermission,
    ContentRequest,
    ContentSubscription,
    ExtractionJob,
    TranscriptSegment,
)
from app.models.exam import Exam, ExamAttempt, ExamQuestion
from app.models.friend import Friendship
from app.models.game import (
    BingoMatch,
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
from app.models.retention import QuestCompletion, StreakSaverUse, XpSpend
from app.models.routine import ContentRoutineProgress, ContentSummary, ListenCheck
from app.models.shop import ItemGrant, ItemSetting, Purchase
from app.models.theme import ThemeGrant, ThemeRewardRule, ThemeSetting
from app.models.translation import ChatTranslation, TranslationUsage
from app.models.tts import TtsAudio
from app.models.usage import UsageEvent
from app.models.user import User, UserSettings

__all__ = [
    "Base",
    "ChatMessage",
    "ChatTranslation",
    "ChatRead",
    "Conversation",
    "DailyPuzzlePlay",
    "DictationRace",
    "Content",
    "ContentPermission",
    "ContentSubscription",
    "Exam",
    "ExamAttempt",
    "ExamQuestion",
    "ExtractionJob",
    "Friendship",
    "GameMatch",
    "QuizRoyaleMatch",
    "QuizRoyalePlayer",
    "BingoMatch",
    "ScrambleRace",
    "TranslationUsage",
    "TypingRace",
    "ItemGrant",
    "ItemOccurrence",
    "ItemSetting",
    "LearningItem",
    "ListenCheck",
    "Notification",
    "Purchase",
    "PushSubscription",
    "QuestCompletion",
    "ContentRequest",
    "ContentRoutineProgress",
    "ContentSummary",
    "ReviewCard",
    "ReviewLog",
    "StreakSaverUse",
    "XpSpend",
    "TtsAudio",
    "UsageEvent",
    "ThemeGrant",
    "ThemeRewardRule",
    "ThemeSetting",
    "TranscriptSegment",
    "User",
    "UserSettings",
    "WordInsight",
]
