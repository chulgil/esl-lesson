from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin
from app.models.types import IntList

ROLE_LEARNER = "learner"
ROLE_ADMIN = "admin"


class User(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin','learner')", name="ck_users_role"),)

    google_sub: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, default=ROLE_LEARNER, server_default=ROLE_LEARNER)
    last_login_at: Mapped[datetime | None]


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    daily_new_limit: Mapped[int] = mapped_column(Integer, default=20, server_default="20")
    daily_review_limit: Mapped[int] = mapped_column(Integer, default=200, server_default="200")
    desired_retention: Mapped[float] = mapped_column(default=0.9, server_default="0.9")
    # 힌트까지 대기 시간(초), 0=끄기 (docs/specs/learning.md 힌트 타이머)
    hint_delay_seconds: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    # 학습 난이도: 1 입문(단어) 2 초급(+숙어) 3 중급(+패턴) 4 고급(+문장 타이핑)
    # (docs/specs/learning.md 레벨별 학습 설계 — 저레벨은 선택식, 문장은 고급)
    study_level: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    levels_enabled: Mapped[list[int]] = mapped_column(
        IntList, default=lambda: [1, 2]
    )
