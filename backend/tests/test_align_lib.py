"""에이전트 정렬 라이브러리 — remap 순수 로직 (docs/specs/word-alignment.md)."""

from types import SimpleNamespace

from scripts.lib.align import remap_result_to_segments


def _word(text, start, end):
    return SimpleNamespace(word=text, start=start, end=end)


def _seg(words):
    return SimpleNamespace(words=words)


def test_remap_index_maps_when_counts_match():
    result_segments = [
        _seg([_word(" Hi", 0.10, 0.70), _word(" there", 0.70, 1.40)]),
        _seg([_word(" Bye", 5.20, 5.90)]),
    ]
    out = remap_result_to_segments(result_segments, 2)
    assert out == {
        0: [{"w": "Hi", "s": 100, "e": 700}, {"w": "there", "s": 700, "e": 1400}],
        1: [{"w": "Bye", "s": 5200, "e": 5900}],
    }


def test_remap_returns_none_on_count_mismatch():
    result_segments = [_seg([_word("a", 0.0, 0.1)])]
    assert remap_result_to_segments(result_segments, 2) is None


def test_remap_returns_none_when_segment_has_no_words():
    result_segments = [_seg([_word("a", 0.0, 0.1)]), _seg([])]
    assert remap_result_to_segments(result_segments, 2) is None
