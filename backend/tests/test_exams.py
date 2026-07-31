"""라이브러리 시험 — 스냅샷 생성·응시 채점·랭킹·회차 보존.

스펙: .harness/spec/2026-07-30-library-exam.md
"""

from sqlalchemy import select

from app.models import Content, Exam, ExamAttempt, ExamQuestion
from tests.test_friends import make_user


async def make_content(db, title="시험 콘텐츠") -> Content:
    content = Content(source="manual", title=title, status="ready", visibility="public")
    db.add(content)
    await db.flush()
    return content


async def test_exam_models_roundtrip(db_session):
    """AC-1: 모델 3종 메타데이터 생성 + insert/조회 왕복."""
    content = await make_content(db_session)
    exam = Exam(content_id=content.id, round=1, status="active", question_count=2)
    db_session.add(exam)
    await db_session.flush()
    db_session.add_all(
        [
            ExamQuestion(
                exam_id=exam.id,
                seq=1,
                item_id=None,
                payload={"quiz_mode": "choice_en2ko", "answer_index": 2},
            ),
            ExamQuestion(
                exam_id=exam.id,
                seq=2,
                item_id=None,
                payload={"quiz_mode": "cloze", "answer_index": 0},
            ),
        ]
    )
    taker = await make_user(db_session, "taker@example.com", "응시자")
    db_session.add(ExamAttempt(exam_id=exam.id, user_id=taker.id))
    await db_session.commit()

    loaded = (
        await db_session.execute(select(Exam).where(Exam.content_id == content.id))
    ).scalar_one()
    assert loaded.round == 1 and loaded.status == "active"
    seqs = (
        (await db_session.execute(select(ExamQuestion.seq).where(ExamQuestion.exam_id == exam.id)))
        .scalars()
        .all()
    )
    assert sorted(seqs) == [1, 2]
    attempt = (
        await db_session.execute(select(ExamAttempt).where(ExamAttempt.exam_id == exam.id))
    ).scalar_one()
    # started_at 은 서버 기록, 제출 전 필드는 전부 NULL (진행 중 표시)
    assert attempt.started_at is not None
    assert attempt.submitted_at is None and attempt.score is None
