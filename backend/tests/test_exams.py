"""라이브러리 시험 — 스냅샷 생성·응시 채점·랭킹·회차 보존.

스펙: .harness/spec/2026-07-30-library-exam.md
"""

from sqlalchemy import select

from app.models import Content, Exam, ExamAttempt, ExamQuestion, ItemOccurrence, LearningItem
from tests.test_friends import make_user
from tests.test_study import login

_item_counter = 0


async def seed_exam_items(db, content, count=5, item_type="word"):
    """콘텐츠에 승인 항목 + occurrence 시드 — 시험지 출제 풀."""
    global _item_counter
    items = []
    for _ in range(count):
        _item_counter += 1
        n = _item_counter
        item = LearningItem(
            item_type=item_type,
            en_text=f"exam {item_type} {n}" if item_type == "pattern" else f"examword{n}",
            ko_text=f"뜻{n}",
            normalized_key=f"exam-{item_type}-{n}",
            review_status="approved",
        )
        db.add(item)
        await db.flush()
        db.add(
            ItemOccurrence(
                item_id=item.id,
                content_id=content.id,
                context_en=f"They said exam {item_type} {n} today.",
                context_ko=f"오늘 {n}번을 말했다.",
            )
        )
        items.append(item)
    await db.flush()
    return items


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


# ---------------------------------------------------------------- J2: 생성


async def test_exam_generation_snapshots_up_to_20(admin_client, db_session):
    """AC-2: 승인 항목에서 최대 20문항 스냅샷 — 4지선다·answer_index 포함."""
    content = await make_content(db_session)
    await seed_exam_items(db_session, content, count=25, item_type="word")
    await db_session.commit()

    res = await admin_client.post(f"/api/admin/contents/{content.id}/exam")
    assert res.status_code == 200
    body = res.json()
    assert body["round"] == 1 and body["question_count"] == 20

    questions = (
        (
            await db_session.execute(
                select(ExamQuestion).where(ExamQuestion.exam_id == body["exam_id"])
            )
        )
        .scalars()
        .all()
    )
    assert len(questions) == 20
    assert sorted(q.seq for q in questions) == list(range(1, 21))
    for q in questions:
        payload = q.payload
        assert len(payload["choices"]) == 4
        assert 0 <= payload["answer_index"] <= 3
        assert payload["en_text"] and payload["ko_text"]
        assert q.item_id is not None


async def test_exam_generation_pattern_forced_to_choices(admin_client, db_session):
    """패턴 항목도 4지선다로 강제 — 칩 조립 대신 해석→문장 고르기."""
    content = await make_content(db_session)
    await seed_exam_items(db_session, content, count=3, item_type="word")
    await seed_exam_items(db_session, content, count=3, item_type="pattern")
    await db_session.commit()

    res = await admin_client.post(f"/api/admin/contents/{content.id}/exam")
    assert res.status_code == 200
    assert res.json()["question_count"] == 6

    questions = (
        (
            await db_session.execute(
                select(ExamQuestion).where(ExamQuestion.exam_id == res.json()["exam_id"])
            )
        )
        .scalars()
        .all()
    )
    patterns = [q for q in questions if q.payload["quiz_mode"] == "pattern"]
    assert len(patterns) == 3
    for q in patterns:
        choices = q.payload["choices"]
        assert len(choices) == 4
        # 정답 = 대표 출처 문장 (occurrence context)
        assert "exam pattern" in choices[q.payload["answer_index"]]


async def test_exam_generation_not_enough_items(admin_client, db_session):
    """승인 항목 5개 미만 → 422 not_enough_items. 미존재 콘텐츠 404."""
    content = await make_content(db_session)
    await seed_exam_items(db_session, content, count=4, item_type="word")
    # rejected 는 출제 풀에서 제외 — 5개 채우기에 못 미친다
    rejected = await seed_exam_items(db_session, content, count=1, item_type="idiom")
    rejected[0].review_status = "rejected"
    await db_session.commit()

    res = await admin_client.post(f"/api/admin/contents/{content.id}/exam")
    assert res.status_code == 422
    assert res.json()["detail"] == "not_enough_items"
    assert (await admin_client.post("/api/admin/contents/99999/exam")).status_code == 404


async def test_regenerate_archives_and_increments_round(admin_client, db_session):
    """AC-2: 재생성 = 기존 active → archived + round+1. 회차 목록 미리보기."""
    content = await make_content(db_session)
    await seed_exam_items(db_session, content, count=6, item_type="word")
    await db_session.commit()

    first = (await admin_client.post(f"/api/admin/contents/{content.id}/exam")).json()
    second = (await admin_client.post(f"/api/admin/contents/{content.id}/exam")).json()
    assert second["round"] == 2

    exams = (
        (await db_session.execute(select(Exam).where(Exam.content_id == content.id)))
        .scalars()
        .all()
    )
    status_by_round = {e.round: e.status for e in exams}
    assert status_by_round == {1: "archived", 2: "active"}

    listing = (await admin_client.get(f"/api/admin/contents/{content.id}/exams")).json()
    rounds = [(e["round"], e["status"]) for e in listing["items"]]
    assert rounds == [(2, "active"), (1, "archived")]
    preview = listing["items"][0]["questions"]
    assert len(preview) == 6
    assert {"seq", "prompt", "choices", "answer_index"} <= set(preview[0])
    assert first["exam_id"] != second["exam_id"]


async def test_snapshot_immutable_after_item_edit(admin_client, db_session):
    """AC-2.1: 원본 항목 수정/거절 후에도 기존 문항 payload 불변."""
    content = await make_content(db_session)
    items = await seed_exam_items(db_session, content, count=5, item_type="word")
    await db_session.commit()

    exam_id = (await admin_client.post(f"/api/admin/contents/{content.id}/exam")).json()["exam_id"]
    before = {
        q.seq: dict(q.payload)
        for q in (
            await db_session.execute(select(ExamQuestion).where(ExamQuestion.exam_id == exam_id))
        ).scalars()
    }

    # 원본 수정 + 거절 — 스냅샷은 흔들리지 않아야 한다
    target = items[0]
    res = await admin_client.patch(
        f"/api/admin/items/{target.id}",
        json={"en_text": "CHANGED", "ko_text": "변경됨", "review_status": "rejected"},
    )
    assert res.status_code == 200

    after = {
        q.seq: dict(q.payload)
        for q in (
            await db_session.execute(select(ExamQuestion).where(ExamQuestion.exam_id == exam_id))
        ).scalars()
    }
    assert after == before
    assert not any(p["en_text"] == "CHANGED" for p in after.values())


async def test_exam_admin_forbidden_for_learner(client, db_session):
    """비관리자 생성/목록 403."""
    content = await make_content(db_session)
    await db_session.commit()
    await login(client, db_session)
    assert (await client.post(f"/api/admin/contents/{content.id}/exam")).status_code == 403
    assert (await client.get(f"/api/admin/contents/{content.id}/exams")).status_code == 403
