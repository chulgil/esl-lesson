"""라이브러리 시험 — 스냅샷 생성·응시 채점·랭킹·회차 보존.

스펙: .harness/spec/2026-07-30-library-exam.md
"""

from sqlalchemy import select

from app.models import (
    Content,
    Exam,
    ExamAttempt,
    ExamQuestion,
    ItemOccurrence,
    LearningItem,
    User,
)
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


# ---------------------------------------------------------------- J3: 응시


async def make_exam(admin_client, db, count=5, item_type="word"):
    """콘텐츠 + 승인 항목 + 활성 시험지 준비. (content, exam_id) 반환."""
    content = await make_content(db)
    await seed_exam_items(db, content, count=count, item_type=item_type)
    await db.commit()
    res = await admin_client.post(f"/api/admin/contents/{content.id}/exam")
    assert res.status_code == 200
    return content, res.json()["exam_id"]


async def answer_key(db, exam_id) -> list[int]:
    """seq 순 정답 인덱스 — 테스트가 서버 스냅샷에서 직접 읽는다."""
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
    return [q.payload["answer_index"] for q in questions]


async def switch_user(client, user):
    from app.core.security import SESSION_COOKIE, create_session_token

    client.cookies.set(SESSION_COOKIE, create_session_token(user))


async def test_attempt_flow_start_and_submit(client, admin_client, db_session):
    """AC-3: 시작 시 정답 없는 문항 + 서버 채점 (score=정답수x5, duration 서버 계산)."""
    content, exam_id = await make_exam(admin_client, db_session, count=5)
    me = await login(client, db_session)

    # 시험 없는 콘텐츠 요약 — 오류 없이 exam_id null
    empty = await make_content(db_session)
    await db_session.commit()
    res = await client.get(f"/api/contents/{empty.id}/exam")
    assert res.status_code == 200 and res.json()["exam_id"] is None

    # 요약 — 응시 전
    summary = (await client.get(f"/api/contents/{content.id}/exam")).json()
    assert summary["exam_id"] == exam_id
    assert summary["round"] == 1 and summary["question_count"] == 5
    assert summary["attempt_count"] == 0 and summary["my_best"] is None
    assert summary["top"] == []

    # 시작 — 정답(answer_index) 미포함 문항
    res = await client.post(f"/api/exams/{exam_id}/attempts")
    assert res.status_code == 200
    started = res.json()
    assert len(started["questions"]) == 5
    for q in started["questions"]:
        assert "answer_index" not in q and "en_text" not in q
        assert len(q["choices"]) == 4

    # 제출 — 정답 3 + 오답 2
    key = await answer_key(db_session, exam_id)
    answers = list(key)
    answers[3] = (key[3] + 1) % 4
    answers[4] = (key[4] + 1) % 4
    res = await client.post(
        f"/api/exams/{exam_id}/attempts/{started['attempt_id']}/submit",
        json={"answers": answers},
    )
    assert res.status_code == 200
    graded = res.json()
    assert graded["score"] == 15 and graded["correct_count"] == 3
    assert graded["duration_ms"] >= 0
    assert graded["rank"] == 1
    assert [r["correct"] for r in graded["results"]] == [True, True, True, False, False]
    assert [r["answer_index"] for r in graded["results"]] == key

    # 요약 — 제출 후 내 최고점 반영
    summary = (await client.get(f"/api/contents/{content.id}/exam")).json()
    assert summary["attempt_count"] == 1
    assert summary["my_best"]["score"] == 15 and summary["my_best"]["rank"] == 1
    assert summary["top"][0]["nickname"] == me.nickname


async def test_submit_validations(client, admin_client, db_session):
    """AC-3.1: 길이/범위 422, 중복 제출 409, 타인 attempt 404."""
    _content, exam_id = await make_exam(admin_client, db_session, count=5)
    me = await login(client, db_session)
    attempt_id = (await client.post(f"/api/exams/{exam_id}/attempts")).json()["attempt_id"]

    # 길이 불일치 / 범위 밖 → 422
    bad_len = await client.post(
        f"/api/exams/{exam_id}/attempts/{attempt_id}/submit", json={"answers": [0, 1]}
    )
    assert bad_len.status_code == 422
    bad_range = await client.post(
        f"/api/exams/{exam_id}/attempts/{attempt_id}/submit",
        json={"answers": [0, 1, 2, 3, 4]},
    )
    assert bad_range.status_code == 422

    # 정상 제출 후 중복 → 409
    key = await answer_key(db_session, exam_id)
    ok = await client.post(
        f"/api/exams/{exam_id}/attempts/{attempt_id}/submit", json={"answers": key}
    )
    assert ok.status_code == 200
    dup = await client.post(
        f"/api/exams/{exam_id}/attempts/{attempt_id}/submit", json={"answers": key}
    )
    assert dup.status_code == 409
    assert dup.json()["detail"] == "already_submitted"

    # 타인 attempt → 404 (존재 노출 금지)
    other = await make_user(db_session, "other@example.com", "타인")
    await db_session.commit()
    await switch_user(client, other)
    stolen = await client.post(
        f"/api/exams/{exam_id}/attempts/{attempt_id}/submit", json={"answers": key}
    )
    assert stolen.status_code == 404
    ghost = await client.post(f"/api/exams/{exam_id}/attempts/99999/submit", json={"answers": key})
    assert ghost.status_code == 404
    assert me.id != other.id


