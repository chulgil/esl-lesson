from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PkMixin
from app.models.types import JsonDict

MATCH_MODES = ("pvp", "pve")
MATCH_STATUSES = ("waiting", "playing", "finished", "aborted")


class GameMatch(Base, PkMixin, CreatedAtMixin):
    """페이즈 2 — 워드 테트리스 대전 기록 (docs/specs/word-tetris.md)."""

    __tablename__ = "game_matches"
    __table_args__ = (
        CheckConstraint("mode IN ('pvp','pve')", name="ck_matches_mode"),
        CheckConstraint(
            "status IN ('waiting','playing','finished','aborted')",
            name="ck_matches_status",
        ),
    )

    mode: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="waiting", server_default="waiting")
    room_code: Mapped[str | None] = mapped_column(Text)
    player1_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    player2_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    bot_level: Mapped[int | None] = mapped_column(SmallInteger)
    winner_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    p1_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    p2_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    stats: Mapped[dict] = mapped_column(JsonDict, default=dict)
    started_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]


class TypingRace(Base, PkMixin, CreatedAtMixin):
    """영문 타자연습 — 싱글 기록/2인 대결 (docs/specs/typing-race.md)."""

    __tablename__ = "typing_races"
    __table_args__ = (
        CheckConstraint("mode IN ('solo','race')", name="ck_typing_mode"),
        CheckConstraint(
            "status IN ('waiting','playing','finished','aborted')",
            name="ck_typing_status",
        ),
    )

    mode: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="waiting", server_default="waiting")
    player1_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    player2_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    winner_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    p1_chars: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    p2_chars: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # {"p1": {wpm, accuracy, sentences}, "p2": {...}}
    stats: Mapped[dict] = mapped_column(JsonDict, default=dict)
    ended_at: Mapped[datetime | None]


class ScrambleRace(Base, PkMixin, CreatedAtMixin):
    """어순 조립 레이스 — 문장 어순 퍼즐 동기 레이스, 1~4인 (docs/specs/scramble-race.md)."""

    __tablename__ = "scramble_races"
    __table_args__ = (
        CheckConstraint("mode IN ('solo','race')", name="ck_scramble_mode"),
        CheckConstraint(
            "status IN ('waiting','playing','finished','aborted')",
            name="ck_scramble_status",
        ),
    )

    mode: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="waiting", server_default="waiting")
    player1_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    player2_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    winner_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    p1_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    p2_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # {"p1": {name, sentences, mistakes, score}, "p2": {...}}
    stats: Mapped[dict] = mapped_column(JsonDict, default=dict)
    ended_at: Mapped[datetime | None]


class QuizRoyaleMatch(Base, PkMixin, CreatedAtMixin):
    """스피드 퀴즈 로얄 — 최대 4인, 1:1 전용 game_matches 와 분리 (proposal/quiz-royale.md)."""

    __tablename__ = "quiz_royale_matches"
    __table_args__ = (
        CheckConstraint("mode IN ('solo','room')", name="ck_qr_mode"),
        CheckConstraint(
            "status IN ('waiting','playing','finished','aborted')",
            name="ck_qr_status",
        ),
    )

    host_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    mode: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="waiting", server_default="waiting")
    # {"players": [{user_id,name,score,rank,is_bot}]} — 결과 화면 스냅샷 (표시 전용)
    players: Mapped[dict] = mapped_column(JsonDict, default=dict)
    ended_at: Mapped[datetime | None]


class QuizRoyalePlayer(Base, PkMixin, CreatedAtMixin):
    """퀴즈 로얄 참가 기록(정규화) — 집계 전용, 봇 제외 (DB 감사 2026-07-15).

    players JSONB 파이썬 풀스캔(XP·최고기록·업적·리더보드)을 인덱스 집계로 대체한다.
    표시용 스냅샷은 QuizRoyaleMatch.players 유지.
    """

    __tablename__ = "quiz_royale_players"

    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quiz_royale_matches.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rank: Mapped[int | None] = mapped_column(SmallInteger)
