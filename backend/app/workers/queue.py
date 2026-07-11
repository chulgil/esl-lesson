"""프로세스 내 추출 워커 큐 (docs/specs/content-pipeline.md 실행 모델).

- 동시 실행 2개 제한 (AI 레이트/서버 부하 보호)
- 재시작 시 extracting 콘텐츠를 pending 으로 되돌려 재큐잉 (단계 done 기록으로 멱등)
"""

import asyncio
import logging

from sqlalchemy import select, update

from app.core.db import get_session_factory
from app.models import Content
from app.services.pipeline import run_pipeline

logger = logging.getLogger(__name__)

WORKER_COUNT = 2

_queue: asyncio.Queue[int] = asyncio.Queue()
_tasks: list[asyncio.Task] = []


def enqueue(content_id: int) -> None:
    _queue.put_nowait(content_id)


async def _worker_loop(worker_id: int) -> None:
    while True:
        content_id = await _queue.get()
        try:
            await run_pipeline(content_id)
        except Exception:
            logger.exception("worker %s: pipeline crashed content=%s", worker_id, content_id)
        finally:
            _queue.task_done()


async def start_workers() -> None:
    """앱 기동 훅: 미완료 콘텐츠 재큐잉 + 워커 시작."""
    factory = get_session_factory()
    async with factory() as db:
        await db.execute(
            update(Content).where(Content.status == "extracting").values(status="pending")
        )
        await db.commit()
        result = await db.execute(select(Content.id).where(Content.status == "pending"))
        pending = list(result.scalars())
    for content_id in pending:
        enqueue(content_id)
    for i in range(WORKER_COUNT):
        _tasks.append(asyncio.create_task(_worker_loop(i)))
    logger.info("extraction workers started: %s (requeued %s)", WORKER_COUNT, len(pending))


async def stop_workers() -> None:
    for task in _tasks:
        task.cancel()
    _tasks.clear()
