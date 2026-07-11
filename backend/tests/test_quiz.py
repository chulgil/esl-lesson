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


def test_build_pattern_question_chips_cover_sentence():
    item = make_item(
        item_type="pattern",
        en="It takes time to learn.",
        ko="배우는 데 시간이 걸린다",
        pattern_template="It takes ___ to ...",
    )
    q = build_question(item, [])
    assert q["quiz_mode"] == "pattern"
    for word in "It takes time to learn.".split():
        assert word in q["chips"]
    assert len(q["chips"]) == len("It takes time to learn.".split()) + 2
