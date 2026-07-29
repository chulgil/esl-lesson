---
name: cg-lore-proposal
description: |
  Phase 5 journal 의 "결정:" 블록에서 git trailer 미기록 의사결정을 candidate 로
  제안. 데몬 없음 · auto-적재 금지 · trailer 커밋은 사용자 명시 동작.
  트리거: /lore-propose, "결정 누적", "lore promote", "trailer 후보".
---

# Skill — Lore Proposal (의사결정 trailer 누적)

## 목적

Phase 5 Execution Loop 의 journal 엔트리에서 **"결정:" 블록의 의사결정** 을
git trailer 후보로 누적합니다. 코드는 무엇(what)을, lore 는 왜·무엇을
배제했는가(why / rejected)를 보관합니다.

> Hermes Agent 의 "auto-memory" 메커니즘을 cg-harness 철학에 맞게 경량화한
> 패턴. **사람 게이트 강제** 로 자동 변형을 차단합니다.

## 입력

- `.harness/journal/*.md` — "결정:" 블록 스캔 대상.
- `git log Lore-*` trailer — 이미 기록된 결정 (자동 제외).

## 출력

- `.harness/lore/{slug}.md` — 새 candidate (사용자 검토 + 직접 trailer 커밋 대기).
- `.harness/lore/archive/{slug}.md` — trailer 커밋 완료 후 이동.

## 흐름

```
1. propose       — cg lore propose [--json]
                   → "결정:" 블록 추출 → trailer 미기록 결정만 candidate
   ↓
2. 사람 검토      — .harness/lore/{slug}.md 열어 체크리스트 확인
                   - 단순 작업? vs 재검토 가치 있는 의사결정?
                   - 거절이면 이유 포함?
                   - 코드 상세 제거?
   ↓
3. trailer 커밋   — 사용자가 직접 git commit 메시지에 추가
                   Lore-directive: <결정 한 줄>
                   Lore-rejected: <대안> — 이유
   ↓
4. promote       — cg lore promote {slug}
                   → .harness/lore/archive/{slug}.md 로 이동 (이력 보존)
```

## 사용 시점

| 시점 | 행동 |
|---|---|
| Phase 5 종료 후 | `cg lore propose --json` 으로 후보 확인 |
| 새 의사결정이 journal 에 누적 | propose 재실행 (이전 candidate 는 skipped) |
| 90일 이상 된 directive | `auto lore stale` 또는 수동 재검토 |

## 자동 제외 규칙

`cg lore propose` 는 다음을 candidate 에서 제외:

- `git log` 에 이미 `Lore-directive:`, `Lore-rejected:`, `Lore-constraint:`
  trailer 로 기록된 결정 텍스트 (전체 일치 비교).
- "결정:" 블록 외부의 일반 본문.
- "산출물:", "비고:", "결과:", "## " 헤딩으로 시작하는 다른 섹션.

## 분류 규칙

자동 분류 키워드 (대소문자 무시):

| kind | 트리거 키워드 |
|---|---|
| `rejected` | 거절, 거부, rejected, reject, 버림 |
| `directive` | (그 외 모든 결정) |

`Lore-constraint` 는 자동 감지하지 않습니다 — 사용자가 candidate 검토 시
trailer 형식을 `Lore-constraint:` 로 직접 변경하세요.

## 원칙

- **데몬/스케줄러 사용 금지** — Hermes 와 달리 24/7 자율 실행 안 함.
- **Auto-적재 금지** — `cg` 가 git commit 을 만들지 않음. trailer 는
  사용자가 직접 작성/커밋.
- **로컬 파일만 사용** — 외부 의존성 0.
- **격리는 호출자 책임** — Code Critic 평가가 필요하면 별도 게이트.

## trailer 포맷 (필수 일치)

`~/.../claude-forge/rules/lore-commit.md` 의 3개 공식 키만 사용:

```
Lore-directive: <결정 한 줄>            # 채택된 결정
Lore-constraint: <제약 한 줄>           # 의식적 범위 제한
Lore-rejected: <거절된 대안> — 이유      # 배제된 옵션 (이유 필수)
```

`Lore-why`, `Lore-because`, `Lore-note` 등 임의 키는 금지.

## 출력 포맷 (Researcher 역할, 200단어 이내)

```
**요약**: Phase 5 journal {N}개 스캔, 미기록 결정 {M}개 발견
**작성 candidate**: oauth-pkce (directive), bloc (rejected) (총 2건)
**스킵 (existing trailer)**: riverpod (1건)
**다음 단계**: .harness/lore/{slug}.md 검토 → trailer 커밋 → cg lore promote
```

## 금지

- candidate 의 trailer 를 `cg` 가 자동으로 커밋 → auto-적재 안티패턴.
- 단순 작업/문구 수정 결정을 trailer 로 승격 → trailer 잡음 증가.
- 거절(rejected) 결정에 **이유 없이** trailer 작성 → `lore-commit.md` 위반.
- 같은 결정을 여러 커밋에 반복 trailer 기록 → 최초 커밋에만.

## 관련

- 글로벌 규칙: `~/.../claude-forge/rules/lore-commit.md`
- 비교 대상: Hermes Agent auto-memory (DEFER, CHANGELOG `[Unreleased]` 참조)
- 트리거 위치: `cg-execution-loop` SKILL.md `## 결정 누적 (Lore Proposal)`
- 자매 스킬: `cg-recipe-promotion` (반복 명령 → 스킬 승격)
