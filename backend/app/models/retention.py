"""리텐션 장치 — 책갈피(스트릭 보호)·오늘의 미션 원장 (docs/proposal/retention-plan.md)."""

from datetime import date as date_type

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin


class StreakSaverUse(Base, PkMixin, CreatedAtMixin):
    """책갈피 소모 원장 — 놓친 날짜에 자동으로 끼워져 연속 학습을 지킨다.

    행의 존재 자체가 '그 날은 책갈피로 보호됨' — 스트릭 일수에는 +0,
    리셋만 방지 (공짜 진행 없음). 잔디 표기에도 쓰인다.
    """

    __tablename__ = "streak_saver_uses"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_saver_user_day"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date_type] = mapped_column(Date)


class QuestCompletion(Base, PkMixin, CreatedAtMixin):
    """오늘의 미션 완료 원장 — XP 보너스의 근거.

    XP 는 원본 로그 실시간 집계가 원칙이나, 미션 완료는 '그 순간의 로테이션'에
    의존하는 상태라 원장에 적립한다 (DB 감사 원칙: 집계 필요 상태는 정규 테이블).
    """

    __tablename__ = "quest_completions"
    __table_args__ = (
        UniqueConstraint("user_id", "day", "quest_key", name="uq_quest_user_day_key"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date_type] = mapped_column(Date)
    quest_key: Mapped[str] = mapped_column(Text)
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class XpSpend(Base, PkMixin, CreatedAtMixin):
    """XP 소비 원장 — 테마 구매 등 상점 지출 (docs/specs/theme-mall.md XP 상점).

    적립은 로그 실시간 집계 원칙 그대로 두고(레벨은 누적 XP 기준 불변),
    소비만 원장에 남긴다 — 가용 XP = 누적 XP - 소비 합.
    """

    __tablename__ = "xp_spends"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[int] = mapped_column(Integer)
    # 지출 사유 — "theme:ocean" 형식 (감사·중복 방지 조회용)
    reason: Mapped[str] = mapped_column(Text)
