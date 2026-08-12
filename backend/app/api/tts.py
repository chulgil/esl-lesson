"""발음 오디오 API — 신경망 TTS 캐시 서빙 (services/tts.py)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.services import tts as tts_service
from app.services.langs import SUPPORTED_LANGS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["tts"])


@router.get("")
async def get_tts(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[object, Depends(get_current_user)],
    text: Annotated[str, Query(min_length=1, max_length=tts_service.MAX_TEXT_LEN)],
    lang: str = tts_service.DEFAULT_LANG,
) -> Response:
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unsupported_lang")
    try:
        audio = await tts_service.get_or_generate(db, text, lang)
    except Exception as exc:  # 외부 TTS 실패 — 프론트가 브라우저 TTS 로 폴백
        logger.exception("tts failed text=%r lang=%s", text[:40], lang)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "tts_failed") from exc
    return Response(
        content=audio,
        media_type="audio/mpeg",
        # 같은 단어 재청취는 브라우저 캐시로 — 인증 응답이라 private
        headers={"Cache-Control": "private, max-age=86400"},
    )
