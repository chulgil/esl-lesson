---
name: cg-orchestrate
description: "멀티에이전트 워커 디스패치 층. Phase 5 / cg-parallel-dispatch 가 교차 벤더 워커(codex/gemini)를 라우팅·승인·호출할 때 사용. backends.json + call_worker.sh + 승인 게이트 + graceful degradation. 트리거: 워커 디스패치, codex 호출, gemini 호출, 멀티에이전트, orchestrate, 백엔드 가용성."
---

# cg-orchestrate — 멀티에이전트 워커 디스패치

**Trigger Keywords**: "워커 디스패치", "codex", "gemini", "멀티에이전트", "orchestrate", "제3자 검토", "대용량 문서 분석"

Phase 5 / `cg-parallel-dispatch` 가 **교차 벤더 워커**(codex/gemini)를 호출할 때 거치는
디스패치 층. native Claude 만으로 충분하면 이 스킬 없이 Task tool 을 쓴다. codex/gemini
같은 외부 백엔드가 필요할 때만 이 층을 경유한다.

## 사용 흐름 (5단계)

### 1. 워커 선택 (routing.md decision tree)

`.harness/orchestration/routing.md` 의 decision tree 로 **누구를** 부를지 정한다:

- 메인 코딩·설계·전략 → `claude-main` (native, 항상 가용)
- claude-main 산출물 비평 → `codex-critic`
- 보조 구현·테스트·이미지 → `codex-main`
- 이미지/대용량 문서/제3자 검토 → `gemini`

그다음 토폴로지(Pipeline / Fan-out·in / Expert Pool / Producer-Reviewer)로 **어떻게 엮을지** 정한다.

### 2. 가용성 + graceful-degrade 계획 확인

```bash
cg orchestrate doctor          # 백엔드 가용성 + 워커별 폴백/강등 계획
cg orchestrate doctor --json   # 스크립트용
```

- `gemini` 가 `NO`(agy 없음)면 → API 폴백 → 그래도 없으면 `claude-main` 강등.
- `codex_mcp` 는 `UNKNOWN`(정적 감지 불가) → **선제 강등하지 않고** 시도, 실패 시 CLI 폴백 → native.
- `requires_runtime_check=YES` 인 워커는 호출 실패를 폴백 체인이 흡수한다.

### 3. 승인 게이트 (approval-policy.md)

모든 워커 호출은 **작업별 명시적 승인** 필요(claude-main 포함). 사용자에게
**어떤 워커를 / 무슨 목적으로 / 예상 호출 횟수**를 제시하고 승인을 받은 뒤
`[APPROVAL]` 로그를 남긴다. 외부 repo 쓰기는 4조건(approval-policy.md) 충족 필수.

오케스트레이터의 **내부 추론**은 워커 호출이 아니므로 승인 불필요.

### 4. 호출

- **native (claude-main)**: Claude Code Task tool 로 직접 호출.
  `subagent_type: claude-main`, prompt = brief 내용, `model: opus` 는 agent 정의에서 자동.
  결과 텍스트를 받아 `result.md` 에 저장 (워커는 직접 파일 쓰기 X).
- **cli/api (gemini·codex 폴백)**: 디스패처 경유.

  ```bash
  bash .harness/orchestration/adapters/call_worker.sh <role> <brief-file>
  # 반환 = JSON envelope (status / exit_code / stdout / stderr_sanitized / fallback_used)
  ```

  brief 는 `.harness/orchestration/templates/worker-brief.md` 양식. **Worker 행동 규약**
  고정 블록을 삭제하지 말 것(INV12).

### 5. 결과 보존 + 검증

- 각 워커 원문을 `result.md` 에 그대로 보존 (file-as-memory, telephone game 방지).
- 병렬 결과 충돌 시 삭제 금지 → 양쪽 출처 병기 + `[DECISION]` 로그 (Fan-in 규칙).
- 자산을 편집했으면 `cg orchestrate validate --strict` 로 일관성 점검 후 커밋.

## 자산 위치

| 자산 | 경로 |
|------|------|
| 백엔드 레지스트리 정본 | `.cg/backends.json` |
| 디스패처 | `.harness/orchestration/adapters/call_worker.sh` |
| 라우팅 규칙 | `.harness/orchestration/routing.md` |
| 승인 정책 | `.harness/orchestration/approval-policy.md` |
| 운영 규칙 | `.harness/orchestration/orchestrator-rules.md` |
| 불변식 정본 | `.harness/orchestration/system-invariants.md` |
| brief/result 템플릿 | `.harness/orchestration/templates/` |
| 워커 정의 | `.claude/agents/claude-main.md` |

## 금지

- 같은 입력에 같은 종류 워커 동시 호출 (예: claude-main 2개).
- Supervisor·Hierarchical Delegation 토폴로지 (단일 orchestrator 와 충돌 → 배제).
- worktree/백그라운드 세션에서 오케스트레이터 실행 (INV8 — 인터랙티브 전용).
- 승인 없이 워커 호출 / 4조건 없이 외부 repo 쓰기.
- 폐기 브리지(`mcp__gemini__*`·`mcp__gemini-pro__*`) 호출 — gemini 는 `agy` CLI 정본.
