"""내가 쓰는 말 덱 — 채팅 발화를 학습 항목으로 (docs/specs/my-phrases.md).

내가 보낸 주언어 메시지 중 번역 캐시(chat_translations)에 쌍이 있는 것만
수집한다 — 추가 번역 비용 0 원칙. 발화가 속한 **방의 target_lang** 별로
그룹핑해 언어당 1개의 개인 콘텐츠(source="chat", private)에 문장 항목으로
합류시키면 복습 큐·문장 게임 3종(타자/어순/받아쓰기)·덱 학습·시험이 기존
파이프라인 그대로 태워진다. 활성 문장은 언어당 100개 목표로 순환 보충된다
(장기기억 도달 시 졸업 → 빈 자리를 다음 sync 가 채운다).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChatMessage,
    ChatTranslation,
    Content,
    ContentSubscription,
    Conversation,
    ItemOccurrence,
    LearningItem,
    PhraseExclusion,
)
from app.models.user import User, UserSettings
from app.services import translation as translation_service
from app.services.langs import LANG_LABELS, detect_lang, normalize_text_key

MIN_CHARS = 4  # "ㅋㅋ"·"네" 제외
# 채택 = 빈도 2회 이상 — "자주 쓰는 말"의 이름값 (2026-08-12 기획 점검:
# 길이 조건으로 1회 발화가 올라가던 규칙 제거. 한 번 쓴 말은 아직 '내 말'이 아니다)
MIN_FREQUENCY = 2
CANDIDATE_CAP = 200  # 언어별 동기화당 채택 상한 (폭주 방지)
MESSAGE_SCAN_LIMIT = 2000  # 최근 메시지 스캔 창 (전체 방 합산 — 다작 유저 트레이드오프)
DECK_TITLE_PREFIX = "내가 쓰는 말"
# 활성(비장기기억) 목표 — 언어당 100문장, 부족분만 빈도순 승격 (my-phrases.md)
ACTIVE_TARGET = 100


def deck_title(lang: str) -> str:
    label = LANG_LABELS.get(lang, lang)
    return f"{DECK_TITLE_PREFIX} ({label})"


async def _get_or_create_deck(db: AsyncSession, user: User, lang: str) -> Content:
    deck = (
        await db.execute(
            select(Content).where(
                Content.source == "chat",
                Content.created_by == user.id,
                Content.lang == lang,
                # legacy((일반) 덱)는 별개 행 — 여기서 재사용하지 않는다 (덱 그룹화)
                Content.chat_kind.is_(None),
            )
        )
    ).scalar_one_or_none()
    if deck is None:
        deck = Content(
            source="chat",
            visibility="private",
            title=deck_title(lang),
            status="ready",
            created_by=user.id,
            lang=lang,
        )
        db.add(deck)
        await db.flush()
        # 구독은 **생성 시 1회만** — sync 마다 재구독하면 문서함에서 뺀
        # 사용자의 의사를 다음 조회가 뒤집는다 (2026-08-18 담기/빼기)
        db.add(ContentSubscription(content_id=deck.id, user_id=user.id))
        await db.flush()
    else:
        # 기존 단일 덱(언어 표기 없던 시절) 제목을 lazy 갱신 — lang 은 유지
        wanted_title = deck_title(lang)
        if deck.title != wanted_title:
            deck.title = wanted_title
    return deck


async def is_subscribed(db: AsyncSession, deck_id: int, user_id: int) -> bool:
    """문서함 담김 상태 — 빼면 큐·게임에서 제외되고 수집·편집은 계속된다."""
    return (
        await db.execute(
            select(ContentSubscription.id).where(
                ContentSubscription.content_id == deck_id,
                ContentSubscription.user_id == user_id,
            )
        )
    ).scalar_one_or_none() is not None


async def deck_counts(db: AsyncSession, user_id: int, deck_id: int) -> tuple[int, int]:
    """(활성, 전체) — 활성 = 장기기억 미도달 occurrence (mastered_item_clause 반대).

    졸업(장기기억 도달)한 occurrence 는 지운 것이 아니라 활성 카운트에서만
    제외된다 — 다음 sync 가 그 빈 자리를 새 후보로 채운다.
    """
    from app.services.game.typing_race import mastered_item_clause

    total = (
        await db.execute(
            select(func.count(ItemOccurrence.id)).where(ItemOccurrence.content_id == deck_id)
        )
    ).scalar_one()
    active = (
        await db.execute(
            select(func.count(ItemOccurrence.id))
            .join(LearningItem, LearningItem.id == ItemOccurrence.item_id)
            .where(ItemOccurrence.content_id == deck_id, mastered_item_clause(user_id))
        )
    ).scalar_one()
    return active, total


async def get_legacy_deck(db: AsyncSession, user_id: int) -> Content | None:
    """(일반) 덱 — 개편 전(언어 분리 이전) 수집분 (chat_kind='legacy').

    신규 수집은 동결(sync_my_phrases 가 만들지 않는다) — 편집·번역 새로고침·
    학습·게임 풀 합류는 언어별 덱과 동일하게 동작한다 (my-phrases.md 덱 그룹화).
    사용자당 1개가 정상이지만, id 오름차순 1건으로 방어적으로 고른다."""
    return (
        (
            await db.execute(
                select(Content)
                .where(
                    Content.source == "chat",
                    Content.created_by == user_id,
                    Content.chat_kind == "legacy",
                )
                .order_by(Content.id)
                .limit(1)
            )
        )
        .scalars()
        .first()
    )


async def legacy_total(db: AsyncSession, user_id: int) -> int:
    """(일반) 덱 문장 수 — 프론트가 (일반) 칩 노출 여부를 판단하는 근거
    (my-phrases.md API·화면)."""
    deck = await get_legacy_deck(db, user_id)
    if deck is None:
        return 0
    return (
        await db.execute(
            select(func.count(ItemOccurrence.id)).where(ItemOccurrence.content_id == deck.id)
        )
    ).scalar_one()


async def _promote_candidates(
    db: AsyncSession,
    user: User,
    deck: Content,
    counts: dict[str, tuple[str, int]],
    excluded: set[str],
    primary: str,
) -> int:
    """빈도순 정렬 후 활성 100 목표까지 승격 + 기존 occurrence freq 재집계.

    이미 덱에 있는 occurrence(활성이든 졸업이든)는 freq 만 최신화하고,
    새 occurrence 는 활성 목표(ACTIVE_TARGET)에 여유가 있을 때만 추가한다
    — 졸업으로 빈 자리가 생겨야 다음 후보가 올라온다 (100 초과 강등 없음)."""
    accepted = sorted(
        (
            (key, original, n)
            for key, (original, n) in counts.items()
            if key not in excluded and n >= MIN_FREQUENCY
        ),
        key=lambda t: -t[2],
    )[:CANDIDATE_CAP]
    if not accepted:
        return 0

    translations = dict(
        (
            await db.execute(
                select(ChatTranslation.text_key, ChatTranslation.text).where(
                    ChatTranslation.text_key.in_([k for k, _, _ in accepted]),
                    ChatTranslation.target_lang == deck.lang,
                )
            )
        ).all()
    )

    active, _total = await deck_counts(db, user.id, deck.id)
    budget = max(0, ACTIVE_TARGET - active)

    added = 0
    for key, original, n in accepted:
        translated = (translations.get(key) or "").strip()
        if not translated:
            continue  # 번역 캐시 미히트 — 추가 비용 0 원칙, 이번엔 건너뜀
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
                select(ItemOccurrence).where(
                    ItemOccurrence.item_id == item.id, ItemOccurrence.content_id == deck.id
                )
            )
        ).scalar_one_or_none()
        if occurrence is not None:
            occurrence.freq = n  # 재집계 — 활성/졸업 무관 최신화
            continue
        if budget <= 0:
            continue  # 활성 100 도달 — 다음 sync 의 졸업 빈 자리를 기다린다
        db.add(ItemOccurrence(item_id=item.id, content_id=deck.id, freq=n))
        added += 1
        budget -= 1
    if added:
        await db.flush()
    return added


async def sync_my_phrases(
    db: AsyncSession, user: User, settings: UserSettings | None, lang: str | None = None
) -> tuple[Content, int]:
    """멱등 동기화 — 스캔 창의 메시지를 방(target_lang)별로 그룹핑해 언어별
    덱에 합류시킨다. 반환: (요청한 lang 의 덱, 이번 sync 로 그 덱에 새로
    추가된 항목 수). 커밋은 호출자 책임."""
    primary = settings.primary_lang if settings and settings.primary_lang else "ko"
    default_lang = (settings.learning_langs if settings and settings.learning_langs else ["en"])[0]
    resolved_lang = lang or default_lang

    rows = (
        await db.execute(
            select(ChatMessage.body, Conversation.target_lang)
            .join(Conversation, Conversation.id == ChatMessage.conversation_id)
            .where(
                ChatMessage.sender_id == user.id,
                ChatMessage.deleted_at.is_(None),
                ChatMessage.body != "",
                # 시스템 줄(공지 등) 제외 (docs/specs/chat-notice.md)
                ChatMessage.kind.is_(None),
                # 일반 대화 방(plain)은 학습 문맥이 아님 — 수집 제외 (스펙 §일반 대화 방)
                Conversation.mode == "learn",
            )
            .order_by(ChatMessage.id.desc())
            .limit(MESSAGE_SCAN_LIMIT)
        )
    ).all()

    # 후보 집계 — 발화가 속한 방의 target_lang 별로 그룹핑 (설정값이 아니라
    # 방 기준, docs/specs/my-phrases.md 언어별 덱). 정규화 키 기준 빈도.
    counts_by_lang: dict[str, dict[str, tuple[str, int]]] = {}
    for body, target_lang in rows:
        text = body.strip()
        if len(text) < MIN_CHARS or "http" in text:
            continue
        if detect_lang(text) != primary:
            continue
        key = normalize_text_key(text)
        bucket = counts_by_lang.setdefault(target_lang, {})
        first, n = bucket.get(key, (text, 0))
        bucket[key] = (first, n + 1)

    # 사용자가 뺀 문장은 재수집하지 않는다 (my-phrases.md 편집) — 언어 무관 공용 원장
    excluded = set(
        (
            await db.execute(
                select(PhraseExclusion.text_key).where(PhraseExclusion.user_id == user.id)
            )
        ).scalars()
    )

    added_for_resolved = 0
    for target_lang, counts in counts_by_lang.items():
        deck = await _get_or_create_deck(db, user, target_lang)
        added = await _promote_candidates(db, user, deck, counts, excluded, primary)
        if target_lang == resolved_lang:
            added_for_resolved = added

    # 요청한 언어의 덱은 이번 스캔 창에 후보가 없어도 존재를 보장 (기존 조회 계약)
    deck = await _get_or_create_deck(db, user, resolved_lang)
    return deck, added_for_resolved


REFRESH_CAP = 300  # 한 번에 갱신하는 항목 상한 (LLM 호출 폭주 방지)


async def refresh_my_phrases(
    db: AsyncSession, user: User, settings: UserSettings | None, lang: str | None = None
) -> int:
    """내 덱 전체 번역 품질 새로고침 — 항목 ID 유지(복습 진행도 보존).

    엔진·프롬프트가 개선됐을 때 기존 문장을 새 품질로: 원문 실명 치환
    (anonymize) 후 재번역해 ko/en 텍스트를 제자리 갱신. 본인 덱만(언어별,
    lang 지정 — 미지정 시 learning_langs[0], 'legacy'=(일반) 덱) — 항목이
    공유(전역 dedup)됐어도 chat 덱 항목은 채팅 유래라 사실상 개인 소유.
    사용량은 translation_usage 에 기록(예산 회계). 커밋은 호출자 책임.
    """
    from app.models import TranslationUsage

    primary = settings.primary_lang if settings and settings.primary_lang else "ko"
    default_lang = (settings.learning_langs if settings and settings.learning_langs else ["en"])[0]
    resolved_lang = lang or default_lang
    if resolved_lang == "legacy":
        deck = await get_legacy_deck(db, user.id)
    else:
        deck = (
            await db.execute(
                select(Content).where(
                    Content.source == "chat",
                    Content.created_by == user.id,
                    Content.lang == resolved_lang,
                    Content.chat_kind.is_(None),
                )
            )
        ).scalar_one_or_none()
    if deck is None:
        return 0
    items = (
        (
            await db.execute(
                select(LearningItem)
                .join(ItemOccurrence, ItemOccurrence.item_id == LearningItem.id)
                .where(ItemOccurrence.content_id == deck.id)
                .limit(REFRESH_CAP)
            )
        )
        .scalars()
        .all()
    )
    updated = 0
    for item in items:
        ko = (item.ko_text or "").strip()
        if not ko:
            continue
        safe = await translation_service.anonymize_names(ko, primary)
        # deck.lang(실제 번역 대상 언어) 사용 — resolved_lang 은 'legacy' 일 수 있어
        # 번역 엔진에 그대로 넘기면 안 된다 (덱 그룹화)
        result = await translation_service._translate_via_chain(safe, deck.lang)  # noqa: SLF001
        if result is None:
            continue  # 엔진 불가 — 남은 항목은 다음 새로고침에서
        translated, engine = result
        item.ko_text = safe
        item.en_text = translated
        db.add(TranslationUsage(user_id=user.id, chars=len(safe), engine=engine))
        updated += 1
    if updated:
        await db.flush()
    return updated


async def exclude_phrase(db: AsyncSession, user: User, item_id: int) -> bool:
    """덱에서 문장 빼기 — Occurrence 삭제 + 원문 키를 제외 원장에 기록.

    항목이 내 chat 덱들(언어 무관) 중 어디에 속하든 탐색한다 — 언어별로
    나뉜 덱이라도 빼기는 사용자 기준 단일 동작 (my-phrases.md DELETE).
    제외 키는 원문(ko_text) 정규화 키 — 번역이 바뀌어도 같은 발화는 계속
    제외된다. 카드(FSRS)는 남지만 항목이 내 콘텐츠에서 빠져 가시성 규칙상
    복습 큐·게임 풀에서 함께 사라진다. 커밋은 호출자 책임.
    """
    deck_ids = (
        (
            await db.execute(
                select(Content.id).where(Content.source == "chat", Content.created_by == user.id)
            )
        )
        .scalars()
        .all()
    )
    if not deck_ids:
        return False
    occurrence = (
        await db.execute(
            select(ItemOccurrence).where(
                ItemOccurrence.item_id == item_id, ItemOccurrence.content_id.in_(deck_ids)
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
