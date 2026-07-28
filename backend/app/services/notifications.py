"""알림 센터 서비스 — 적재 + 실시간 전달 (docs/specs/notifications.md)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification
from app.services import chat


async def notify(db: AsyncSession, user_id: int, type_: str, payload: dict) -> None:
    """알림 행 적재 + 접속 중이면 WS `notif.new` 즉시 전달. 커밋은 호출자 책임.

    payload 는 발생 시점 스냅샷(닉네임 등) — chat_messages.item_ref 패턴.
    WS 미전달(오프라인)이어도 행은 남으므로 벨에서 나중에 확인된다.
    """
    db.add(Notification(user_id=user_id, type=type_, payload=payload))
    await db.flush()
    await chat.deliver_ws(user_id, {"t": "notif.new", "type": type_, **payload})
