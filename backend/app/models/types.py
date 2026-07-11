"""DB 타입 별칭 — 운영은 PostgreSQL 네이티브(JSONB/ARRAY), 테스트(sqlite)는 JSON 폴백."""

from sqlalchemy import JSON, Integer
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

JsonDict = JSON().with_variant(JSONB(), "postgresql")
IntList = JSON().with_variant(ARRAY(Integer()), "postgresql")
