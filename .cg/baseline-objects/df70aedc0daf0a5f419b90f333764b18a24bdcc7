---
name: cg-ralph
description: "검증 통과까지 멈추지 않는 영속 루프. 구현 → 검증 → 실패 시 재시도. max_iterations 필수. Adapted from Q00/ouroboros (MIT)."
---

# cg-ralph — The Boulder Never Stops

**트리거 키워드**: "ralph", "계속", "멈추지 마", "될 때까지", "실패하면 다시"

## 개요

실패 → 분석 → 재시도를 루프로 돌려, QA PASS 에 도달할 때까지 세션 내에서 자율 반복. 각 반복은 최신 실패 신호(테스트 로그, 타입 오류, 드리프트)를 입력으로 삼는다.

`cg-evaluation` 과의 차이:
- `cg-evaluation` = 3-critic 포멀 검증 (1회 판정)
- `cg-ralph` = 경량 QA + 루프 (PASS 까지 계속)

## 선행 조건 (중단 조건)

다음 중 하나라도 미충족이면 ralph 를 시작하지 않는다:

- [ ] `.harness/spec/{feature}.md` §2 성공 기준 존재
- [ ] `max_iterations` 명시 (기본값 10, 사용자 지정 가능)
- [ ] 기계적 검증 명령 존재 (`.cg/mechanical.toml` 또는 명시된 test 명령)

조건 미충족 → `cg-interview` 또는 `cg-spec-and-harness` 로 먼저 유도.

## 루프 구조

```
iteration = 1
while iteration <= max_iterations:
  1. EXECUTE
     - 최근 실패 신호를 먼저 요약
     - 스펙 §2 성공 기준 중 미충족 항목만 타겟
     - 독립 작업은 병렬 (여러 파일 동시 수정)
     - 실패 재현 테스트를 먼저 씀 (TDD RED)

  2. VERIFY (경량 QA)
     - .cg/mechanical.toml 의 build/test/lint 실행
     - frontend 구성도 설치되어 있다면, UI 작업 시 ui 게이트(골든) 포함 — 시각 증거 확인은 cg-ui-loop 절차
     - 출력 파싱 → 점수 0.0 ~ 1.0
     - verdict: PASS (>=0.80) / REVISE (0.40-0.79) / FAIL (<0.40)

  3. DECIDE
     - PASS → 종료, cg-evaluation 으로 포멀 검증 제안
     - REVISE → 아래 §정체·진동 감지 먼저 확인 → 해당 없으면 실패 신호 요약 후 iteration += 1
     - FAIL → 즉시 중단, cg-unstuck 으로 에스컬레이션

  4. TRACE (반복마다, .harness/status/loop-trace.jsonl 에 append)
     {"i": 2, "max": 10, "verdict": "REVISE", "score": 0.65,
      "failed_checks": ["test_timeout", "type:api.py"], "ladder": 1, "ts": "..."}

  5. REPORT (반복마다)
     [Ralph Iteration {i}/{max}]
     QA Verdict: {PASS/REVISE/FAIL} ({score}, 직전 대비 {+/-delta})
     실패 신호:
       - {signal 1}
       - {signal 2}
     The boulder never stops. 다음 시도: {action} (사다리 {ladder}단)
```

## 정체·진동 감지 — 같은 재시도의 반복 금지

REVISE 에서 무조건 재시도하지 않는다. loop-trace 의 직전 기록과 비교해:

| 신호 | 판정 기준 | 행동 |
|---|---|---|
| **정체(plateau)** | score 개선 < 0.05 가 2회 연속 | 사다리 1단 승급 (같은 접근 재시도 금지) |
| **retry-storm** | failed_checks 집합이 직전과 동일 | 사다리 1단 승급 — 같은 실패에 같은 처방은 무효였다는 증거 |
| **진동(oscillation)** | loop-detection 훅이 A→B→A 경고 | 사다리 2단 이상으로 점프 (두 접근 모두 불충분 — 제3의 접근 또는 트레이드오프 질문) |

## 에스컬레이션 사다리 (5단)

무진전 시 아래 순서로 **한 단씩** 올라간다. 각 단은 loop-trace 의 `ladder` 필드에 기록:

1. **실패 신호 반영 재시도** — 기본. 최신 실패 신호를 입력으로 다른 수정 시도
2. **접근 전환** — `cg-unstuck` 5-persona 측면 사고로 다른 각도의 해법
3. **scope 축소** — 가장 작은 검증 가능 단위로 좁혀 부분 PASS 확보 후 확장 (retry-storm 표준 처방)
4. **effort/모델 승급** — 더 깊은 추론(ultrathink) 또는 상위 모델 워커/fresh 서브에이전트에 해당 job 위임 (reasoning-budget.md "repeated failures 시 escalate" 의 구체화)
5. **defer** — 사용자에게 트레이드오프 질문 (night 구성도 설치되어 있다면, 무인모드는 night-queue.md 적재 — unattended-autonomy.md)

## 이중 제약 게이트 — 검증 해킹 방어

PASS 판정은 두 조건을 **동시에** 요구한다 (한 차원만 약화시켜 통과하는 것을 차단):

