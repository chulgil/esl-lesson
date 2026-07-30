"""사용자 테마 카탈로그 API (docs/specs/theme-mall.md)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import User
from app.services.themes import allowed_theme_keys, effective_theme_access

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get("")
async def list_themes(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """카탈로그 전체 + 내 사용 가능 여부 — 표시 순서·라벨은 프론트 APP_THEMES 가 결정."""
    allowed = set(await allowed_theme_keys(db, user.id, user.role))
    access_map = await effective_theme_access(db)
    return {
        "items": [
            {"key": key, "access": access, "allowed": key in allowed}
            for key, access in access_map.items()
        ]
    }
