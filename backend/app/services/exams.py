"""시험지 생성 — 승인 항목 스냅샷 (docs/specs/library-exam.md).

quiz.build_question 을 재사용하되 시험은 4지선다로 강제한다 — pattern 은
칩 조립 대신 "해석 -> 영어 문장 고르기" 선다로 변환 (sentence 는 출제 제외).
문항은 생성 시점 payload 로 고정되어 원본 항목 변경과 무관하다.
"""

import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Exam, ExamQuestion, ItemOccurrence, LearningItem
from app.services.quiz import FALLBACK_EN, build_question

EXAM_ITEM_TYPES = ("word", "idiom", "pattern")
MAX_QUESTIONS = 20
MIN_ITEMS = 5
POINTS_PER_QUESTION = 5


class NotEnoughItemsError(Exception):
    """승인 항목 5개 미만 — 시험지 생성 거부 (422 not_enough_items)."""


def _sentence_of(item: LearningItem) -> str:
    """대표 출처 문장 — quiz._pattern_answer 와 동일 규칙 (없으면 en_text)."""
    for occ in item.occurrences:
        if occ.context_en:
            return occ.context_en
    return item.en_text


def _pattern_payload(item: LearningItem, items: list[LearningItem]) -> dict:
    """패턴 -> 4지선다: 한글 해석을 주고 맞는 영어 문장을 고른다."""
    answer = _sentence_of(item)
    # 오답 후보: 같은 타입(패턴) 문장 우선, 부족하면 다른 항목 문장으로 채움
    ordered = [i for i in items if i.item_type == "pattern"] + [
        i for i in items if i.item_type != "pattern"
    ]
    picked: list[str] = []
    for other in ordered:
        if len(picked) >= 3:
            break
        if other.id == item.id:
            continue
        candidate = _sentence_of(other)
        if candidate != answer and candidate not in picked:
            picked.append(candidate)
    for value in FALLBACK_EN:
        if len(picked) >= 3:
            break
        if value != answer and value not in picked:
            picked.append(value)
    choices = [answer, *picked[:3]]
    random.shuffle(choices)
    prompt_ko = next((o.context_ko for o in item.occurrences if o.context_ko), None)
    return {
        "quiz_mode": "pattern",
        "prompt": prompt_ko or item.ko_text,
        "prompt_ko": None,
        "choices": choices,
        "answer_index": choices.index(answer),
    }


def _choice_payload(item: LearningItem, pool: list[LearningItem]) -> dict:
    """word/idiom — build_question 결과(4지선다)를 answer_index 스냅샷으로 변환."""
    question = build_question(item, pool)
    choices = question["choices"]
    return {
        "quiz_mode": question["quiz_mode"],
        "prompt": question["prompt"],
        "prompt_ko": question.get("prompt_ko"),
        "choices": choices,
        "answer_index": choices.index(question["hint_answer"]),
    }


def snapshot_question(
    item: LearningItem, items: list[LearningItem], pools: dict[str, list[LearningItem]]
) -> dict:
    payload = (
        _pattern_payload(item, items)
        if item.item_type == "pattern"
        else _choice_payload(item, pools[item.item_type])
    )
    # 복기 화면용 원문 스냅샷 — 채점·표시 모두 payload 로 자립
    return {**payload, "en_text": item.en_text, "ko_text": item.ko_text}


async def approved_exam_items(db: AsyncSession, content_id: int) -> list[LearningItem]:
    """해당 콘텐츠 출처(occurrence)의 승인 항목 — word/idiom/pattern 만."""
    return (
        (
            await db.execute(
                select(LearningItem)
                .join(ItemOccurrence, ItemOccurrence.item_id == LearningItem.id)
                .where(
                    ItemOccurrence.content_id == content_id,
                    LearningItem.review_status == "approved",
                    LearningItem.item_type.in_(EXAM_ITEM_TYPES),
                )
                .options(selectinload(LearningItem.occurrences))
                .distinct()
            )
        )
        .scalars()
        .all()
    )


async def create_exam(db: AsyncSession, content_id: int, created_by: int) -> Exam:
    """생성/재생성 — 기존 active 는 archived, 새 회차가 active 가 된다.

    커밋은 호출자(API) 책임 — 검증 실패 시 부분 상태가 남지 않는다.
    """
    items = await approved_exam_items(db, content_id)
    if len(items) < MIN_ITEMS:
        raise NotEnoughItemsError

    previous = (
        await db.execute(select(Exam).where(Exam.content_id == content_id, Exam.status == "active"))
    ).scalar_one_or_none()
    if previous is not None:
        previous.status = "archived"
    last_round = (
        await db.execute(select(func.max(Exam.round)).where(Exam.content_id == content_id))
    ).scalar_one() or 0

    chosen = random.sample(list(items), min(MAX_QUESTIONS, len(items)))
    exam = Exam(
        content_id=content_id,
        round=last_round + 1,
        status="active",
        question_count=len(chosen),
        created_by=created_by,
    )
    db.add(exam)
    await db.flush()
    pools = {t: [i for i in items if i.item_type == t] for t in EXAM_ITEM_TYPES}
    for seq, item in enumerate(chosen, start=1):
        db.add(
            ExamQuestion(
                exam_id=exam.id,
                seq=seq,
                item_id=item.id,
                payload=snapshot_question(item, chosen, pools),
            )
        )
    return exam
