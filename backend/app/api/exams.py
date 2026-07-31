"""시험 응시 — 요약·시작·제출 채점·랭킹 (docs/specs/library-exam.md).

채점·순위 판정 전부 서버 — 클라이언트 입력은 answers 배열만 경계 검증한다.
랭킹 = 유저별 best(score DESC, duration ASC, submitted_at ASC) 실시간 집계.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contents import visible_content_clause
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Content, Exam, ExamAttempt, ExamQuestion, User
from app.services.exams import POINTS_PER_QUESTION
from app.services.notifications import notify

router = APIRouter(tags=["exams"])

RANKING_LIMIT = 50

# 시험 XP — 제출 20(게임 참여 동급) + 점수 10점당 1 (만점 +10). stats 와 동일 산식
XP_PER_SUBMIT = 20


def exam_xp(score: int) -> int:
    return XP_PER_SUBMIT + score // 10


def _aware(dt: datetime) -> datetime:
    """sqlite(테스트) 왕복 시 naive 로 돌아온다 — UTC 저장 규칙이라 그대로 부착."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


async def _best_rows(db: AsyncSession, exam_id: int):
    """유저별 best 1행 — 랭킹 순서(score DESC, duration ASC, submitted_at ASC)로 반환."""
    rn = (
        func.row_number()
        .over(
            partition_by=ExamAttempt.user_id,
            order_by=(
                ExamAttempt.score.desc(),
                ExamAttempt.duration_ms.asc(),
                ExamAttempt.submitted_at.asc(),
            ),
        )
        .label("rn")
    )
    inner = (
        select(
            ExamAttempt.user_id,
            ExamAttempt.score,
            ExamAttempt.duration_ms,
            ExamAttempt.submitted_at,
            rn,
        )
        .where(ExamAttempt.exam_id == exam_id, ExamAttempt.submitted_at.is_not(None))
        .subquery()
    )
    return (
        await db.execute(
            select(
                inner.c.user_id,
                inner.c.score,
                inner.c.duration_ms,
                User.nickname,
                User.name,
            )
            .join(User, User.id == inner.c.user_id)
            .where(inner.c.rn == 1)
            .order_by(inner.c.score.desc(), inner.c.duration_ms.asc(), inner.c.submitted_at.asc())
        )
    ).all()


def _display_name(nickname: str, name: str) -> str:
    """nickname 미설정 유저는 name 폴백 (Phase 3 다이어그램 검토 보강)."""
    return nickname or name


