"""마스코트·악세사리 카탈로그 — XP 상점 상품 (docs/specs/mascot-shop.md).

테마몰과 같은 원칙: 카탈로그는 백엔드가 단일 근거, 보유는 item_grants 행 존재.
가격은 일일 획득량(활성 시 ~500XP) 기준 층위화 — 벤치마크(Duolingo/Habitica/
Forest): 소모품 = 며칠치, 프리미엄 = 층위 상단 (proposal/xp-shop-mascot-2026-08.md).
"""

# 마스코트 — 좌하단 슬롯에 상시 노출되는 움직이는 캐릭터 (1개 활성)
MASCOTS: dict[str, dict] = {
    "henyang": {"label": "헤냥이", "price_xp": 2000},  # 크림 고양이 — cat 테마 대사
    "bricky": {"label": "브리키", "price_xp": 1500},  # 레고 브릭 로봇
    "mongi": {"label": "몽이", "price_xp": 1500},  # 파란 문어
}

# 악세사리/옷 — 보유하면 활성 마스코트에 전부 착용 (all-on, 2026-08-11 사용자 결정)
OUTFITS: dict[str, dict] = {
    "ribbon": {"label": "리본", "price_xp": 300},
    "glasses": {"label": "동그란 안경", "price_xp": 400},
    "scarf": {"label": "목도리", "price_xp": 500},
    "crown": {"label": "왕관", "price_xp": 1000},
}

# 책갈피(스트릭 보호) 충전 — 벤치마크 1순위 상품(손실 회피). 주 1회 무료 지급과 별개
STREAK_SAVER_PRICE_XP = 500

# 소모성 이용권 — 1회권, 보유는 user_settings 카운터 (item_grants 아님).
# message: 캐릭터 말풍선 문구 변경권 (2026-08-21 요청, docs/specs/mascot-shop.md)
PERKS: dict[str, dict] = {
    "message": {"label": "말풍선 변경권", "price_xp": 800},
}


def item_price(item_key: str) -> int | None:
    """ "mascot:henyang" / "outfit:ribbon" / "perk:message" 형식 키의 카탈로그 기본가."""
    kind, _, key = item_key.partition(":")
    if kind == "mascot":
        entry = MASCOTS.get(key)
    elif kind == "outfit":
        entry = OUTFITS.get(key)
    elif kind == "perk":
        entry = PERKS.get(key)
    else:
        return None
    return entry["price_xp"] if entry else None


async def item_policies(db) -> dict[str, dict]:
    """전 아이템의 유효 판매 정책 — 백오피스 오버라이드(item_settings) 병합.

    {item_key: {"price_xp": 유효가, "sale": "xp"|"event"}} — 행 없음 = 기본가·XP 판매.
    카탈로그 조회와 구매 검증이 같은 값을 보도록 단일 헬퍼로 묶는다.
    """
    from sqlalchemy import select

    from app.models import ItemSetting

    overrides = {s.item_key: s for s in (await db.execute(select(ItemSetting))).scalars()}
    policies: dict[str, dict] = {}
    for kind, catalog in (("mascot", MASCOTS), ("outfit", OUTFITS), ("perk", PERKS)):
        for key, meta in catalog.items():
            item_key = f"{kind}:{key}"
            setting = overrides.get(item_key)
            policies[item_key] = {
                "price_xp": setting.price_xp
                if setting and setting.price_xp is not None
                else meta["price_xp"],
                "sale": setting.sale if setting else "xp",
            }
    return policies
