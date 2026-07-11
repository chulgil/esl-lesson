"""게임 엔진 규칙 검증 (docs/specs/word-tetris.md)."""

from app.services.game.bots import Bot
from app.services.game.engine import (
    BOARD_ROWS,
    MATCH_SECONDS,
    Board,
    Match,
    build_word_queue,
)

WORDS = [(i, w, w) for i, w in enumerate(["apple", "banana", "cherry", "dragonfruit", "kiwi"])]


def make_board() -> Board:
    return Board(word_queue=list(WORDS))


def tick_until_spawn(board: Board) -> None:
    while not board.bricks:
        board.tick(0.1)


def test_spawn_and_fall_and_land():
    board = make_board()
    tick_until_spawn(board)
    assert len(board.bricks) == 1
    brick = board.bricks[0]
    y0 = brick.y
    board.tick(1.0)
    assert brick.y > y0
    for _ in range(600):
        board.tick(0.1)
    assert brick.landed


def test_submit_clears_matching_brick_and_scores():
    board = make_board()
    tick_until_spawn(board)
    text = board.bricks[0].text
    result = board.submit(text)
    assert result.ok and result.combo == 1 and result.score_gained > 0
    assert board.bricks == []


def test_miss_resets_combo_and_locks_input():
    board = make_board()
    tick_until_spawn(board)
    board.combo = 5
    result = board.submit("nonexistent")
    assert not result.ok and board.combo == 0
    # 잠금 시간(0.3s) 동안 정답도 거부
    locked = board.submit(board.bricks[0].text)
    assert not locked.ok
    board.tick(0.4)  # 잠금 해제
    ok = board.submit(board.bricks[0].text)
    assert ok.ok


def test_combo_attack_every_third_and_long_word():
    board = make_board()
    # 콤보 3회 → attack 1
    attacks = 0
    for _ in range(3):
        tick_until_spawn(board)
        result = board.submit(board.bricks[0].text)
        assert result.ok
        attacks += result.attack
    assert attacks >= 1
    # 8자 이상 단어 클리어 → long_word 공격
    board2 = Board(word_queue=[(1, "dragonfruit", "dragonfruit")])
    tick_until_spawn(board2)
    result = board2.submit("dragonfruit")
    assert result.attack >= 1 and "long_word" in result.effects


def test_garbage_stacks_and_cleared_by_any_word():
    board = make_board()
    board.add_garbage(2)
    assert board.landed_count == 2
    while not [b for b in board.bricks if not b.is_garbage]:
        board.tick(0.1)
    normal = [b for b in board.bricks if not b.is_garbage]
    result = board.submit(normal[0].text)
    assert result.ok and "garbage_cleared" in result.effects
    assert board.landed_count == 1  # garbage 하나 소멸


def test_ko_when_stack_reaches_top():
    board = make_board()
    board.add_garbage(BOARD_ROWS)
    assert board.ko


def test_speed_increases_over_time():
    board = make_board()
    level0_interval = board.spawn_interval
    board.elapsed = 31.0
    assert board.speed_level == 1
    assert board.fall_speed > 0.35
    assert board.spawn_interval < level0_interval


def test_match_winner_by_ko_and_garbage_transfer():
    match = Match(board1=make_board(), board2=make_board())
    # p1 이 3콤보 → p2 에 garbage 전송
    for _ in range(3):
        while not match.board1.bricks:
            match.board1.tick(0.1)
        match.submit(1, match.board1.bricks[0].text)
    assert match.board2.landed_count >= 1
    # p2 KO → p1 승
    match.board2.add_garbage(BOARD_ROWS)
    match.tick(0.1)
    assert match.finished and match.winner == 1


def test_match_timeout_score_decides():
    match = Match(board1=make_board(), board2=make_board())
    match.board1.score = 50
    match.board2.score = 30
    match.tick(MATCH_SECONDS + 1)
    assert match.finished and match.winner == 1


def test_word_queue_seeded_shuffle_is_deterministic():
    q1 = build_word_queue(WORDS, seed=42)
    q2 = build_word_queue(WORDS, seed=42)
    q3 = build_word_queue(WORDS, seed=7)
    assert q1 == q2
    assert q1 != q3 or len(WORDS) <= 1


def test_bot_eventually_clears_bricks():
    board = make_board()
    bot = Bot.create(level=3, seed=1)
    cleared = 0
    for _ in range(1200):  # 120초 시뮬레이션
        board.tick(0.1)
        text = bot.act(board)
        if text is not None:
            result = board.submit(text)
            if result.ok:
                cleared += 1
    assert cleared >= 5
    assert not board.ko  # 레벨 3 봇은 초반 2분을 버틴다


def test_spawn_skips_when_word_queue_empty():
    """단어 풀이 비어도 크래시하지 않는다 (2026-07-11 운영 크래시 회귀)."""
    board = Board(word_queue=[])
    for _ in range(200):
        board.tick(0.1)
    assert board.bricks == []
    assert not board.ko
