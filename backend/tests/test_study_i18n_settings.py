"""다국어 학습 설정 — primary_lang/learning_langs/chat_translate (chat-translation.md)."""

from tests.test_study import login


async def test_settings_default_values(client, db_session):
    await login(client, db_session)
    res = await client.get("/api/settings")
    body = res.json()
    assert body["primary_lang"] == "ko"
    assert body["learning_langs"] == ["en"]
    assert body["chat_translate"] is False


async def test_settings_patch_updates_lang_fields(client, db_session):
    await login(client, db_session)
    res = await client.patch(
        "/api/settings",
        json={"primary_lang": "en", "learning_langs": ["ja"], "chat_translate": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["primary_lang"] == "en"
    assert body["learning_langs"] == ["ja"]
    assert body["chat_translate"] is True

    # 재조회에도 반영
    again = (await client.get("/api/settings")).json()
    assert again["primary_lang"] == "en"
    assert again["learning_langs"] == ["ja"]
    assert again["chat_translate"] is True


async def test_settings_patch_rejects_unsupported_primary(client, db_session):
    await login(client, db_session)
    res = await client.patch("/api/settings", json={"primary_lang": "fr"})
    assert res.status_code == 422


async def test_settings_patch_rejects_unsupported_learning_lang(client, db_session):
    await login(client, db_session)
    res = await client.patch("/api/settings", json={"learning_langs": ["fr"]})
    assert res.status_code == 422


async def test_settings_patch_rejects_empty_learning_langs(client, db_session):
    await login(client, db_session)
    res = await client.patch("/api/settings", json={"learning_langs": []})
    assert res.status_code == 422


async def test_settings_patch_rejects_primary_in_learning(client, db_session):
    await login(client, db_session)
    # 명시적으로 같은 값으로 지정하면 거부
    res = await client.patch("/api/settings", json={"primary_lang": "en", "learning_langs": ["en"]})
    assert res.status_code == 422


async def test_settings_patch_cross_validates_against_existing_value(client, db_session):
    """primary_lang 만 바꿔도 기존 learning_langs 와의 중복은 거부돼야 한다."""
    await login(client, db_session)
    # 먼저 learning_langs=[ja] 로 설정
    await client.patch("/api/settings", json={"learning_langs": ["ja"]})
    # 이제 primary_lang 을 ja 로 바꾸면 학습언어와 겹침 — 거부
    res = await client.patch("/api/settings", json={"primary_lang": "ja"})
    assert res.status_code == 422


async def test_settings_patch_only_chat_translate(client, db_session):
    await login(client, db_session)
    res = await client.patch("/api/settings", json={"chat_translate": True})
    assert res.status_code == 200
    assert res.json()["chat_translate"] is True
    assert res.json()["primary_lang"] == "ko"  # 다른 필드는 그대로
