"""기존 콘텐츠 유튜브 라이선스 백필 — CC 게이트 도입(2026-07-14) 이전 등록분.

YOUTUBE_API_KEY 설정 후 실행 (서버 컨테이너):
    docker exec englesson-api sh -c \
        "PYTHONPATH=/app uv run --no-dev python scripts/backfill_licenses.py"
"""

import asyncio

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models import Content
from app.services import youtube


async def main() -> None:
    async with get_session_factory()() as db:
        rows = (
            (
                await db.execute(
                    select(Content).where(
                        Content.youtube_video_id.is_not(None),
                        Content.youtube_license.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        print(f"라이선스 미확인 콘텐츠 {len(rows)}건")
        updated = 0
        for content in rows:
            license_ = await youtube.fetch_license(content.youtube_video_id)
            if license_ is None:
                print(f"  [x] #{content.id} {content.title[:40]}: 조회 실패/키 없음")
                continue
            content.youtube_license = license_
            updated += 1
            marker = "CC" if license_ == "creativeCommons" else "표준"
            print(f"  [o] #{content.id} {content.title[:40]}: {marker}")
        await db.commit()
        print(f"{updated}건 저장 완료")


if __name__ == "__main__":
    asyncio.run(main())
