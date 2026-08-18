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
    if quiz_mode in ("pattern", "compose", "sentence_assemble"):
        if quiz_mode == "pattern":
            # 밑줄 단어들만 기대 — 문항 생성(pattern_blank_split)과 동일 분해
            split = pattern_blank_split(item)
            expected = " ".join(split[1]) if split is not None else _pattern_answer(item)
        else:
            expected = item.en_text
        correct, _exact = grade_sentence(expected, answer)
        return correct
    raise ValueError(f"unknown quiz_mode: {quiz_mode}")


def _pattern_answer(item: LearningItem) -> str:
    """패턴 조립 문제의 정답 문장 = 대표 출처 문장(없으면 en_text)."""
    for occ in item.occurrences:
        if occ.context_en:
            return occ.context_en
    return item.en_text


# 템플릿 자리표시자 — ___/~/.../단독 X. 구두점이 붙은 형태(`___?` `___.`)도 인식
# (프로드 실측: 미인식 시 90건 중 40건이 불필요 폴백 — 2026-07-31 데이터 검증)
_PLACEHOLDER_RE = re.compile(r"^\W*(?:_{2,}|~|\.{3,})\W*$")


def _norm_word(word: str) -> str:
    return re.sub(r"[^a-z0-9']", "", word.lower())


def _is_placeholder(token: str) -> bool:
    return bool(_PLACEHOLDER_RE.match(token)) or _norm_word(token) == "x"


def pattern_blank_split(item: LearningItem) -> tuple[str, list[str]] | None:
    """문장을 템플릿 고정부/밑줄(변수부)로 분해 — (표시 문장, 밑줄 단어들).

    레벨3 은 밑줄 부분만 조립해야 한다 (2026-07-31 보고 — 전체 문장 조립은
    고정부까지 다시 맞추게 해 템플릿 표시와 어긋남). 템플릿의 고정 세그먼트를
    문장에서 순서대로 찾고, **자리표시자 위치의 단어만** 조립 대상으로 남긴다.

    템플릿 밖 주변부(문장 앞뒤의 "And," 같은 잉여 단어)는 밑줄이 아니라
    문맥 — 템플릿이 그 가장자리에 자리표시자를 둘 때만 밑줄로 취급한다
    (프로드 실측: 미처리 시 17건이 사실상 전체 조립으로 퇴화).
    자리표시자가 없거나 고정부가 문장과 안 맞으면 None — 전체 조립 폴백.
    """
    return split_pattern_sentence(item.pattern_template or item.en_text, _pattern_answer(item))


def split_pattern_sentence(template: str, sentence: str) -> tuple[str, list[str]] | None:
    words = sentence.split()
    template_words = template.split()

    segments: list[list[str]] = [[]]
    has_placeholder = False
    for token in template_words:
        if _is_placeholder(token):
            has_placeholder = True
            if segments[-1]:
                segments.append([])
        else:
            segments[-1].append(_norm_word(token))
    leading_placeholder = bool(template_words) and _is_placeholder(template_words[0])
    trailing_placeholder = bool(template_words) and _is_placeholder(template_words[-1])
    segments = [seg for seg in segments if seg]
    if not has_placeholder or not segments:
        return None

    norm_words = [_norm_word(w) for w in words]
    fixed = [False] * len(words)
    pos = 0
    first_start = last_end = None
    for seg in segments:
        found = -1
        # 실화행은 템플릿 선두 단어를 흘리기도 한다 ("It turns out" → "turns out")
        # — 선두를 하나씩 줄여 재시도 (최소 1단어). 2026-07-31 보고 반영
        for drop in range(len(seg)):
            sub = seg[drop:]
            for start in range(pos, len(norm_words) - len(sub) + 1):
                if norm_words[start : start + len(sub)] == sub:
                    found = start
                    break
            if found >= 0:
                seg = sub
                break
        if found < 0:
            return None  # 고정부 불일치 — 안전 폴백
        for i in range(found, found + len(seg)):
            fixed[i] = True
        if first_start is None:
            first_start = found
        last_end = found + len(seg)
        pos = found + len(seg)

    # 템플릿 스팬 밖 가장자리 — 그 자리에 자리표시자가 없으면 문맥(고정 표시)
    if not leading_placeholder and first_start is not None:
        for i in range(first_start):
            fixed[i] = True
    if not trailing_placeholder and last_end is not None:
        for i in range(last_end, len(words)):
            fixed[i] = True

    blanks = [w for w, is_fixed in zip(words, fixed, strict=True) if not is_fixed]
    if not blanks or len(blanks) == len(words):
        return None
    display = " ".join(w if is_fixed else "___" for w, is_fixed in zip(words, fixed, strict=True))
    return display, blanks


