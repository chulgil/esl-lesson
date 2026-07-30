"""FastAPI 엔트리포인트. 모든 라우트는 /api 프리픽스 (traefik PathPrefix 라우팅)."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_contents import router as admin_contents_router
from app.api.admin_themes import router as admin_themes_router
from app.api.admin_users import router as admin_users_router
from app.api.agent import router as agent_router
from app.api.auth import me_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.contents import router as contents_router
from app.api.friends import router as friends_router
from app.api.game import router as game_router
from app.api.game import ws_router as game_ws_router
from app.api.my_contents import router as my_contents_router
from app.api.notifications import router as notifications_router
from app.api.push import router as push_router
from app.api.study import cards_router, settings_router
from app.api.study import router as study_router
from app.api.themes import router as themes_router
from app.core.config import assert_production_secrets, get_settings
from app.core.db import get_db
from app.workers.queue import start_workers, stop_workers
from app.workers.reminders import start_reminders, stop_reminders

logging.basicConfig(level=logging.INFO)


class AgentPollFilter(logging.Filter):
    """자막 수집기 폴링 액세스 로그 제거 — 수 초 간격 폴링이 로그를 도배해
    실제 오류 진단을 방해한다 (2026-07-15 실측)."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "/api/agent/pending-transcripts" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(AgentPollFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    assert_production_secrets(settings)
    if settings.enable_workers:
        await start_workers()
        start_reminders()
    yield
    stop_reminders()
    await stop_workers()


app = FastAPI(title="eng-lesson API", docs_url=None, redoc_url=None, lifespan=lifespan)

app.include_router(auth_router, prefix="/api")
app.include_router(me_router, prefix="/api")
app.include_router(admin_contents_router, prefix="/api")
app.include_router(admin_themes_router, prefix="/api")
app.include_router(admin_users_router, prefix="/api")
app.include_router(contents_router, prefix="/api")
app.include_router(my_contents_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(study_router, prefix="/api")
app.include_router(cards_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(themes_router, prefix="/api")
app.include_router(friends_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(push_router, prefix="/api")
app.include_router(game_router, prefix="/api")
app.include_router(game_ws_router)  # /ws/game (traefik PathPrefix:/ws)


@app.get("/api/health")
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