@router.get("/exams/open")
async def open_exams(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """열린 시험 목록 — 학습 허브 도전 카드·라이브러리 시험 칩용.

    active 회차만, 최신 생성 순. 응시자 수·내 최고점·현재 1위 이름을 붙여
    "도전할 이유"(경쟁 상태)를 목록에서 바로 보여준다 (2026-07-31 goal).

    시험당 랭킹 1쿼리 — 최신 20개 상한으로 상수 상한 (심층 리뷰 반영).
    가시성: 비공개 콘텐츠의 시험은 구독자에게만 (visible_content_clause)."""
    exams = (
        await db.execute(
            select(Exam, Content.title)
            .join(Content, Content.id == Exam.content_id)
            .where(Exam.status == "active", visible_content_clause(user.id))
            .order_by(Exam.id.desc())
            .limit(20)
        )
    ).all()

    items = []
    for exam, content_title in exams:
        rows = await _best_rows(db, exam.id)
        mine = next((r for r in rows if r.user_id == user.id), None)
        top = rows[0] if rows else None
        items.append(
            {
                "exam_id": exam.id,
                "content_id": exam.content_id,
                "content_title": content_title,
                "round": exam.round,
                "question_count": exam.question_count,
                "attempt_user_count": len(rows),
                "my_best": (
                    {"score": mine.score, "duration_ms": mine.duration_ms} if mine else None
                ),
                "top_name": _display_name(top.nickname, top.name) if top else None,
            }
        )
    return {"items": items}


@router.get("/contents/{content_id}/exam")
async def exam_summary(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """활성 시험 요약 — 시험 없으면 exam_id null (오류 아님, 시나리오 4).

    비공개 콘텐츠는 구독자에게만 (미구독 = 시험 없음과 동일 응답, 존재 비노출).
    active 는 부분 유니크 인덱스가 1개를 보장하지만, 혹시 깨져도 최신 회차로
    자가 복구 (scalar_one 500 방지 — 2026-07-31 심층 리뷰)."""
    exam = (
        (
            await db.execute(
                select(Exam)
                .join(Content, Content.id == Exam.content_id)
                .where(
                    Exam.content_id == content_id,
                    Exam.status == "active",
                    visible_content_clause(user.id),
                )
                .order_by(Exam.round.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if exam is None:
        return {"exam_id": None}
    rows = await _best_rows(db, exam.id)
    mine = next(((idx + 1, row) for idx, row in enumerate(rows) if row.user_id == user.id), None)
    return {
        "exam_id": exam.id,
        "round": exam.round,
        "question_count": exam.question_count,
        # 응시자 수 — 제출 완료 기준 distinct 유저 (유저별 best 1행이므로 행 수 = 유저 수)
        "attempt_count": len(rows),
        "my_best": None
        if mine is None
        else {
            "score": mine[1].score,
            "duration_ms": mine[1].duration_ms,
            "rank": mine[0],
        },
        "top": [
            {
                "nickname": _display_name(row.nickname, row.name),
                "score": row.score,
                "duration_ms": row.duration_ms,
            }
            for row in rows[:3]
        ],
    }


@router.post("/exams/{exam_id}/attempts")
async def start_attempt(
    exam_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """응시 시작 — attempt INSERT(started_at 서버 시각) + 정답 없는 문항 반환.

    비공개 콘텐츠의 시험은 구독자만 (미구독 404 — 존재 비노출, 심층 리뷰 반영)."""
    exam = (
        (
            await db.execute(
                select(Exam)
                .join(Content, Content.id == Exam.content_id)
                .where(Exam.id == exam_id, visible_content_clause(user.id))
            )
        )
        .scalars()
        .first()
    )
    if exam is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exam not found")
    if exam.status != "active":
        # 회차 보존 = 새 응시 시작 차단 (진행 중 attempt 제출은 허용 — submit 참조)
        raise HTTPException(status.HTTP_409_CONFLICT, "exam_archived")
    attempt = ExamAttempt(exam_id=exam_id, user_id=user.id)
    db.add(attempt)
    await db.flush()
    questions = (
        (
            await db.execute(
                select(ExamQuestion)
                .where(ExamQuestion.exam_id == exam_id)
                .order_by(ExamQuestion.seq)
            )
        )
        .scalars()
        .all()
    )
    await db.commit()
    return {
        "attempt_id": attempt.id,
        "questions": [
            {
                "seq": q.seq,
                "quiz_mode": q.payload.get("quiz_mode"),
                "prompt": q.payload.get("prompt"),
                "prompt_ko": q.payload.get("prompt_ko"),
                "choices": q.payload.get("choices", []),
            }
            for q in questions
        ],
    }


class SubmitBody(BaseModel):
    answers: list[int]


@router.post("/exams/{exam_id}/attempts/{attempt_id}/submit")
async def submit_attempt(
    exam_id: int,
    attempt_id: int,
    body: SubmitBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """서버 채점 — score=정답수x5, duration=제출-시작 서버 시각차.

    archived 시험이라도 진행 중 attempt 는 제출 허용(시작한 시험지를 마칠 권리)
    — 해당 회차 랭킹에 반영된다 (spec §4, Phase 4.5 지적 반영).
    """
    attempt = await db.get(ExamAttempt, attempt_id)
    if attempt is None or attempt.exam_id != exam_id or attempt.user_id != user.id:
        # 타인 attempt 는 존재 자체를 노출하지 않는다
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attempt not found")
    if attempt.submitted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_submitted")
    questions = (
        (
            await db.execute(
                select(ExamQuestion)
                .where(ExamQuestion.exam_id == exam_id)
                .order_by(ExamQuestion.seq)
            )
        )
        .scalars()
        .all()
    )
    # 신뢰 경계 검증 — 길이=문항 수, 각 값 0..3
    if len(body.answers) != len(questions) or any(a < 0 or a > 3 for a in body.answers):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_answers")

    now = datetime.now(UTC)
    results = []
    correct_count = 0
    for question, answer in zip(questions, body.answers, strict=True):
        correct = answer == question.payload["answer_index"]
        correct_count += int(correct)
        results.append(
            {
                "seq": question.seq,
                "correct": correct,
                "answer_index": question.payload["answer_index"],
            }
        )
    # 탈환 판정용 — 이 attempt 가 제출되기 전의 1위 (submitted_at NULL 이라 아직 미포함)
    prev_rows = await _best_rows(db, exam_id)
    prev_top = prev_rows[0] if prev_rows else None

    score = correct_count * POINTS_PER_QUESTION
    duration_ms = max(0, int((now - _aware(attempt.started_at)).total_seconds() * 1000))
    # 원자적 클레임 — 동시 이중 제출이 둘 다 통과해 이중 채점·이중 알림 되는
    # 경합 차단 (앱 레벨 재확인만으로는 부족 — 2026-07-31 심층 리뷰)
    claimed = await db.execute(
        update(ExamAttempt)
        .where(ExamAttempt.id == attempt.id, ExamAttempt.submitted_at.is_(None))
        .values(
            submitted_at=now,
            score=score,
            correct_count=correct_count,
            duration_ms=duration_ms,
            answers=list(body.answers),
        )
    )
    if claimed.rowcount == 0:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "already_submitted")
    await db.flush()

    rows = await _best_rows(db, exam_id)
    rank = next((idx + 1 for idx, row in enumerate(rows) if row.user_id == user.id), None)

    # 1위 탈환 알림 — 뺏긴 사람에게만 (자기 갱신·최초 등극 제외, 2026-07-31 goal)
    new_top = rows[0] if rows else None
    if (
        prev_top is not None
        and new_top is not None
        and new_top.user_id == user.id
        and prev_top.user_id != user.id
    ):
        exam = await db.get(Exam, exam_id)
        content = await db.get(Content, exam.content_id) if exam else None
        await notify(
            db,
            prev_top.user_id,
            "exam_dethroned",
            {
                "content_id": exam.content_id if exam else None,
                "content_title": content.title if content else "",
                "by_name": _display_name(user.nickname, user.name),
            },
        )
    await db.commit()

    return {
        "score": score,
        "correct_count": correct_count,
        "duration_ms": duration_ms,
        "rank": rank,
        "results": results,
        # 보상 체감 — 결과 화면에 "+N XP" 즉시 표시 (stats 산식과 동일)
        "xp_gained": exam_xp(score),
    }


@router.get("/exams/{exam_id}/rankings")
async def exam_rankings(
    exam_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """TOP 50 + 내 순위 — archived 회차도 조회 가능 (읽기 전용 보존).

    비공개 콘텐츠의 시험은 구독자만 (미구독 404 — 존재 비노출)."""
    exam = (
        (
            await db.execute(
                select(Exam)
                .join(Content, Content.id == Exam.content_id)
                .where(Exam.id == exam_id, visible_content_clause(user.id))
            )
        )
        .scalars()
        .first()
    )
    if exam is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exam not found")
    rows = await _best_rows(db, exam_id)
    items = [
        {
            "rank": idx + 1,
            "nickname": _display_name(row.nickname, row.name),
            "score": row.score,
            "duration_ms": row.duration_ms,
            "is_me": row.user_id == user.id,
        }
        for idx, row in enumerate(rows[:RANKING_LIMIT])
    ]
    mine = next(
        (
            {
                "rank": idx + 1,
                "nickname": _display_name(row.nickname, row.name),
                "score": row.score,
                "duration_ms": row.duration_ms,
                "is_me": True,
            }
            for idx, row in enumerate(rows)
            if row.user_id == user.id
        ),
        None,
    )
    return {"items": items, "me": mine}
