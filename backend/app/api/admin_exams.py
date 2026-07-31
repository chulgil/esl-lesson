"""백오피스 시험지 — 생성/재생성·회차 목록 (docs/specs/library-exam.md)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.security import require_admin
from app.models import Content, Exam, ExamAttempt
from app.models.user import User
from app.services.exams import NotEnoughItemsError, create_exam

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/contents/{content_id}/exam")
async def generate_exam(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    """생성/재생성 — 기존 active -> archived, 새 회차 active."""
    content = await db.get(Content, content_id)
    if content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    try:
        exam = await create_exam(db, content_id, admin.id)
    except NotEnoughItemsError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "not_enough_items") from None
    await db.commit()
    return {"exam_id": exam.id, "round": exam.round, "question_count": exam.question_count}


@router.get("/contents/{content_id}/exams")
async def list_exams(content_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """회차 목록 + 문항 미리보기 (검수용 — 정답 포함)."""
    exams = (
        (
            await db.execute(
                select(Exam)
                .where(Exam.content_id == content_id)
                .options(selectinload(Exam.questions))
                .order_by(Exam.round.desc())
            )
        )
        .scalars()
        .all()
    )
    submit_counts = dict(
        (
            await db.execute(
                select(ExamAttempt.exam_id, func.count(ExamAttempt.id))
                .where(
                    ExamAttempt.exam_id.in_([e.id for e in exams] or [0]),
                    ExamAttempt.submitted_at.is_not(None),
                )
                .group_by(ExamAttempt.exam_id)
            )
        ).all()
    )
    return {
        "items": [
            {
                "exam_id": e.id,
                "round": e.round,
                "status": e.status,
                "question_count": e.question_count,
                "submitted_count": submit_counts.get(e.id, 0),
                "created_at": e.created_at,
                "questions": [
                    {
                        "seq": q.seq,
                        "quiz_mode": q.payload.get("quiz_mode"),
                        "prompt": q.payload.get("prompt"),
                        "prompt_ko": q.payload.get("prompt_ko"),
                        "choices": q.payload.get("choices", []),
                        "answer_index": q.payload.get("answer_index"),
                        "en_text": q.payload.get("en_text"),
                        "ko_text": q.payload.get("ko_text"),
                    }
                    for q in e.questions
                ],
            }
            for e in exams
        ]
    }
