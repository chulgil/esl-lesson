"""Claude API 번역 + 학습 항목 4종 추출 (docs/specs/content-pipeline.md 단계 3-4)."""

import json
from functools import lru_cache
from pathlib import Path

from anthropic import AsyncAnthropic

from app.core.config import get_settings

TRANSLATE_BATCH_SIZE = 50
EXTRACT_CHUNK_WORDS = 8000

EXTRACT_TOOL = {
    "name": "save_learning_items",
    "description": "스크립트에서 추출한 학습 항목을 저장한다",
    "input_schema": {
        "type": "object",
        "properties": {
            "words": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "en": {"type": "string"},
                        "ko": {"type": "string"},
                        "difficulty": {"enum": ["basic", "intermediate", "advanced"]},
                        "segment_seq": {"type": "integer"},
                    },
                    "required": ["en", "ko", "difficulty", "segment_seq"],
                },
            },
            "idioms": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "en": {"type": "string"},
                        "ko": {"type": "string"},
                        "difficulty": {"enum": ["basic", "intermediate", "advanced"]},
                        "segment_seq": {"type": "integer"},
                    },
                    "required": ["en", "ko", "difficulty", "segment_seq"],
                },
            },
            "patterns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "template": {"type": "string"},
                        "en_example": {"type": "string"},
                        "ko": {"type": "string"},
                        "segment_seq": {"type": "integer"},
                    },
                    "required": ["template", "en_example", "ko", "segment_seq"],
                },
            },
            "sentences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "en": {"type": "string"},
                        "ko": {"type": "string"},
                        "thinking_ko": {
                            "type": "string",
                            "description": "영어 어순 그대로 직역한 한국어 (영어식 사고 힌트)",
                        },
                        "segment_seq": {"type": "integer"},
                    },
                    "required": ["en", "ko", "thinking_ko", "segment_seq"],
                },
            },
        },
        "required": ["words", "idioms", "patterns", "sentences"],
    },
}

EXTRACT_SYSTEM = """\
당신은 한국인 학습자를 위한 영어 교육 콘텐츠 큐레이터다.
주어진 영어 스크립트(세그먼트 번호 포함)에서 학습 가치가 높은 항목을 추출한다.

규칙:
- CEFR A1 수준의 기초 표현(thank you, sorry, got it, hello 등 인사/맞장구/기초 어휘)은 제외
- words: 주제 이해에 중요한 중급 이상 단어 10-30개
- idioms: 관용 표현, phrasal verb, collocation 5-15개
- patterns: 스크립트에 반복되거나 범용성 높은 문형 3-10개. template 은 빈칸을 ___ 로 표기
- sentences: 통암기 가치가 있는 완결 문장 5-15개. thinking_ko 는 영어 어순 그대로 직역한
  한국어 (예: "There is a tree over there" -> "있다, 나무 한 그루가, 저기에")
- segment_seq 는 항목이 등장한 세그먼트 번호
- 각 항목의 difficulty 를 basic/intermediate/advanced 로 자기 평가하고
  basic 은 가급적 포함하지 않는다
반드시 save_learning_items 도구를 호출한다."""

TRANSLATE_SYSTEM = """\
영어 문장 배열을 자연스러운 한국어로 번역한다.
입력과 같은 길이의 JSON 배열(문자열)만 출력한다. 다른 텍스트 금지."""


@lru_cache
def easy_words() -> frozenset[str]:
    path = Path(__file__).parent.parent / "data" / "easy_words.txt"
    return frozenset(w.strip().lower() for w in path.read_text().splitlines() if w.strip())


def is_easy_word(en_text: str) -> bool:
    """단어 타입 2차 필터 — 스톱리스트 단일 단어만 제외 (숙어/패턴/문장 미적용)."""
    normalized = en_text.strip().lower()
    return " " not in normalized and normalized in easy_words()


def _client() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=get_settings().anthropic_api_key)


async def translate_texts(texts: list[str]) -> list[str]:
    """세그먼트 배치 번역. 배치 단위로 나눠 호출."""
    results: list[str] = []
    model = get_settings().anthropic_model
    client = _client()
    for i in range(0, len(texts), TRANSLATE_BATCH_SIZE):
        batch = texts[i : i + TRANSLATE_BATCH_SIZE]
        res = await client.messages.create(
            model=model,
            max_tokens=8000,
            system=TRANSLATE_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(batch, ensure_ascii=False)}],
        )
        translated = json.loads(_first_text(res))
        if not isinstance(translated, list) or len(translated) != len(batch):
            raise ValueError("translation batch size mismatch")
        results.extend(str(t) for t in translated)
    return results


async def extract_items(segments: list[tuple[int, str]]) -> dict:
    """(seq, en_text) 목록에서 4종 추출. 긴 스크립트는 청크 분할 후 병합."""
    chunks = _chunk_segments(segments)
    merged: dict = {"words": [], "idioms": [], "patterns": [], "sentences": []}
    model = get_settings().anthropic_model
    client = _client()
    for chunk in chunks:
        body = "\n".join(f"[{seq}] {text}" for seq, text in chunk)
        res = await client.messages.create(
            model=model,
            max_tokens=16000,
            system=EXTRACT_SYSTEM,
            tools=[EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": "save_learning_items"},
            messages=[{"role": "user", "content": body}],
        )
        tool_use = next(b for b in res.content if b.type == "tool_use")
        data = tool_use.input
        for key in merged:
            merged[key].extend(data.get(key, []))
    return _filter_items(merged)


def _first_text(res) -> str:
    """응답에서 첫 텍스트 블록 추출 — thinking 블록이 선행될 수 있음 (claude-sonnet-5)."""
    for block in res.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise ValueError("no text block in response")


def _chunk_segments(segments: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    chunks: list[list[tuple[int, str]]] = [[]]
    words = 0
    for seg in segments:
        seg_words = len(seg[1].split())
        if words + seg_words > EXTRACT_CHUNK_WORDS and chunks[-1]:
            chunks.append([])
            words = 0
        chunks[-1].append(seg)
        words += seg_words
    return chunks


def _filter_items(data: dict) -> dict:
    """코드 레벨 2차 필터: basic 제거 + word 스톱리스트 (docs/specs/content-pipeline.md)."""
    return {
        "words": [
            w for w in data["words"] if w.get("difficulty") != "basic" and not is_easy_word(w["en"])
        ],
        "idioms": [i for i in data["idioms"] if i.get("difficulty") != "basic"],
        "patterns": data["patterns"],
        "sentences": data["sentences"],
    }
