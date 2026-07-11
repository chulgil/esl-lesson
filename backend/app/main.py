"""FastAPI 엔트리포인트. 모든 라우트는 /api 프리픽스 (traefik PathPrefix 라우팅)."""

import logging
from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import me_router
from app.api.auth import router as auth_router
from app.core.db import get_db

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="eng-lesson API", docs_url=None, redoc_url=None)

app.include_router(auth_router, prefix="/api")
app.include_router(me_router, prefix="/api")


@app.get("/api/health")
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