def build_question(
    item: LearningItem,
    pool: list[LearningItem],
    similar: list[dict] | None = None,
    *,
    study_level: int = 4,
    deck_sentences: list[str] | None = None,
) -> dict:
    """카드 1장 -> 퀴즈 문항. pool 은 같은 타입 approved 항목 (오답 보기 샘플링용).

    similar: 임베딩 최근접 이웃 (P2 — 있으면 오답 선지에 우선 배치해 변별 학습).
    study_level·deck_sentences: chat 덱 문장 전용 — deck_sentences(같은 덱 문장
    텍스트)가 주어지면 형식 사다리로 출제: 레벨 1 뜻 매칭 선다 → 2 청크 조립 →
    3 단어 칩 조립 → 4 타이핑 (proposal/level-format-fit-2026-08.md,
    docs/specs/my-phrases.md 레벨별 학습카드). 일반 문장은 그대로 타이핑.
    """
    context = next((o.context_en for o in item.occurrences if o.context_en), None)
    context_ko = next((o.context_ko for o in item.occurrences if o.context_ko), None)

    if item.item_type == "word":
        return _word_question(item, pool, context, similar)
    if item.item_type == "idiom":
        return _idiom_question(item, pool, context, similar)
    if item.item_type == "pattern":
        return _pattern_question(item, context, context_ko)
    if deck_sentences is not None and study_level <= 3:
        if study_level <= 1:
            choice = _sentence_choice_question(item, deck_sentences)
            if choice is not None:
                return choice
            # 덱 문장이 4개 미만이라 선다 불가 — 한 단계 위 형식으로 폴백
            return _sentence_chunk_question(item, deck_sentences)
        if study_level == 2:
            return _sentence_chunk_question(item, deck_sentences)
        return _sentence_assemble_question(item, deck_sentences)
    return _sentence_question(item)


def _distractors(
    item: LearningItem,
    pool: list[LearningItem],
    field: str,
    preferred: list[dict] | None = None,
) -> list[str]:
    answer = getattr(item, field)
    picked: list[str] = []
    # 임베딩 유사단어를 최대 2개 우선 배치 — 3개 전부 유사면 난이도 급상승이라 2+1 배합 (P2)
    for cand in preferred or []:
        value = cand.get(field)
        if value and value != answer and value not in picked:
            picked.append(value)
        if len(picked) >= 2:
            break
    candidates = list(
        {
            getattr(p, field)
            for p in pool
            if p.id != item.id and getattr(p, field) != answer and getattr(p, field) not in picked
        }
    )
    random.shuffle(candidates)
    picked.extend(candidates[: 3 - len(picked)])
    fallback = FALLBACK_KO if field == "ko_text" else FALLBACK_EN
    for value in fallback:
        if len(picked) >= 3:
            break
        if value != answer and value not in picked:
            picked.append(value)
    return picked


def _choice_refs(
    item: LearningItem,
    choices: list[str],
    field: str,
    pool: list[LearningItem],
    preferred: list[dict] | None = None,
) -> list[dict]:
    """보기 텍스트 → 출처 항목 매핑 — 피드백 화면 '다른 보기 단어 정보' 진입용
    (docs/specs/word-insight.md). 더미 폴백 보기는 출처 항목이 없어 제외된다."""
    wanted = set(choices)
    by_text: dict[str, dict] = {}
    for cand in preferred or []:
        value = cand.get(field)
        if value in wanted and value not in by_text and cand.get("id") is not None:
            # similar_items 는 id/en/ko 를 항상 주지만, 호출자가 최소 키만 줄 수도 있다
            by_text[value] = {
                "item_id": cand["id"],
                "en_text": cand.get("en_text", ""),
                "ko_text": cand.get("ko_text", ""),
            }
    for p in pool:
        value = getattr(p, field)
        if value in wanted and value not in by_text:
            by_text[value] = {"item_id": p.id, "en_text": p.en_text, "ko_text": p.ko_text}
    # 정답 텍스트는 항상 출제 항목 자신으로 — 풀에 같은 표기가 있어도 덮는다
    by_text[getattr(item, field)] = {
        "item_id": item.id,
        "en_text": item.en_text,
        "ko_text": item.ko_text,
    }
    return [{"text": c, **by_text[c]} for c in choices if c in by_text]


