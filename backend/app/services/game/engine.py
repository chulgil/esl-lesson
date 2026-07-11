"""워드 테트리스 게임 엔진 — 순수 로직, I/O 없음 (docs/specs/word-tetris.md).

시간 단위: 초. 서버 매니저가 10Hz 로 tick() 을 호출한다.
보드 좌표: y=0 천장, y=BOARD_ROWS 바닥. 브릭은 y 가 증가하며 낙하한다.
"""

import random
from dataclasses import dataclass, field

BOARD_ROWS = 12
MATCH_SECONDS = 180.0

# 낙하 가속 곡선: 30초당 1단계, 10단계 상한 (테트리스 레벨업)
SPEED_STEP_SECONDS = 30.0
MAX_SPEED_LEVEL = 10
BASE_FALL_SPEED = 0.35  # rows/sec (레벨 0)
FALL_SPEED_PER_LEVEL = 0.18
BASE_SPAWN_INTERVAL = 5.0  # sec (레벨 0)
SPAWN_INTERVAL_PER_LEVEL = 0.35
MIN_SPAWN_INTERVAL = 1.6

COMBO_ATTACK_EVERY = 3  # 3콤보마다 garbage 1개
LONG_WORD_LEN = 8  # 8자 이상 클리어 시 garbage 1개
MISS_LOCK_SECONDS = 0.3


@dataclass
class Brick:
    brick_id: int
    text: str  # 정답 입력 텍스트 (영단어)
    display: str  # 브릭에 표시할 텍스트 (en 또는 ko)
    y: float = 0.0
    landed: bool = False
    is_garbage: bool = False


@dataclass
class ClearResult:
    ok: bool
    brick_id: int | None = None
    combo: int = 0
    attack: int = 0  # 상대에게 보낼 garbage 수
    effects: list[str] = field(default_factory=list)
    score_gained: int = 0


