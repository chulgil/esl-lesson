"""채팅 번역 캐시·사용량 원장 (docs/specs/chat-translation.md).

비용 방어 1층: 같은 문장은 전 사용자 공유 캐시 — 메시지가 아니라 **문장** 단위
(정규화 키 + 대상 언어 유니크, tts_audio 패턴). 사용량 원장은 월 예산 하드캡과
사용자 일일 한도 판정의 근거.
"""

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin


class ChatTranslation(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "chat_translations"
    __table_args__ = (
        UniqueConstraint("text_key", "target_lang", name="uq_chat_translations_key_lang"),
    )

    # 정규화 키 (공백 접기 + 소문자, 200자 절단) — tts_audio.text_key 와 같은 원칙
    text_key: Mapped[str] = mapped_column(String(200))
    source_lang: Mapped[str] = mapped_column(String(8))
    target_lang: Mapped[str] = mapped_column(String(8))
    text: Mapped[str] = mapped_column(Text)
    # "deepl" | "haiku" — 품질 이슈 추적·비용 산정용
    engine: Mapped[str] = mapped_column(String(16))


class TranslationUsage(Base, PkMixin, CreatedAtMixin):
    """번역 엔진 호출 1건 = 1행 (캐시 히트는 기록 안 함 — 비용 0)."""

    __tablename__ = "translation_usage"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    chars: Mapped[int] = mapped_column(Integer)
    engine: Mapped[str] = mapped_column(String(16))


class PhraseExclusion(Base, PkMixin, CreatedAtMixin):
    """내가 쓰는 말에서 뺀 문장 — 재동기화가 다시 수집하지 않게 하는 원장.

    키는 **원문(주언어) 정규화 키** — 번역 엔진이 바뀌어 번역문이 달라져도
    같은 발화는 계속 제외된다 (my-phrases.md 편집).
    """

    __tablename__ = "phrase_exclusions"
    __table_args__ = (
        UniqueConstraint("user_id", "text_key", name="uq_phrase_exclusions_user_key"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    text_key: Mapped[str] = mapped_column(String(200))
