"""선다형 정답 위치 분포 회귀 검증 (2026-07-13 사용자 보고 "정답이 항상 2번째").

코드 조사·시뮬레이션 결과 균등 분포였으나, 셔플 누락 회귀를 CI 가 계속
감시하도록 고정한다. random 을 시드 고정해 플레이키 없음.
"""

import random
from collections import Counter
from types import SimpleNamespace

from app.services import quiz


def _item(i: int, item_type: str = "word") -> SimpleNamespace:
    return SimpleNamespace(
        id=i,
        en_text=f"word{i:02d}",
        ko_text=f"뜻{i:02d}",
        item_type=item_type,
        pattern_template=None,
    )


def _positions(build, n: int = 200) -> Counter:
    pos: Counter = Counter()
    for _ in range(n):
        q = build()
        pos[q["choices"].index(q["hint_answer"])] += 1
    return pos


def test_word_choice_answer_position_not_fixed():
    """단어 4지선다 — 정답이 모든 위치(0-3)에 고르게 등장해야 함."""
    random.seed(7)
    pool = [_item(i) for i in range(12)]
    pos = _positions(lambda: quiz._word_question(pool[0], pool, None))
    assert set(pos.keys()) == {0, 1, 2, 3}
    # 균등(25%)에서 크게 벗어나 한 위치에 몰리면 실패 (셔플 누락 감지)
    assert all(count >= 200 * 0.1 for count in pos.values()), dict(pos)


def test_cloze_choice_answer_position_not_fixed():
    """숙어 빈칸(cloze) — 동일하게 정답 위치가 고정되지 않아야 함."""
    random.seed(7)
    pool = [_item(i, "idiom") for i in range(12)]
    target = pool[0]
    context = f"I will {target.en_text} tomorrow"
    pos = _positions(lambda: quiz._idiom_question(target, pool, context))
    assert set(pos.keys()) == {0, 1, 2, 3}
    assert all(count >= 200 * 0.1 for count in pos.values()), dict(pos)