async def test_archived_start_blocked_but_inflight_submit_allowed(client, admin_client, db_session):
    """AC-3.1: archived 시험 새 응시 409 — 진행 중 attempt 제출은 허용(그 회차 랭킹)."""
    from app.core.security import SESSION_COOKIE

    content, exam_id = await make_exam(admin_client, db_session, count=5)
    # admin_client 는 client 와 동일 인스턴스(쿠키만 admin) — login 이 덮기 전에 보관
    admin_cookie = admin_client.cookies.get(SESSION_COOKIE)
    me = await login(client, db_session)
    attempt_id = (await client.post(f"/api/exams/{exam_id}/attempts")).json()["attempt_id"]
    key = await answer_key(db_session, exam_id)

    # 회차 재생성 → 기존 exam archived (admin 쿠키 복원 후 호출)
    admin_client.cookies.set(SESSION_COOKIE, admin_cookie)
    regen = await admin_client.post(f"/api/admin/contents/{content.id}/exam")
    assert regen.status_code == 200 and regen.json()["round"] == 2
    await switch_user(client, me)

    # archived 시험에 새 응시 시작 → 409
    blocked = await client.post(f"/api/exams/{exam_id}/attempts")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "exam_archived"

    # 진행 중이던 attempt 제출은 허용 — 그 회차 랭킹에 반영
    res = await client.post(
        f"/api/exams/{exam_id}/attempts/{attempt_id}/submit", json={"answers": key}
    )
    assert res.status_code == 200 and res.json()["rank"] == 1
    old_rankings = (await client.get(f"/api/exams/{exam_id}/rankings")).json()
    assert len(old_rankings["items"]) == 1

    # 활성 회차(2)의 랭킹은 비어 있다 — 회차 분리
    new_exam_id = regen.json()["exam_id"]
    new_rankings = (await client.get(f"/api/exams/{new_exam_id}/rankings")).json()
    assert new_rankings["items"] == []


async def test_rankings_best_tiebreak_and_fallback(client, admin_client, db_session):
    """AC-4: 유저별 best 1행, 동점은 duration 짧은 쪽 상위, nickname 없으면 name."""
    from datetime import UTC, datetime, timedelta

    _content, exam_id = await make_exam(admin_client, db_session, count=5)
    key = await answer_key(db_session, exam_id)
    wrong_two = list(key)
    wrong_two[0] = (key[0] + 1) % 4
    wrong_two[1] = (key[1] + 1) % 4

    async def attempt_as(user, answers, slow_seconds=0):
        await switch_user(client, user)
        attempt_id = (await client.post(f"/api/exams/{exam_id}/attempts")).json()["attempt_id"]
        if slow_seconds:
            row = await db_session.get(ExamAttempt, attempt_id)
            row.started_at = datetime.now(UTC) - timedelta(seconds=slow_seconds)
            await db_session.commit()
        res = await client.post(
            f"/api/exams/{exam_id}/attempts/{attempt_id}/submit", json={"answers": answers}
        )
        assert res.status_code == 200
        return res.json()

    fast = await make_user(db_session, "fast@example.com", "빠른이")
    slow = await make_user(db_session, "slow@example.com", "느린이")
    plain = User(google_sub="g-plain", email="plain@example.com", name="이름폴백")
    db_session.add(plain)
    await db_session.commit()

    # slow: 만점(느림) / fast: 오답 2 -> 재응시 만점(빠름) — best 만 랭킹에 남는다
    await attempt_as(slow, key, slow_seconds=60)
    await attempt_as(fast, wrong_two)
    await attempt_as(fast, key)
    await attempt_as(plain, wrong_two)

    rankings = (await client.get(f"/api/exams/{exam_id}/rankings")).json()
    rows = rankings["items"]
    assert [(r["rank"], r["nickname"], r["score"]) for r in rows] == [
        (1, "빠른이", 25),
        (2, "느린이", 25),
        (3, "이름폴백", 15),
    ]
    # 동점(25) — duration 짧은 빠른이가 상위
    assert rows[0]["duration_ms"] <= rows[1]["duration_ms"]
    # is_me — 마지막 로그인(plain) 기준
    assert [r["is_me"] for r in rows] == [False, False, True]
    assert rankings["me"]["rank"] == 3