def _mask_context(context: str | None, target: str) -> str | None:
    if not context:
        return None
    pattern = re.compile(re.escape(target), re.IGNORECASE)
    if not pattern.search(context):
        return context
    return pattern.sub("___", context)


def _word_question(
    item: LearningItem,
    pool: list[LearningItem],
    context: str | None,
    similar: list[dict] | None = None,
) -> dict:
    mode = random.choice(["choice_en2ko", "choice_ko2en"])
    if mode == "choice_en2ko":
        prompt, answer_field = item.en_text, "ko_text"
    else:
        prompt, answer_field = item.ko_text, "en_text"
    choices = [getattr(item, answer_field), *_distractors(item, pool, answer_field, similar)]
    random.shuffle(choices)
    return {
        "quiz_mode": mode,
        "level": 1,
        "hint_answer": getattr(item, answer_field),
        "prompt": prompt,
        "choices": choices,
        "choice_refs": _choice_refs(item, choices, answer_field, pool, similar),
        "context": _mask_context(context, item.en_text),
    }


def _idiom_question(
    item: LearningItem,
    pool: list[LearningItem],
    context: str | None,
    similar: list[dict] | None = None,
) -> dict:
    masked = _mask_context(context, item.en_text)
    if masked and "___" in masked:
        choices = [item.en_text, *_distractors(item, pool, "en_text", similar)]
        random.shuffle(choices)
        return {
            "quiz_mode": "cloze",
            "level": 2,
            "hint_answer": item.en_text,
            "prompt": masked,
            "prompt_ko": item.ko_text,
            "choices": choices,
            "choice_refs": _choice_refs(item, choices, "en_text", pool, similar),
            "context": None,
        }
    # 문맥이 없으면 뜻 매칭 선다로 폴백
    choices = [item.ko_text, *_distractors(item, pool, "ko_text", similar)]
    random.shuffle(choices)
    return {
        "quiz_mode": "choice_en2ko",
        "level": 2,
        "hint_answer": item.ko_text,
        "prompt": item.en_text,
        "choices": choices,
        "choice_refs": _choice_refs(item, choices, "ko_text", pool, similar),
        "context": None,
    }


def _pattern_question(item: LearningItem, context: str | None, context_ko: str | None) -> dict:
    sentence = context or item.en_text
    words = sentence.split()
    # 밑줄 부분만 조립 (2026-07-31) — 분해 실패 시 전체 조립 폴백
    split = pattern_blank_split(item)
    if split is not None:
        display, assemble_words = split
    else:
        display, assemble_words = (item.pattern_template or item.en_text), words
    decoys = random.sample([w for w in FALLBACK_EN if w not in words], 2)
    chips = list(assemble_words) + decoys
    random.shuffle(chips)
    return {
        "quiz_mode": "pattern",
        "level": 3,
        "hint_answer": " ".join(assemble_words),
        "prompt_ko": context_ko or item.ko_text,
        # 밑줄(___)이 한글 해석의 어느 부분인지 명시 — 혼동 방지 (2026-07-14 피드백)
        "blank_ko": item.ko_text,
        # 고정부는 완성된 문장으로 표시, 조립 자리만 ___
        "template": display,
        "chips": chips,
        "context": None,
    }


def _sentence_question(item: LearningItem) -> dict:
    return {
        "quiz_mode": "compose",
        "level": 4,
        "hint_answer": item.en_text,
        "prompt_ko": item.ko_text,
        "hint_thinking": item.hint_thinking,
        "context": None,
    }


