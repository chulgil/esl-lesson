"""푸시 발송 루프 — 10분 주기로 조건 평가.

복습 리마인더(docs/specs/push-reminder.md) + 월요일 주간 성적표
(docs/specs/weekly-report.md) 를 같은 루프에서 평가한다.
"""

import asyncio
import logging

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.services import push

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 600

_task: asyncio.Task | None = None


async def _loop() -> None:
    while True:
        try:
            factory = get_session_factory()
            async with factory() as db:
                sent = await push.send_review_reminders(db)
                # 주간 성적표 — 같은 루프에 얹는다 (월요일·주 1회 게이트는 서비스가 판단)
                weekly = await push.send_weekly_reports(db)
                await db.commit()
                if sent:
                    logger.info("review reminders sent: %s", sent)
                if weekly:
                    logger.info("weekly reports sent: %s", weekly)
        except Exception:
            logger.exception("reminder loop failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def start_reminders() -> None:
    global _task
    if not push.enabled(get_settings()):
        logger.info("push reminders disabled (no VAPID keys)")
        return
    _task = asyncio.create_task(_loop())
    logger.info("reminder loop started")


def stop_reminders() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        _task = None
