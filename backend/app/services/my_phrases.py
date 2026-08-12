"""내가 쓰는 말 덱 — 채팅 발화를 학습 항목으로 (docs/specs/my-phrases.md).

내가 보낸 주언어 메시지 중 번역 캐시(chat_translations)에 쌍이 있는 것만
수집한다 — 추가 번역 비용 0 원칙. 유저당 1개의 개인 콘텐츠(source="chat",
private)에 문장 항목으로 합류시키면 복습 큐·문장 게임 3종(타자/어순/받아쓰기)·
덱 학습·시험이 기존 파이프라인 그대로 태워진다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChatMessage,
    ChatTranslation,
    Content,
    ContentSubscription,
    ItemOccurrence,
    LearningItem,
    PhraseExclusion,
)
from app.models.user import User, UserSettings
from app.services import translation as translation_service
from app.services.langs import detect_lang, normalize_text_key

MIN_CHARS = 4  # "ㅋㅋ"·"네" 제외
SOLO_MIN_CHARS = 6  # 1회 사용도 채택되는 문장 길이 — 그 미만은 빈도 2회 필요
CANDIDATE_CAP = 200  # 동기화당 채택 상한 (폭주 방지)
MESSAGE_SCAN_LIMIT = 2000  # 최근 메시지 스캔 창
DECK_TITLE = "내가 쓰는 말"


async def _get_or_create_deck(db: AsyncSession, user: User, learning: str) -> Content:
    deck = (
        await db.execute(
            select(Content).where(Content.source == "chat", Content.created_by == user.id)
        )
    ).scalar_one_or_none()
    if deck is None:
        deck = Content(
            source="chat",
            visibility="private",
            title=DECK_TITLE,
            status="ready",
            created_by=user.id,
            lang=learning,
        )
        db.add(deck)
        await db.flush()
    sub = (
        await db.execute(
            select(ContentSubscription.id).where(
                ContentSubscription.content_id == deck.id,
                ContentSubscription.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        db.add(ContentSubscription(content_id=deck.id, user_id=user.id))
        await db.flush()
    return deck


async def sync_my_phrases(
    db: AsyncSession, user: User, settings: UserSettings | None
) -> tuple[Content, int]:
    """멱등 동기화 — (덱, 이번에 추가된 항목 수). 커밋은 호출자 책임."""
    primary = settings.primary_lang if settings and settings.primary_lang else "ko"
    learning = (settings.learning_langs if settings and settings.learning_langs else ["en"])[0]
    deck = await _get_or_create_deck(db, user, learning)

    bodies = (
        (
            await db.execute(
                select(ChatMessage.body)
                .where(
                    ChatMessage.sender_id == user.id,
                    ChatMessage.deleted_at.is_(None),
                    ChatMessage.body != "",
                )
                .order_by(ChatMessage.id.desc())
                .limit(MESSAGE_SCAN_LIMIT)
            )
        )
        .scalars()
        .all()
    )

    # 후보 집계 — 정규화 키 기준 빈도 (같은 말을 다르게 띄어써도 한 문장)
    counts: dict[str, tuple[str, int]] = {}
    for body in bodies:
        text = body.strip()
        if len(text) < MIN_CHARS or "http" in text:
            continue
        if detect_lang(text) != primary:
            continue
        key = normalize_text_key(text)
        first, n = counts.get(key, (text, 0))
        counts[key] = (first, n + 1)

    # 사용자가 뺀 문장은 재수집하지 않는다 (my-phrases.md 편집)
    excluded = set(
        (
            await db.execute(
                select(PhraseExclusion.text_key).where(PhraseExclusion.user_id == user.id)
            )
        ).scalars()
    )
    accepted = [
        (key, original)
        for key, (original, n) in counts.items()
        if key not in excluded and (n >= 2 or len(original) >= SOLO_MIN_CHARS)
    ][:CANDIDATE_CAP]
    if not accepted:
        return deck, 0

    # 번역 캐시 일괄 조회 — 캐시에 없는 문장은 이번엔 건너뜀 (추가 비용 0 원칙)
    translations = dict(
        (
            await db.execute(
                select(ChatTranslation.text_key, ChatTranslation.text).where(
                    ChatTranslation.text_key.in_([k for k, _ in accepted]),
                    ChatTranslation.target_lang == learning,
                )
            )
        ).all()
    )

    added = 0
    for key, original in accepted:
        translated = (translations.get(key) or "").strip()
        if not translated:
            continue
        nk = translated.lower()
        # 재사용 항목 방어 — 전역 dedup 으로 기존 항목을 재사용하면 ko_text 가
        # 내 발화와 달라 원문 키 제외가 안 걸린다. 번역문 키(nk:)도 함께 확인
        if f"nk:{nk}"[:200] in excluded:
            continue
        item = (
            await db.execute(
                select(LearningItem).where(
                    LearningItem.item_type == "sentence", LearningItem.normalized_key == nk
                )
            )
        ).scalar_one_or_none()
        if item is None:
            # 학습 카드에 지인 실명이 박제되지 않게 원문 이름을 평범한 이름으로
            # 치환 (2026-08-12 요청 — 직급·직함은 유지). 새 항목 1회만 호출
            safe_original = await translation_service.anonymize_names(original, primary)
            item = LearningItem(
                item_type="sentence",
                en_text=translated,
                ko_text=safe_original,
                normalized_key=nk,
            )
            db.add(item)
            await db.flush()
        occurrence = (
            await db.execute(
                select(ItemOccurrence.id).where(
                    ItemOccurrence.item_id == item.id,
                    ItemOccurrence.content_id == deck.id,
                )
            )
        ).scalar_one_or_none()
        if occurrence is None:
            db.add(ItemOccurrence(item_id=item.id, content_id=deck.id))
            added += 1
    if added:
        await db.flush()
    return deck, added


async def exclude_phrase(db: AsyncSession, user: User, item_id: int) -> bool:
    """덱에서 문장 빼기 — Occurrence 삭제 + 원문 키를 제외 원장에 기록.

    제외 키는 원문(ko_text) 정규화 키 — 번역이 바뀌어도 같은 발화는 계속
    제외된다. 카드(FSRS)는 남지만 항목이 내 콘텐츠에서 빠져 가시성 규칙상
    복습 큐·게임 풀에서 함께 사라진다. 커밋은 호출자 책임.
    """
    deck = (
        await db.execute(
            select(Content).where(Content.source == "chat", Content.created_by == user.id)
        )
    ).scalar_one_or_none()
    if deck is None:
        return False
    occurrence = (
        await db.execute(
            select(ItemOccurrence).where(
                ItemOccurrence.item_id == item_id, ItemOccurrence.content_id == deck.id
            )
        )
    ).scalar_one_or_none()
    if occurrence is None:
        return False
    item = await db.get(LearningItem, item_id)
    await db.delete(occurrence)
    if item is not None:
        # 이중 키 기록 — 원문 키(내 발화) + 번역문 키(nk:). 전역 dedup 으로
        # 재사용된 항목은 ko_text 가 내 발화와 달라 원문 키만으로는 재수집을
        # 못 막는다 (2026-08-12)
        keys = []
        if item.ko_text:
            keys.append(normalize_text_key(item.ko_text))
        keys.append(f"nk:{item.normalized_key}"[:200])
        for key in keys:
            exists = (
                await db.execute(
                    select(PhraseExclusion.id).where(
                        PhraseExclusion.user_id == user.id, PhraseExclusion.text_key == key
                    )
                )
            ).scalar_one_or_none()
            if exists is None:
                db.add(PhraseExclusion(user_id=user.id, text_key=key))
    await db.flush()
    return True
