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

    async def bad_batch(client, model, batch, source_lang="en"):
        raise ValueError("translation batch size mismatch")

    async def one(client, model, text, source_lang="en"):
        return f"번역:{text}"

    monkeypatch.setattr(extraction, "_translate_batch", bad_batch)
    monkeypatch.setattr(extraction, "_translate_one", one)
    result = await extraction.translate_texts(["a", "b", "c"])
    assert result == ["번역:a", "번역:b", "번역:c"]


async def test_translate_texts_forwards_source_lang_to_batch(monkeypatch):
    """source_lang 파라미터가 배치 번역 호출까지 전달된다 (다국어 소스 지원)."""
    from app.services import extraction

    captured = {}

    async def fake_batch(client, model, batch, source_lang="en"):
        captured["source_lang"] = source_lang
        return [f"번역:{t}" for t in batch]

    monkeypatch.setattr(extraction, "_translate_batch", fake_batch)
    result = await extraction.translate_texts(["こんにちは"], source_lang="ja")
    assert result == ["번역:こんにちは"]
    assert captured["source_lang"] == "ja"

    # 기본값은 하위 호환을 위해 en 유지
    await extraction.translate_texts(["hello"])
    assert captured["source_lang"] == "en"


def test_translate_system_prompt_reflects_source_lang():
    """번역 시스템 프롬프트가 소스 언어 라벨을 반영 — 영어 하드코딩 제거."""
    from app.services.extraction import _translate_system

    assert "일본어" in _translate_system("ja")
    assert "영어" not in _translate_system("ja")
    assert "한국어" in _translate_system("ko")
    assert "영어" in _translate_system("en")


def test_translate_one_system_prompt_reflects_source_lang():
    from app.services.extraction import _translate_one_system

    assert "일본어" in _translate_one_system("ja")
    assert "한국어" in _translate_one_system("ko")
    assert "영어" in _translate_one_system("en")


def test_extract_system_prompt_reflects_source_lang():
    """추출 프롬프트가 소스 언어 라벨을 반영 — ja 콘텐츠에서 '영어' 하드코딩 문구 제거."""
    from app.services.extraction import _extract_system

    ja_system = _extract_system("ja")
    assert "일본어" in ja_system
    assert "영어 스크립트" not in ja_system
    assert "영어 교육" not in ja_system

    en_system = _extract_system("en")
    assert "영어" in en_system

    # 기본값(source_lang 미지정)은 영어 — 기존 콘텐츠 하위 호환
    assert _extract_system("en") == en_system
