"""상점 아이템 보유 원장 — 마스코트·악세사리 (docs/specs/mascot-shop.md).

테마몰 엔타이틀먼트 패턴: 행 존재 = 보유. 카탈로그·가격은 코드가 단일 근거
(services/mascots.py), 소비는 xp_spends 원장 (reason = item_key).
"""

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, UniqueConstraint
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


class ItemSetting(Base):
    """상점 아이템 판매 정책 — 백오피스 오버라이드 (테마 몰 ThemeSetting 대응).

    행 없음 = 카탈로그 기본가·XP 판매. price_xp NULL = 기본가 유지,
    sale="event" = XP 구매 차단(이벤트 지급 전용).
    """

    __tablename__ = "item_settings"

    item_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    price_xp: Mapped[int | None] = mapped_column(Integer)
    sale: Mapped[str] = mapped_column(String(16), default="xp", server_default="xp")


class Purchase(Base, PkMixin, CreatedAtMixin):
    """구매 이력 원장 — 사용자별 무엇을 언제 어떤 결제수단으로 얼마에 샀는가.

    xp_spends 가 지갑(가용 XP 차감) 원장이라면 purchases 는 구매 내역 원장.
    method 는 현금·카드 결제 도입 대비 — 현재는 "xp" 만 기록된다.
    """

    __tablename__ = "purchases"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # "theme:ocean" | "mascot:henyang" | "outfit:ribbon" | "saver:streak"
    item_key: Mapped[str] = mapped_column(String(64))
    # "xp" | "cash" | "card" — 결제수단
    method: Mapped[str] = mapped_column(String(16), default="xp", server_default="xp")
    # 결제 금액 — XP 결제면 XP, 통화 결제면 통화 최소단위
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="XP", server_default="XP")
