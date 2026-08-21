"""사용 이벤트 수집 — 파이어-앤-포겟 최소 로깅 (P1-D, docs/specs/usage-events.md).

클라이언트 관측용이라 실패해도 UX 에 영향이 없어야 한다 — 프론트는 응답을
기다리지 않고, 서버는 화이트리스트 밖 kind 만 거른다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import UsageEvent
from app.models.user import User

router = APIRouter(prefix="/events", tags=["events"])

# 관측 대상 표면 (effectiveness-audit 4차 P1-D) — 새 표면은 여기에 추가
# speech_check: 발음 확인 시도 (pronunciation-scoring V1) — speak_3 미션 집계 재료
KINDS = frozenset(
    {"record_compare", "method_view", "weekly_report_view", "review_add", "speech_check"}
)
META_MAX_KEYS = 8
META_MAX_VALUE_LEN = 100


class EventIn(BaseModel):
    kind: str
    meta: dict[str, str] = {}

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, v: str) -> str:
        if v not in KINDS:
            raise ValueError("unknown kind")
        return v

    @field_validator("meta")
    @classmethod
    def _small_meta(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > META_MAX_KEYS:
            raise ValueError("meta too large")
        if any(len(val) > META_MAX_VALUE_LEN for val in v.values()):
            raise ValueError("meta value too long")
        return v


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def log_event(
    body: EventIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    db.add(UsageEvent(user_id=user.id, kind=body.kind, meta=body.meta))
    await db.commit()
