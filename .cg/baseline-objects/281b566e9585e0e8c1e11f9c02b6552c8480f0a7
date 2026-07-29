---
name: cg-spec-and-harness
description: Phase 2 — 인터뷰를 공식 스펙으로 변환하고, 이 feature 에 적용될 품질 계약을 확정합니다. `.harness/spec/{YYYY-MM-DD}-{feature}.md` + `harness/current.md` 업데이트.
---

# Phase 2 — Spec & Harness

## 목적

인터뷰에서 얻은 요구사항을 **실행 가능한 스펙** 과 **품질 계약** 으로 굳힙니다. 이후 모든 phase 가 이 스펙을 절대 기준으로 삼습니다.

## 입력

- Phase 1 의 `interview/{YYYY-MM-DD}-{feature}.md`
- Phase 0 의 `harness/current.md`

## 출력

- `.harness/spec/{YYYY-MM-DD}-{feature-slug}.md`
- `.harness/evals/{feature-slug}.toml` — §2 성공 기준 중 기계 검증 가능한 항목의 회귀 eval
- 필요 시 `harness/current.md` 업데이트 (예: 새 테스트 프레임워크 도입)

## 스펙 템플릿

```markdown
# Spec — {feature-slug}

> 날짜: {YYYY-MM-DD} | 상태: draft|locked
> 인터뷰: .harness/interview/{YYYY-MM-DD}-{feature-slug}.md

## 1. 목표 (한 문장)

## 2. 성공 기준 (측정 가능해야 함)
- [ ] ...

## 3. 사용자 시나리오 (Given/When/Then)
### 시나리오 1: 
- Given ...
- When ...
- Then ...

## 4. 스키마 / 인터페이스
### 새 엔티티
```
{타입/스키마 정의}
```

### API 엔드포인트
| Method | Path | Body | Response |
|--------|------|------|----------|

## 5. 비기능 요구사항
- 성능: p95 < ...ms
- 보안: ...
- 관측성: ...

## 6. 아키텍처 결정
- 채택 패턴:
- 거절한 대안 (이유 포함):

## 7. 품질 계약 (이 feature 에 적용)
- 단위 테스트 커버리지: ≥ N%
- E2E 시나리오: ...
- Lint 예외: 없음 | (있다면 사유)

## 8. 위험과 완화
| 위험 | 영향도 | 완화 |
|------|--------|------|

## 9. 범위 외
- ...
```

## 회귀 eval 내리기 (성공 기준 → 기계 검증 자산)

스펙 확정 시 **§2 성공 기준 중 기계 검증 가능한 항목**(이진/숫자로 판정되는 것)을
`.harness/evals/{feature-slug}.toml` 로 내립니다 — `_template.toml` 을 복사해
`[[case]]` = `cmd`/`expect_exit`/`expect_contains` 로 작성. 수용 기준이 문서로
끝나지 않고 `cg diagnose --gate eval` 로 **전체 기능 회귀를 재실행 가능한 자산**이
되며, Phase 6 (cg-evaluation) Stage 1 의 입력이 됩니다.
상세: [.harness/evals/README.md](../../../.harness/evals/README.md).

- 기계 검증 불가능한 기준(예: "직관적인 UX")만 남는다면 §2 를 측정 가능하게 재작성
- eval 케이스는 검증자산 — 이후 phase 에서 FAIL 을 통과시키려 완화·삭제 금지

## 품질 계약 체크

`harness/current.md` 와 스펙이 충돌하지 않는지 확인:
- 새 lib 추가 → current.md 의 "허용 라이브러리" 업데이트
- 새 테스트 프레임 → current.md 의 "테스트" 섹션 갱신

## 완료 조건

1. 모든 성공 기준이 **측정 가능** (이진 또는 숫자)
2. 사용자가 "spec locked" 를 명시적으로 승인
3. `.harness/spec/...` 파일 커밋
