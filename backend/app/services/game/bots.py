"""AI 봇 — 가상 타이핑 속도를 가진 플레이어 시뮬레이션 (docs/specs/word-tetris.md)."""

import random
from dataclasses import dataclass, field

from app.services.game.engine import Board

# 난이도: (WPM, 정확도, 반응지연 min-max sec)
BOT_LEVELS: dict[int, tuple[int, float, tuple[float, float]]] = {
    1: (15, 0.88, (1.5, 3.0)),
    2: (25, 0.92, (1.0, 2.0)),
    3: (35, 0.95, (0.7, 1.5)),
    4: (50, 0.97, (0.5, 1.0)),
    5: (70, 0.99, (0.3, 0.6)),
}

CHARS_PER_WORD = 5.0  # WPM 표준 정의


@dataclass
class Bot:
    level: int
    rng: random.Random
    _target_brick_id: int | None = None
    _finish_at: float = 0.0
    _typo_pending: bool = field(default=False)

    @classmethod
    def create(cls, level: int, seed: int) -> "Bot":
        return cls(level=max(1, min(5, level)), rng=random.Random(seed))

    def act(self, board: Board) -> str | None:
        """매 틱 호출. 타이핑 완료 시점이 되면 제출할 텍스트를 반환."""
        if board.ko:
            return None
        wpm, accuracy, (react_min, react_max) = BOT_LEVELS[self.level]

        target = self._pick_target(board)
        if target is None:
            self._target_brick_id = None
            return None

        if target.brick_id != self._target_brick_id:
            # 새 목표: 반응 지연 + 타이핑 시간 산정
            self._target_brick_id = target.brick_id
            reaction = self.rng.uniform(react_min, react_max)
            typing_seconds = (len(target.answer) / CHARS_PER_WORD) * (60.0 / wpm)
            self._finish_at = board.elapsed + reaction + typing_seconds
            self._typo_pending = self.rng.random() > accuracy
            return None

        if board.elapsed >= self._finish_at:
            self._target_brick_id = None
            if self._typo_pending:
                self._typo_pending = False
                return target.answer + "x"  # 오타 — 콤보 리셋되는 사람다운 실수
            return target.answer
        return None

    def _pick_target(self, board: Board):
        candidates = [b for b in board.bricks if not b.is_garbage and not b.is_item and b.answer]
        if not candidates:
            return None
        return max(candidates, key=lambda b: (b.landed, b.y))
