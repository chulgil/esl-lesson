---
name: cg-harness-legacy-scan
description: "하네스(규칙·스킬·전역 컨텍스트·설정)를 읽기 전용으로 감사해 낡은 규칙·중복·과도한 전역 컨텍스트·너무 넓은 Skill·제품 기능 중복을 KEEP/SHRINK/MOVE/SPLIT/CONVERT/DELETE 로 분류. 파일 수정 안 함. 트리거: harness legacy scan, 하네스 다이어트 진단, 레거시 규칙 점검, 하네스 군살."
---

# cg-harness-legacy-scan — 하네스 레거시 읽기 전용 진단

**트리거 키워드**: "harness legacy scan", "하네스 다이어트 진단", "레거시 규칙", "하네스 군살", "규칙 너무 많아"

> 출처: 개발동생 harness-legacy-scan 패턴 흡수 (2026-06-19).
> 짝 스킬: 정리 실행은 [cg-harness-diet]. 이 스킬은 **진단만** 한다.

## 이 스킬이 다른 도구와 다른 점 (중복 회피)

| 도구 | 역할 | 이 스킬과의 차이 |
|------|------|------------------|
| `cg-trace-analyzer` | journal/trace 의 실패 패턴 분석 | 실패가 아니라 **군살**(낡은·중복·과도)을 본다 |
| `cg-recipe-promotion` / `cg-lore-proposal` | 자산을 **늘리는** 방향 | 이 스킬은 **줄이는** 방향 |
| 글로벌 `harness-audit` (있으면) | 죽은 규칙·고아 훅 탐지 | 여기는 6분류 + 전역 컨텍스트 세금 + 제품 중복까지 |

## 절대 규칙 (이 단계)

- 파일을 **수정/삭제하지 않는다**. hooks·MCP·allowed-tools 를 **건드리지 않는다**.
- 결과는 **분석 리포트만**. 실제 정리는 [cg-harness-diet] 가 승인 후 수행.

## 감사 범위

- `CLAUDE.md`, (있으면) `AGENTS.md`, `.cursor/rules/**`
- `.claude/rules/**`, `.claude/skills/**`, `.claude/commands/**`
- `.claude/settings.json` (읽기만 — 권한 변경 금지)
- MCP 설정 / hooks 설정 (읽기만)

## 감사 원칙

- 좋은 하네스는 **반복되는 실제 실수**를 막는다. 과거 습관 보존용으로 존재하면 안 된다.
- 하네스는 더 붙이는 게 아니라 **필요한 순간에만 나타나야** 한다.
- 목표는 규칙 추가가 아니라 **낡은 규칙을 찾아 줄일 후보를 분류**하는 것.
- **안전장치(실수 차단 훅·게이트)는 줄이지 않는다.**

## 7 관점 (서브에이전트 분담 권장 — Agent 도구 병렬)

1. **Inventory** — 하네스 파일·설정 목록화.
2. **Global Context Tax** — CLAUDE.md/AGENTS.md/Cursor Rules 등 매 세션 붙는 지침이 불필요한 컨텍스트 비용을 만드는지.
3. **Skill Quality** — 각 Skill 이 지금도 필요한지, description 이 너무 넓지 않은지, SKILL.md 가 너무 긴지.
4. **Product Overlap** — 이제 Claude Code/Codex/Cursor 기본 기능과 중복되는 규칙.
5. **Safety & Permission** — hooks/allowed-tools/MCP 가 과도한 권한을 주는지 (지적만, 변경 금지).
6. **Refactor Planner** — 각 항목을 KEEP/SHRINK/MOVE/SPLIT/CONVERT/DELETE 로 분류.
7. **Adversarial Reviewer** — 줄이면 오히려 위험해질 항목을 반박 검토.

> 서브에이전트 사용 시 [subagent-output.md] 포맷(200단어·구조화)을 따른다.

## 항목별 보고 형식

```
- 경로:
- 현재 목적:
- 발견한 문제:
- 근거:
- 추천 조치: KEEP / SHRINK / MOVE / SPLIT / CONVERT / DELETE
- 옮긴다면 추천 위치:
- 변경 시 위험도: low / medium / high
- 신뢰도: HIGH / MEDIUM / LOW
- cg-harness-diet 자동 처리 가능: 예 / 아니오
```

## 마지막 필수 섹션

1. 전체 요약
2. 유지해야 할 항목 (KEEP)
3. 줄여야 할 항목 (SHRINK)
4. 전역 지침 → Skill 로 옮길 항목 (MOVE)
5. SKILL.md → reference.md / examples.md 분리 항목 (SPLIT)
6. 삭제 후보 (DELETE — archive 이동 대상)
7. **사람 승인 필요한 위험 변경** (high risk)
8. **cg-harness-diet 로 넘겨도 되는 low-risk 목록**
9. cg-harness-diet 실행용 추천 프롬프트
