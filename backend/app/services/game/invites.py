"""친구 게임 초대 — 프레즌스 + 릴레이 (P2 경쟁 루프, docs/specs/study-spectate.md 확장).

WS 접속(페이지별 다중 소켓)을 유저 단위로 추적하고, 대기실에서 보낸 초대를
접속 중인 친구의 모든 소켓에 전달한다. 방 입장은 기존 ?join= 코드 흐름 재사용.
"""

import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

Sender = Callable[[dict], Awaitable[None]]

# 게임 키 ↔ 한글 이름 단일 소스 — GAMES 는 여기서 파생 (새 게임 추가 시 라벨 누락 방지)
GAME_LABELS = {
    "tetris": "워드 테트리스",
    "quiz": "스피드 퀴즈 로얄",
    "typing": "영문 타자연습",
    "scramble": "어순 조립 레이스",
    "dictation": "받아쓰기 배틀",
}
GAMES = tuple(GAME_LABELS)


def invite_push_payload(from_name: str, game: str, code: str) -> dict:
    """오프라인 친구용 웹 푸시 — 알림 클릭 시 대기실 자동 입장(?join=)."""
    label = GAME_LABELS.get(game, game)
    return {
        "title": "게임 초대",
        "body": f"{from_name} 님이 {label}에 초대했어요!",
        "url": f"/game/{game}?join={code}",
        "tag": "game-invite",
    }


class InviteHub:
    def __init__(self) -> None:
        self.sockets: dict[int, list[Sender]] = {}
        self.names: dict[int, str] = {}

    def attach(self, user_id: int, name: str, send: Sender) -> None:
        self.sockets.setdefault(user_id, []).append(send)
        self.names[user_id] = name

    def detach(self, user_id: int, send: Sender) -> None:
        sends = self.sockets.get(user_id, [])
        if send in sends:
            sends.remove(send)
        if not sends:
            self.sockets.pop(user_id, None)
            self.names.pop(user_id, None)

    def online(self, user_id: int) -> bool:
        return bool(self.sockets.get(user_id))

    async def invite(self, from_user_id: int, to_user_id: int, game: str, code: str) -> bool:
        """접속 중인 친구의 모든 소켓에 초대 전달. 오프라인이면 False."""
        if game not in GAMES or not self.online(to_user_id):
            return False
        message = {
            "t": "iv.invited",
            "from": self.names.get(from_user_id, "친구"),
            "game": game,
            "code": code,
        }
        for send in list(self.sockets.get(to_user_id, [])):
            try:
                await send(message)
            except Exception:
                logger.debug("invite send failed", exc_info=True)
        return True


invite_hub = InviteHub()
