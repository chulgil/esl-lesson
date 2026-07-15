"""닉네임 — 랜덤 초기값 생성 + 검증 (개인정보 비노출 원칙).

구글 이름은 다른 사용자에게 절대 노출하지 않는다. 가입 시 랜덤 닉네임을
부여하고, 사용자가 설정에서 언제든 바꾼다 (docs/specs/auth.md 닉네임).
"""

import secrets

ADJECTIVES = (
    "몰랑한",
    "명랑한",
    "반짝이는",
    "씩씩한",
    "포근한",
    "재빠른",
    "궁금한",
    "신나는",
    "의젓한",
    "엉뚱한",
)
NOUNS = (
    "냥이",
    "브릭",
    "연필",
    "별사탕",
    "곰돌이",
    "토끼",
    "펭귄",
    "고래",
    "여우",
    "부엉이",
)

MIN_LEN = 2
MAX_LEN = 16


def random_nickname() -> str:
    """예: 몰랑한냥이42 — 형용사+명사+2자리 (충돌 확률만 낮추면 충분, 유일성 비강제)."""
    return f"{secrets.choice(ADJECTIVES)}{secrets.choice(NOUNS)}{secrets.randbelow(90) + 10}"


def normalize_nickname(raw: str) -> str:
    """공백 정리 + 길이/제어문자 검증. 위반 시 ValueError."""
    nickname = " ".join(raw.split())
    if not (MIN_LEN <= len(nickname) <= MAX_LEN):
        raise ValueError(f"nickname must be {MIN_LEN}-{MAX_LEN} chars")
    return nickname
