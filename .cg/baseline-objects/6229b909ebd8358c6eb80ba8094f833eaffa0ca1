---
origin_model: claude-fable-5
review_by: 2026-10-26
---

# Skill Authoring — 스킬을 TDD 로 쓴다

> 출처: superpowers `writing-skills` (MIT) 패턴 흡수.
> cg-harness 의 제품이 곧 스킬이다 (scaffold · recipe-promotion). 스킬 품질이 모든
> 하위 작업 품질을 결정하므로, 스킬도 코드처럼 검증하며 쓴다.

## 1. description = WHEN, not WHAT

frontmatter `description` 은 **언제 이 스킬을 쓰는가(트리거 조건)** 를 적는다.
무엇을 하는지(절차 요약)를 적으면 에이전트가 description 만 읽고 본문을 안 펼친 채
대충 실행한다 — 2단계 스킬 로딩이 무너진다.

```
# BAD (WHAT — 본문을 안 열게 됨)
description: 테스트를 만들고 구현하고 리팩토링한다.

# GOOD (WHEN — 트리거 조건)
description: 새 기능/버그픽스 구현 직전 사용. 트리거: TDD, 테스트 먼저, red-green.
```

## 2. 금지문은 출력형 실패에 역효과 — 긍정 레시피로

"~하지 마" 같은 금지문은 막연한 폭주(Goal Fixation)조차 잘 막지 못하고, **출력의 형태를
망치는 실패**(장황·빠뜨림·잘못된 구조)는 더더욱 못 막는다. 출력 형태를 잡으려면 **무엇을
만들지 슬롯으로 명시**한다(긍정 레시피).

```
# 약함: "장황하게 쓰지 마"
# 강함: "출력은 정확히 이 4슬롯: 요약 / 변경파일 / 테스트 / 판정"
```

> goal-fixation-guard.md 와 한 쌍: 거기선 "산출물을 명시해 폭주를 끊고", 여기선
> "출력 슬롯을 명시해 형태를 잡는다".

## 3. 무가이드 대조군 압박 테스트 (스킬의 RED→GREEN)

새 스킬(또는 승격된 recipe)을 배포 전에 검증한다:

1. **RED**: 스킬 없이(또는 description 만으로) 대표 시나리오를 시켜본다 → 실패/약점 관찰.
2. **GREEN**: 스킬 본문을 적용해 같은 시나리오 → 그 약점이 사라지는지 확인.
3. 사라지지 않으면 스킬이 실제 행동을 바꾸지 못한 것 — 문구를 고친다(슬롯/예시 추가).

스킬이 "있으나 마나" 면 토큰만 쓴다. 행동 변화를 **관찰**해야 GREEN.

## 4. 작게 유지

- 한 스킬 = 한 책임. 본문이 길면 `reference.md` 로 분리(2단계 로딩).
- 예시 1~2개 > 규칙 10개. 에이전트는 예시를 모방한다.

## 적용 시점

| 시점 | 행동 |
|------|------|
| 새 스킬 작성 | 1·2·4 적용 후 3(압박테스트) |
| `cg recipe promote` 후 SKILL.md 편집 | 1(description) 필수, 2·4 점검 |
| `/code-review` 가 스킬 파일 포함 | 이 룰 기준 검토 |

## 관련

- [skill-loading.md](skill-loading.md): 2단계 로딩 — description 이 Stage 1 판단 근거.
- [goal-fixation-guard.md](goal-fixation-guard.md): 금지문 한계 (산출물 명시).
- cg-recipe-promotion: 승격 스킬은 이 룰을 따른다.
