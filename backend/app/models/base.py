from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# sqlite(테스트)는 INTEGER PK만 autoincrement 지원
BigIntPk = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    # datetime 은 전부 timestamptz (UTC 저장 규칙 — docs/architecture/database.md)
    type_annotation_map = {datetime: DateTime(timezone=True)}


class PkMixin:
    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
