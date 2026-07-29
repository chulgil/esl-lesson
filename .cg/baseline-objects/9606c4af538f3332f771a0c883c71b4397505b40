---
name: cg-pm
description: "Product Manager 페르소나로 spec 의 비즈니스 합리성·범위·우선순위를 검토. 트리거: PM 리뷰, product review, 우선순위 검토, scope check, 이거 만들 가치 있나, 비즈니스 검증."
---

# cg-pm — Product Manager 검토 스킬

## 트리거 키워드

`PM 리뷰`, `product review`, `우선순위 검토`, `scope check`,
`이거 만들 가치`, `비즈니스 검증`, `pm 관점`, `왜 만드는가`.

## 목적

엔지니어 관점 (cg-evaluation Critic 1: Code) 만으로는 **잘못된 것을
잘 만드는** 위험이 남는다. cg-pm 은 spec 단계에서 PM 페르소나로
세 가지 질문을 던져 범위 inflation 과 가치 누락을 잡아낸다.

## 입력

- `.harness/spec/{date}-{feature}.md` (가장 최근 spec)
- 선택: `.harness/visuals/{feature}/` (있으면 참고)

## 3대 질문 + 점수

| 질문 | 점수 (0–3) | 통과선 |
|---|---|---|
| **1. Why now?** 왜 지금 만들어야 하는가? 다른 우선순위 대비 시급한가? | 0–3 | ≥2 |
| **2. Who suffers if we don't?** 만들지 않으면 누가 어떤 손해를 보는가? | 0–3 | ≥2 |
| **3. Smallest valuable slice?** 가치를 검증할 가장 작은 범위는 무엇인가? | 0–3 | ≥2 |

세 항목 모두 ≥2 → **PM-PASS**. 하나라도 <2 → **PM-REVISE**.
모두 0–1 → **PM-REJECT** (아직 spec 작성하지 말 것).

### 점수 기준

- **3**: spec 본문에 명시적 근거가 있다 (수치, 사용자 인용, 시장 데이터).
- **2**: 합리적 추정이 가능하다 (논리적 추론, 유사 사례 참조).
- **1**: 추정 가능하나 근거가 약하다.
- **0**: 답할 수 없다.

## 절차

1. spec 의 "Why" / "사용자" / "범위" 섹션을 읽는다 (없으면 0점 직행).
2. 3대 질문에 대해 각각 점수 + 한 줄 근거 작성.
3. 미달 항목이 있으면 spec 으로 돌려보내며 **무엇을 추가해야 하는가** 명시.

## 출력 포맷

```
PM Review — {feature-slug}
============================================================
Q1. Why now?              [3] "이번 분기 OKR 의 핵심 지표"
Q2. Who suffers if not?   [2] "월 50건 수동 처리 → 운영팀 부하"
Q3. Smallest slice?       [1] "MVP 정의 부재 — '관리자 알림만' 으로 좁힐 수 있음"

Verdict: PM-REVISE
다음 행동:
  - spec 의 "범위" 섹션을 MVP 1단계 (관리자 알림) 만으로 축소
  - "사용자 알림 / 이메일 / 푸시" 는 Phase 2 spec 으로 분리
```

## 호출 시점

- Phase 2 (`cg-spec-and-harness`) **직후**, decomposition 이전.
- spec 큰 변경 후 재검토 시.
- 기존 feature 가 너무 커졌다고 느낄 때 (scope creep 점검).

## 원칙

- 코드를 읽지 않는다 (Code Critic 과 격리).
- spec 의 본문 근거만 본다. 추측·추정에 점수 후하게 주지 않는다.
- "PM-REJECT" 는 강한 신호. spec 자체를 쓰기 전에 cg-interview 로 회귀.
- cg-pm 은 cg-evaluation (3-critic) 의 Pre-flight. 통과 후 평가 단계로.