@dataclass
class Board:
    """플레이어 1명의 보드."""

    word_queue: list[tuple[int, str, str]]  # (word_id, answer_text, display)
    combo: int = 0
    score: int = 0
    cleared_words: int = 0
    misses: int = 0
    max_combo: int = 0
    elapsed: float = 0.0
    lock_until: float = 0.0
    ko: bool = False
    bricks: list[Brick] = field(default_factory=list)
    _next_brick_id: int = 1
    _next_word_idx: int = 0
    _spawn_timer: float = 0.0

    @property
    def speed_level(self) -> int:
        return min(MAX_SPEED_LEVEL, int(self.elapsed // SPEED_STEP_SECONDS))

    @property
    def fall_speed(self) -> float:
        return BASE_FALL_SPEED + FALL_SPEED_PER_LEVEL * self.speed_level

    @property
    def spawn_interval(self) -> float:
        return max(
            MIN_SPAWN_INTERVAL, BASE_SPAWN_INTERVAL - SPAWN_INTERVAL_PER_LEVEL * self.speed_level
        )

    @property
    def landed_count(self) -> int:
        return sum(1 for b in self.bricks if b.landed)

    def floor_y(self) -> float:
        """다음 브릭이 굳는 높이 (쌓인 만큼 위로 올라옴)."""
        return float(BOARD_ROWS - self.landed_count)

    def tick(self, dt: float) -> list[str]:
        """시간 진행. 발생한 이벤트 이름 목록을 반환."""
        if self.ko:
            return []
        events: list[str] = []
        prev_level = self.speed_level
        self.elapsed += dt
        if self.speed_level > prev_level:
            events.append("speed_up")

        self._spawn_timer += dt
        if self._spawn_timer >= self.spawn_interval:
            self._spawn_timer = 0.0
            if self._spawn_brick():
                events.append("spawn")

        floor = self.floor_y()
        for brick in self.bricks:
            if brick.landed:
                continue
            brick.y += self.fall_speed * dt
            if brick.y >= floor:
                brick.y = floor
                brick.landed = True
                events.append("land")
                floor = self.floor_y()

        if self.landed_count >= BOARD_ROWS:
            self.ko = True
            events.append("ko")
        return events

    def _spawn_brick(self) -> bool:
        if not self.word_queue:
            return False  # 단어 풀 없음 — 크래시 대신 스폰 스킵
        if self._next_word_idx >= len(self.word_queue):
            self._next_word_idx = 0  # 큐 소진 시 순환
        word_id, text, display = self.word_queue[self._next_word_idx]
        self._next_word_idx += 1
        self.bricks.append(Brick(brick_id=self._next_brick_id, text=text, display=display))
        self._next_brick_id += 1
        return True

    def add_garbage(self, count: int = 1) -> None:
        """상대 공격 수신: 회색 브릭이 스택에 즉시 쌓인다."""
        for _ in range(count):
            self.bricks.append(
                Brick(
                    brick_id=self._next_brick_id,
                    text="",  # 직접 타이핑으로는 제거 불가
                    display="###",
                    y=self.floor_y(),
                    landed=True,
                    is_garbage=True,
                )
            )
            self._next_brick_id += 1
        if self.landed_count >= BOARD_ROWS:
            self.ko = True

    def submit(self, text: str) -> ClearResult:
        """타이핑 제출. 일치하는 가장 위험한 브릭 제거."""
        if self.ko or self.elapsed < self.lock_until:
            return ClearResult(ok=False, combo=self.combo)

        normalized = text.strip().lower()
        target = self._most_dangerous_match(normalized)
        if target is None:
            self.misses += 1
            self.combo = 0
            self.lock_until = self.elapsed + MISS_LOCK_SECONDS
            return ClearResult(ok=False, combo=0, effects=["miss"])

        self.bricks.remove(target)
        self.combo += 1
        self.max_combo = max(self.max_combo, self.combo)
        self.cleared_words += 1

        effects = ["clear"]
        attack = 0
        if self.combo >= 3:
            effects.append(f"combo{self.combo}")
        if self.combo % COMBO_ATTACK_EVERY == 0:
            attack += 1
            effects.append("attack")
        if len(target.text) >= LONG_WORD_LEN:
            attack += 1
            effects.append("long_word")

        # garbage 소멸: 일반 단어 클리어 1회당 garbage 1개 제거
        garbage = next((b for b in self.bricks if b.is_garbage), None)
        if garbage is not None:
            self.bricks.remove(garbage)
            effects.append("garbage_cleared")

        gained = int(10 * (1 + self.combo * 0.1)) + (5 if len(target.text) >= LONG_WORD_LEN else 0)
        self.score += gained
        return ClearResult(
            ok=True,
            brick_id=target.brick_id,
            combo=self.combo,
            attack=attack,
            effects=effects,
            score_gained=gained,
        )

    def _most_dangerous_match(self, normalized: str) -> Brick | None:
        """일치 브릭 중 가장 위험한 것: 굳은 것 우선, 그다음 가장 낮게 내려온 것."""
        matches = [b for b in self.bricks if not b.is_garbage and b.text.lower() == normalized]
        if not matches:
            return None
        return max(matches, key=lambda b: (b.landed, b.y))

    def danger(self) -> bool:
        return self.landed_count >= BOARD_ROWS - 3

    def snapshot(self) -> dict:
        return {
            "bricks": [
                {
                    "id": b.brick_id,
                    "display": b.display,
                    "y": round(b.y, 2),
                    "landed": b.landed,
                    "garbage": b.is_garbage,
                }
                for b in self.bricks
            ],
            "combo": self.combo,
            "score": self.score,
            "speed_level": self.speed_level,
            "danger": self.danger(),
            "ko": self.ko,
        }


def build_word_queue(
    words: list[tuple[int, str, str]], seed: int, size: int = 100
) -> list[tuple[int, str, str]]:
    """시드 고정 셔플 — 양 플레이어 동일 순서 (공정성)."""
    rng = random.Random(seed)
    pool = list(words)
    rng.shuffle(pool)
    return pool[:size] if len(pool) >= size else pool


@dataclass
class Match:
    """1:1 매치 상태. p1/p2 보드 + 승패 판정."""

    board1: Board
    board2: Board
    elapsed: float = 0.0
    finished: bool = False
    winner: int | None = None  # 1 | 2 | None(무승부)

    def tick(self, dt: float) -> dict[int, list[str]]:
        if self.finished:
            return {1: [], 2: []}
        self.elapsed += dt
        events = {1: self.board1.tick(dt), 2: self.board2.tick(dt)}
        self._check_end()
        return events

    def submit(self, player: int, text: str) -> ClearResult:
        board = self.board1 if player == 1 else self.board2
        other = self.board2 if player == 1 else self.board1
        result = board.submit(text)
        if result.attack and not self.finished:
            other.add_garbage(result.attack)
        self._check_end()
        return result

    def forfeit(self, player: int) -> None:
        if self.finished:
            return
        self.finished = True
        self.winner = 2 if player == 1 else 1

    def _check_end(self) -> None:
        if self.finished:
            return
        if self.board1.ko and self.board2.ko:
            self.finished = True
            self.winner = None
        elif self.board1.ko:
            self.finished = True
            self.winner = 2
        elif self.board2.ko:
            self.finished = True
            self.winner = 1
        elif self.elapsed >= MATCH_SECONDS:
            self.finished = True
            if self.board1.score > self.board2.score:
                self.winner = 1
            elif self.board2.score > self.board1.score:
                self.winner = 2
            else:
                self.winner = None
