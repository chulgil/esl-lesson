"""어순 조립 레이스 — 칩 셔플·점수·랭킹 규칙 (docs/specs/scramble-race.md)."""

import random

from app.services.game import scramble as sc


def test_scramble_chips_differs_from_answer_but_same_words():
    words = "I met him at the station yesterday".split()
    rng = random.Random(42)
    chips = sc.scramble_chips(words, rng)
    assert chips != words  # 정답 어순 그대로 내지 않음
    assert sorted(chips) == sorted(words)  # 단어 구성은 동일

    # 전 단어 동일 등 섞기 불가능한 경우는 그대로 통과
    same = ["go", "go", "go"]
    assert sc.scramble_chips(same, rng) == same


def test_sentence_score_bonus_penalty_floor():
    fast = sc.sentence_score(elapsed=0.0, mistakes=0)
    slow = sc.sentence_score(elapsed=sc.SENTENCE_SECONDS, mistakes=0)
    assert fast == sc.BASE_SCORE + sc.TIME_BONUS_MAX  # 즉답 = 보너스 최대
    assert slow == sc.BASE_SCORE  # 제한시간 직전 = 보너스 0
    assert sc.sentence_score(10.0, mistakes=2) < sc.sentence_score(10.0, mistakes=0)
    # 실수가 아무리 많아도 완성하면 최소 점수 보장 (포기 방지)
    assert sc.sentence_score(30.0, mistakes=50) == sc.MIN_SENTENCE_SCORE


def test_build_rounds_filters_by_chip_range_and_scrambles():
    pool = [
        {"en": "Too short", "ko": "짧음"},  # 2칩 — 제외
        {"en": "This one has exactly six words", "ko": "여섯 단어"},
        {"en": "Another sentence with five words", "ko": "다섯 단어"},
    ]
    rounds = sc.build_rounds(pool, count=4, seed=7)
    assert len(rounds) == 4  # 부족하면 순환
    for r in rounds:
        assert sc.MIN_CHIPS <= len(r["answer"]) <= sc.MAX_CHIPS
        assert sorted(r["chips"]) == sorted(r["answer"])
        assert " ".join(r["answer"]) in {p["en"] for p in pool}


def test_rank_players_score_then_mistakes_then_time():
    def player(name, uid, score, mistakes, ms):
        p = sc.ScramblerState(user_id=uid, name=name)
        p.score, p.mistakes, p.total_ms = score, mistakes, ms
        return p

    name, uid = sc.rank_players([player("a", 1, 900, 5, 9000), player("b", 2, 800, 0, 100)])
    assert (name, uid) == ("a", 1)  # 점수 우선
    name, _ = sc.rank_players([player("a", 1, 900, 5, 900), player("b", 2, 900, 2, 9000)])
    assert name == "b"  # 같은 점수면 실수 적은 쪽
    name, uid = sc.rank_players([player("a", 1, 900, 2, 5000), player("b", 2, 900, 2, 5000)])
    assert (name, uid) == (None, None)  # 완전 동률 = 무승부
    assert sc.rank_players([player("솔로", 1, 900, 0, 100)]) == (None, None)
