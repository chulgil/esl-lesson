"""상점 아이템 보유 원장 — 마스코트·악세사리 (docs/specs/mascot-shop.md).

테마몰 엔타이틀먼트 패턴: 행 존재 = 보유. 카탈로그·가격은 코드가 단일 근거
(services/mascots.py), 소비는 xp_spends 원장 (reason = item_key).
"""

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin


class ItemGrant(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "item_grants"
    __table_args__ = (UniqueConstraint("user_id", "item_key", name="uq_item_grants_user_key"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # "mascot:henyang" | "outfit:ribbon" — services/mascots.py 카탈로그의 키
    item_key: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
