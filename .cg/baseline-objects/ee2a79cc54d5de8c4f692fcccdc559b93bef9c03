---
origin_model: claude-fable-5
review_by: 2026-10-26
---

# 2단계 스킬 로딩 (oh-my-agent 패턴)

> 60+ 스킬이 매 세션 로딩되면 초기 컨텍스트를 12만+ 토큰 소비한다.
> 이 규칙으로 불필요한 스킬 본문 로딩을 방지한다.

## 원칙

**Stage 1**: 스킬의 `name`과 `description`(frontmatter)만으로 적합성 판단
**Stage 2**: 실제 호출이 필요할 때만 전체 본문 로딩

## 스킬 호출 판단 규칙

1. 사용자가 명시적으로 슬래시 명령(`/스킬명`)을 호출하면 즉시 로딩
2. 사용자의 요청이 특정 스킬의 description과 정확히 일치하면 로딩
3. **"혹시 관련될 수도 있다"는 이유로 스킬을 미리 로딩하지 않는다**
4. 한 턴에 2개 이상의 스킬을 동시에 로딩하지 않는다

## 스킬 작성 가이드

새 스킬을 만들 때 frontmatter의 `description`을 충분히 구체적으로 작성:

```markdown
# BAD — 모호한 description
---
description: 코드 관련 작업을 도와줍니다
---

# GOOD — 구체적 description (Stage 1에서 판단 가능)
---
description: Git 커밋 메시지 자동 생성 + 푸시 + PR 생성. 검증 완료 후 사용.
---
```

## 트리거 키워드 포함

description에 트리거 키워드를 명시하면 Stage 1 판단이 빨라진다:

```markdown
---
description: |
  빌드/테스트/린트를 한 번에 자동 검증합니다.
  트리거: /handoff-verify, 검증, 빌드 확인, 테스트 통과 확인
---
```
