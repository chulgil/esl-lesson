"""게임 엔진 규칙 검증 (docs/specs/word-tetris.md)."""

from app.services.game.bots import Bot
from app.services.game.engine import (
    BOARD_ROWS,
    MATCH_SECONDS,
    Board,
    Brick,
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
    text = board.bricks[0].answer
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
    locked = board.submit(board.bricks[0].answer)
    assert not locked.ok
    board.tick(0.4)  # 잠금 해제
    ok = board.submit(board.bricks[0].answer)
    assert ok.ok


def test_combo_attack_every_third_and_long_word():
    board = make_board()
    # 콤보 3회 → attack 1
    attacks = 0
    for _ in range(3):
        tick_until_spawn(board)
        result = board.submit(board.bricks[0].answer)
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
    result = board.submit(normal[0].answer)
    assert result.ok and "garbage_cleared" in result.effects
    assert board.landed_count == 1  # garbage 하나 소멸


def test_ko_when_stack_reaches_top():
    board = make_board()
    board.add_garbage(BOARD_ROWS)
    assert board.ko


def test_clear_compacts_stack_no_gap_or_overlap():
    """스택 중간/바닥 클리어 시 위 브릭이 내려앉아야 함 — 공중부양/겹침 금지."""
    board = make_board()
    for i, (_, en, ko) in enumerate(WORDS[:3]):
        board.bricks.append(
            Brick(brick_id=100 + i, en=en, ko=ko, y=float(BOARD_ROWS - i), landed=True)
        )
    # 바닥(y=12) apple 클리어 → banana/cherry 가 12, 11 로 내려앉아야 함
    result = board.submit("apple")
    assert result.ok
    ys = sorted(b.y for b in board.bricks if b.landed)
    assert ys == [float(BOARD_ROWS - 1), float(BOARD_ROWS)]
    # 다음 착지선(개수 기반)과 기존 브릭 y 가 겹치지 않음
    assert board.floor_y() not in ys


def test_bomb_compacts_stack():
    """폭탄으로 garbage 일괄 제거 시 남은 브릭이 바닥까지 내려앉아야 함."""
    board = make_board()
    board.add_garbage(2)  # y=12, 11
    board.bricks.append(Brick(brick_id=200, en="kiwi", ko="kiwi", y=10.0, landed=True))
    board.items.append("bomb")
    board.use_item("bomb")
    assert [b.y for b in board.bricks if b.landed] == [float(BOARD_ROWS)]


def test_match_tick_clamps_dt_spike():
    """서버 스톨 후 큰 dt 가 와도 한 틱에 왕창 진행(브릭 순간이동) 금지."""
    from app.services.game.engine import MAX_TICK_SECONDS

    m = Match(board1=make_board(), board2=make_board())
    m.tick(5.0)
    assert m.elapsed <= MAX_TICK_SECONDS + 1e-9
    assert m.board1.elapsed <= MAX_TICK_SECONDS + 1e-9


def test_item_brick_shows_question_and_chip():
    """★ 브릭도 문제 텍스트를 표시하고 정답 칩이 내려와야 탭 구간에서 클리어 가능."""
    board = make_board()
    board.bricks.append(Brick(brick_id=300, en="apple", ko="사과", is_item=True))
    assert board.bricks[0].display == "apple"  # en2ko: ★만이 아니라 영단어 표시
    snap = board.snapshot()
    assert "사과" in snap["chips"]  # 정답 칩 포함 → 탭으로 클리어 가능


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
        match.submit(1, match.board1.bricks[0].answer)
    assert match.board2.landed_count >= 1
    # p2 KO → p1 승
    match.board2.add_garbage(BOARD_ROWS)
    match.tick(0.1)
    assert match.finished and match.winner == 1


def test_match_timeout_score_decides():
    match = Match(board1=make_board(), board2=make_board())
    match.board1.score = 50
    match.board2.score = 30
    # 한 방 큰 dt 는 MAX_TICK_SECONDS 로 잘리므로 (순간이동 방지),
    # 제한시간 도달 상태를 직접 만들고 다음 틱에서 판정을 확인한다
    match.elapsed = MATCH_SECONDS
    match.tick(0.1)
    assert match.finished and match.winner == 1


def test_word_queue_seeded_shuffle_is_deterministic():
    q1 = build_word_queue(WORDS, seed=42)
    q2 = build_word_queue(WORDS, seed=42)
    q3 = build_word_queue(WORDS, seed=7)
    assert q1 == q2
    assert q1 != q3 or len(WORDS) <= 1


def test_word_queue_puts_priority_items_first():
    """P0-A 게임-복습 편입: due·최근 오답 항목이 큐 앞으로 (effectiveness-audit 4차).

    파티션 안에서는 셔플 순서 유지 — 공정성(양 플레이어 동일 큐)·결정성 불변.
    """
    words = [(i, f"word{i:02d}", f"뜻{i:02d}") for i in range(1, 21)]
    priority = {3, 8, 15}
    q1 = build_word_queue(words, seed=42, priority=priority)
    q2 = build_word_queue(words, seed=42, priority=priority)
    assert q1 == q2  # 결정적
    assert {w[0] for w in q1[:3]} == priority  # 우선 항목이 맨 앞
    plain = build_word_queue(words, seed=42)
    assert sorted(q1) == sorted(plain)  # 구성은 동일, 순서만 당김


def test_spawned_brick_carries_word_id():
    """브릭이 학습 항목 id 를 보유 — 종료 시 못 지운 단어를 복습 항목으로 회수."""
    board = make_board()
    tick_until_spawn(board)
    assert board.bricks[0].word_id == board.word_queue[0][0]


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


# --- 레벨 구간 방향 + 탭 + 아이템 (2026-07-11 추가) ---

from app.services.game.engine import direction_for_level  # noqa: E402


def bilingual_board():
    words = [(i, f"word{i:02d}", f"뜻{i:02d}") for i in range(20)]
    return Board(word_queue=words, _rng_seed=42)


def test_segment_direction_by_level():
    assert direction_for_level(0) == "en2ko"
    assert direction_for_level(1) == "en2ko"
    assert direction_for_level(2) == "ko2en"
    assert direction_for_level(3) == "ko2en"
    assert direction_for_level(4) == "en2ko"
    assert direction_for_level(6) == "ko2en"


def test_brick_direction_fixed_at_spawn_and_answer():
    board = bilingual_board()
    tick_until_spawn(board)
    brick = board.bricks[0]
    # 레벨 0 → en2ko: 표시는 영어, 정답은 한글 (탭)
    assert brick.direction == "en2ko"
    assert brick.display == brick.en
    assert brick.answer == brick.ko
    # 한글 뜻을 제출(탭)하면 제거
    assert board.submit(brick.ko).ok


def test_ko2en_tap_segment_shows_english_chip():
    board = bilingual_board()
    board.elapsed = 65.0  # 레벨 2 → ko2en, tap 구간
    tick_until_spawn(board)
    brick = board.bricks[0]
    assert brick.direction == "ko2en" and brick.mode == "tap"
    assert brick.display == brick.ko  # 한글 표시
    assert brick.answer == brick.en  # 영어 정답
    snap = board.snapshot()
    assert snap["input_mode"] == "tap"
    b = snap["bricks"][0]
    assert b["chip"] == brick.en  # tap 구간은 영어 칩(정답) 노출 — 양방향 동일
    assert brick.en in snap["chips"]


def test_all_levels_are_tap_mode():
    """타이핑 구간 폐지 (2026-08-03) — 전 레벨이 칩 탭. 고속 구간도 IME 없이 즐긴다."""
    from app.services.game.engine import MAX_SPEED_LEVEL, input_mode_for_level

    assert all(input_mode_for_level(lv) == "tap" for lv in range(MAX_SPEED_LEVEL + 1))
    board = bilingual_board()
    board.elapsed = 160.0  # 레벨 5 — 예전 타이핑 구간
    tick_until_spawn(board)
    brick = board.bricks[0]
    assert brick.mode == "tap"
    snap = board.snapshot()
    assert snap["input_mode"] == "tap"
    assert snap["bricks"][0]["chip"] == brick.answer  # 탭 대상이므로 칩 노출


def test_chip_groups_by_danger_order_sizes_3_3_2():
    """학습카드式 보기 (2026-08-10 기획): 위험한 브릭 순 3개에 3+3+2 그룹, 총 8개 이하.

    4번째 이후 브릭의 정답은 아직 안 나온다 — 앞 브릭을 지우면 차례가 온다.
    """
    board = bilingual_board()
    for i in range(4):
        board.bricks.append(
            Brick(
                brick_id=400 + i,
                en=f"word{i:02d}",
                ko=f"뜻{i:02d}",
                y=float(BOARD_ROWS - i),
                landed=True,
            )
        )
    snap = board.snapshot()
    groups = snap["chip_groups"]
    assert [len(g) for g in groups] == [3, 3, 2]
    assert len(snap["chips"]) <= 8
    assert "뜻00" in groups[0]  # 가장 아래(위험) 브릭의 학습카드 보기
    assert "뜻01" in groups[1]
    assert "뜻02" in groups[2]
    assert "뜻03" not in snap["chips"]  # 4번째 브릭 정답은 오답으로도 안 씀


def test_chip_group_distractors_match_brick_language():
    """그룹의 오답은 그 브릭 정답과 같은 언어 — ko2en 브릭엔 영어, en2ko 브릭엔 한글."""
    board = bilingual_board()
    board.bricks.append(
        Brick(brick_id=500, en="word00", ko="뜻00", direction="ko2en", y=12.0, landed=True)
    )
    board.bricks.append(
        Brick(brick_id=501, en="word01", ko="뜻01", direction="en2ko", y=11.0, landed=True)
    )
    groups = board.snapshot()["chip_groups"]
    assert "word00" in groups[0] and all(c.isascii() for c in groups[0])
    assert "뜻01" in groups[1] and all(not c.isascii() for c in groups[1])


def test_chip_groups_deterministic_across_snapshots():
    """같은 보드 상태면 스냅샷마다 같은 보기 — 매 틱 흔들리면 탭할 수 없다."""
    board = bilingual_board()
    tick_until_spawn(board)
    assert board.snapshot()["chip_groups"] == board.snapshot()["chip_groups"]


def test_single_brick_gets_card_style_three_options():
    """브릭 1개면 학습카드 1장과 동일 — 정답 1 + 오답 2 = 3지선다."""
    board = bilingual_board()
    tick_until_spawn(board)
    brick = board.bricks[0]
    snap = board.snapshot()
    groups = snap["chip_groups"]
    assert len(groups) == 1 and len(groups[0]) == 3
    assert brick.answer in groups[0]
    assert snap["chips"] == groups[0]  # 평탄화된 chips 는 그룹 순서 그대로


def test_ko2en_segment_snapshot_offers_english_options():
    board = bilingual_board()
    board.elapsed = 65.0  # 레벨 2 → ko2en, tap
    tick_until_spawn(board)
    snap = board.snapshot()
    en_chips = [c for c in snap["chips"] if c.isascii()]
    assert len(en_chips) >= 3  # 정답 + 오답 2 (학습카드式)
    assert board.bricks[0].en in en_chips


def test_en2ko_snapshot_reveals_ko_chips():
    board = bilingual_board()
    tick_until_spawn(board)
    snap = board.snapshot()
    assert snap["direction"] == "en2ko" and snap["input_mode"] == "tap"
    assert len(snap["chips"]) >= 3  # 정답 뜻 + 오답 2 (학습카드式)
    assert board.bricks[0].ko in snap["chips"]


def test_combo_grants_item_every_5():
    board = bilingual_board()
    gained = []
    for _ in range(5):
        tick_until_spawn(board)
        r = board.submit(board.bricks[0].answer)
        if r.item_gained:
            gained.append(r.item_gained)
    assert gained  # 5콤보에서 아이템 획득
    assert board.items


def test_combo_reset_on_miss_also_resets_item_marker():
    """오답으로 콤보가 0으로 리셋되면 아이템 마커도 함께 리셋돼야 다음 스트릭에서도
    5콤보에 아이템이 나온다 (버그: marker 미리셋 시 10콤보 후 리셋되면 다음 스트릭은
    15콤보까지 아이템이 안 나옴)."""
    board = bilingual_board()
    first_gain = None
    for _ in range(5):
        tick_until_spawn(board)
        r = board.submit(board.bricks[0].answer)
        if r.item_gained:
            first_gain = r.item_gained
    assert first_gain is not None
    assert board._combo_item_marker == 1

    miss = board.submit("no-such-word-xyz")
    assert not miss.ok and board.combo == 0
    assert board._combo_item_marker == 0  # 리셋되어야 다음 스트릭에서 다시 지급

    second_gain = None
    for _ in range(5):
        tick_until_spawn(board)
        r = board.submit(board.bricks[0].answer)
        if r.item_gained:
            second_gain = r.item_gained
    assert second_gain is not None


def test_item_brick_grants_item_on_clear():
    board = bilingual_board()
    # 아이템 브릭이 나올 때까지 스폰 (7스폰당 1회)
    item_brick = None
    for _ in range(2000):
        board.tick(0.1)
        item_brick = next((b for b in board.bricks if b.is_item), None)
        if item_brick:
            break
    # 2026-07-13 개정: ★ 브릭도 문제 텍스트 표시 (★만 표시하면 클리어 수단 없음)
    assert item_brick is not None and item_brick.display == item_brick.en
    before = len(board.items)
    board.submit(item_brick.answer)
    assert len(board.items) == before + 1


def test_freeze_item_stops_fall_and_spawn():
    board = bilingual_board()
    board.items.append("freeze")
    tick_until_spawn(board)
    y0 = board.bricks[0].y
    board.use_item("freeze")
    assert board.frozen
    for _ in range(20):
        board.tick(0.1)  # 2초 — freeze 3초 안이므로 정지
    assert board.bricks[0].y == y0  # 낙하 멈춤


def test_shield_blocks_one_attack():
    board = bilingual_board()
    board.items.append("shield")
    board.use_item("shield")
    assert board.shield_count == 1
    actual = board.add_garbage(2)
    assert actual == 1  # 1개만 막힘
    assert board.shield_count == 0


def test_bomb_clears_garbage():
    board = bilingual_board()
    board.add_garbage(3)
    board.items.append("bomb")
    res = board.use_item("bomb")
    assert res["cleared"] == 3
    assert board.landed_count == 0


def test_hint_returns_answer_of_lowest_brick():
    board = bilingual_board()
    board.items.append("hint")
    tick_until_spawn(board)
    res = board.use_item("hint")
    assert res["hint_answer"] == board.bricks[0].answer


def test_use_missing_item_returns_none():
    board = bilingual_board()
    assert board.use_item("freeze") is None