def _deck_pool_words(item: LearningItem, deck_sentences: list[str]) -> list[str]:
    """같은 덱의 다른 문장에서 방해칩 후보 단어 추출 (원문 단어 제외)."""
    own = {_norm_word(w) for w in item.en_text.split()}
    pool = [w.strip(".,!?;:\"'") for text in deck_sentences for w in text.split()]
    return list({w for w in pool if _norm_word(w) and _norm_word(w) not in own})


def _sentence_choice_question(item: LearningItem, deck_sentences: list[str]) -> dict | None:
    """레벨 1 chat 덱 문장 — 뜻 매칭 선다 (recognition, level-format-fit).

    내 원문(ko_text)을 제시하고 같은 덱 문장 4개 중 번역문을 고른다. 오답
    선지가 3개 미만이면 None (호출부가 청크 조립으로 폴백). 채점은 기존
    choice_ko2en 경로(정규화 일치) 재사용.
    """
    answer_norm = normalize_answer(item.en_text)
    candidates = list({s for s in deck_sentences if normalize_answer(s) != answer_norm})
    if len(candidates) < 3:
        return None
    choices = [item.en_text, *random.sample(candidates, 3)]
    random.shuffle(choices)
    return {
        "quiz_mode": "choice_ko2en",
        "level": 4,
        "hint_answer": item.en_text,
        "prompt": item.ko_text,
        "choices": choices,
        "context": None,
    }


def _sentence_chunk_question(item: LearningItem, deck_sentences: list[str]) -> dict:
    """레벨 2 chat 덱 문장 — 청크 조립 (cued recall 저부하, level-format-fit).

    문장을 2~4덩이(칩 최대 4개 — WM 4±1 정합)로 균등 분절해 배열한다.
    방해칩은 0~1개: 같은 덱 다른 문장의 연속 단어 조각, 원문에 없는 단어를
    반드시 포함할 때만. 채점은 sentence_assemble 경로(청크를 공백으로 이어
    붙이면 en_text — 정규화가 공백을 접는다) 그대로 합류한다.
    """
    words = item.en_text.split()
    n = len(words)
    k = min(4, n, max(2, (n + 1) // 2))
    size = (n + k - 1) // k if k else 1
    chunks = [" ".join(words[i : i + size]) for i in range(0, n, size)]

    own = {_norm_word(w) for w in words}
    chunk_norms = {normalize_answer(c) for c in chunks}
    decoy = None
    answer_norm = normalize_answer(item.en_text)
    others = [s for s in deck_sentences if normalize_answer(s) != answer_norm]
    random.shuffle(others)
    for text in others:
        other_words = [w.strip(".,!?;:\"'") for w in text.split() if w.strip(".,!?;:\"'")]
        candidate_words = other_words[: max(1, min(size, len(other_words)))]
        candidate = " ".join(candidate_words)
        has_foreign = any(_norm_word(w) not in own for w in candidate_words)
        if candidate and has_foreign and normalize_answer(candidate) not in chunk_norms:
            decoy = candidate
            break
    chips = [*chunks, *([decoy] if decoy else [])]
    random.shuffle(chips)
    return {
        "quiz_mode": "sentence_assemble",
        "level": 4,
        "hint_answer": item.en_text,
        "prompt_ko": item.ko_text,
        "chips": chips,
        "context": None,
    }


def _sentence_assemble_question(item: LearningItem, deck_sentences: list[str]) -> dict:
    """레벨 3 chat 덱 문장 카드 — 단어 칩 조립 (my-phrases.md 레벨별 학습카드).

    답 = en_text(번역문) 단어를 순서대로 조립. 오답 칩은 같은 덱의 다른 문장
    단어에서 최대 2개 샘플링(level-format-fit: 기존 3개에서 축소. 없으면 칩
    없이 순서 조립만). 채점은 compose 와 동일 경로(정규화 후 일치, Levenshtein
    허용)로 합류한다.
    """
    words = item.en_text.split()
    decoy_candidates = _deck_pool_words(item, deck_sentences)
    random.shuffle(decoy_candidates)
    decoys = decoy_candidates[:2]
    chips = [*words, *decoys]
    random.shuffle(chips)
    return {
        "quiz_mode": "sentence_assemble",
        "level": 4,
        "hint_answer": item.en_text,
        "prompt_ko": item.ko_text,
        "chips": chips,
        "context": None,
    }
