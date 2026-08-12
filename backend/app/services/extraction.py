"""Claude API 번역 + 학습 항목 4종 추출 (docs/specs/content-pipeline.md 단계 3-4)."""

import json
import re
from functools import lru_cache
from pathlib import Path

from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.services.langs import LANG_LABELS

TRANSLATE_BATCH_SIZE = 20
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
                        # en/ko 필드명은 역사적 유산 — 실제로는 콘텐츠 언어(en/ja/ko)
                        # 원문/한국어 번역 쌍을 담는다 (Phase 4 에서 필드 일반화 예정)
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
                            "description": "원문 어순 그대로 직역한 한국어 (원문식 사고 힌트)",
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


def _extract_system(source_lang: str = "en") -> str:
    """추출 시스템 프롬프트 — 소스 언어 라벨을 반영 (다국어 학습, langs.LANG_LABELS 단일 근거)."""
    label = LANG_LABELS.get(source_lang, LANG_LABELS["en"])
    return f"""\
당신은 한국인 학습자를 위한 {label} 교육 콘텐츠 큐레이터다.
주어진 {label} 스크립트(세그먼트 번호 포함)에서 학습 가치가 높은 항목을 추출한다.

규칙:
- CEFR A1 수준의 기초 표현(thank you, sorry, got it, hello 등 인사/맞장구/기초 어휘)은 제외
- words: 주제 이해에 중요한 중급 이상 단어 10-30개
- idioms: 관용 표현, phrasal verb, collocation 5-15개
- patterns: 스크립트에 반복되거나 범용성 높은 문형 3-10개. template 은 빈칸을 ___ 로 표기
- sentences: 통암기 가치가 있는 완결 문장 5-15개. thinking_ko 는 {label} 어순 그대로 직역한
  한국어 (예: "There is a tree over there" -> "있다, 나무 한 그루가, 저기에")
- segment_seq 는 항목이 등장한 세그먼트 번호
- 각 항목의 difficulty 를 basic/intermediate/advanced 로 자기 평가하고
  basic 은 가급적 포함하지 않는다
반드시 save_learning_items 도구를 호출한다."""


def _translate_system(source_lang: str = "en") -> str:
    """번역 시스템 프롬프트 — 소스 언어 라벨을 반영 (영어 하드코딩 제거)."""
    label = LANG_LABELS.get(source_lang, LANG_LABELS["en"])
    return f"""\
{label} 문장 배열을 자연스러운 한국어로 번역한다.
입력과 같은 길이의 JSON 배열(문자열)만 출력한다. 다른 텍스트 금지."""


def _translate_one_system(source_lang: str = "en") -> str:
    label = LANG_LABELS.get(source_lang, LANG_LABELS["en"])
    return f"다음 {label} 문장을 자연스러운 한국어로 번역한다. 번역문만 출력한다."


@lru_cache
def easy_words() -> frozenset[str]:
    path = Path(__file__).parent.parent / "data" / "easy_words.txt"
    return frozenset(w.strip().lower() for w in path.read_text().splitlines() if w.strip())


def is_easy_word(en_text: str) -> bool:
    """단어 타입 2차 필터 — 스톱리스트 단일 단어만 제외 (숙어/패턴/문장 미적용)."""
    normalized = en_text.strip().lower()
    return " " not in normalized and normalized in easy_words()


def _client() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=get_settings().anthropic_api_key, timeout=600, max_retries=2)


async def translate_texts(texts: list[str], source_lang: str = "en") -> list[str]:
    """세그먼트 배치 번역. 배치 개수 불일치 시 문장별 개별 번역으로 폴백.

    source_lang: 원문 언어(en/ja/ko, langs.SUPPORTED_LANGS) — 번역 대상은 항상 한국어.
    """
    results: list[str] = []
    model = get_settings().anthropic_translate_model
    client = _client()
    for i in range(0, len(texts), TRANSLATE_BATCH_SIZE):
        batch = texts[i : i + TRANSLATE_BATCH_SIZE]
        try:
            results.extend(await _translate_batch(client, model, batch, source_lang))
        except (ValueError, json.JSONDecodeError):
            # 모델이 개수를 안 맞추면 느리지만 확실한 개별 번역 (2026-07-11 운영 실측)
            for text in batch:
                results.append(await _translate_one(client, model, text, source_lang))
    return results


async def _translate_batch(
    client: AsyncAnthropic, model: str, batch: list[str], source_lang: str = "en"
) -> list[str]:
    res = await client.messages.create(
        model=model,
        max_tokens=8000,
        system=_translate_system(source_lang),
        messages=[{"role": "user", "content": json.dumps(batch, ensure_ascii=False)}],
    )
    translated = _parse_json_array(_first_text(res))
    if not isinstance(translated, list) or len(translated) != len(batch):
        raise ValueError("translation batch size mismatch")
    return [str(t) for t in translated]


async def _translate_one(
    client: AsyncAnthropic, model: str, text: str, source_lang: str = "en"
) -> str:
    res = await client.messages.create(
        model=model,
        max_tokens=1000,
        system=_translate_one_system(source_lang),
        messages=[{"role": "user", "content": text}],
    )
    return _first_text(res).strip()


async def extract_items(segments: list[tuple[int, str]], source_lang: str = "en") -> dict:
    """(seq, en_text) 목록에서 4종 추출. 긴 스크립트는 청크 분할 후 병합.

    source_lang: 원문 언어(en/ja/ko) — 추출 프롬프트에 반영 (ja 콘텐츠면 세그먼트
    텍스트가 일본어라는 뜻이며, 그래도 결과의 en/ko 필드명은 그대로 유지된다).
    """
    chunks = _chunk_segments(segments)
    merged: dict = {"words": [], "idioms": [], "patterns": [], "sentences": []}
    model = get_settings().anthropic_model
    client = _client()
    system = _extract_system(source_lang)
    for chunk in chunks:
        body = "\n".join(f"[{seq}] {text}" for seq, text in chunk)
        # 장시간 생성 대비 스트리밍으로 수신 (비스트리밍은 대형 응답에서 타임아웃 위험)
        async with client.messages.stream(
            model=model,
            max_tokens=16000,
            system=system,
            tools=[EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": "save_learning_items"},
            messages=[{"role": "user", "content": body}],
        ) as stream:
            res = await stream.get_final_message()
        tool_use = next(b for b in res.content if b.type == "tool_use")
        data = tool_use.input
        for key in merged:
            merged[key].extend(data.get(key, []))
    return _filter_items(merged)


def _parse_json_array(text: str) -> list:
    """모델 응답에서 JSON 배열 파싱 — 코드펜스/서두 텍스트 허용 (haiku 실측)."""
    stripped = text.strip()
    stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("["), stripped.rfind("]")
        if start != -1 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


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
