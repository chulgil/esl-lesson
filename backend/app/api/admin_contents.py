"""백오피스 콘텐츠/항목 API — 공용(public) 콘텐츠 전용 (docs/specs/backoffice.md)."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_admin
from app.models import (
    Content,
    ContentPermission,
    ItemOccurrence,
    LearningItem,
    TranscriptSegment,
)
from app.models.user import User
from app.services import youtube
from app.services.content_service import (
    ContentCreate,
    content_detail,
    content_summary,
    create_content,
    delete_content_row,
    retry_content_row,
)
from app.services.youtube import parse_video_id
from app.workers.queue import enqueue

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/youtube/cc-search")
async def cc_search(
    q: Annotated[str, Query(min_length=1, max_length=100)],
    page_token: Annotated[str | None, Query(max_length=300)] = None,
) -> dict:
    """CC(creativeCommon)·자막 보유·영어 영상만 검색 — 등록 후보 제시.

    page_token 으로 다음 페이지 (2026-08-05 페이징). 검색 필터는 후보용이고,
    등록(POST /contents) 시 fetch_license 가 라이선스를 서버에서 재확인한다
    (허위/변경 대비 이중 게이트)."""
    try:
        result = await youtube.search_cc_videos(q, page_token=page_token)
    except Exception as exc:  # noqa: BLE001 — 쿼터 초과 등 구글 API 오류
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "youtube_search_failed") from exc
    if result is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "youtube_api_key_missing")
    return result


async def get_public_content(db: AsyncSession, content_id: int) -> Content:
    content = await db.get(Content, content_id)
    if content is None or content.visibility != "public":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    return content


class PermissionInput(BaseModel):
    """원저작자 이용허락 증빙 (docs/specs/content-governance.md)."""

    rights_holder: str = Field(min_length=1, max_length=200)
    rights_holder_contact: str | None = Field(default=None, max_length=200)
    granted_at: date
    scope_transcript: bool = False
    scope_translate: bool = False
    scope_derive: bool = False
    scope_commercial: bool = False
    evidence: str = Field(min_length=1)
    note: str | None = None


class PublicContentCreate(ContentCreate):
    # 비 CC 영상은 이 증빙이 있어야 등록된다 (기존 allow_non_cc 불리언 대체)
    permission: PermissionInput | None = None


def _permission_row(content_id: int, perm: PermissionInput, admin_id: int) -> ContentPermission:
    # 파이프라인이 실제로 수행하는 이용 3종이 모두 허락돼야 처리 자체가 범위 안이다
    if not (perm.scope_transcript and perm.scope_translate and perm.scope_derive):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "permission_scope_insufficient")
    return ContentPermission(
        content_id=content_id,
        rights_holder=perm.rights_holder,
        rights_holder_contact=perm.rights_holder_contact,
        granted_at=perm.granted_at,
        scope_transcript=perm.scope_transcript,
        scope_translate=perm.scope_translate,
        scope_derive=perm.scope_derive,
        scope_commercial=perm.scope_commercial,
        evidence=perm.evidence,
        note=perm.note,
        recorded_by=admin_id,
    )


@router.post("/contents", status_code=status.HTTP_202_ACCEPTED)
async def create_public_content(
    body: PublicContentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    license_: str | None = None
    if body.source == "youtube":
        video_id = parse_video_id(body.url or "")
        if video_id:
            # 공용 = 전 회원 제공이라 CC(재배포 허용) 영상만 증빙 없이 허용.
            # 미확인(키 없음/조회 실패)도 안전 기본값으로 차단 — 허락 증빙으로만 우회
            license_ = await youtube.fetch_license(video_id)
            if license_ != "creativeCommon" and body.permission is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "cc_required")
            # 이미 개인이 등록한 영상이면 공용으로 승격 (재추출 없음)
            existing = (
                await db.execute(select(Content).where(Content.youtube_video_id == video_id))
            ).scalar_one_or_none()
            if existing is not None and existing.visibility == "private":
                if body.permission is not None:
                    db.add(_permission_row(existing.id, body.permission, admin.id))
                existing.visibility = "public"
                existing.youtube_license = existing.youtube_license or license_
                await db.commit()
                return {"id": existing.id, "status": existing.status, "promoted": True}
    # 범위 검증을 콘텐츠 생성보다 먼저 — 반려 시 고아 콘텐츠가 남지 않게
    permission = (
        _permission_row(0, body.permission, admin.id) if body.permission is not None else None
    )
    content = await create_content(db, body, admin.id, visibility="public")
    if license_ is not None:
        content.youtube_license = license_
    if permission is not None:
        permission.content_id = content.id
        db.add(permission)
    await db.commit()
    enqueue(content.id)
    return {"id": content.id, "status": content.status}


@router.get("/contents")
async def list_contents(
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    query = select(Content).where(Content.visibility == "public").order_by(Content.id.desc())
    if status_filter:
        query = query.where(Content.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = ((await db.execute(query.offset((page - 1) * size).limit(size))).scalars()).all()
    return {"total": total, "page": page, "items": [content_summary(c) for c in rows]}


@router.get("/contents/{content_id}")
async def get_content(content_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    content = await get_public_content(db, content_id)
    detail = await content_detail(db, content)
    perm = (
        await db.execute(
            select(ContentPermission).where(ContentPermission.content_id == content_id)
        )
    ).scalar_one_or_none()
    detail["youtube_license"] = content.youtube_license
    detail["permission"] = (
        None
        if perm is None
        else {
            "rights_holder": perm.rights_holder,
            "rights_holder_contact": perm.rights_holder_contact,
            "granted_at": perm.granted_at,
            "scope_transcript": perm.scope_transcript,
            "scope_translate": perm.scope_translate,
            "scope_derive": perm.scope_derive,
            "scope_commercial": perm.scope_commercial,
            "evidence": perm.evidence,
            "note": perm.note,
        }
    )
    return detail


@router.post("/contents/{content_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_content(content_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    content = await get_public_content(db, content_id)
    retry_content_row(content)
    await db.commit()
    enqueue(content_id)
    return {"id": content_id, "status": "pending"}


@router.delete("/contents/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(content_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    content = await get_public_content(db, content_id)
    await delete_content_row(db, content)


class SegmentPatch(BaseModel):
    en_text: str | None = None
    ko_text: str | None = None


@router.patch("/segments/{segment_id}")
async def patch_segment(
    segment_id: int, body: SegmentPatch, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    segment = await db.get(TranscriptSegment, segment_id)
    if segment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "segment not found")
    if body.en_text is not None:
        segment.en_text = body.en_text
    if body.ko_text is not None:
        segment.ko_text = body.ko_text
    await db.commit()
    return {"id": segment.id, "en_text": segment.en_text, "ko_text": segment.ko_text}


class ItemPatch(BaseModel):
    en_text: str | None = None
    ko_text: str | None = None
    hint_thinking: str | None = None
    review_status: Literal["pending", "approved", "rejected"] | None = None


@router.patch("/items/{item_id}")
async def patch_item(
    item_id: int, body: ItemPatch, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    item = await db.get(LearningItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item not found")
    if body.review_status == "approved" and item.item_type == "sentence":
        hint = body.hint_thinking if body.hint_thinking is not None else item.hint_thinking
        if not hint:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "sentence item requires hint_thinking before approval",
            )
    for field in ("en_text", "ko_text", "hint_thinking", "review_status"):
        value = getattr(body, field)
        if value is not None:
            setattr(item, field, value)
    await db.commit()
    return {"id": item.id, "review_status": item.review_status}


@router.post("/contents/{content_id}/approve-all")
async def approve_all(content_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    items = (
        (
            await db.execute(
                select(LearningItem)
                .join(ItemOccurrence, ItemOccurrence.item_id == LearningItem.id)
                .where(
                    ItemOccurrence.content_id == content_id,
                    LearningItem.review_status == "pending",
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    approved = 0
    skipped = 0
    for item in items:
        # 사고 힌트 없는 문장은 일괄 승인에서 제외 (개별 검수 필요)
        if item.item_type == "sentence" and not item.hint_thinking:
            skipped += 1
            continue
        item.review_status = "approved"
        approved += 1
    await db.commit()
    return {"approved": approved, "skipped": skipped}


@router.get("/items")
async def search_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    item_type: Annotated[str | None, Query(alias="type")] = None,
    review_status: Annotated[str | None, Query(alias="status")] = None,
    q: str | None = None,
    page: int = 1,
    size: int = 50,
) -> dict:
    query = select(LearningItem).order_by(LearningItem.id.desc())
    if item_type:
        query = query.where(LearningItem.item_type == item_type)
    if review_status:
        query = query.where(LearningItem.review_status == review_status)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            func.lower(LearningItem.en_text).like(pattern)
            | func.lower(LearningItem.ko_text).like(pattern)
        )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = ((await db.execute(query.offset((page - 1) * size).limit(size))).scalars()).all()
    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": i.id,
                "item_type": i.item_type,
                "en_text": i.en_text,
                "ko_text": i.ko_text,
                "review_status": i.review_status,
                "difficulty_hint": i.difficulty_hint,
            }
            for i in rows
        ],
    }


@router.get("/dashboard")
async def dashboard(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    pending_items = (
        await db.execute(select(func.count()).where(LearningItem.review_status == "pending"))
    ).scalar_one()
    failed_contents = (
        await db.execute(
            select(func.count()).where(Content.status == "failed", Content.visibility == "public")
        )
    ).scalar_one()
    extracting = (
        await db.execute(
            select(func.count()).where(
                Content.status.in_(("pending", "extracting")), Content.visibility == "public"
            )
        )
    ).scalar_one()
    total_contents = (
        await db.execute(select(func.count(Content.id)).where(Content.visibility == "public"))
    ).scalar_one()
    return {
        "pending_items": pending_items,
        "failed_contents": failed_contents,
        "in_progress_contents": extracting,
        "total_contents": total_contents,
    }
