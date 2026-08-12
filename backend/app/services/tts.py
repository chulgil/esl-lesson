"""신경망 TTS — edge-tts(Microsoft 신경망 음성) + DB 캐시.

단어/짧은 표현의 발음 재생용 (docs/proposal/word-insight.md 듣기).
외부 서비스 실패 시 API 가 502 를 주고 프론트가 브라우저 TTS 로 폴백한다.

다국어 발음 지원 (docs/specs/chat-translation.md) — 보이스는 langs.TTS_VOICES
에서 언어별로 파생한다. 캐시 키는 기존 그대로 (text_key, voice) 라 en 전용
시절의 캐시 행과 그대로 호환된다.
"""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tts import TtsAudio
from app.services.langs import TTS_VOICES

logger = logging.getLogger(__name__)

DEFAULT_LANG = "en"
RATE = "-10%"  # 학습용 — 조금 천천히
MAX_TEXT_LEN = 120


def normalize_key(text: str) -> str:
    return " ".join(text.split()).lower()[:MAX_TEXT_LEN]


def voice_for(lang: str) -> str:
    return TTS_VOICES.get(lang, TTS_VOICES[DEFAULT_LANG])


async def synthesize(text: str, voice: str) -> bytes:
    """edge-tts 호출 — mp3 바이트. 실패는 호출자가 처리."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=RATE)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    if not chunks:
        raise ValueError("tts returned no audio")
    return b"".join(chunks)


async def get_or_generate(db: AsyncSession, text: str, lang: str = DEFAULT_LANG) -> bytes:
    voice = voice_for(lang)
    key = normalize_key(text)
    cached = (
        await db.execute(
            select(TtsAudio.audio).where(TtsAudio.text_key == key, TtsAudio.voice == voice)
        )
    ).scalar_one_or_none()
    if cached is not None:
        return cached

    audio = await synthesize(text, voice)
    db.add(TtsAudio(text_key=key, voice=voice, audio=audio))
    try:
        await db.commit()
    except IntegrityError:
        # 동시 생성 경합 — 먼저 저장된 쪽 채택
        await db.rollback()
    return audio
