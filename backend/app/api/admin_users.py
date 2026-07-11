"""백오피스 사용자 관리 (docs/specs/backoffice.md)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_admin
from app.models import ReviewLog, User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
    page: int = 1,
    size: int = 50,
) -> dict:
    total = (await db.execute(select(func.count(User.id)))).scalar_one()
    rows = (
        await db.execute(
            select(User, func.count(ReviewLog.id))
            .outerjoin(ReviewLog, ReviewLog.user_id == User.id)
            .group_by(User.id)
            .order_by(User.id)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()
    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "created_at": u.created_at,
                "last_login_at": u.last_login_at,
                "total_reviews": review_count,
            }
            for u, review_count in rows
        ],
    }


class UserPatch(BaseModel):
    role: Literal["admin", "learner"]


@router.patch("/users/{user_id}")
async def patch_user(
    user_id: int,
    body: UserPatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    if user_id == admin.id and body.role != "admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot demote yourself")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    user.role = body.role
    await db.commit()
    return {"id": user.id, "role": user.role}
