"""학습 관전 릴레이 — 승인제 (docs/specs/study-spectate.md).

서버는 게임 로직 없이 릴레이만 한다: 학습자(호스트)가 보내는 화면 상태를
호스트가 **수락한** 관전자에게만 전달. 코드는 무작위, 기본은 비공개.
"""

import logging
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

Sender = Callable[[dict], Awaitable[None]]


@dataclass
class Watcher:
    name: str
    send: Sender


@dataclass
class SpectateRoom:
    code: str
    host_id: int
    host_name: str
    host_send: Sender
    watchers: dict[int, Watcher] = field(default_factory=dict)  # 수락됨
    pending: dict[int, Watcher] = field(default_factory=dict)  # 수락 대기
    last_event: dict | None = None  # 늦게 합류한 관전자에게 현재 화면 재생


class SpectateHub:
    def __init__(self) -> None:
        self.rooms: dict[str, SpectateRoom] = {}
        self.by_host: dict[int, str] = {}
        self.by_watcher: dict[int, str] = {}

    async def host(self, user_id: int, name: str, send: Sender) -> str:
        """관전 허용 시작 — 기존 방은 대체(이전 코드 무효)."""
        await self.detach(user_id)
        code = secrets.token_hex(3).upper()
        self.rooms[code] = SpectateRoom(code=code, host_id=user_id, host_name=name, host_send=send)
        self.by_host[user_id] = code
        await self._safe(send, {"t": "st.hosting", "code": code})
        return code

    async def request(self, user_id: int, name: str, send: Sender, code: str) -> None:
        room = self.rooms.get(code.upper())
        if room is None or user_id == room.host_id:
            await self._safe(send, {"t": "error", "code": "room_not_found"})
            return
        room.pending[user_id] = Watcher(name=name, send=send)
        self.by_watcher[user_id] = room.code
        await self._safe(send, {"t": "st.requested", "host": room.host_name})
        await self._safe(room.host_send, {"t": "st.request", "watcher_id": user_id, "name": name})

    async def allow(self, host_id: int, watcher_id: int, allow: bool) -> None:
        room = self.rooms.get(self.by_host.get(host_id, ""))
        if room is None:
            return
        watcher = room.pending.pop(watcher_id, None)
        if watcher is None:
            return
        if not allow:
            self.by_watcher.pop(watcher_id, None)
            await self._safe(watcher.send, {"t": "st.denied"})
            return
        room.watchers[watcher_id] = watcher
        await self._safe(watcher.send, {"t": "st.approved", "host": room.host_name})
        if room.last_event is not None:
            # 진행 중 화면을 바로 재생 — 빈 화면 대기 방지
            await self._safe(watcher.send, {"t": "st.event", "payload": room.last_event})

    async def event(self, host_id: int, payload: dict) -> None:
        room = self.rooms.get(self.by_host.get(host_id, ""))
        if room is None:
            return
        room.last_event = payload
        for watcher in list(room.watchers.values()):
            await self._safe(watcher.send, {"t": "st.event", "payload": payload})

    async def detach(self, user_id: int) -> None:
        """호스트 이탈 → 방 해체 + 관전자 통지. 관전자 이탈 → 목록 정리."""
        code = self.by_host.pop(user_id, None)
        if code is not None:
            room = self.rooms.pop(code, None)
            if room is not None:
                for watcher in list(room.watchers.values()) + list(room.pending.values()):
                    await self._safe(watcher.send, {"t": "st.end"})
                for wid in list(room.watchers) + list(room.pending):
                    self.by_watcher.pop(wid, None)
            return
        watch_code = self.by_watcher.pop(user_id, None)
        if watch_code is not None:
            room = self.rooms.get(watch_code)
            if room is not None:
                left = room.watchers.pop(user_id, None) or room.pending.pop(user_id, None)
                if left is not None:
                    await self._safe(room.host_send, {"t": "st.left", "name": left.name})

    @staticmethod
    async def _safe(send: Sender | None, message: dict) -> None:
        if send is None:
            return
        try:
            await send(message)
        except Exception:
            logger.debug("spectate send failed", exc_info=True)


spectate_hub = SpectateHub()
