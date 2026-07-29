# Recipes — 누적 학습 자산

Phase 5 Execution Loop 의 journal 에서 **3회 이상 반복된 명령 패턴**이
candidate 로 자동 제안되는 디렉토리.

## 구조

```
recipes/
├── README.md         # 이 파일
└── {slug}.md         # 자동 생성된 candidate (status: candidate)
```

## 흐름

```
.harness/journal/{date}.md
        ↓ cg recipe propose  (사용자 명시 호출)
.harness/recipes/{slug}.md   ← 검토 단계
        ↓ cg recipe promote {slug}  (사용자 승인)
.claude/skills/{slug}/SKILL.md   ← 정식 스킬
```

## 원칙

- **데몬 없음** — `cg recipe propose` 를 사용자가 직접 호출했을 때만 동작.
- **Auto-merge 금지** — candidate 는 항상 사람 검토를 거친다.
- **로컬 파일** — 벡터 DB / 외부 의존성 없음.

## 사용 예

```bash
# 임계 3회 (기본) 로 스캔, candidate 작성
cg recipe propose

# 임계 변경 (5회 이상)
cg recipe propose --threshold 5

# JSON 출력 (CI/스크립트용)
cg recipe propose --json

# 검토 후 승격
cg recipe promote run-pytest
```

## 검토 체크리스트

candidate 를 promote 하기 전에:

- [ ] 이 패턴이 **재사용 가치**가 있는가? (1회성 작업이면 삭제)
- [ ] **매개변수화**가 필요한가? (입력 인자가 있다면 SKILL.md 직접 수정)
- [ ] 어느 phase / 어떤 트리거에서 호출할지 명시했는가?
- [ ] 보안/billing 영역 명령이면 ultra 모드 검증을 거쳤는가?

## 관련

- Skill: `.claude/skills/cg-recipe-promotion/SKILL.md`
- Slash: `.claude/commands/recipe-propose.md`
- Trigger: `.claude/skills/cg-execution-loop/SKILL.md` (Phase 5 종료 후 권장)
