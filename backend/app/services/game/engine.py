"""워드 테트리스 게임 엔진 — 순수 로직, I/O 없음 (docs/specs/word-tetris.md).

시간 단위: 초. 서버 매니저가 10Hz 로 tick() 을 호출한다.
보드 좌표: y=0 천장, y=BOARD_ROWS 바닥. 브릭은 y 가 증가하며 낙하한다.

방향은 브릭마다 섞지 않고 속도 레벨 구간으로 고정한다(en2ko ↔ ko2en 번갈아).
브릭은 (en, ko) 를 모두 보유하고 스폰 시점의 구간 방향으로 표시/정답이 정해진다.
"""

import random
from dataclasses import dataclass, field

BOARD_ROWS = 12
MATCH_SECONDS = 180.0
# 서버 스톨(스왑/CPU 경합) 후 벽시계 dt 가 커져도 한 틱 진행 상한 — 브릭 순간이동 방지.
# 두 보드가 같은 루프에서 같이 느려지므로 공정성은 유지된다.
MAX_TICK_SECONDS = 0.3

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

# 아이템 시스템
ITEM_KINDS = ("freeze", "hint", "bomb", "shield")
ITEM_SPAWN_EVERY = 7  # 일반 스폰 N회당 1회 아이템(별) 브릭
COMBO_ITEM_EVERY = 5  # 5콤보마다 아이템 1개
MAX_ITEMS = 3
FREEZE_SECONDS = 3.0
TAP_DECOY_CHIPS = 3  # en2ko 탭 오답 칩 수


TYPE_LEVEL = 5  # 이 레벨 이상은 타이핑(영어 생산) 구간, 그 아래는 칩 탭


def direction_for_level(level: int) -> str:
    """레벨 구간별 방향 (섞지 않음). 타이핑 구간(5+)은 항상 ko2en(영어 생산, IME 불필요)."""
    if level >= TYPE_LEVEL:
        return "ko2en"
    band = level // 2
    return "en2ko" if band % 2 == 0 else "ko2en"


def input_mode_for_level(level: int) -> str:
    """레벨 5+ 는 타이핑, 그 아래는 칩 탭 (2026-07-11 사용자 기획)."""
    return "type" if level >= TYPE_LEVEL else "tap"


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _fuzzy_equal(a: str, b: str) -> bool:
    """타이핑 근사 정답 — 짧은 단어 1글자, 그 외 2글자 오차 허용 (비슷하면 정답)."""
    if a == b:
        return True
    threshold = 1 if max(len(a), len(b)) <= 6 else 2
    return _levenshtein(a, b) <= threshold


@dataclass
class Brick:
    brick_id: int
    en: str
    ko: str
    direction: str = "en2ko"  # 스폰 시 고정
    mode: str = "tap"  # tap(칩 선택) | type(타이핑) — 스폰 시 고정
    y: float = 0.0
    landed: bool = False
    is_garbage: bool = False
    is_item: bool = False  # 별(★) 아이템 브릭

    @property
    def answer(self) -> str:
        """정답 입력 텍스트 — en2ko 는 한글(탭), ko2en 은 영어(타이핑)."""
        return self.ko if self.direction == "en2ko" else self.en

    @property
    def display(self) -> str:
        """브릭에 표시 — en2ko 는 영단어, ko2en 은 한글 뜻.

        ★(아이템) 브릭도 문제 텍스트를 그대로 표시한다 — ★만 표시하면
        무엇을 탭/타이핑해야 할지 알 수 없어 클리어 불가 (별 장식은 프론트 캔버스 담당).
        """
        return self.en if self.direction == "en2ko" else self.ko


@dataclass
class ClearResult:
    ok: bool
    brick_id: int | None = None
    combo: int = 0
    attack: int = 0
    effects: list[str] = field(default_factory=list)
    score_gained: int = 0
    item_gained: str | None = None


