"""백오피스 번역 사용량 — 월 예산 소진 현황 (docs/specs/chat-translation.md).

admin_shop.py 와 같은 관리 모델: 판매/과금 정책은 코드(설정)가 단일 근거이고,
이 화면은 그 정책 대비 실제 소진량을 보여주는 조회 전용 대시보드다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import require_admin
from app.models.translation import TranslationUsage
from app.services.translation import current_day_start_kst, current_month_start

router = APIRouter(
    prefix="/admin/translation-usage", tags=["admin"], dependencies=[Depends(require_admin)]
)


@router.get("")
async def translation_usage(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    cfg = get_settings()
    month_start = current_month_start()

    month_chars = (
        await db.execute(
            select(func.coalesce(func.sum(TranslationUsage.chars), 0)).where(
                TranslationUsage.created_at >= month_start
            )
        )
    ).scalar_one()

    by_engine = dict(
        (
            await db.execute(
                select(TranslationUsage.engine, func.count(TranslationUsage.id))
                .where(TranslationUsage.created_at >= month_start)
                .group_by(TranslationUsage.engine)
            )
        ).all()
    )

    today_calls = (
        await db.execute(
            select(func.count(TranslationUsage.id)).where(
                TranslationUsage.created_at >= current_day_start_kst()
            )
        )
    ).scalar_one()

    return {
        "month_chars": month_chars,
        "budget_chars": cfg.translate_monthly_budget_chars,
        "by_engine": {"deepl": by_engine.get("deepl", 0), "haiku": by_engine.get("haiku", 0)},
        "today_calls": today_calls,
    }
