from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin
from app.models.types import IntList, StrList

ROLE_LEARNER = "learner"
ROLE_ADMIN = "admin"


class User(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin','learner')", name="ck_users_role"),)

    google_sub: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    # 다른 사용자에게 보이는 유일한 이름 — 구글 이름(name)은 본인 외 비노출
    nickname: Mapped[str] = mapped_column(Text, default="", server_default="")
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
    # 오늘의 목표 — 밀린 양과 무관한 달성 가능 소량 (포기 방지 기획 2026-07-15,
    # 2026-08-05 프리셋 상향: 가볍게 15/기본 30/열심히 50)
    daily_goal: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    desired_retention: Mapped[float] = mapped_column(default=0.9, server_default="0.9")
    # 힌트까지 대기 시간(초), 0=끄기 (docs/specs/learning.md 힌트 타이머)
    hint_delay_seconds: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    # 학습 난이도: 1 입문(단어) 2 초급(+숙어) 3 중급(+패턴) 4 고급(+문장 타이핑)
    # (docs/specs/learning.md 레벨별 학습 설계 — 저레벨은 선택식, 문장은 고급)
    study_level: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    levels_enabled: Mapped[list[int]] = mapped_column(IntList, default=lambda: [1, 2])
    # 복습 리마인더 시각(KST, 5-23시) — 사용자의 생활 리듬에 맞춘 실행 의도
    # (user-journey-motivation-2026-08.md P1, docs/specs/push-reminder.md)
    reminder_hour: Mapped[int] = mapped_column(Integer, default=20, server_default="20")
    # 책갈피(스트릭 보호) 보유 — 주 1회 목표 달성 시 지급, 최대 2 (retention-plan.md)
    streak_savers: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # 마지막 지급 ISO 주 ("2026-W29") — 주 1회 지급 가드
    saver_award_week: Mapped[str | None] = mapped_column(Text)
    # 주간 성적표를 보낸 대상 주 ISO ("2026-W31" = 그 성적표가 다룬 지난주)
    # — 월요일 1회 발송 가드 (docs/specs/weekly-report.md)
    weekly_report_week: Mapped[str | None] = mapped_column(Text)
    # 활성 마스코트 — 좌하단에 상시 표시되는 캐릭터, NULL=끔 (docs/specs/mascot-shop.md)
    mascot_key: Mapped[str | None] = mapped_column(Text)
    # 대표 업적 키 — 대전·리더보드 프로필 밑 칭호 (mascot-shop.md 플레이어 배지)
    featured_achievement: Mapped[str | None] = mapped_column(Text)
    # 다국어 학습 (docs/specs/chat-translation.md) — 주언어(모국어)·학습언어(복수)
    primary_lang: Mapped[str] = mapped_column(Text, default="ko", server_default="ko")
    learning_langs: Mapped[list[str]] = mapped_column(StrList, default=lambda: ["en"])
    # 채팅 자동번역 ON/OFF — 메시지 밑 번역 줄 + 스피커 (기본 끔, 설정에서 켬)
    chat_translate: Mapped[bool] = mapped_column(default=False, server_default="false")
