"""TTS 오디오 캐시 — 신경망 음성 파일을 텍스트 단위로 영구 캐시.

브라우저 내장 TTS(기기 의존, 기계음)를 서버 신경망 음성으로 대체한다
(2026-08-05 보고: "너무 로봇 같은 목소리"). 같은 단어는 전역 공유 —
음성 종류가 바뀌면 voice 키가 달라져 자연 재생성된다.
"""

from sqlalchemy import LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin


class TtsAudio(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "tts_audio"
    __table_args__ = (UniqueConstraint("text_key", "voice", name="uq_tts_text_voice"),)

    # 정규화 키 (공백 접기 + 소문자) — 대소문자만 다른 요청의 중복 생성 방지
    text_key: Mapped[str] = mapped_column(String(120))
    voice: Mapped[str] = mapped_column(String(64))
    audio: Mapped[bytes] = mapped_column(LargeBinary)
