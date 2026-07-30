"""테마 카탈로그 + 접근 정책 (docs/specs/theme-mall.md)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ThemeGrant
from app.models.user import ROLE_ADMIN, ROLE_LEARNER

# 테마별 접근 정책 — 카탈로그의 단일 근거 (프론트 APP_THEMES 와 키 일치).
# 지금은 free/restricted 2종. 유료 전환 시 "paid" 값 추가 예정 (PG 결정 후)
THEME_ACCESS: dict[str, str] = {
    "note": "free",
    "candy": "free",
    "lego": "free",
    "excel": "free",
    "cat": "restricted",
}


async def allowed_theme_keys(db: AsyncSession, user_id: int, role: str = ROLE_LEARNER) -> list[str]:
    """free 전부 + 해당 유저의 grants. 관리자는 전 테마 허용 (운영 확인용)."""
    if role == ROLE_ADMIN:
        return list(THEME_ACCESS)
    granted = set(
        (
            await db.execute(select(ThemeGrant.theme_key).where(ThemeGrant.user_id == user_id))
        ).scalars()
    )
    return [key for key, access in THEME_ACCESS.items() if access == "free" or key in granted]
