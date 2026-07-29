# Lore — 의사결정 trailer 후보

Phase 5 journal 의 **"결정:" 블록**에서 git trailer 로 아직 기록되지 않은
의사결정이 candidate 로 자동 제안되는 디렉토리.

## 구조

```
lore/
├── README.md         # 이 파일
├── {slug}.md         # 자동 생성된 candidate (검토 대기)
└── archive/
    └── {slug}.md     # trailer 커밋 완료 후 이동된 파일
```

## 흐름

```
.harness/journal/{date}.md  ("결정:" 블록 포함)
        ↓ cg lore propose     (사용자 명시 호출)
.harness/lore/{slug}.md      ← 검토 + git trailer 작성
        ↓ git commit (Lore-directive: ...)  (사용자 명시 커밋)
        ↓ cg lore promote {slug}            (사용자 명시 승격)
.harness/lore/archive/{slug}.md ← 이력 보존
```

## 원칙

- **데몬 없음** — `cg lore propose` 를 사용자가 직접 호출했을 때만 동작.
- **Auto-적재 금지** — candidate 는 항상 사람 검토를 거친다.
- **trailer 커밋은 사용자 책임** — `cg` 가 git 커밋을 자동 생성하지 않는다.
- **로컬 파일만** — 벡터 DB / 외부 의존성 없음.

## 사용 예

```bash
# journal "결정:" 블록 스캔, 미기록 결정을 candidate 로 작성
cg lore propose

# JSON 출력 (CI/스크립트용)
cg lore propose --json

# 검토 후 git trailer 커밋 (사용자가 직접)
git commit --amend  # 또는 새 커밋
# 메시지에 추가:
#   Lore-directive: OAuth 2.0 PKCE 채택 (RFC 7636)

# trailer 가 커밋되면 archive 로 이동
cg lore promote oauth
```

## 검토 체크리스트

candidate 를 trailer 로 승격하기 전에:

- [ ] 이 결정이 **단순 작업**인가, **재검토 가치 있는 의사결정**인가?
- [ ] 거절(rejected)이라면 **이유**가 결정 텍스트에 포함됐는가?
- [ ] 90일 후 재검토 시 충분한 컨텍스트인가?
- [ ] 코드 상세(파일명/함수명/라인 번호)가 trailer 에 있나? (있으면 제거)

## trailer 포맷

`~/.../claude-forge/rules/lore-commit.md` 와 일치:

```
Lore-directive: <결정 한 줄>
Lore-constraint: <제약 한 줄>
Lore-rejected: <거절된 대안> — 이유
```

## 관련

- Skill: `.claude/skills/cg-lore-proposal/SKILL.md`
- Slash: `.claude/commands/lore-propose.md`
- Trigger: `cg-execution-loop` SKILL.md (Phase 5 결정 발생 시 권장)
- 글로벌 규칙: `~/.../claude-forge/rules/lore-commit.md`
