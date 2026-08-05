"""콘텐츠 루틴 여정 API — 6단계 체크 + 한 문장 요약 (ted-routine-2026-08.md P1).

구독한 콘텐츠만 — 비구독은 존재 여부도 흘리지 않는 404 (my_contents 계약 재사용).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.my_contents import get_subscribed_content
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import ContentRoutineProgress, ContentSummary, User
from app.models.routine import ROUTINE_STEP_COUNT
from app.services import routine as routine_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contents", tags=["routine"])

SUMMARY_STEP = ROUTINE_STEP_COUNT  # 마지막 단계 = 한 문장 요약


async def _done_steps(db: AsyncSession, user_id: int, content_id: int) -> set[int]:
    return set(
        (
            await db.execute(
                select(ContentRoutineProgress.step).where(
                    ContentRoutineProgress.user_id == user_id,
                    ContentRoutineProgress.content_id == content_id,
                )
            )
        ).scalars()
    )


async def _latest_summary(db: AsyncSession, user_id: int, content_id: int) -> dict | None:
    row = (
        await db.execute(
            select(ContentSummary)
            .where(ContentSummary.user_id == user_id, ContentSummary.content_id == content_id)
            .order_by(ContentSummary.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return {"text": row.text, "feedback": row.feedback, "created_at": row.created_at}


def _routine_payload(done: set[int], summary: dict | None) -> dict:
    return {
        "steps": [
            {"step": step, "done": step in done} for step in range(1, ROUTINE_STEP_COUNT + 1)
        ],
        "completed": len(done) == ROUTINE_STEP_COUNT,
        "summary": summary,
    }


@router.get("/{content_id}/routine")
async def get_routine(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    content = await get_subscribed_content(db, content_id, user)
    done = await _done_steps(db, user.id, content.id)
    summary = await _latest_summary(db, user.id, content.id)
    return _routine_payload(done, summary)


class StepBody(BaseModel):
    done: bool


@router.post("/{content_id}/routine/{step}")
async def set_step(
    content_id: int,
    body: StepBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    step: Annotated[int, Path(ge=1, le=ROUTINE_STEP_COUNT)],
) -> dict:
    """단계 체크/해제 — 멱등 (중복 체크는 기존 행 유지)."""
    content = await get_subscribed_content(db, content_id, user)
    # rollback 이 ORM 객체(user/content)를 만료시켜도 안전하게 — 값으로 캡처
    uid, cid = user.id, content.id
    if body.done:
        db.add(ContentRoutineProgress(user_id=uid, content_id=cid, step=step))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()  # 이미 체크됨 — 멱등
    else:
        await db.execute(
            delete(ContentRoutineProgress).where(
                ContentRoutineProgress.user_id == uid,
                ContentRoutineProgress.content_id == cid,
                ContentRoutineProgress.step == step,
            )
        )
        await db.commit()
    done = await _done_steps(db, uid, cid)
    return {"step": step, "done": step in done, "completed": len(done) == ROUTINE_STEP_COUNT}


class SummaryBody(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@router.post("/{content_id}/summary")
async def submit_summary(
    content_id: int,
    body: SummaryBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """한 문장 요약 제출 — 액티브 인출. LLM 피드백 실패해도 저장은 진행."""
    content = await get_subscribed_content(db, content_id, user)
    uid, cid = user.id, content.id  # rollback 대비 값 캡처
    feedback: str | None = None
    try:
        feedback = await routine_service.summary_feedback(db, content, body.text)
    except Exception:
        logger.exception("summary feedback failed content=%s", cid)

    db.add(ContentSummary(user_id=uid, content_id=cid, text=body.text, feedback=feedback))
    # 요약 제출 = 마지막 단계 자동 체크
    done = await _done_steps(db, uid, cid)
    if SUMMARY_STEP not in done:
        db.add(ContentRoutineProgress(user_id=uid, content_id=cid, step=SUMMARY_STEP))
    try:
        await db.commit()
    except IntegrityError:
        # 6단계 동시 체크 경합 — 요약 저장만 다시
        await db.rollback()
        db.add(ContentSummary(user_id=uid, content_id=cid, text=body.text, feedback=feedback))
        await db.commit()
    return {"feedback": feedback}
