"""채팅 자동번역 API 동봉 — 목록 조회 + 단건 엔드포인트 (docs/specs/chat-translation.md)."""

import pytest

from app.models import UserSettings
from app.services import chat as chat_service
from app.services import translation as translation_service
from tests.test_chat import login, send_body, two_friends
from tests.test_my_contents import login_as


@pytest.fixture(autouse=True)
def _fresh_caches():
    """test_chat.py 와 동일 격리 — 인프로세스 캐시가 파일 경계를 넘어 새지 않게."""
    chat_service.reset_caches()
    yield
    chat_service.reset_caches()


async def enable_translate(db, user_id, primary="ko", learning=None):
    settings = await db.get(UserSettings, user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
    settings.chat_translate = True
    settings.primary_lang = primary
    settings.learning_langs = learning or ["en"]
    await db.commit()
    return settings


async def stub_translation(monkeypatch, mapping):
    """text -> (translated_text, engine) 매핑으로 엔진 체인을 대체 — 실호출 금지.

    타깃 언어(lang)는 translate_chat 이 뷰어 설정에서 직접 계산하므로 매핑에
    넣지 않는다 — 여기선 엔진이 반환하는 (번역문, engine) 만 흉내낸다."""

    async def fake_chain(text, target):
        result = mapping.get(text)
        if result is None:
            return None
        return result

    monkeypatch.setattr(translation_service, "_translate_via_chain", fake_chain)


async def test_messages_omit_translation_field_when_setting_off(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.post("/api/chat/messages", json=send_body(b.id, "hello", "cid-tr00001"))

    res = (await client.get(f"/api/chat/with/{b.id}/messages")).json()
    assert res["translate"] is False
    assert all("translation" not in m for m in res["items"])


async def test_messages_attach_translation_when_setting_on(client, db_session, monkeypatch):
    a, b = await two_friends(client, db_session)
    await stub_translation(monkeypatch, {"hello": ("안녕", "haiku")})
    await login(client, db_session, a)
    await client.post("/api/chat/messages", json=send_body(b.id, "hello", "cid-tr00002"))
    await enable_translate(db_session, a.id)

    res = (await client.get(f"/api/chat/with/{b.id}/messages")).json()
    assert res["translate"] is True
    row = next(m for m in res["items"] if m["body"] == "hello")
    assert row["translation"] == {"lang": "ko", "text": "안녕"}


async def test_messages_translation_direction_uses_viewer_settings(client, db_session, monkeypatch):
    """번역 방향은 조회하는 사람(viewer)의 설정 기준 — 상대 설정과 무관."""
    a, b = await two_friends(client, db_session)
    await stub_translation(monkeypatch, {"hello": ("안녕", "haiku")})
    await login(client, db_session, a)
    await client.post("/api/chat/messages", json=send_body(b.id, "hello", "cid-tr00003"))

    # b 는 번역을 켜지 않음 — a 가 조회할 때만 번역 필드가 붙는다
    await login(client, db_session, b)
    off = (await client.get(f"/api/chat/with/{a.id}/messages")).json()
    assert off["translate"] is False

    await enable_translate(db_session, a.id)
    await login(client, db_session, a)
    on = (await client.get(f"/api/chat/with/{b.id}/messages")).json()
    assert on["translate"] is True


async def test_messages_skips_deleted_and_empty_body(client, db_session, monkeypatch):
    a, b = await two_friends(client, db_session)
    called_texts: list[str] = []

    async def fake_chain(text, target):
        called_texts.append(text)
        return "x", "haiku"

    monkeypatch.setattr(translation_service, "_translate_via_chain", fake_chain)
    await login(client, db_session, a)
    sent = await client.post(
        "/api/chat/messages", json=send_body(b.id, "지울 메시지", "cid-tr00004")
    )
    await client.delete(f"/api/chat/messages/{sent.json()['id']}")
    await enable_translate(db_session, a.id)

    res = (await client.get(f"/api/chat/with/{b.id}/messages")).json()
    deleted_row = next(m for m in res["items"] if m["id"] == sent.json()["id"])
    assert deleted_row["translation"] is None
    assert called_texts == []  # 삭제된 메시지는 엔진 호출 안 함


async def test_messages_translation_window_caps_at_30(client, db_session, monkeypatch):
    """비용 상한 — 최신 30개만 번역 대상, 그 밖은 translation: null."""
    a, b = await two_friends(client, db_session)
    called_texts: list[str] = []

    async def fake_chain(text, target):
        called_texts.append(text)
        return "t", "haiku"

    monkeypatch.setattr(translation_service, "_translate_via_chain", fake_chain)
    await login(client, db_session, a)
    for i in range(35):
        body = send_body(b.id, f"msg number {i}", f"cid-win{i:05d}")
        await client.post("/api/chat/messages", json=body)
    await enable_translate(db_session, a.id)

    res = (await client.get(f"/api/chat/with/{b.id}/messages?limit=50")).json()
    items = res["items"]
    assert len(items) == 35
    # 오래된 5개는 번역 대상 밖
    for m in items[:5]:
        assert m["translation"] is None
    # 최신 30개는 번역 시도됨 (캐시 미스 → 엔진 1회씩)
    # msg number N 은 영문 → 뷰어 기본 설정(primary=ko)과 달라 target=ko(모국어로 번역)
    for m in items[5:]:
        assert m["translation"] == {"lang": "ko", "text": "t"}
    assert len(called_texts) == 30


# --- 단건 엔드포인트 ---------------------------------------------------------------


async def test_single_message_translation_requires_participant(client, db_session, monkeypatch):
    """단건 엔드포인트는 방 기준 번역 — 뷰어 설정(chat_translate) 과 무관하게 항상
    시도한다 (docs/specs/chat-language-rooms.md 번역 규칙, 2026-08-14 개편)."""
    a, b = await two_friends(client, db_session)
    await stub_translation(monkeypatch, {"안녕": ("hi", "haiku")})
    await login(client, db_session, a)
    sent = (
        await client.post("/api/chat/messages", json=send_body(b.id, "안녕", "cid-tr00005"))
    ).json()

    await login_as(client, db_session, "outsider@example.com")
    res = await client.get(f"/api/chat/messages/{sent['id']}/translation")
    assert res.status_code == 403

    await login(client, db_session, a)
    ok = await client.get(f"/api/chat/messages/{sent['id']}/translation")
    assert ok.status_code == 200
    # 방 기본 언어쌍은 ko→en — "안녕"(ko) 은 방 target(en) 과 달라 항상 번역된다
    assert ok.json()["translation"] == {"lang": "en", "text": "hi"}


async def test_single_message_translation_missing_message_is_404(client, db_session):
    a, _b = await two_friends(client, db_session)
    await login(client, db_session, a)
    res = await client.get("/api/chat/messages/999999/translation")
    assert res.status_code == 404


async def test_single_message_translation_null_when_setting_off(client, db_session, monkeypatch):
    a, b = await two_friends(client, db_session)
    await stub_translation(monkeypatch, {"hi there": ("안녕", "haiku")})
    await login(client, db_session, a)
    sent = (
        await client.post("/api/chat/messages", json=send_body(b.id, "hi there", "cid-tr00006"))
    ).json()
    # chat_translate 기본값 False — 켜지 않음
    res = await client.get(f"/api/chat/messages/{sent['id']}/translation")
    assert res.status_code == 200
    assert res.json()["translation"] is None


async def test_scope_default_translates_only_my_messages(client, db_session, monkeypatch):
    """기본 범위 = 내 글만 (2026-08-12 요청) — 상대 글은 번역이 붙지 않는다."""
    a, b = await two_friends(client, db_session)
    await stub_translation(
        monkeypatch, {"mine msg": ("내 글", "haiku"), "theirs msg": ("상대 글", "haiku")}
    )
    await login(client, db_session, b)
    await client.post("/api/chat/messages", json=send_body(a.id, "theirs msg", "cid-sc00001"))
    await login(client, db_session, a)
    await client.post("/api/chat/messages", json=send_body(b.id, "mine msg", "cid-sc00002"))
    await enable_translate(db_session, a.id)

    res = (await client.get(f"/api/chat/with/{b.id}/messages")).json()
    assert res["translate_mine"] is True and res["translate_theirs"] is False
    mine = next(m for m in res["items"] if m["body"] == "mine msg")
    theirs = next(m for m in res["items"] if m["body"] == "theirs msg")
    assert mine["translation"] == {"lang": "ko", "text": "내 글"}
    assert theirs["translation"] is None


async def test_scope_checkboxes_control_each_side(client, db_session, monkeypatch):
    """둘 다 체크 = 전체 번역 / 상대만 체크 = 상대 글만 (목록 조회 — 개인 설정 기반).

    단건 엔드포인트(GET /messages/{id}/translation)는 2026-08-14 개편으로 방
    기준 번역으로 전환돼 이 scope 설정과 무관해졌다 — test_chat_translation.py
    의 단건 테스트들 참조."""
    a, b = await two_friends(client, db_session)
    await stub_translation(monkeypatch, {"mine2": ("m", "haiku"), "theirs2": ("t", "haiku")})
    await login(client, db_session, b)
    await client.post("/api/chat/messages", json=send_body(a.id, "theirs2", "cid-sc00003"))
    await login(client, db_session, a)
    await client.post("/api/chat/messages", json=send_body(b.id, "mine2", "cid-sc00004"))
    settings = await enable_translate(db_session, a.id)

    # 둘 다 체크 — 전체 번역 (기존 동작)
    settings.translate_theirs = True
    await db_session.commit()
    res = (await client.get(f"/api/chat/with/{b.id}/messages")).json()
    assert res["translate_theirs"] is True
    assert all(
        m["translation"] is not None for m in res["items"] if m["body"] in ("mine2", "theirs2")
    )

    # 상대 글만 체크 — 내 글은 번역 안 붙음
    settings.translate_mine = False
    await db_session.commit()
    res = (await client.get(f"/api/chat/with/{b.id}/messages")).json()
    mine = next(m for m in res["items"] if m["body"] == "mine2")
    assert mine["translation"] is None


async def test_single_message_translation_scope_blocks_theirs_by_default(
    client, db_session, monkeypatch
):
    """WS 수신분 단건 조회 — 기본(내 글만)에서는 상대 글이 null."""
    a, b = await two_friends(client, db_session)
    await stub_translation(monkeypatch, {"from peer": ("상대", "haiku")})
    await login(client, db_session, b)
    sent = (
        await client.post("/api/chat/messages", json=send_body(a.id, "from peer", "cid-sc00005"))
    ).json()
    await enable_translate(db_session, a.id)
    await login(client, db_session, a)

    res = await client.get(f"/api/chat/messages/{sent['id']}/translation")
    assert res.status_code == 200
    assert res.json()["translation"] is None


async def test_single_message_translation_null_for_deleted(client, db_session, monkeypatch):
    a, b = await two_friends(client, db_session)
    await stub_translation(monkeypatch, {"del me": ("안녕", "haiku")})
    await login(client, db_session, a)
    sent = (
        await client.post("/api/chat/messages", json=send_body(b.id, "del me", "cid-tr00007"))
    ).json()
    await client.delete(f"/api/chat/messages/{sent['id']}")
    await enable_translate(db_session, a.id)

    res = await client.get(f"/api/chat/messages/{sent['id']}/translation")
    assert res.status_code == 200
    assert res.json()["translation"] is None
