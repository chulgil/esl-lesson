"""업적 달성 → 테마 자동 지급 엔진 (docs/specs/theme-mall.md).

업적은 로그 실시간 집계(소급 반영)라, 규칙만 있으면 과거 달성자도
다음 테마 조회 때 자동 지급된다 — 별도 백필 불필요.

호출 지점: GET /api/themes (AppNav 가드·설정) + GET /api/study/achievements
(학습 홈). 잠김 오판(달성했는데 미지급 상태로 note 복귀) 방지를 위해
allowed 판정보다 먼저 실행한다.

비용 가드: 미지급 규칙 테마가 없으면 업적 집계를 건너뛴다 —
정착 상태에선 규칙·지급 2쿼리로 끝난다.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ThemeGrant, ThemeRewardRule
from app.services import achievements
from app.services.notifications import notify


async def sync_theme_rewards(db: AsyncSession, user_id: int) -> list[str]:
    """달성한 업적의 보상 테마를 지급 (멱등). 새로 지급된 테마 키를 반환."""
    rules = (await db.execute(select(ThemeRewardRule))).scalars().all()
    if not rules:
        return []
    granted = set(
        (
            await db.execute(select(ThemeGrant.theme_key).where(ThemeGrant.user_id == user_id))
        ).scalars()
    )
    pending = [r for r in rules if r.theme_key not in granted]
    if not pending:
        return []

    items = await achievements.compute(db, user_id)
    achieved = {i["key"] for i in items if i["achieved"]}
    titles = {i["key"]: i["title"] for i in items}

    newly: list[str] = []
    for rule in pending:
        if rule.achievement_key not in achieved or rule.theme_key in granted:
            continue
        title = titles.get(rule.achievement_key, rule.achievement_key)
        # note = 지급 사유 이력 — 규칙이 나중에 바뀌어도 "왜 받았는지" 가 남는다
        try:
            # SAVEPOINT 로 이 grant 시도만 격리 — GET /api/themes 와
            # GET /api/study/achievements 병렬 호출 경합(uq_theme_grants_user_theme)
            # 으로 한 건이 실패해도, 같은 호출에서 먼저 성공한 다른 grant 는
            # 롤백되지 않는다 (2026-08-11 500 픽스)
            async with db.begin_nested():
                db.add(
                    ThemeGrant(
                        user_id=user_id, theme_key=rule.theme_key, note=f"업적 달성: {title}"
                    )
                )
                await db.flush()
        except IntegrityError:
            # 동시 요청이 이미 지급을 마쳤다 — 그냥 넘어간다
            granted.add(rule.theme_key)
            continue
        await notify(db, user_id, "theme_granted", {"theme_key": rule.theme_key, "note": title})
        granted.add(rule.theme_key)
        newly.append(rule.theme_key)
    if newly:
        await db.commit()
    return newly
