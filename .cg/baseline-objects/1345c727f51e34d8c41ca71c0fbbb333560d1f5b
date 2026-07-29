---
name: harness-absorb
description: 누적된 하네스 신호를 분류해 rules·hooks·skills·memory·CLAUDE.md 중 어디에 반영할지 제안 테이블을 생성한다. `--apply` 없이는 쓰기 없음.
---

# /harness-absorb — 하네스 신호 흡수

자가 개선 하네스의 **APPLY 레이어**. `harness-improve` 스킬의 판정을 받아 사용자에게 제안 테이블을 보여주고, 승인된 항목만 실제 파일로 반영한다.

**기본 동작: 드라이런**. `--apply` 인자가 없으면 쓰기는 절대 하지 않는다.

---

## 인자

| 인자 | 기본값 | 설명 |
|------|--------|------|
| `[source]` (positional) | `recent` | 입력 소스 선택. `recent` / `autopus-patterns` / 파일 경로 |
| `--since` | `7d` | 신호 기간. `7d`, `30d`, `YYYY-MM-DD` |
| `--apply` | false | 실제 파일 반영 (승인 1회 후 일괄 수정) |
| `--scope` | `both` | `global` / `project` / `both` |
| `--min-confidence` | `MEDIUM` | `HIGH` / `MEDIUM` / `LOW` |

### 소스 옵션

- `recent` — 최근 `--since` 기간의 글로벌+프로젝트 신호 (기본)
- `autopus-patterns` — `~/qjc-office/` 내 autopus 7개 패턴을 입력으로 사용
- 파일 경로 — 임의의 JSONL 파일을 입력으로 지정

---

## 실행 절차

### 1. 입력 수집

```bash
# recent 소스
SINCE_TS=$(date -v-7d +%s)  # macOS; Linux는 date -d
GLOBAL="${HOME}/.claude/homunculus/observations.jsonl"
PROJECT="${CLAUDE_PROJECT_DIR}/.claude/harness-signals/*.jsonl"
# 두 소스를 합쳐 timestamp >= SINCE_TS 만 필터
```

처리 이력 제외: `~/.claude/homunculus/processed/` 의 `session+timestamp` 조합 제거.

### 2. harness-improve 스킬 호출

Skill 툴로 `harness-improve` 스킬을 불러와 CLASSIFY 알고리즘을 적용.
스킬의 **단계 1~5**를 그대로 실행하여 제안 목록 생성.

### 3. 제안 테이블 출력

```
## Harness Absorb — 제안 (N건) [DRY-RUN]
(모든 건은 승인 후에만 반영됩니다. --apply 추가 시 쓰기)

| # | 신호 요약 | 신뢰도 | 반복 | 스코프 | 대상 | 액션 |
|---|-----------|--------|------|--------|------|------|
| 1 | ... | HIGH | 5회 | 글로벌 | ~/.claude/rules/git-workflow-v2.md | 갱신 |

## Diff 미리보기
### [1] ~/.claude/rules/git-workflow-v2.md
```diff
+ 커밋 메시지 prefix 뒤 본문은 반드시 한글로 작성.
```

## 다음 단계
- 모두 승인: `/harness-absorb --apply`
- 일부만: `/harness-absorb --apply --only 1,3`
- 거절: 이 대화에서 "거절" 이라고 응답하면 제안 폐기
```

### 4. 적용 단계 (--apply 시)

1. 사용자에게 최종 확인: "위 N건을 모두 반영합니까? (yes/no/only N,M)"
2. `yes` → 순차 반영
3. 각 파일 반영 시:
   - 기존 파일 존재: `Edit` 으로 섹션 삽입/갱신
   - 신규 파일: `Write` 로 생성 (frontmatter 포함)
   - `CLAUDE.md` 수정: 관련 섹션 찾아 append
4. 반영 완료 후 `harness-signals/processed/YYYY-MM/`에 처리 이력 JSONL 추가
5. 각 파일별 변경 라인 수 요약 출력

### 5. 충돌 처리

- 같은 topic 규칙이 상충하는 경우: 적용 중단, 사용자에게 선택 요청
- 사용자가 "기존 유지" → 신호를 `processed/rejected.jsonl` 로 이동
- 사용자가 "신규 적용" → 기존 규칙을 `archive/YYYY-MM-DD/` 로 이동 후 갱신

---

## autopus-patterns 소스 특별 처리

`/harness-absorb autopus-patterns` 호출 시:

1. `~/qjc-office/` 하위에서 autopus 스펙 문서 경로 확인
2. 7개 패턴을 분석:
   - @AX Annotation → `~/.claude/rules/ax-annotation.md`
   - Lore Commit → `~/.claude/rules/lore-commit.md`
   - Hash-Anchored Edit → `~/.claude/rules/hash-anchored-edit.md`
   - Entropy Scan → `~/.claude/skills/entropy-scan/SKILL.md`
   - Adaptive Quality → `~/.claude/rules/adaptive-quality.md`
   - Frontend Verify → `~/.claude/skills/ux-consistency-check/` 확장
   - Git Worktrees → `~/.claude/rules/git-worktrees.md`
3. 각 제안을 일반 신호와 동일한 테이블 포맷으로 출력
4. 사용자 선별 승인

---

## 출력 예시 (드라이런)

```
## Harness Absorb — 제안 (3건) [DRY-RUN, 기간: 최근 7일]

| # | 신호 요약 | 신뢰도 | 반복 | 스코프 | 대상 | 액션 |
|---|-----------|--------|------|--------|------|------|
| 1 | 커밋 메시지는 한글 | HIGH | 12회 | 글로벌 | ~/.claude/rules/git-workflow-v2.md | 이미 있음, 변경 없음 |
| 2 | §7 Notebook 작업 시 §7.17/§7.27/§7.50 순서 준수 | HIGH | 8회 | 프로젝트 | $PROJECT/.claude/rules/notebook-score.md | 신규 |
| 3 | "자동 쓰기 금지" 재확인 | MEDIUM | 3회 | 글로벌 | ~/.claude/rules/interaction.md | 갱신 (첫 섹션) |

## Diff 미리보기
### [2] $PROJECT/.claude/rules/notebook-score.md (신규)
...
### [3] ~/.claude/rules/interaction.md (갱신)
...

## 다음 단계
- 전체 반영: /harness-absorb --apply
- 2번만: /harness-absorb --apply --only 2
- 거절: 이 대화에서 "거절"
```

---

## 운영 원칙

1. **자동 쓰기 금지**. `--apply` + 명시적 승인 없이는 절대 쓰지 않는다.
2. **보수적 선별**. HIGH 신호여도 중복/상충이면 승격 보류.
3. **처리 이력 보존**. 한 번 반영하거나 거절한 신호는 재제안하지 않는다.
4. **롤백 가능**. 모든 파일 수정 전 `git diff` 가능한 상태 (unstaged) 유지.
5. **한 번에 하나의 스코프**. `global` 과 `project` 는 분리 커밋 권장.

---

## 성공 기준

- 드라이런이 제안 테이블을 오류 없이 출력
- `--apply` 실행 후 승인된 항목만 반영, 거절 항목은 `rejected.jsonl` 로 이동
- `processed/` 이력이 다음 호출에서 중복 제안을 억제

---

## 주의

- 자동 승인 모드(`--yes`) 는 의도적으로 만들지 않는다. 사용자 1회 승인이 최소 요구.
- `~/.claude/homunculus/` 시스템과 공존: 이 커맨드는 observations.jsonl을 읽기만 하고, instincts/evolved 로직은 건드리지 않는다.
