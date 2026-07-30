"""테마 카탈로그 + 접근 정책 (docs/specs/theme-mall.md)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ThemeGrant, ThemeSetting
from app.models.user import ROLE_ADMIN, ROLE_LEARNER

# 테마별 접근 정책 기본값 — 유효 키 목록의 단일 근거 (프론트 APP_THEMES 와 키 일치).
# 실제 정책은 theme_settings 오버라이드 우선 (백오피스 무료/제한 전환).
# 기본 무료는 note 하나 — 나머지는 업적 보상(theme_reward_rules)·이벤트 지급으로만
# 열린다 (2026-07-30 전환). 유료 전환 시 "paid" 값 추가 예정 (PG 결정 후)
THEME_ACCESS: dict[str, str] = {
    "note": "free",
    "candy": "restricted",
    "lego": "restricted",
    "excel": "restricted",
    "cat": "restricted",
}

# 잠금 해제 복귀(fallback) 테마 — 제한 전환 금지 (클라 가드가 여기로 복귀시킨다)
FALLBACK_THEME = "note"


async def effective_theme_access(db: AsyncSession) -> dict[str, str]:
    """카탈로그 기본값 + theme_settings 오버라이드 병합 — 정책 판정의 단일 진입점."""
    overrides = dict((await db.execute(select(ThemeSetting.theme_key, ThemeSetting.access))).all())
    # 카탈로그에 없는 키의 오버라이드는 무시 — 유효 키는 THEME_ACCESS 가 결정
    return {key: overrides.get(key, default) for key, default in THEME_ACCESS.items()}


async def allowed_theme_keys(db: AsyncSession, user_id: int, role: str = ROLE_LEARNER) -> list[str]:
    """free 전부 + 해당 유저의 grants. 관리자는 전 테마 허용 (운영 확인용)."""
    if role == ROLE_ADMIN:
        return list(THEME_ACCESS)
    access_map = await effective_theme_access(db)
    granted = set(
        (
            await db.execute(select(ThemeGrant.theme_key).where(ThemeGrant.user_id == user_id))
        ).scalars()
    )
    return [key for key, access in access_map.items() if access == "free" or key in granted]
