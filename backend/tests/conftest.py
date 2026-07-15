"""테스트 픽스처: 인메모리 sqlite + get_db 오버라이드."""

import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("ADMIN_EMAILS", "boss@example.com")
os.environ.setdefault("ENABLE_WORKERS", "false")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.db import get_db
from app.main import app
from app.models import Base

get_settings.cache_clear()


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def admin_client(client, db_session):
    """admin 세션 쿠키가 설정된 클라이언트."""
    from app.api.auth import upsert_google_user
    from app.core.security import SESSION_COOKIE, create_session_token

    admin = await upsert_google_user(
        db_session,
        {
            "sub": "g-admin",
            "email": "boss@example.com",
            "email_verified": True,
            "name": "Boss",
        },
        get_settings(),
    )
    client.cookies.set(SESSION_COOKIE, create_session_token(admin))
    return client


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def vapid_keys():
    """VAPID 키 설정/해제 — push 관련 테스트 공용."""
    from app.core.config import get_settings

    settings = get_settings()
    settings.vapid_public_key = "test-public-key"
    settings.vapid_private_key = "test-private-key"
    yield settings
    settings.vapid_public_key = ""
    settings.vapid_private_key = ""
