"""단어 인사이트 — lazy 생성 + 캐시 + API (docs/proposal/word-insight.md P1)."""

from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models import WordInsight
from tests.test_study import login, seed_items

FAKE_PAYLOAD = {
    "ipa": "/rɪˈzɪliənt/",
    "pos": "adjective",
    "nuance_ko": "긍정적 톤 — 사람/시스템 모두에 씀, 문어·구어 무난",
    "examples": [
        {
            "en": "She stayed resilient after the failure.",
            "ko": "그녀는 실패 후에도 회복력을 유지했다.",
        },
        {"en": "A resilient economy recovers quickly.", "ko": "회복력 있는 경제는 빨리 회복한다."},
    ],
    "collocations": ["resilient economy", "remain resilient", "resilient to stress"],
    "synonyms": [
        {"word": "tough", "ko": "강인한", "diff_ko": "물리적 단단함/사람의 강함에 폭넓게"},
    ],
    "confusables": [
        {
            "word": "resistant",
            "ko": "저항성 있는",
            "diff_ko": "변화·영향을 막는 쪽 (회복이 아니라 방어)",
        },
    ],
}


async def test_insight_generated_once_and_cached(db_session):
    """최초 조회 시 LLM 1회 생성, 재조회는 캐시 반환 (LLM 재호출 없음)."""
    from app.services import insights

    items = await seed_items(db_session, count=1)
    item_id = items[0].id

    with patch.object(insights, "_generate", new=AsyncMock(return_value=FAKE_PAYLOAD)) as gen:
        first = await insights.get_or_generate(db_session, item_id)
        second = await insights.get_or_generate(db_session, item_id)

    assert first == FAKE_PAYLOAD and second == FAKE_PAYLOAD
    assert gen.await_count == 1  # 캐시 적중 — 두 번째 호출은 생성 없음
    rows = (await db_session.execute(select(WordInsight))).scalars().all()
    assert len(rows) == 1 and rows[0].item_id == item_id


async def test_insight_unknown_item_returns_none(db_session):
    from app.services import insights

    assert await insights.get_or_generate(db_session, 999_999) is None


async def test_insight_api_endpoint(client, db_session):
    from app.services import insights

    await login(client, db_session)
    items = await seed_items(db_session, count=1)

    with patch.object(insights, "_generate", new=AsyncMock(return_value=FAKE_PAYLOAD)):
        res = await client.get(f"/api/study/items/{items[0].id}/insight")
    assert res.status_code == 200
    body = res.json()
    assert body["ipa"] == FAKE_PAYLOAD["ipa"]
    assert len(body["examples"]) == 2

    missing = await client.get("/api/study/items/999999/insight")
    assert missing.status_code == 404


def test_parse_json_tolerates_fences():
    """모델이 ```json 펜스나 설명을 붙여도 JSON 만 뽑아낸다."""
    from app.services.insights import _parse_json

    fenced = '```json\n{"ipa": "/a/"}\n```'
    assert _parse_json(fenced) == {"ipa": "/a/"}
    chatty = 'Here you go:\n{"pos": "noun"} hope this helps'
    assert _parse_json(chatty) == {"pos": "noun"}


class _Block:
    def __init__(self, text=None):
        if text is not None:
            self.text = text


class _Res:
    def __init__(self, text, stop_reason="end_turn", leading_non_text=False):
        self.content = ([_Block()] if leading_non_text else []) + [_Block(text)]
        self.stop_reason = stop_reason


async def test_generate_retries_on_truncation(db_session, monkeypatch):
    """max_tokens 절단(잘린 JSON) → 예산 늘려 1회 재시도 (2026-07-15 delegate 502 실측)."""
    import json

    from app.services import insights

    items = await seed_items(db_session, count=1)
    ok_json = json.dumps(FAKE_PAYLOAD, ensure_ascii=False)
    calls: list[int] = []

    async def fake_create(*, model, max_tokens, messages):
        calls.append(max_tokens)
        if len(calls) == 1:
            return _Res(ok_json[:80], stop_reason="max_tokens")  # 잘린 응답
        return _Res(ok_json, leading_non_text=True)  # thinking 류 선행 블록도 통과

    class FakeClient:
        def __init__(self, **kwargs):
            self.messages = type("M", (), {"create": staticmethod(fake_create)})()

    monkeypatch.setattr(insights, "AsyncAnthropic", FakeClient)
    payload = await insights._generate(items[0], [])
    assert payload == FAKE_PAYLOAD
    assert len(calls) == 2 and calls[1] > calls[0]
