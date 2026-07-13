"""기존 승인 항목(word/idiom) 임베딩 백필 — 1회성 (P2 도입 시).

사용: docker exec englesson-api uv run --no-dev python scripts/backfill_embeddings.py
파이프라인의 embed 단계는 신규 콘텐츠만 처리하므로, 도입 이전 항목은 이걸로 채운다.
멱등: 이미 임베딩 있는 항목은 건너뜀.
"""

import asyncio
import logging

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models import LearningItem
from app.services import embeddings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill")


async def main() -> None:
    factory = get_session_factory()
    async with factory() as db:
        if not embeddings.enabled(db):
            logger.error("임베딩 비활성 — VOYAGE_EMBEDDING_SECRET/postgres 확인")
            return
        items = (
            (
                await db.execute(
                    select(LearningItem).where(
                        LearningItem.item_type.in_(("word", "idiom")),
                        LearningItem.review_status == "approved",
                    )
                )
            )
            .scalars()
            .all()
        )
        missing = set(await embeddings.missing_item_ids(db, [i.id for i in items]))
        targets = [i for i in items if i.id in missing]
        logger.info(
            "대상 %s건 (전체 %s, 기존 %s)", len(targets), len(items), len(items) - len(targets)
        )
        count = await embeddings.embed_items(db, targets)
        await db.commit()
        logger.info("완료: %s건 임베딩 저장", count)


if __name__ == "__main__":
    asyncio.run(main())
