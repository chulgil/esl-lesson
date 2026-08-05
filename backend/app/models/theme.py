"""테마 엔타이틀먼트 — 제한 테마 보유권 (docs/specs/theme-mall.md)."""

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin


class ThemeSetting(Base):
    """테마별 접근 정책 오버라이드. 행 없음 = 코드 카탈로그 기본값.

    백오피스에서 무료/제한 전환 시 upsert — 카탈로그(THEME_ACCESS)는
    기본값이자 유효 키 목록으로만 남는다 (docs/specs/theme-mall.md)."""

    __tablename__ = "theme_settings"

    theme_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    access: Mapped[str] = mapped_column(String(16))  # "free" | "restricted"
    # XP 상점 가격 — NULL = 미판매. 업적 보상 규칙이 있는 테마는 가격 설정
    # 자체를 거부한다 (이벤트/업적 전용 — 2026-08-05 사용자 결정)
    price_xp: Mapped[int | None] = mapped_column(Integer)


class ThemeRewardRule(Base, PkMixin, CreatedAtMixin):
    """업적 달성 → 테마 지급 매핑. 백오피스에서 관리 (docs/specs/theme-mall.md).

    규칙 삭제/변경은 이후 지급에만 영향 — 이미 지급된 theme_grants 는 유지된다
    (달성 스펙이 바뀌어도 보유 보장 + note 로 지급 사유 이력)."""

    __tablename__ = "theme_reward_rules"
    __table_args__ = (
        UniqueConstraint("achievement_key", "theme_key", name="uq_theme_reward_rules_pair"),
    )

    achievement_key: Mapped[str] = mapped_column(String(64))
    theme_key: Mapped[str] = mapped_column(String(32))


class ThemeGrant(Base, PkMixin, CreatedAtMixin):
    """유저별 제한 테마 보유권. 행 존재 = 사용 가능 (단순 소유 모델).

    유료 판매로 확장돼도 이 테이블이 '보유' 의 단일 근거 — 결제 이력은
    별도 purchases 테이블로 분리 예정 (PG 결정 후, docs/specs/theme-mall.md)."""

    __tablename__ = "theme_grants"
    __table_args__ = (UniqueConstraint("user_id", "theme_key", name="uq_theme_grants_user_theme"),)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    theme_key: Mapped[str] = mapped_column(String(32))
    # 지급 사유 (이벤트명 등) — 백오피스 감사용
    note: Mapped[str | None] = mapped_column(Text)
    # 지급한 관리자. 시드 지급(마이그레이션)은 null. 관리자 탈퇴 시에도
    # 지급 이력은 남겨야 하므로 SET NULL — 참조만 비운다
    granted_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
