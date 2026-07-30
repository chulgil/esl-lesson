"""테마 엔타이틀먼트 — 제한 테마 보유권 (docs/specs/theme-mall.md)."""

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin


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
