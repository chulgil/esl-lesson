---
origin_model: claude-fable-5
review_by: 2026-10-26
---

# Adaptive Quality — 작업 난이도 기반 품질 모드

> autopus `auto effort` / `--quality` 패턴 흡수 (2026-04-23).
> 목적: 모든 작업에 동일한 검증 강도를 적용하면 낭비(docs)와 부족(migration) 이 공존한다. 우선순위·변경 범위·리스크로 **검증 강도**를 조절한다.
> 보완: [rubric-evaluation.md](./rubric-evaluation.md) 의 7.5 합격 기준은 유지. 이 규칙은 "얼마나 깊이 검사할지"를 결정.

## 3단 모드

| 모드 | 사용 기준 | 검증 | 비용 |
|---|---|---|---|
| **ultra** | P0 / security / data migration / 배포 전 | 다중 모델 리뷰, TDD, handoff-verify 5회 루프, /code-review + /security-review | 높음 |
| **balanced** (기본) | feature / refactor / bugfix | 단일 모델, TDD, handoff-verify 1회, /code-review | 중간 |
| **fast** | docs / chore / 오탈자 | 문법/링크만, 전체 테스트 스킵 가능 | 낮음 |

## 감지 규칙

자동 판정 우선순위 (첫 일치 규칙이 모드 결정):

1. 커밋이 다음 라벨/경로를 건드림 → **ultra**
   - `security`, `migration`, `auth`, `billing`, `payment`
   - 프로덕션 배포 스크립트 (`deploy`, `docker-compose.prod`, `release.yaml`)
   - 시크릿 관리 파일 (`.env.*`, `secrets.yaml`)
2. 테스트 파일 없이 비즈니스 로직 파일만 변경 → **ultra** (테스트 누락 의심)
3. 변경 라인 500+ OR 파일 10+ → **ultra**
4. 문서·주석 전용 (`*.md`, `*.txt`, 주석 라인만) → **fast**
5. package-lock/pubspec.lock/Cargo.lock 만 변경 → **fast**
6. 그 외 → **balanced**

## autopus 사용 시

```bash
auto effort detect              # 현재 변경에 대한 추천 effort
auto <cmd> --quality ultra      # ultra 모드 강제
auto <cmd> --quality balanced   # balanced 모드 강제
```

## autopus 미사용 환경 (수동 적용)

변경 내용을 훑은 뒤, 위 감지 규칙 중 어느 것에 해당하는지 먼저 판단하고 시작한다:

```
이번 변경: features/auth/ 3개 파일, 테스트 없음, 로직 변경 120줄
→ 감지 규칙 2번 (테스트 누락 의심) → ultra 모드
→ /tdd 먼저, /code-review + /security-review 2회, handoff-verify 5회 루프
```

## 충돌 처리

- 사용자가 "빠르게 갑시다" 라고 명시적 지시 → 감지 규칙 1번(security/migration) 외에는 **balanced 로 하향 허용**
- 사용자가 "꼼꼼히" → 한 단계 상향 (balanced → ultra, fast → balanced)
- security/migration 에 한해 사용자 하향 지시 거부. 이유: 복구 불가능한 리스크.

## 금지

- 모든 작업에 ultra 고정 (낭비) 또는 모든 작업에 fast 고정 (위험) — 둘 다 안티패턴.
- 모드 결정을 커밋 후에 사후 적용 → 검증 강도는 **작업 시작 시점**에 확정.

## 상위 규칙과의 관계

- [rubric-evaluation.md](./rubric-evaluation.md): 합격선 7.5 유지.
- [verification.md](./verification.md): ultra 에서는 Red-Green 사이클 필수, balanced 는 Green 1회 허용.
- [golden-principles.md §10 Evidence-Based Completion](./golden-principles.md): 모드 무관 적용.

결정 로그(Lore) 와 조합: 모드를 ultra 로 강제한 경우 그 이유를 `Lore-directive:` 로 남긴다.
