"""추출 필터/청크 로직 (docs/specs/content-pipeline.md 단계 4)."""

from app.services.extraction import _chunk_segments, _filter_items, is_easy_word


def test_easy_word_filter():
    assert is_easy_word("thank")
    assert is_easy_word("Sorry")
    assert not is_easy_word("resilient")
    assert not is_easy_word("get it over with")  # 숙어(공백 포함)는 스톱리스트 미적용


def test_filter_items_drops_basic_and_easy():
    data = {
        "words": [
            {"en": "resilient", "ko": "회복력 있는", "difficulty": "intermediate"},
            {"en": "thank", "ko": "감사하다", "difficulty": "intermediate"},  # 스톱리스트
            {"en": "obscure", "ko": "모호한", "difficulty": "basic"},  # basic 자기평가
        ],
        "idioms": [
            {"en": "get it over with", "ko": "해치우다", "difficulty": "intermediate"},
            {"en": "hello there", "ko": "안녕", "difficulty": "basic"},
        ],
        "patterns": [{"template": "It takes ___ to ...", "ko": "~하는 데 ~가 걸린다"}],
        "sentences": [
            {"en": "There is a tree.", "ko": "나무가 있다", "thinking_ko": "있다, 나무가"}
        ],
    }
    result = _filter_items(data)
    assert [w["en"] for w in result["words"]] == ["resilient"]
    assert [i["en"] for i in result["idioms"]] == ["get it over with"]
    assert len(result["patterns"]) == 1
    assert len(result["sentences"]) == 1


def test_chunk_segments_splits_long_scripts():
    segments = [(i, "word " * 500) for i in range(40)]  # 각 500단어 x 40 = 20,000단어
    chunks = _chunk_segments(segments)
    assert len(chunks) == 3
    assert sum(len(c) for c in chunks) == 40


def test_first_text_skips_thinking_block():
    """claude-sonnet-5 는 thinking 블록이 선행될 수 있다 (2026-07-11 운영 실측)."""
    from types import SimpleNamespace

    from app.services.extraction import _first_text

    res = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking="..."),
            SimpleNamespace(type="text", text='["안녕"]'),
        ]
    )
    assert _first_text(res) == '["안녕"]'


def test_parse_json_array_tolerates_fences_and_preamble():
    """haiku 응답이 코드펜스/서두 텍스트를 붙이는 경우 (2026-07-11 운영 실측)."""
    from app.services.extraction import _parse_json_array

    assert _parse_json_array('["a", "b"]') == ["a", "b"]
    assert _parse_json_array('```json\n["a"]\n```') == ["a"]
    assert _parse_json_array('다음은 번역입니다:\n["안녕", "잘가"]') == ["안녕", "잘가"]


async def test_translate_falls_back_to_per_item(monkeypatch):
    """배치 개수 불일치 시 문장별 번역 폴백 (2026-07-11 운영 실측)."""
    from app.services import extraction

    async def bad_batch(client, model, batch):
        raise ValueError("translation batch size mismatch")

    async def one(client, model, text):
        return f"번역:{text}"

    monkeypatch.setattr(extraction, "_translate_batch", bad_batch)
    monkeypatch.setattr(extraction, "_translate_one", one)
    result = await extraction.translate_texts(["a", "b", "c"])
    assert result == ["번역:a", "번역:b", "번역:c"]
