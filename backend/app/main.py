"""FastAPI 엔트리포인트. 모든 라우트는 /api 프리픽스 (traefik PathPrefix 라우팅)."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_contents import router as admin_contents_router
from app.api.admin_users import router as admin_users_router
from app.api.agent import router as agent_router
from app.api.auth import me_router
from app.api.auth import router as auth_router
from app.api.contents import router as contents_router
from app.api.game import router as game_router
from app.api.game import ws_router as game_ws_router
from app.api.my_contents import router as my_contents_router
from app.api.study import cards_router, settings_router
from app.api.study import router as study_router
from app.core.config import get_settings
from app.core.db import get_db
from app.workers.queue import start_workers, stop_workers

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().enable_workers:
        await start_workers()
    yield
    await stop_workers()


app = FastAPI(title="eng-lesson API", docs_url=None, redoc_url=None, lifespan=lifespan)

app.include_router(auth_router, prefix="/api")
app.include_router(me_router, prefix="/api")
app.include_router(admin_contents_router, prefix="/api")
app.include_router(admin_users_router, prefix="/api")
app.include_router(contents_router, prefix="/api")
app.include_router(my_contents_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(study_router, prefix="/api")
app.include_router(cards_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(game_router, prefix="/api")
app.include_router(game_ws_router)  # /ws/game (traefik PathPrefix:/ws)


@app.get("/api/health")
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
