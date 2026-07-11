"""레벨별 퀴즈 생성/채점 (docs/specs/learning.md).

quiz_mode: choice_en2ko | choice_ko2en | cloze | pattern | compose
"""

import random
import re

from app.models import LearningItem

FALLBACK_KO = ["성취하다", "우연히 마주치다", "결과적으로", "명백한"]
FALLBACK_EN = ["accomplish", "encounter", "consequently", "evident"]

CONTRACTIONS = {
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "can't": "cannot",
    "won't": "will not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "i'm": "i am",
    "it's": "it is",
    "that's": "that is",
    "there's": "there is",
    "let's": "let us",
    "i've": "i have",
    "you're": "you are",
    "they're": "they are",
    "we're": "we are",
    "i'll": "i will",
    "you'll": "you will",
}


def normalize_answer(text: str) -> str:
    """소문자 + 축약형 통일 + 문장부호 제거 + 공백 정규화."""
    lowered = text.lower().strip()
    for contraction, expanded in CONTRACTIONS.items():
        lowered = lowered.replace(contraction, expanded)
    lowered = re.sub(r"[^\w\s']", " ", lowered)
    lowered = lowered.replace("'", "")
    return " ".join(lowered.split())


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def grade_sentence(expected: str, answer: str) -> tuple[bool, bool]:
    """(정답 여부, 완전 일치 여부). 정규화 후 Levenshtein <= 2 는 '거의 정답'으로 인정."""
    norm_expected = normalize_answer(expected)
    norm_answer = normalize_answer(answer)
    if norm_expected == norm_answer:
        return True, True
    return levenshtein(norm_expected, norm_answer) <= 2, False


def grade(item: LearningItem, quiz_mode: str, answer: str) -> bool:
    if quiz_mode == "choice_en2ko":
        return answer.strip() == item.ko_text.strip()
    if quiz_mode in ("choice_ko2en", "cloze"):
        return normalize_answer(answer) == normalize_answer(item.en_text)
    if quiz_mode in ("pattern", "compose"):
        expected = _pattern_answer(item) if quiz_mode == "pattern" else item.en_text
        correct, _exact = grade_sentence(expected, answer)
        return correct
    raise ValueError(f"unknown quiz_mode: {quiz_mode}")


def _pattern_answer(item: LearningItem) -> str:
    """패턴 조립 문제의 정답 문장 = 대표 출처 문장(없으면 en_text)."""
    for occ in item.occurrences:
        if occ.context_en:
            return occ.context_en
    return item.en_text


def build_question(item: LearningItem, pool: list[LearningItem]) -> dict:
    """카드 1장 -> 퀴즈 문항. pool 은 같은 타입 approved 항목 (오답 보기 샘플링용)."""
    context = next((o.context_en for o in item.occurrences if o.context_en), None)
    context_ko = next((o.context_ko for o in item.occurrences if o.context_ko), None)

    if item.item_type == "word":
        return _word_question(item, pool, context)
    if item.item_type == "idiom":
        return _idiom_question(item, pool, context)
    if item.item_type == "pattern":
        return _pattern_question(item, context, context_ko)
    return _sentence_question(item)


def _distractors(item: LearningItem, pool: list[LearningItem], field: str) -> list[str]:
    answer = getattr(item, field)
    candidates = list(
        {getattr(p, field) for p in pool if p.id != item.id and getattr(p, field) != answer}
    )
    random.shuffle(candidates)
    picked = candidates[:3]
    fallback = FALLBACK_KO if field == "ko_text" else FALLBACK_EN
    for value in fallback:
        if len(picked) >= 3:
            break
        if value != answer and value not in picked:
            picked.append(value)
    return picked


def _mask_context(context: str | None, target: str) -> str | None:
    if not context:
        return None
    pattern = re.compile(re.escape(target), re.IGNORECASE)
    if not pattern.search(context):
        return context
    return pattern.sub("___", context)


def _word_question(item: LearningItem, pool: list[LearningItem], context: str | None) -> dict:
    mode = random.choice(["choice_en2ko", "choice_ko2en"])
    if mode == "choice_en2ko":
        prompt, answer_field = item.en_text, "ko_text"
    else:
        prompt, answer_field = item.ko_text, "en_text"
    choices = [getattr(item, answer_field), *_distractors(item, pool, answer_field)]
    random.shuffle(choices)
    return {
        "quiz_mode": mode,
        "level": 1,
        "prompt": prompt,
        "choices": choices,
        "context": _mask_context(context, item.en_text),
    }


def _idiom_question(item: LearningItem, pool: list[LearningItem], context: str | None) -> dict:
    masked = _mask_context(context, item.en_text)
    if masked and "___" in masked:
        choices = [item.en_text, *_distractors(item, pool, "en_text")]
        random.shuffle(choices)
        return {
            "quiz_mode": "cloze",
            "level": 2,
            "prompt": masked,
            "prompt_ko": item.ko_text,
            "choices": choices,
            "context": None,
        }
    # 문맥이 없으면 뜻 매칭 선다로 폴백
    choices = [item.ko_text, *_distractors(item, pool, "ko_text")]
    random.shuffle(choices)
    return {
        "quiz_mode": "choice_en2ko",
        "level": 2,
        "prompt": item.en_text,
        "choices": choices,
        "context": None,
    }


def _pattern_question(item: LearningItem, context: str | None, context_ko: str | None) -> dict:
    sentence = context or item.en_text
    words = sentence.split()
    decoys = random.sample([w for w in FALLBACK_EN if w not in words], 2)
    chips = words + decoys
    random.shuffle(chips)
    return {
        "quiz_mode": "pattern",
        "level": 3,
        "prompt_ko": context_ko or item.ko_text,
        "template": item.pattern_template or item.en_text,
        "chips": chips,
        "context": None,
    }


def _sentence_question(item: LearningItem) -> dict:
    return {
        "quiz_mode": "compose",
        "level": 4,
        "prompt_ko": item.ko_text,
        "hint_thinking": item.hint_thinking,
        "context": None,
    }
