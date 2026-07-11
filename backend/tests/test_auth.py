"""인증 스펙 검증 (docs/specs/auth.md)."""

import jwt as pyjwt
import pytest
from fastapi import HTTPException

from app.api.auth import upsert_google_user
from app.core.config import get_settings
from app.core.security import (
    SESSION_COOKIE,
    create_session_token,
    create_state_token,
    decode_session_token,
    safe_next_path,
    verify_state_token,
)
from app.models.user import User


def make_userinfo(sub="g-123", email="user@example.com", **over):
    info = {
        "sub": sub,
        "email": email,
        "email_verified": True,
        "name": "Test User",
        "picture": "https://example.com/a.png",
    }
    info.update(over)
    return info


async def test_health(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


async def test_me_requires_session(client):
    res = await client.get("/api/me")
    assert res.status_code == 401


async def test_me_with_valid_session(client, db_session):
    user = await upsert_google_user(db_session, make_userinfo(), get_settings())
    client.cookies.set(SESSION_COOKIE, create_session_token(user))
    res = await client.get("/api/me")
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "user@example.com"
    assert body["role"] == "learner"


async def test_me_rejects_tampered_token(client, db_session):
    user = await upsert_google_user(db_session, make_userinfo(), get_settings())
    bad = pyjwt.encode({"sub": str(user.id)}, "wrong-secret", algorithm="HS256")
    client.cookies.set(SESSION_COOKIE, bad)
    res = await client.get("/api/me")
    assert res.status_code == 401


async def test_upsert_promotes_admin_email(db_session):
    user = await upsert_google_user(
        db_session, make_userinfo(sub="g-9", email="boss@example.com"), get_settings()
    )
    assert user.role == "admin"


async def test_upsert_is_idempotent_by_sub(db_session):
    a = await upsert_google_user(db_session, make_userinfo(), get_settings())
    b = await upsert_google_user(db_session, make_userinfo(name="Renamed"), get_settings())
    assert a.id == b.id
    from sqlalchemy import func, select

    count = (await db_session.execute(select(func.count(User.id)))).scalar_one()
    assert count == 1


def test_session_token_roundtrip():
    user = User(id=7, google_sub="g", email="e@x.com", name="n", role="learner")
    claims = decode_session_token(create_session_token(user))
    assert claims["sub"] == "7"
    assert claims["role"] == "learner"


def test_state_token_roundtrip_and_mismatch():
    token, nonce = create_state_token("/study")
    assert verify_state_token(token, nonce) == "/study"
    with pytest.raises(HTTPException):
        verify_state_token(token, "forged-nonce")


def test_safe_next_path_blocks_open_redirect():
    assert safe_next_path("https://evil.com") == "/"
    assert safe_next_path("//evil.com") == "/"
    assert safe_next_path("/admin/contents") == "/admin/contents"
