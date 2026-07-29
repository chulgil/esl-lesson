# Worker Routing Rules — 워커 선택 + 토폴로지

> "누구를(decision tree)" 고른 뒤 "어떻게 엮을지(토폴로지)" 고른다.
> 백엔드 정본은 `.cg/backends.json`, 호출은 `adapters/call_worker.sh` 또는 native Task.

## Decision Tree

```
작업 성격 파악
│
├── 메인 코딩 / 디버깅 / 기획 · 설계 · 요구사항 · 전략 · 문서화?
│   └── claude-main
│
├── claude-main 산출물 리뷰 / 비판적 검증?
│   └── codex-critic   (Codex 의 주된 역할)
│
├── 보조 구현 / 코드 분석 / 테스트 / 이미지 생성?
│   └── codex-main
│
├── 이미지 · 스크린샷 분석 / 50페이지+ 문서 / 제3자 시각의 검토?
│   └── gemini
│
└── 판단 어려움?
    └── claude-main 으로 시작 후 필요 시 추가
```

## 복합 작업 우선순위

한 작업이 여러 분기에 해당할 때:

1. **선행 의존성 우선**: codex-critic 은 리뷰 대상(보통 claude-main 결과)이 먼저 있어야 함
2. **Orchestrator 내부 추론 우선**: 워커 호출 전에 오케스트레이터 자체 추론으로 풀리는지 먼저 판단
3. **검증은 한 번만**: codex-critic 은 작업당 1회 원칙. 재호출은 검증 실패 시만
4. **gemini 는 명시적 트리거 시만**: 멀티모달·"제3자 시각" 명시 없으면 호출 금지

## 토폴로지 패턴 (워커를 어떻게 엮을까)

**단일 orchestrator 구조에 맞는 4패턴만** 쓴다.

| 패턴 | 언제 | 이 시스템에서 |
|------|------|-------------|
| Pipeline (순차) | 앞 결과가 뒤 입력 | 기본. claude-main → codex-critic → claude-main(반영) |
| Fan-out/Fan-in (병렬→통합) | 독립 산출물 여럿을 하나로 통합 | claude-main(코드) ∥ gemini(이미지). 통합은 아래 Fan-in 규칙 |
| Expert Pool (전문가 선택) | 작업 성격에 맞는 워커만 | 새 실행 패턴이 아니라 **워커 선택 정책** — 위 decision tree + 최소 set |
| Producer-Reviewer (생성+게이트) | 산출물 품질 검증 필요 | claude-main(생성) → codex-critic(adversarial 게이트) |

**금지**: 같은 입력에 같은 종류 워커 동시 호출 (예: claude-main 2개).

**배제**: Supervisor(별도 long-lived 조정자 워커·런타임 동적 분배 계층)·Hierarchical
Delegation(워커가 워커를 부르는 재귀 위임)은 단일 orchestrator·워커 간 무통신·
file-as-memory 와 충돌 → 미사용.

### Fan-in 규칙 (병렬 결과 통합)

병렬 워커 결과를 오케스트레이터가 하나로 합칠 때:

1. 각 워커 원문을 `result.md` 에 그대로 보존 (요약본만 남기지 말 것 — telephone game 방지)
2. 결과가 충돌하면 삭제 금지 → 양쪽 출처 병기, 권위 우선순위/사실검증으로 해소,
   `[DECISION]` 로그에 근거 기록
3. 통합 결론 한 줄을 컨텍스트에 기록

## Worker 역할 요약

- **claude-main** (native Task, `model: opus`): 메인 코딩·디버깅·설계·전략. 직접 파일 쓰기 X,
  반환 텍스트를 오케스트레이터가 `result.md` 에 저장.
- **codex-main** (mcp→cli 폴백): 보조 구현·코드 분석·테스트·이미지 생성.
- **codex-critic** (mcp, read-only): claude-main 산출물 adversarial 리뷰. **Codex 의 주된 역할.**
- **gemini** (agy cli→api 폴백, `gemini-3.1-pro-high`): 이미지/스크린샷 분석·대용량 문서·제3자 검토.

## write_scope 값 (정본 — 모든 brief·승인이 이 집합을 따른다)

`none`(쓰기 금지) / `tasks-only`(작업 폴더 내부만) / 패턴(외부 repo 해당 경로 — 4조건 승인 필요).

## 모델 정책

- **claude-main**: 별칭 `opus` (버전 핀 안 함 — 환경 최신 Opus 로 해석).
- **codex-main / codex-critic**: 사용자 `~/.codex/config.toml` 기본값.
- **gemini**: 백엔드 = `agy` CLI(`.cg/backends.json` 정본), 기본 `gemini-3.1-pro-high`,
  폴백 `api`. agy 모델은 전역 단위라 per-call 핀 불가 → gemini 전용 전역을 pro-high 로.

### 난이도별 모델 티어 (native 서브에이전트 디스패치)

claude-main 워커는 `opus` 고정이지만, native Task 로 보조 서브에이전트를 띄울 때는
**작업 난이도에 모델 티어를 맞춘다** — 모두 Opus 로 띄우지 않는다:

| 작업 성격 | 모델 티어 |
|-----------|-----------|
| 코드베이스 탐색·검색, 기계적 변환, 단순 추출 | Haiku |
| 일반 구현·수정 (탐색 + 편집) | Sonnet |
| 계획 수립·어려운 검증·adversarial 비평 | Opus |

> 컨텍스트 격리된 서브에이전트는 작은 작업을 다루므로 작은 모델로 충분하다. 난이도↔티어를
> 맞추면 토큰·시간을 아끼면서 품질을 유지한다. Claude Code 내장 Explore(Haiku)·Plan(상속)·
> General(Sonnet) 이 이미 이 원리를 따른다. (출처: Claude Code 멀티에이전트 — 모델 인텔리전스 라우팅)

## 최소 Worker Set

| 작업 유형 | 권장 최소 set |
|----------|------------|
| 문서/기획만 | claude-main |
| 코드 구현 | claude-main |
| 구현 + 비평 | claude-main → codex-critic → claude-main(반영) |
| 보조 구현 / 이미지 | codex-main |
| 대용량 문서 처리 | gemini |

모든 워커를 기본 호출하지 말 것. 필요한 워커만.
