"""언어 감지·카탈로그 — 다국어 학습의 단일 근거 (docs/specs/chat-translation.md).

지원 언어는 3개(ko/en/ja)로 고정 — 카탈로그·TTS 보이스·번역 프롬프트가
여기서 파생된다. 감지는 휴리스틱(문자 범위) — 짧은 채팅에 LLM 감지는 과하고,
오판해도 번역이 어색한 정도라 무해.
"""

import re

SUPPORTED_LANGS = ("ko", "en", "ja")

LANG_LABELS = {"ko": "한국어", "en": "영어", "ja": "일본어"}

# DeepL target_lang 코드
DEEPL_CODES = {"ko": "KO", "en": "EN-US", "ja": "JA"}

# edge-tts 보이스 (학습용 — 약간 느리게 읽는 RATE 는 tts 서비스가 적용)
TTS_VOICES = {
    "en": "en-US-ChristopherNeural",
    "ko": "ko-KR-InJoonNeural",
    "ja": "ja-JP-NanamiNeural",
}

_HANGUL = re.compile(r"[가-힯ᄀ-ᇿ]")
_KANA = re.compile(r"[぀-ヿ]")


def detect_lang(text: str) -> str:
    """한글 → ko, 가나 → ja, 그 외 → en.

    한자만 있는 문장(가나 없음)은 일/중 구분이 불가능해 en 폴백 — 채팅에서
    희귀하고, 오판 시 번역 방향만 어긋날 뿐 오류는 아니다.
    """
    if _HANGUL.search(text):
        return "ko"
    if _KANA.search(text):
        return "ja"
    return "en"


def normalize_text_key(text: str, max_len: int = 200) -> str:
    """공백 접기 + 소문자 + 절단 — tts_audio.text_key 와 같은 원칙의 캐시 키."""
    return re.sub(r"\s+", " ", text).strip().lower()[:max_len]
