"""퀴즈 생성/채점 (docs/specs/learning.md 레벨 1-4)."""

from app.models import LearningItem
from app.services.quiz import (
    build_question,
    grade,
    grade_sentence,
    levenshtein,
    normalize_answer,
)


def make_item(item_type="word", en="resilient", ko="회복력 있는", **kw):
    item = LearningItem(
        id=kw.pop("id", 1),
        item_type=item_type,
        en_text=en,
        ko_text=ko,
        normalized_key=en.lower(),
        **kw,
    )
    item.occurrences = []
    return item


def test_normalize_answer_handles_contractions_and_punctuation():
    assert normalize_answer("Don't worry, it's fine!") == "do not worry it is fine"
    assert normalize_answer("  There IS a tree.  ") == "there is a tree"


def test_levenshtein():
    assert levenshtein("tree", "tree") == 0
    assert levenshtein("tree", "trea") == 1
    assert levenshtein("a tree", "the tree") == 3


def test_grade_sentence_allows_near_miss():
    expected = "There is a tree over there."
    assert grade_sentence(expected, "there is a tree over there") == (True, True)
    correct, exact = grade_sentence(expected, "There is a tre over there")
    assert correct and not exact
    correct, _ = grade_sentence(expected, "A cat sat on the mat")
    assert not correct


def test_grade_by_mode():
    word = make_item()
    assert grade(word, "choice_en2ko", "회복력 있는")
    assert not grade(word, "choice_en2ko", "명백한")
    assert grade(word, "choice_ko2en", "Resilient")

    sentence = make_item(item_type="sentence", en="There is a tree.", ko="나무가 있다")
    assert grade(sentence, "compose", "there is a tree")


def test_build_word_question_has_answer_among_choices():
    pool = [make_item(id=i, en=f"word{i}", ko=f"뜻{i}") for i in range(2, 8)]
    item = make_item()
    q = build_question(item, [item, *pool])
    assert q["quiz_mode"] in ("choice_en2ko", "choice_ko2en")
    assert len(q["choices"]) == 4
    answer = item.ko_text if q["quiz_mode"] == "choice_en2ko" else item.en_text
    assert answer in q["choices"]


def test_build_word_question_pads_with_fallback_when_pool_small():
    item = make_item()
    q = build_question(item, [item])  # 오답 풀 없음
    assert len(q["choices"]) == 4


def test_build_sentence_question_includes_thinking_hint():
    item = make_item(
        item_type="sentence",
        en="There is a tree over there.",
        ko="저기에 나무가 있다.",
        hint_thinking="있다, 나무가, 저기에",
    )
    q = build_question(item, [])
    assert q["quiz_mode"] == "compose"
    assert q["hint_thinking"] == "있다, 나무가, 저기에"
    assert q["prompt_ko"] == "저기에 나무가 있다."


def test_build_pattern_question_blanks_only(monkeypatch):
    """레벨3: 밑줄(___) 부분만 조립 — 템플릿 고정부는 완성된 채 표시 (2026-07-31 보고).

    template "It takes ___ to ..." x 문장 "It takes time to learn."
    → 고정부 It takes/to 는 표시, 조립 대상은 time·learn. 뿐."""
    item = make_item(
        item_type="pattern",
        en="It takes time to learn.",
        ko="배우는 데 시간이 걸린다",
        pattern_template="It takes ___ to ...",
    )
    q = build_question(item, [])
    assert q["quiz_mode"] == "pattern"
    # 조립 칩 = 밑줄 단어 2개 + 오답 칩 2개 — 고정부(It/takes/to)는 칩에 없다
    assert len(q["chips"]) == 2 + 2
    assert "time" in q["chips"] and "learn." in q["chips"]
    for fixed in ("It", "takes", "to"):
        assert fixed not in q["chips"]
    # 표시 문장 = 고정부 완성 + 밑줄 자리만 ___ (진행형 힌트도 밑줄 단어 기준)
    assert q["template"] == "It takes ___ to ___"
    assert q["hint_answer"] == "time learn."
    # 밑줄(___)의 한글 대응을 명시 — 어느 부분인지 혼동 방지 (2026-07-14)
    assert q["blank_ko"] == "배우는 데 시간이 걸린다"


def test_pattern_grade_expects_blank_words_only():
    item = make_item(
        item_type="pattern",
        en="It takes time to learn.",
        ko="배우는 데 시간이 걸린다",
        pattern_template="It takes ___ to ...",
    )
    assert grade(item, "pattern", "time learn")
    assert not grade(item, "pattern", "banana apple")


def test_pattern_without_placeholder_falls_back_to_full_sentence():
    """템플릿에 밑줄이 없으면(문장 전체가 패턴) 기존 전체 조립 유지."""
    item = make_item(
        item_type="pattern",
        en="We think it's quite the opposite",
        ko="우리는 정반대라고 생각해요",
        pattern_template="We think it's quite the opposite",
    )
    q = build_question(item, [])
    for word in "We think it's quite the opposite".split():
        assert word in q["chips"]
    assert grade(item, "pattern", "We think it's quite the opposite")


def test_pattern_template_mismatch_falls_back_to_full_sentence():
    """고정부가 문장과 안 맞으면(추출 불일치) 전체 조립으로 안전 폴백."""
    item = make_item(
        item_type="pattern",
        en="Something completely different here.",
        ko="전혀 다른 문장",
        pattern_template="It takes ___ to ...",
    )
    q = build_question(item, [])
    for word in "Something completely different here.".split():
        assert word in q["chips"]
    assert grade(item, "pattern", "Something completely different here.")