1. 기계 게이트 green (`.cg/mechanical.toml` build/test/lint)
2. **검증자산 불변**: 이번 루프의 diff 에 테스트 삭제·skip 추가·assertion 완화·
   확정 골든(스냅샷) 파일 갱신·mechanical.toml/게이트 스크립트 수정이 없어야 한다.
   있으면 verdict 무효 — FAIL 처리 (임시 골든 예외는 frontend 구성의 cg-ui-loop 참조)

게이트 자체는 루프 안에서 수정 금지(immutable). 게이트가 잘못됐다고 판단되면 루프를 멈추고 사용자에게 보고한다.

## 컨텍스트 위생 — fresh process 원칙

인세션 루프는 iteration 이 쌓일수록 컨텍스트가 부패한다(context rot). Ralph 정본(Huntley)은 매 iteration 새 프로세스다:

- **5+ iterations 예상** 또는 **컨텍스트 50% 초과** → 인세션 루프 대신 headless 외곽 루프(night 구성도 설치되어 있다면 `.harness/night/cg-night-run.sh` 계열, iteration 마다 fresh `claude -p`)로 전환을 제안
- 인세션 유지 시: 사다리 4단의 fresh 서브에이전트 위임으로 메인 컨텍스트를 얇게 유지 (서브에이전트 = 컨텍스트 경계)

## 라운드 위생 — 반복 자체는 신뢰성이 아니다

> 출처 수렴 (2026-07-28): arXiv 2607.24604 "Looping Is Not Reliability" — 강제
> 리비전 반복 시 정확도 0.820 → 0.673 (맞는 답을 찾고도 잃는다), stale trace 가
> 정답 훼손의 주범. + AHE 라운드 검증 + superpowers v6.2.0 범위 한정 re-review.

반복 횟수가 아니라 **각 라운드에 주는 증거의 신선도**가 루프 품질을 결정한다:

1. **상태-바인딩 신선 증거**: 매 iteration 의 판단 근거는 이번 라운드에 새로 실행한
   게이트 출력만 사용한다. 이전 iteration 의 실패 로그·요약(stale trace)을 근거로
   수정하지 않는다 — 이미 고쳐진 문제를 다시 "고치다" 정답을 훼손하는 실측 실패 모드.
2. **범위 한정 리비전**: REVISE 는 이번 라운드 실패 신호가 가리키는 범위만 수정한다.
   실패 신호가 없는데 리비전을 강제하지 않는다 (green 인데 "한 번 더 다듬기" 금지).
3. **PASS 후 재진입 금지**: 이중 제약 게이트 PASS 후 같은 목표로 루프를 더 돌리지
   않는다. 개선 여지는 루프 밖 별도 스코프로 (cg-evaluation·/simplify).

## 종료 처리

| 종료 사유 | 다음 단계 제안 |
|---|---|
| PASS 도달 | `cg-evaluation` 으로 3-critic 포멀 검증 |
| max_iterations 도달 | `cg-unstuck` 으로 측면 사고 시도 또는 `cg-interview` 로 스펙 재검토 |
| FAIL 에스컬레이션 | 즉시 `cg-unstuck` 호출 |
| 사용자 "stop" | 현재 iteration 결과 유지, 재개 가능 상태로 보고 |

## 반복 로그 (권장)

각 iteration 의 요약을 `.harness/journal/{YYYY-MM-DD}.md` 에 기록:

```markdown
## Ralph Session {session_id}
- Request: {원래 요청}
- Spec: {참조 spec 파일}
- Max iterations: {N}

### Iteration 1/N
- Verdict: REVISE (0.65)
- 실패 신호: 3개 테스트 여전히 실패, api.py 타입 오류
- 적용한 변경: type annotations 보강

### Iteration 2/N
- Verdict: PASS (1.0)
- 종료
```

## 예시

```
사용자: /cg-ralph 실패하는 모든 테스트 고쳐줘 (max_iterations=5)

[Ralph Iteration 1/5]
QA Verdict: REVISE (0.65)
실패 신호:
  - tests/test_api.py::test_timeout 실패 (TimeoutError 미처리)
  - src/api.py:42 타입 오류
The boulder never stops. 다음 시도: fetch_data() 에 try/except TimeoutError 추가

[Ralph Iteration 2/5]
QA Verdict: REVISE (0.88)
실패 신호:
  - tests/test_api.py::test_edge_case 엣지 케이스 실패
The boulder never stops. 다음 시도: parse_input() 경계 검사 추가

[Ralph Iteration 3/5]
QA Verdict: PASS (1.0)

Ralph COMPLETE
==============
총 iterations: 3
다음: /cg-evaluation 으로 3-critic 포멀 검증
```

## 원칙 — "The Boulder Never Stops"

- 실패는 종료가 아니라 **다음 시도의 입력** — 단, 같은 시도의 반복은 입력이 아니다 (§정체·진동)
- 수렴 판단은 이중 제약 (기계 게이트 green + 검증자산 불변)
- 루프 안에서 새로운 복잡도 추가 금지 (scope creep 방지)
- max_iterations 는 **사용자가 명시**, 무한 루프 금지
- 좋은 하네스와 나쁜 하네스의 차이 = **이 루프를 얼마나 오래 안 끊기고 돌릴 수 있느냐** — 하드스톱 전에 사다리부터
