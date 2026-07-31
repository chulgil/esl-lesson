"""손상된 패턴 문맥 복구 — 일회성 백필 (2026-07-31).

자막 큐는 문장 경계를 무시한 조각이라("happen Well turns out that the")
이를 context_en 으로 저장한 패턴은 레벨3 조립·표시가 깨진다. 이웃 큐(seq±1)를
이어붙인 텍스트에서 LLM 으로 완전한 한 문장을 복원해 갱신한다.
split_pattern_sentence 가 이미 성공하는 문맥은 건드리지 않는다 (수술적 복구).

실행: docker exec englesson-api uv run python -m app.scripts.repair_patterns
"""

import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.models import ItemOccurrence, LearningItem, TranscriptSegment
from app.services.extraction import _client
from app.services.quiz import split_pattern_sentence


async def _rewrite(template: str, joined: str) -> str | None:
    client = _client()
    res = await client.messages.create(
        model=get_settings().anthropic_translate_model,
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": (
                    "다음은 유튜브 자막 조각이다. 이 안에서 영어 패턴 "
                    f"'{template}' 이 실제로 쓰인 완전한 한 문장을 복원해라.\n"
                    "- 자막에 있는 단어만 사용 (대소문자·구두점만 정리, 창작 금지)\n"
                    "- 문장 하나만 출력, 설명 금지\n"
                    f"자막: {joined}"
                ),
            }
        ],
    )
    text = "".join(b.text for b in res.content if b.type == "text").strip()
    return text or None


async def main() -> None:
    factory = get_session_factory()
    checked = repaired = failed = skipped = 0
    async with factory() as db:
        rows = (
            (
                await db.execute(
                    select(ItemOccurrence, LearningItem)
                    .join(LearningItem, LearningItem.id == ItemOccurrence.item_id)
                    .where(LearningItem.item_type == "pattern")
                )
            )
            .all()
        )
        for occ, item in rows:
            checked += 1
            template = item.pattern_template or item.en_text
            if occ.context_en and split_pattern_sentence(template, occ.context_en):
                continue  # 이미 정상 분해 — 손대지 않음
            if occ.segment_id is None:
                skipped += 1
                continue
            seg = await db.get(TranscriptSegment, occ.segment_id)
            if seg is None:
                skipped += 1
                continue
            neighbors = (
                (
                    await db.execute(
                        select(TranscriptSegment)
                        .where(
                            TranscriptSegment.content_id == seg.content_id,
                            TranscriptSegment.seq.between(seg.seq - 1, seg.seq + 1),
                        )
                        .order_by(TranscriptSegment.seq)
                    )
                )
                .scalars()
                .all()
            )
            joined = " ".join(n.en_text for n in neighbors if n.en_text)
            candidate = await _rewrite(template, joined)
            # 복원문이 실제로 분해 가능할 때만 반영 — 실패분은 현상 유지
            if candidate and split_pattern_sentence(template, candidate):
                occ.context_en = candidate
                repaired += 1
                print(f"[repair] item={item.id} '{occ.context_en[:60]}'")
            else:
                failed += 1
                print(f"[fail]   item={item.id} candidate={candidate!r}")
        await db.commit()
    print(f"checked={checked} repaired={repaired} failed={failed} skipped={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
