---
name: cg-interview
description: Phase 1 — 새 feature 에 대해 사용자를 인터뷰하여 요구사항을 명확히 합니다. 모호한 지점마다 질문하고, 기술 리서치가 필요하면 수행. `.harness/interview/{YYYY-MM-DD}-{feature}.md` 산출.
---

# Phase 1 — Interview

## 목적

"이 기능 만들어줘" 같은 모호한 요청을 **실행 가능한 요구사항** 으로 바꿉니다. 침묵의 가정을 표면화하는 것이 이 단계의 핵심입니다.

## 입력

- 사용자의 원 요청
- Phase 0 의 `harness/current.md` (프로젝트 제약 조건)

## 출력

- `.harness/interview/{YYYY-MM-DD}-{feature-slug}.md`
- `.harness/spec/constitution.md` — 프로젝트 불변원칙 (생성 또는 갱신, 아래 §Constitution 추출)

## 인터뷰 템플릿

```markdown
# Interview — {feature-slug}

> 날짜: {YYYY-MM-DD}
> 요청자: {user}

## 원 요청
{사용자의 최초 메시지 그대로}

## 목적과 배경
- 왜 지금 이 기능이 필요한가?
- 성공 기준은?

## 기능 범위
- 반드시 포함:
- 명시적 제외:

## 사용자 / 행위자
- 누가 사용하나?
- 어떤 권한 레벨?

## 데이터 / 스키마
- 새 엔티티:
- 기존 스키마 변경:

## 통합 포인트
- 외부 API:
- 내부 서비스:

## 제약 조건
- 성능:
- 보안/규정:
- 기존 아키텍처 제약:

## 비기능 요구사항
- 가용성:
- 관측성:

## 해결되지 않은 질문
- [ ] ...
```

## 수행 원칙

1. **한 번에 한 카테고리만 질문** — 인터뷰 피로를 줄임
2. **예/아니오가 아닌 개방형 질문** 선호
3. **추정 대신 확인**: "사용자가 이걸 원할 것 같다" → "확인해주세요: ..."
4. 기술 용어가 등장하면 `mcp__context7__` 로 공식 문서 확인 (인터뷰에 신뢰도 기록)

## Constitution 추출 — 프로젝트 불변원칙

> spec-kit 의 Constitution Check 패턴 흡수: 인터뷰에서 드러난 **절대 제약**을
> `.harness/spec/constitution.md` 로 성문화한다. cg-plan-check(Phase 4.5)가 이
> 파일을 MUST 게이트로 사용해, 위반 계획을 실행 전에 차단한다.

인터뷰 마무리 단계에서 답변 중 "항상 / 절대 / 금지" 급의 제약을 골라낸다:

| 카테고리 | 예 |
|---------|-----|
| 보안 | "결제 토큰은 클라이언트에 저장 금지" |
| 아키텍처 | "domain 은 presentation 을 의존하지 않는다" |
| 데이터 | "회원 테이블 스키마 변경은 마이그레이션 필수" |
| 범위 | "이번 분기는 iOS 만 지원" |

작성 규칙:

1. **MUST 5~9개 청킹** (Miller's Law, 7±2) — 이번 feature 한정 제약이 아니라
   프로젝트 전체 불변원칙만. 10개째가 필요하면 기존 항목과 병합/일반화.
2. 각 항목은 **검증 가능한 한 문장 + 근거** — "보안을 잘 지킨다" 같은 모호한
   선언 금지. 포맷은 constitution.md 의 표(원칙/근거/검증 방법)를 따른다.
3. constitution.md 가 이미 있으면 **갱신(개정)** — append 로 늘리지 않는다.
   변경 diff 를 사용자에게 보여주고 **사람 확인 후** 반영.
4. feature 한정 제약은 constitution 이 아니라 Phase 2 spec 의 제약 조건 섹션으로.

## Ambiguity Score (수치 게이트)

> ouroboros 의 Socratic Clarity 패턴 흡수: 모호함을 **수치화** 해 Phase 2 진입 가능 여부를 결정.

인터뷰 종료 전, 아래 3개 축으로 0.0 ~ 1.0 모호함 점수를 계산한다:

| 축 | 0.0 (명확) | 1.0 (모호) | 가중치 |
|---|---|---|---|
| **Specificity** | 구체적 수치/파일명/API 명시 | "적절히", "알아서" 남발 | 0.4 |
| **Measurability** | 성공 기준이 관측 가능 (테스트로 검증 가능) | "잘 동작", "빠르게" | 0.4 |
| **Unresolved Questions** | 남은 질문 0개 | 남은 질문 5+ 개 | 0.2 |

Ambiguity Score = 0.4 × Specificity + 0.4 × Measurability + 0.2 × Unresolved

### 임계 게이트

| Score | 게이트 | 다음 행동 |
|---|---|---|
| ≤ 0.20 | **PASS** | Phase 2 (cg-spec-and-harness) 진행 가능 |
| 0.21 - 0.40 | **REVISE** | 추가 질문 2-3회 후 재측정 |
| > 0.40 | **BLOCK** | 인터뷰 중단 불가. 사용자에게 핵심 불명확 영역 명시 후 재개 |

### 인터뷰 말미 출력 예시

```
Ambiguity Score: 0.15 / 1.0 [PASS]
  Specificity:   0.10 (API 스펙, 스키마, 에러 케이스 모두 명시)
  Measurability: 0.20 ("p95 지연 < 300ms" 등 측정 가능)
  Unresolved:    0.10 (남은 질문 1개, Phase 2 에서 추정 가능)

📍 Phase 2 (cg-spec-and-harness) 진행 가능
```

## 완료 조건

- **Ambiguity Score ≤ 0.20**
- 새 불변원칙이 드러났으면 `.harness/spec/constitution.md` 생성/갱신 (사람 확인 완료)
- 사용자 명시적 승인
