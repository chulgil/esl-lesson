"""게임 출제 히스토리 — 연속 판에서 같은 문제 반복 방지 (2026-08-20 목표).

인메모리 사용자별 최근 출제 항목 기록 — "다시하기/이어가기" 시 다음 콘텐츠로
넘어가게 한다. 서버 재시작 시 초기화되는 v1 트레이드오프는 스펙에 명시
(항구 저장은 사용률 관측 후 재검토).
"""

from collections import deque
from collections.abc import Callable, Iterable, Sequence
from typing import TypeVar

T = TypeVar("T")


class ServedHistory:
    def __init__(self, per_user: int) -> None:
        self.per_user = per_user
        self._recent: dict[int, deque[int]] = {}

    def note(self, user_ids: Iterable[int], item_ids: Iterable[int]) -> None:
        """이번 판에 출제된 항목을 참여자 전원에게 기록."""
        ids = list(item_ids)
        for uid in user_ids:
            served = self._recent.setdefault(uid, deque(maxlen=self.per_user))
            served.extend(ids)

    def exclude_ids(self, user_ids: Iterable[int]) -> set[int]:
        """참여자 중 누구든 최근에 본 항목 — 합집합으로 제외해야 전원이 새 문제."""
        out: set[int] = set()
        for uid in user_ids:
            out.update(self._recent.get(uid, ()))
        return out

    def filter_fresh(
        self,
        user_ids: Iterable[int],
        pool: Sequence[T],
        key: Callable[[T], int],
        minimum: int,
    ) -> list[T]:
        """최근 출제분을 뺀 풀 — 남는 게 minimum 미만이면 원본 반환 (작은 풀은
        반복 불가피, 게임 시작 보장이 우선)."""
        recent = self.exclude_ids(user_ids)
        if not recent:
            return list(pool)
        fresh = [w for w in pool if key(w) not in recent]
        return fresh if len(fresh) >= minimum else list(pool)
