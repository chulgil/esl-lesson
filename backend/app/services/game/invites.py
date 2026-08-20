"""친구 게임 초대 — 프레즌스 + 릴레이 (P2 경쟁 루프, docs/specs/study-spectate.md 확장).

WS 접속(페이지별 다중 소켓)을 유저 단위로 추적하고, 대기실에서 보낸 초대를
접속 중인 친구의 모든 소켓에 전달한다. 방 입장은 기존 ?join= 코드 흐름 재사용.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from app.services.themes import THEME_ACCESS

logger = logging.getLogger(__name__)

Sender = Callable[[dict], Awaitable[None]]

# 게임 키 ↔ 한글 이름 단일 소스 — GAMES 는 여기서 파생 (새 게임 추가 시 라벨 누락 방지)
GAME_LABELS = {
    "tetris": "워드 테트리스",
    "quiz": "스피드 퀴즈 로얄",
    "typing": "영문 타자연습",
    "scramble": "어순 조립 레이스",
    "dictation": "받아쓰기 배틀",
    "bingo": "리스닝 빙고",
}
GAMES = tuple(GAME_LABELS)


def safe_theme(theme: str | None) -> str | None:
    """카탈로그에 있는 테마 키만 통과 — 클라 주입 값이 URL/알림으로 릴레이되므로 경계 검증."""
    return theme if theme in THEME_ACCESS else None


def invite_push_payload(from_name: str, game: str, code: str, theme: str | None = None) -> dict:
    """오프라인 친구용 웹 푸시 — 알림 클릭 시 대기실 자동 입장(?join=).

    테마가 유효하면 게스트 화면을 초대자 테마로 여는 ?theme= 을 붙인다."""
    label = GAME_LABELS.get(game, game)
    valid = safe_theme(theme)
    suffix = f"&theme={valid}" if valid else ""
    return {
        "title": "게임 초대",
        "body": f"{from_name} 님이 {label}에 초대했어요!",
        "url": f"/game/{game}?join={code}{suffix}",
        "tag": "game-invite",
    }


class InviteHub:
    def __init__(self) -> None:
        self.sockets: dict[int, list[Sender]] = {}
        self.names: dict[int, str] = {}
        # 사용자별 마지막 클라 메시지(하트비트 포함) 시각 — 프리즈된 모바일 탭은
        # TCP send 가 "성공"해도 JS 가 멈춰 알림을 못 띄운다. 최근 하트비트가
        # 없으면 좀비로 보고 웹푸시로 폴백 (2026-07-31 "알림 안 옴" 근본 수정)
        self.last_seen: dict[int, float] = {}

    def attach(self, user_id: int, name: str, send: Sender) -> None:
        self.sockets.setdefault(user_id, []).append(send)
        self.names[user_id] = name
        self.touch(user_id)

    def touch(self, user_id: int) -> None:
        self.last_seen[user_id] = time.monotonic()

    def alive(self, user_id: int, ttl: float = 90.0) -> bool:
        seen = self.last_seen.get(user_id)
        return seen is not None and time.monotonic() - seen < ttl

    def detach(self, user_id: int, send: Sender) -> None:
        sends = self.sockets.get(user_id, [])
        if send in sends:
            sends.remove(send)
        if not sends:
            self.sockets.pop(user_id, None)
            self.names.pop(user_id, None)
            # last_seen 누수 방지 — 접속이 모두 끊긴 사용자의 항목 정리 (2026-08-20 리뷰)
            self.last_seen.pop(user_id, None)

    def online(self, user_id: int) -> bool:
        return bool(self.sockets.get(user_id))

    async def invite(
        self,
        from_user_id: int,
        to_user_id: int,
        game: str,
        code: str,
        theme: str | None = None,
    ) -> bool:
        """접속 중인 친구의 모든 소켓에 초대 전달. 오프라인이면 False."""
        if game not in GAMES or not self.online(to_user_id):
            return False
        message = {
            "t": "iv.invited",
            "from": self.names.get(from_user_id, "친구"),
            "game": game,
            "code": code,
            # 게스트 게임 화면을 초대자 테마로 (무효 값은 None — 클라가 무시)
            "theme": safe_theme(theme),
        }
        for send in list(self.sockets.get(to_user_id, [])):
            try:
                await send(message)
            except Exception:
                logger.debug("invite send failed", exc_info=True)
        return True

    async def notify(self, user_id: int, message: dict) -> bool:
        """접속 중인 사용자의 모든 소켓에 임의 메시지 전달 — 게임 초대 외 범용 릴레이
        (학습 중 알림 등, docs/specs/study-spectate.md §진입 경로 재설계). 오프라인이면 False."""
        if not self.online(user_id):
            return False
        for send in list(self.sockets.get(user_id, [])):
            try:
                await send(message)
            except Exception:
                logger.debug("notify send failed", exc_info=True)
        return True


invite_hub = InviteHub()
