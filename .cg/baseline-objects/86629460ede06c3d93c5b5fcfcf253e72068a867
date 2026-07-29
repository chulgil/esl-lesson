---
name: verification-engine
description: 통합 검증 엔진 - 서브에이전트 기반 fresh-context 검증 루프 (v6)
version: 2.0.0
---

## 검증 원칙

### The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

검증 커맨드를 이번 메시지에서 실행하지 않았다면, 통과했다고 주장할 수 없다.

### The Gate Function

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying
```

> Common Failures 표(Tests/Build/Bug/Agent 별 충분/불충분 증거)는 [reference.md](reference.md) 참조.

---

## Overview

통합 검증 엔진 스킬은 `/handoff-verify` 커맨드의 핵심 동작을 정의한다.
v5의 `/verify` 단독 커맨드에서 v6의 `/handoff-verify` 통합 커맨드로 진화하였다.

핵심 변경: **Task 도구로 verify-agent 서브에이전트를 생성하여 fresh context에서 검증.**
`/clear` 없이도 편향 없는 검증이 가능하다.

---

## Trigger Conditions (요약)

- **직접 호출**: `/handoff-verify` (기본 루프, 최대 5회). 플래그로 동작 변경 —
  `--once`(단발), `--loop N`(N회), `--security`, `--coverage`, `--extract`, `--skip-handoff`.
- **자동 호출**: `/commit-push-pr` 실행 전 (`--once` 사전 검증), `/orchestrate` 검증 단계 (루프 모드 · multiagent 구성 설치 시).

> 전체 트리거 표는 [reference.md](reference.md) 참조.

---

## Architecture (요약)

```
/handoff-verify (부모 컨텍스트)
   ├── [1] handoff.md 자동 생성 (git diff 분석, 변경 의도 문서화)
   ├── [2] verify-agent 서브에이전트 (Task 도구, fresh context — /clear 대체)
   │        → handoff.md 읽기 → 검증 파이프라인 → 실패 시 자동 수정·재시도 → 결과 반환
   └── [3] 결과 수신: PASS → handoff.md 정리·다음 단계 / FAIL → 에러 보고·권장 조치
```

핵심: 부모 컨텍스트를 보존한 채 서브에이전트가 fresh context에서 검증 (v5의 /clear 손실 제거).

> v5 대비 상세 비교 다이어그램은 [reference.md](reference.md) 참조.

---

## Verification Pipeline (요약)

verify-agent 내부 7단계:

1. **환경 파악** — handoff.md, git status/diff, 프로젝트·패키지 매니저 감지
2. **빌드 검증** — 실패 시 Fixable 자동 수정
3. **타입 검사** — 실패 시 Fixable 자동 수정
4. **린트 검사** — 실패 시 Fixable 자동 수정
5. **테스트 실행** — 실패 시 에러 분석 + 수정 시도
6. **코드 리뷰** — effort에 따라 (low 건너뜀 ~ max 전체 영향)
7. **보안 검토** — `--security` 또는 effort:max 시 security-reviewer 연동

**루프**: 실패 시 Fixable 자동 수정 후 재실행. 5회 실패 시 `/learn --from-error` 제안 + 최종 에러 리포트 반환.

> 단계별 명령 예시·루프 다이어그램은 [reference.md](reference.md) 참조.

---

## 자동 수정 (Fixable) 요약

서브에이전트가 사용자 승인 없이 즉시 고치는 오류 **9가지**: missing/unused import,
auto-fixable lint, type mismatch, missing return type, formatting, missing dependency,
enum/const mismatch, test snapshot(승인 필요).

**수정 불가** (사용자 판단): 로직 오류, 아키텍처 변경 타입 오류, 테스트 로직 자체 오류, 보안 취약점.

> Fixable 9목록 표(감지 패턴·수정 방법), Effort별 동작 차이 표,
> Coverage(`--coverage`)·Extract(`--extract`) 모드 출력 예시,
> Integration Points(커맨드/에이전트/security-pipeline/learn/commit-push-pr 연동)는
> 모두 [reference.md](reference.md) 참조.
