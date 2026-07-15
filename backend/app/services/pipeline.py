"""추출 파이프라인 상태 머신 (docs/specs/content-pipeline.md).

단계: metadata -> transcript -> translate -> extract
- 단계별 extraction_jobs 기록, done 단계는 재실행 시 건너뜀 (멱등)
- 단계당 자동 재시도 3회 (지수 백오프)
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session_factory
from app.models import Content, ExtractionJob, ItemOccurrence, LearningItem, TranscriptSegment
from app.models.item import normalize_key
from app.services import embeddings, extraction, youtube
from app.services.youtube import TranscriptBlockedError

logger = logging.getLogger(__name__)

# 사용자 노출 문구 — "수집기" 같은 내부 용어 금지 (my 화면 error_message 로 표시됨)
WAITING_FOR_AGENT_MESSAGE = "자막 준비 중 — 자막을 받아 오면 자동으로 이어서 진행돼요"

MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 5  # 5s -> 25s -> 125s (테스트에서 패치)

STEPS = ("metadata", "transcript", "translate", "extract", "embed")


async def run_pipeline(content_id: int) -> None:
    """콘텐츠 1건의 전체 파이프라인 실행. 워커 큐에서 호출."""
    factory = get_session_factory()
    async with factory() as db:
        content = await db.get(Content, content_id)
        if content is None or content.status == "ready":
            return
        content.status = "extracting"
        await db.commit()

        try:
            if content.source == "youtube":
                await _run_step(db, content, "metadata", _step_metadata)
                await _run_step(db, content, "transcript", _step_transcript)
            await _run_step(db, content, "translate", _step_translate)
            await _run_step(db, content, "extract", _step_extract)
            await _run_step(db, content, "embed", _step_embed)
        except TranscriptBlockedError:
            # 서버 IP 차단 — 실패가 아니라 "자막 대기" (로컬 수집기가 채우면 자동 재개)
            content.status = "pending"
            content.error_message = WAITING_FOR_AGENT_MESSAGE
            await db.commit()
            return
        except Exception as exc:
            logger.exception("pipeline failed content=%s", content_id)
            content.status = "failed"
            content.error_message = str(exc)[:2000]
            await db.commit()
            return

        content.status = "ready"
        content.error_message = None
        await db.commit()


async def _run_step(db: AsyncSession, content: Content, step: str, func) -> None:
    job = await _get_or_create_job(db, content.id, step)
    if job.status == "done":
        return

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        job.status = "running"
        job.attempt = attempt
        job.started_at = datetime.now(UTC)
        await db.commit()
        try:
            payload = await func(db, content)
            job.status = "done"
            job.error = None
            job.payload = payload or {}
            job.finished_at = datetime.now(UTC)
            await db.commit()
            return
        except youtube.TranscriptNotFoundError as exc:
            # 자막 없음/차단은 재시도 무의미 — 즉시 실패. 잡을 failed 로 기록해야
            # 수집기 대기 목록(failed 잡 필터)에 잡힌다. running 방치 = 영구 교착
            job.status = "failed"
            job.error = str(exc)[:2000]
            job.finished_at = datetime.now(UTC)
            await db.commit()
            raise
        except Exception as exc:
            last_error = exc
            job.status = "failed"
            job.error = str(exc)[:2000]
            job.finished_at = datetime.now(UTC)
            await db.commit()
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(BACKOFF_BASE_SECONDS**attempt)
    raise RuntimeError(f"step {step} failed after {MAX_ATTEMPTS} attempts") from last_error


async def _get_or_create_job(db: AsyncSession, content_id: int, step: str) -> ExtractionJob:
    result = await db.execute(
        select(ExtractionJob).where(
            ExtractionJob.content_id == content_id, ExtractionJob.step == step
        )
    )
    job = result.scalar_one_or_none()
    if job is None:
        job = ExtractionJob(content_id=content_id, step=step)
        db.add(job)
        await db.flush()
    return job


# --- 단계 구현 ---


async def _step_metadata(db: AsyncSession, content: Content) -> dict:
    title = await youtube.fetch_title(content.youtube_video_id)
    content.title = title
    if content.youtube_license is None:
        # CC 게이트 참고용 — 키 미설정이면 None 유지 (docs/specs/content-pipeline.md)
        content.youtube_license = await youtube.fetch_license(content.youtube_video_id)
    return {"title": title, "license": content.youtube_license}


async def _step_transcript(db: AsyncSession, content: Content) -> dict:
    existing = await db.execute(
        select(TranscriptSegment.id).where(TranscriptSegment.content_id == content.id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return {"skipped": "segments already exist"}

    en = await asyncio.to_thread(youtube.fetch_transcript, content.youtube_video_id, ("en",))
    sentences = youtube.merge_into_sentences(en.snippets)

    ko_texts: dict[int, str] = {}
    try:
        ko = await asyncio.to_thread(youtube.fetch_transcript, content.youtube_video_id, ("ko",))
        ko_texts = _align_ko_by_time(sentences, ko.snippets)
    except youtube.TranscriptNotFoundError:
        pass  # 한글 자막 없음 — translate 단계에서 AI 번역

    for seq, snippet in enumerate(sentences):
        db.add(
            TranscriptSegment(
                content_id=content.id,
                seq=seq,
                start_ms=snippet.start_ms,
                end_ms=snippet.end_ms,
                en_text=snippet.text,
                ko_text=ko_texts.get(seq),
            )
        )
    await db.flush()
    return {
        "segments": len(sentences),
        "generated": en.is_generated,
        "ko_matched": len(ko_texts),
    }


def _align_ko_by_time(
    sentences: list[youtube.Snippet], ko_snippets: list[youtube.Snippet]
) -> dict[int, str]:
    """타임스탬프 근접 매칭: 영어 문장 구간에 걸치는 한글 자막을 이어 붙인다."""
    aligned: dict[int, str] = {}
    for seq, sent in enumerate(sentences):
        parts = [
            ko.text for ko in ko_snippets if ko.start_ms < sent.end_ms and ko.end_ms > sent.start_ms
        ]
        if parts:
            aligned[seq] = " ".join(parts)
    return aligned


async def _step_translate(db: AsyncSession, content: Content) -> dict:
    result = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.content_id == content.id, TranscriptSegment.ko_text.is_(None))
        .order_by(TranscriptSegment.seq)
    )
    missing = list(result.scalars())
    if not missing:
        return {"translated": 0}
    translated = await extraction.translate_texts([s.en_text for s in missing])
    for segment, ko in zip(missing, translated, strict=True):
        segment.ko_text = ko
    await db.flush()
    return {"translated": len(missing)}


async def _step_extract(db: AsyncSession, content: Content) -> dict:
    result = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.content_id == content.id)
        .order_by(TranscriptSegment.seq)
    )
    segments = list(result.scalars())
    if not segments:
        raise RuntimeError("no segments to extract from")

    data = await extraction.extract_items([(s.seq, s.en_text) for s in segments])
    seg_by_seq = {s.seq: s for s in segments}
    counts = {"created": 0, "reused": 0}

    for kind, items in (
        ("word", data["words"]),
        ("idiom", data["idioms"]),
        ("pattern", data["patterns"]),
        ("sentence", data["sentences"]),
    ):
        for raw in items:
            await _upsert_item(db, content, kind, raw, seg_by_seq, counts)
    await db.flush()
    return counts


async def _step_embed(db: AsyncSession, content: Content) -> dict:
    """콘텐츠의 word/idiom 항목 임베딩 (P2 유사단어/선지 개선).

    키 미설정·비 postgres 환경은 스킵(멱등) — 기능 없이도 파이프라인은 정상 완료.
    """
    if not embeddings.enabled(db):
        return {"skipped": True}
    rows = (
        (
            await db.execute(
                select(LearningItem)
                .join(ItemOccurrence, ItemOccurrence.item_id == LearningItem.id)
                .where(
                    ItemOccurrence.content_id == content.id,
                    LearningItem.item_type.in_(("word", "idiom")),
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    missing = set(await embeddings.missing_item_ids(db, [i.id for i in rows]))
    embedded = await embeddings.embed_items(db, [i for i in rows if i.id in missing])
    await db.flush()
    return {"embedded": embedded, "total": len(rows)}


async def _upsert_item(
    db: AsyncSession,
    content: Content,
    kind: str,
    raw: dict,
    seg_by_seq: dict[int, TranscriptSegment],
    counts: dict,
) -> None:
    en_text = raw.get("template") if kind == "pattern" else raw["en"]
    key = normalize_key(en_text)
    result = await db.execute(
        select(LearningItem).where(
            LearningItem.item_type == kind, LearningItem.normalized_key == key
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        item = LearningItem(
            item_type=kind,
            en_text=en_text,
            ko_text=raw["ko"],
            normalized_key=key,
            hint_thinking=raw.get("thinking_ko"),
            pattern_template=raw.get("template") if kind == "pattern" else None,
            difficulty_hint=raw.get("difficulty", "intermediate"),
        )
        db.add(item)
        await db.flush()
        counts["created"] += 1
    else:
        counts["reused"] += 1

    segment = seg_by_seq.get(raw.get("segment_seq", -1))
    exists = await db.execute(
        select(ItemOccurrence.id).where(
            ItemOccurrence.item_id == item.id,
            ItemOccurrence.content_id == content.id,
            ItemOccurrence.segment_id == (segment.id if segment else None),
        )
    )
    if exists.scalar_one_or_none() is None:
        db.add(
            ItemOccurrence(
                item_id=item.id,
                content_id=content.id,
                segment_id=segment.id if segment else None,
                context_en=segment.en_text if segment else raw.get("en_example"),
                context_ko=segment.ko_text if segment else None,
            )
        )
