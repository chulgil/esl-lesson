"""개인 최고 기록 — 과거 매치 스탯에서 최고치 집계 + 경신 판정 (P3 리텐션).

순수 함수로 분리해 매니저/프로필 API 가 공유하고 단위 테스트를 쉽게 한다.
"""

RECORD_KEYS = ("score", "max_combo", "wpm")


def bests_from_matches(user_id: int, rows: list) -> dict:
    """(player1_id, p1_score, p2_score, stats) 행들에서 이 유저의 최고 기록 집계."""
    bests = {key: 0 for key in RECORD_KEYS}
    for player1_id, p1_score, p2_score, stats in rows:
        side = "p1" if player1_id == user_id else "p2"
        score = (p1_score if side == "p1" else p2_score) or 0
        bests["score"] = max(bests["score"], score)
        side_stats = (stats or {}).get(side) or {}
        for key in ("max_combo", "wpm"):
            try:
                bests[key] = max(bests[key], float(side_stats.get(key) or 0))
            except (TypeError, ValueError):
                continue
    return bests


def new_records(prev_bests: dict, current: dict) -> list[str]:
    """이번 매치가 경신한 기록 키 목록. 0 대비 0 은 경신 아님 (첫 판 인플레 방지)."""
    achieved = []
    for key in RECORD_KEYS:
        try:
            now_value = float(current.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if now_value > float(prev_bests.get(key) or 0) and now_value > 0:
            achieved.append(key)
    return achieved
