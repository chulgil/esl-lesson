# Orchestration — 멀티에이전트 워커 디스패치

Phase 5 / `cg-parallel-dispatch` 가 호출하는 **워커 디스패치 층**. 교차 벤더
워커(codex/gemini) 라우팅 + 승인 게이트 + graceful degradation 을 제공한다.
없는 백엔드는 자동으로 native Claude(Task)로 폴백한다.

## 구조

```
orchestration/
├── README.md             # 이 파일
├── orchestrator-rules.md # 운영 규칙 (INV8 인터랙티브 전용·재진입 프로토콜·운영 원칙)
├── routing.md            # decision tree + 4토폴로지 + Fan-in 규칙
├── approval-policy.md    # 워커 호출 승인 게이트 (외부 쓰기 4조건)
├── system-invariants.md  # cg orchestrate validate 가 참조하는 불변식 정본
├── adapters/
│   └── call_worker.sh    # backends.json 디스패처 (cli/api + 폴백 + timeout + redact)
└── templates/
    ├── worker-brief.md   # 워커 brief (Worker 행동 규약 고정 블록 포함)
    └── worker-result.md  # 워커 result 템플릿
```

백엔드 레지스트리 정본은 `.cg/backends.json` (이 디렉토리 밖).

## 흐름

```
오케스트레이터(인터랙티브 Claude 세션)
        ↓ routing.md decision tree 로 워커 선택
        ↓ approval-policy.md 승인 게이트
        ↓ cg orchestrate doctor   (가용성·graceful-degrade 계획 확인)
native(claude-main) → Task tool 직접 호출
cli/api(gemini·codex 폴백) → adapters/call_worker.sh <role> <brief>
        ↓ 결과를 result.md 에 보존 (file-as-memory)
        ↓ cg orchestrate validate (자산 일관성 점검)
```

## CLI

```bash
cg orchestrate doctor             # 백엔드 가용성 + 워커별 graceful-degrade 계획
cg orchestrate doctor --json      # CI/스크립트용
cg orchestrate validate           # 자산 내부 일관성 점검 (INV1·3·9·11·12)
cg orchestrate validate --strict  # 위반 시 종료코드 3
```

## 원칙

- **graceful degradation**: 선호 백엔드 없으면 폴백 → 최종 native Claude 강등 (무음 실패 없음).
- **codex MCP 는 UNKNOWN**: 정적 감지 불가 → 선제 강등 X, 시도 후 실패 시 폴백.
- **인터랙티브 전용**: worktree/백그라운드 세션 금지 (orchestrator-rules.md §1).
- **승인 게이트**: 모든 워커 호출은 작업별 명시적 승인 (claude-main 포함).
- **file-as-memory**: 워커 결과는 평문 `result.md` 로 보존, 다른 워커가 읽음.

## 관련

- Skill: `.claude/skills/cg-orchestrate/SKILL.md`
- Agent: `.claude/agents/claude-main.md`
- 백엔드 정본: `.cg/backends.json`
