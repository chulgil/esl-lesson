"""콘텐츠 루틴 — 한 문장 요약의 LLM 의미 피드백 (ted-routine-2026-08.md P1-3).

정오답 채점이 아니라 피드백형 — "다 이해하기를 포기"하는 루틴 원리에 맞춰
잘한 점 + 다듬을 표현 1개만 돌려준다. 실패 시 호출자가 None 으로 저장한다
(액티브 인출 자체가 목적이라 피드백 없이도 제출은 성립).
"""

import logging

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Content, TranscriptSegment

logger = logging.getLogger(__name__)

MAX_CONTEXT_SEGMENTS = 12

PROMPT = """당신은 다정한 영어 스피킹 코치다. 학습자가 아래 영상을 공부한 뒤
영상의 메시지를 영어 한 문장으로 요약했다.

영상 제목: {title}
영상 도입부 스크립트:
{transcript}

학습자의 요약: {summary}

한국어 2문장으로 피드백하라:
1. 의미 전달이 되는지 — 잘한 점 한 가지를 꼭 짚는다.
2. 더 자연스러운 표현 제안 1개 (영어 원문 포함). 문법 오류가 있으면 그것을 우선.

규칙: 점수·등급 금지, 훈계 금지, 2문장 이내. 피드백 외 다른 텍스트 금지."""


async def summary_feedback(db: AsyncSession, content: Content, text: str) -> str:
    """요약에 대한 의미 피드백 생성 — 예외는 호출자가 처리."""
    settings = get_settings()
    segments = (
        await db.execute(
            select(TranscriptSegment.en_text)
            .where(TranscriptSegment.content_id == content.id)
            .order_by(TranscriptSegment.seq)
            .limit(MAX_CONTEXT_SEGMENTS)
        )
    ).scalars()
    transcript = "\n".join(f"- {s}" for s in segments) or "(스크립트 없음)"

    client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=45, max_retries=1)
    res = await client.messages.create(
        model=settings.anthropic_insight_model,
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": PROMPT.format(title=content.title, transcript=transcript, summary=text),
            }
        ],
    )
    for block in res.content:
        block_text = getattr(block, "text", None)
        if block_text:
            return block_text.strip()
    raise ValueError("no text block in summary feedback response")
