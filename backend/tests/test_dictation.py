"""받아쓰기 배틀 — 채점·점수·랭킹 규칙 (docs/specs/dictation-battle.md)."""

from app.services.game import dictation as dt


def test_word_accuracy_ignores_case_and_punctuation():
    assert dt.word_accuracy("I met him, yesterday!", "i met him yesterday") == 1.0
    assert dt.word_accuracy("I met him yesterday", "i met her yesterday") < 1.0
    assert dt.word_accuracy("Hello world", "") == 0.0
    assert dt.word_accuracy("", "anything") == 0.0


def test_sentence_score_accuracy_gate_for_bonus():
    perfect_fast = dt.sentence_score(1.0, 0.0)
    assert perfect_fast > dt.BASE_MAX  # 정확 100% + 시간 보너스
    sloppy_fast = dt.sentence_score(0.5, 0.0)
    assert sloppy_fast == 50  # 정확도 90% 미만 — 보너스 없음
    assert dt.sentence_score(1.0, dt.SENTENCE_SECONDS) == dt.BASE_MAX


def test_rank_players_score_accuracy_time():
    def player(name, uid, score, acc, ms):
        p = dt.DictatorState(user_id=uid, name=name)
        p.score, p.accuracy_sum, p.total_ms = score, acc, ms
        return p

    name, uid = dt.rank_players([player("a", 1, 500, 4.0, 900), player("b", 2, 400, 5.0, 100)])
    assert (name, uid) == ("a", 1)
    name, _ = dt.rank_players([player("a", 1, 500, 4.0, 900), player("b", 2, 500, 5.0, 9000)])
    assert name == "b"  # 동점이면 정확도
    assert dt.rank_players([player("솔로", 1, 500, 5.0, 1)]) == (None, None)