@dataclass
class Board:
    """플레이어 1명의 보드."""

    word_queue: list[tuple[int, str, str]]  # (word_id, en, ko)
    combo: int = 0
    score: int = 0
    cleared_words: int = 0
    misses: int = 0
    max_combo: int = 0
    elapsed: float = 0.0
    lock_until: float = 0.0
    frozen_until: float = 0.0
    shield_count: int = 0
    ko: bool = False
    bricks: list[Brick] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    _next_brick_id: int = 1
    _next_word_idx: int = 0
    _spawn_timer: float = 0.0
    _spawn_count: int = 0
    _combo_item_marker: int = 0
    _rng_seed: int = 0

    def __post_init__(self) -> None:
        self._rng = random.Random(self._rng_seed or 1)

    @property
    def speed_level(self) -> int:
        return min(MAX_SPEED_LEVEL, int(self.elapsed // SPEED_STEP_SECONDS))

    @property
    def direction(self) -> str:
        return direction_for_level(self.speed_level)

    @property
    def input_mode(self) -> str:
        return input_mode_for_level(self.speed_level)

    @property
    def frozen(self) -> bool:
        return self.elapsed < self.frozen_until

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
        return float(BOARD_ROWS - self.landed_count)

    def tick(self, dt: float) -> list[str]:
        if self.ko:
            return []
        events: list[str] = []
        prev_level = self.speed_level
        prev_dir = self.direction
        self.elapsed += dt
        if self.speed_level > prev_level:
            events.append("speed_up")
        if self.direction != prev_dir:
            events.append(f"segment:{self.direction}")

        # 시간 정지(freeze) 아이템: 낙하/생성 멈춤
        if self.frozen:
            return events

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
            return False
        self._spawn_count += 1
        is_item = self._spawn_count % ITEM_SPAWN_EVERY == 0
        if self._next_word_idx >= len(self.word_queue):
            self._next_word_idx = 0
        word_id, en, ko = self.word_queue[self._next_word_idx]
        self._next_word_idx += 1
        self.bricks.append(
            Brick(
                brick_id=self._next_brick_id,
                en=en,
                ko=ko,
                direction=self.direction,
                mode=self.input_mode,
                is_item=is_item,
            )
        )
        self._next_brick_id += 1
        return True

    def add_garbage(self, count: int = 1) -> int:
        """상대 공격 수신. 방어막이 있으면 소모하고 막는다. 실제 쌓인 수 반환."""
        blocked = min(self.shield_count, count)
        self.shield_count -= blocked
        actual = count - blocked
        for _ in range(actual):
            self.bricks.append(
                Brick(
                    brick_id=self._next_brick_id,
                    en="",
                    ko="",
                    y=self.floor_y(),
                    landed=True,
                    is_garbage=True,
                )
            )
            self._next_brick_id += 1
        if self.landed_count >= BOARD_ROWS:
            self.ko = True
        return actual

    def _compact_stack(self) -> None:
        """클리어로 스택에 빈 칸이 생기면 위 브릭을 아래로 내려 붙인다 (중력).

        floor_y 가 개수 기반이라 재정렬 없이는 남은 브릭이 공중에 뜨고
        다음 착지 브릭과 같은 칸에 겹친다.
        """
        landed = sorted((b for b in self.bricks if b.landed), key=lambda b: b.y, reverse=True)
        for i, brick in enumerate(landed):
            brick.y = float(BOARD_ROWS - i)

    def _grant_item(self) -> str | None:
        if len(self.items) >= MAX_ITEMS:
            return None
        item = self._rng.choice(ITEM_KINDS)
        self.items.append(item)
        return item

    def submit(self, text: str) -> ClearResult:
        """정답 제출(타이핑 영어 또는 탭한 한글). 일치하는 가장 위험한 브릭 제거."""
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
        item_gained: str | None = None

        if target.is_item:
            item_gained = self._grant_item()
            if item_gained:
                effects.append("item_brick")

        if self.combo >= 3:
            effects.append(f"combo{self.combo}")
        if self.combo % COMBO_ATTACK_EVERY == 0:
            attack += 1
            effects.append("attack")
        if len(target.answer) >= LONG_WORD_LEN:
            attack += 1
            effects.append("long_word")

        # 콤보 보상: 5콤보 단위 도달 시 아이템
        if self.combo // COMBO_ITEM_EVERY > self._combo_item_marker:
            self._combo_item_marker = self.combo // COMBO_ITEM_EVERY
            combo_item = self._grant_item()
            if combo_item:
                item_gained = combo_item
                effects.append("item_combo")

        garbage = next((b for b in self.bricks if b.is_garbage), None)
        if garbage is not None:
            self.bricks.remove(garbage)
            effects.append("garbage_cleared")
        self._compact_stack()

        gained = int(10 * (1 + self.combo * 0.1)) + (
            5 if len(target.answer) >= LONG_WORD_LEN else 0
        )
        self.score += gained
        return ClearResult(
            ok=True,
            brick_id=target.brick_id,
            combo=self.combo,
            attack=attack,
            effects=effects,
            score_gained=gained,
            item_gained=item_gained,
        )

    def use_item(self, kind: str) -> dict | None:
        """아이템 사용. 효과 적용 후 결과(dict) 반환, 인벤토리에 없으면 None."""
        if kind not in self.items:
            return None
        self.items.remove(kind)
        if kind == "freeze":
            self.frozen_until = self.elapsed + FREEZE_SECONDS
            return {"item": "freeze"}
        if kind == "shield":
            self.shield_count += 1
            return {"item": "shield"}
        if kind == "bomb":
            before = len(self.bricks)
            self.bricks = [b for b in self.bricks if not b.is_garbage]
            self._compact_stack()
            return {"item": "bomb", "cleared": before - len(self.bricks)}
        if kind == "hint":
            target = self._lowest_answerable()
            return {"item": "hint", "hint_answer": target.answer if target else None}
        return None

    def _match(self, brick: Brick, normalized: str) -> bool:
        """정답 판정. type 브릭(타이핑)은 유사하면 정답(비슷하면 정답 — 사용자 기획)."""
        answer = brick.answer.lower()
        if answer == normalized:
            return True
        return brick.mode == "type" and _fuzzy_equal(answer, normalized)

    def _most_dangerous_match(self, normalized: str) -> Brick | None:
        matches = [
            b
            for b in self.bricks
            if not b.is_garbage and not b.is_item and self._match(b, normalized)
        ]
        item_matches = [b for b in self.bricks if b.is_item and self._match(b, normalized)]
        candidates = matches + item_matches
        if not candidates:
            return None
        return max(candidates, key=lambda b: (b.landed, b.y))

    def _lowest_answerable(self) -> Brick | None:
        playable = [b for b in self.bricks if not b.is_garbage]
        if not playable:
            return None
        return max(playable, key=lambda b: (b.landed, b.y))

    def danger(self) -> bool:
        return self.landed_count >= BOARD_ROWS - 3

    def snapshot(self) -> dict:
        """tap 브릭은 정답 칩을 노출(선다형이라 안전, 양방향). type 브릭은 정답 미노출."""
        ko_answers: list[str] = []
        en_answers: list[str] = []
        # 아이템(★) 브릭도 포함 — 칩이 없으면 탭 구간에서 클리어 수단이 없음
        for b in self.bricks:
            if b.is_garbage or b.mode != "tap":
                continue
            if b.direction == "en2ko" and b.ko not in ko_answers:
                ko_answers.append(b.ko)
            elif b.direction == "ko2en" and b.en not in en_answers:
                en_answers.append(b.en)
        return {
            "bricks": [
                {
                    "id": b.brick_id,
                    "display": b.display,
                    "y": round(b.y, 2),
                    "landed": b.landed,
                    "garbage": b.is_garbage,
                    "item": b.is_item,
                    # tap 브릭만 정답을 chip 으로 노출 (type=타이핑은 숨김)
                    "chip": b.answer if (b.mode == "tap" and not b.is_garbage) else None,
                }
                for b in self.bricks
            ],
            "chips": build_chips(ko_answers, en_answers),
            "direction": self.direction,
            "input_mode": self.input_mode,
            "combo": self.combo,
            "score": self.score,
            "speed_level": self.speed_level,
            "danger": self.danger(),
            "frozen": self.frozen,
            "shield": self.shield_count,
            "items": list(self.items),
            "ko": self.ko,
        }


# 탭 오답 칩 후보 (초기 데이터 적을 때 폴백)
DECOY_KO = ["회복력 있는", "효율적인", "명백한", "우연한", "지속하다", "모호한", "확장 가능한"]
DECOY_EN = ["resilient", "efficient", "evident", "accidental", "obscure", "sustain"]


def build_chips(ko_answers: list[str], en_answers: list[str]) -> list[str]:
    """탭 칩: 보드의 정답(한/영) + (부족하면) 오답 칩. 결정적(매 틱 안 흔들림)."""
    chips = list(dict.fromkeys([*ko_answers, *en_answers]))
    if not chips:
        return []
    decoys = DECOY_KO if ko_answers and not en_answers else DECOY_EN if en_answers else DECOY_KO
    if len(chips) < 4:
        for d in decoys:
            if d not in chips:
                chips.append(d)
            if len(chips) >= 4:
                break
    return sorted(chips)


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
    winner: int | None = None

    def tick(self, dt: float) -> dict[int, list[str]]:
        if self.finished:
            return {1: [], 2: []}
        # 스톨 후 큰 dt 는 상한으로 자름 — 순간이동 대신 잠깐 느려졌다 회복
        dt = min(dt, MAX_TICK_SECONDS)
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

    def use_item(self, player: int, kind: str) -> dict | None:
        board = self.board1 if player == 1 else self.board2
        return board.use_item(kind)

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
