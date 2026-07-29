---
name: cg-qa
description: "경량 3단 판정 (PASS/REVISE/FAIL) 으로 산출물 품질을 빠르게 판단. cg-evaluation 과 병립. Adapted from Q00/ouroboros (MIT)."
---

# cg-qa — 빠른 품질 판정

**트리거 키워드**: "qa", "품질 확인", "quality check"

## 개요

임의 산출물(코드·스펙·테스트 출력·API 응답)에 대해 **단일 패스**로 점수와 verdict 를 산출한다.

`cg-evaluation` 과 `cg-qa` 는 **보완 관계**이지 대체 관계가 아니다:

| | cg-evaluation | cg-qa |
|---|---|---|
| 용도 | Phase 6 포멀 검증 | 반복 중 빠른 체크 |
| 패스 수 | 3-critic (code / test / e2e) | 단일 패스 |
| 기준 | rubric 가중 평균 ≥ 7.5 | score ≥ 0.80 (PASS) |
| 시간 | 수 분 | 수 초 |
| 용례 | PR 머지 전 최종 검증 | cg-ralph 루프의 검증 단계 (ralph 구성 설치 시) |

## Verdict 임계

| Score | Verdict | Loop Action | 다음 행동 |
|---|---|---|---|
| ≥ 0.80 | **PASS** | done | 품질 기준 달성, 다음 단계 진행 |
| 0.40-0.79 | **REVISE** | continue | 제안사항 반영 후 재실행 |
| < 0.40 | **FAIL** | escalate | 근본적 문제, cg-unstuck(ralph 구성 설치 시) 또는 cg-interview 로 |

### UNCERTAIN — 검증자의 정직한 기권

점수로 판정할 수단이 없으면 낮은 점수로 추측하지 말고 **UNCERTAIN(사유 필수)** 을 반환한다:

| 사유 | 의미 | 처리 경로 |
|---|---|---|
| `unverifiable_runtime` | 실행해야만 확인 가능 (정적 검토로 판정 불가) | 실기/E2E 게이트로 승격 제안 (mechanical e2e; frontend 구성 설치 시 cg-ui-loop) |
| `insufficient_spec` | 스펙이 검증 가능하게 정의되어 있지 않음 | cg-interview / spec 보강 제안 후 재평가 |

**관측된 부재는 UNCERTAIN 이 아니라 FAIL** — "테스트가 없다", "에러 처리가 없다"처럼 산출물에서 직접 관측한 결함은 FAIL/REVISE 로 판정한다. UNCERTAIN 은 "판정할 수단이 없다"일 때만.

## 평가 차원 (5가지)

| 차원 | 설명 |
|---|---|
| **Correctness** | 로직이 의도대로 동작하는가 |
| **Completeness** | 누락된 기능/케이스가 있는가 |
| **Quality** | 네이밍·구조·가독성 |
| **Intent Alignment** | 스펙/요청과의 일치도 |
| **Domain-Specific** | 도메인 규약 (보안·성능·접근성 등) |

## 실행 절차

1. **산출물 결정**
   - 파일 경로 제공 → Read
   - 인라인 텍스트 → 직접 사용
   - 미지정 → 최근 실행 결과 사용
   - 불명확 → 사용자에게 질문

2. **품질 바 결정**
   - spec 에 §2 성공 기준이 있으면 그것 사용
   - 없으면 사용자에게 "이 산출물에서 'PASS' 란 무엇?" 질문
   - TDD 맥락이면: 모든 테스트 통과 + 린트 0건

3. **5개 차원 각각 0.0 ~ 1.0 점수화**
   - 차원별 가중치는 산출물 타입에 따라:
     - code: Correctness 0.3 / Completeness 0.2 / Quality 0.2 / Intent 0.2 / Domain 0.1
     - spec: Intent 0.4 / Completeness 0.3 / Quality 0.2 / Correctness 0.1 / Domain 0.0
     - test output: Correctness 0.5 / Completeness 0.4 / 기타 0.1

4. **verdict + 다음 행동 출력**

## 출력 포맷

```
QA Verdict [Iteration {N}]
============================================================
Session: qa-{id}
Score: 0.72 / 1.00 [REVISE]
Verdict: revise
Threshold: 0.80

Dimensions:
  Correctness:      0.85
  Completeness:     0.60
  Quality:          0.75
  Intent Alignment: 0.80
  Domain-Specific:  0.60

Differences:
  - {구체적 차이 1}
  - {구체적 차이 2}

Suggestions:
  - {실행 가능한 수정 1}
  - {실행 가능한 수정 2}

Reasoning: {1-3 문장 요약}

Loop Action: continue

📍 Next: {PASS/REVISE/FAIL 별 다음 행동}
```

## 반복 QA

`ralph` 구성도 설치되어 있다면, `cg-ralph` 와 결합해 사용할 때:

1. 첫 호출에 `qa_session_id` 생성 (`qa-<uuid4_short>`)
2. 각 반복의 verdict 를 `.harness/journal/{YYYY-MM-DD}.md` 에 누적
3. PASS 또는 FAIL 까지 계속

## 예시

```
사용자: /cg-qa src/main.py

QA Verdict [Iteration 1]
============================================================
Session: qa-a1b2c3d4
Score: 0.72 / 1.00 [REVISE]

Dimensions:
  Correctness:      0.85
  Completeness:     0.60
  Quality:          0.75
  Intent Alignment: 0.80
  Domain-Specific:  0.60

Differences:
  - fetch_data() 에 TimeoutError 처리 없음
  - user_id 입력 검증 없음
  - 3개 public 함수에 타입 힌트 없음

Suggestions:
  - fetch_data() (line 42) 에 try/except TimeoutError 추가
  - 함수 진입 시 isinstance(user_id, str) 체크
  - get_user(), fetch_data(), process_result() 반환 타입 어노테이션

Reasoning: 핵심 로직은 정상이나 프로덕션 코드에 기대되는 방어적 프로그래밍이 부족.

Loop Action: continue

📍 Next: 제안사항 반영 후 /cg-qa 재실행 — 또는 /cg-ralph 로 자동 루프
```

## 금지

- PASS 기준을 **사후에** 낮추기 ("0.75도 통과로 치자") — 품질 바는 산출물 평가 **전**에 결정.
- 차원 점수를 하나도 매기지 않고 총점만 제시.
- 사용자 요청 없이 임계값(0.80) 을 변경.
