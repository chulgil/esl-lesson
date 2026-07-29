---
name: cg-knot-query
description: |
  Knot 지식 그물 — 그물을 질의·합성하여 답하고, 보존 가치가 있으면 note 페이지로
  저장한다. 근거 없으면 지어내지 않는다. 트리거: knot query, 그물 질문,
  "그물에서 찾아줘", 지식 합성.
---

# Skill — Knot Query (그물 질의·합성)

## 목적

vault 의 평문 그물을 질의하여 `[[링크]]` 인용과 함께 답을 합성한다. 답이 재사용
가치가 있으면 `note` 페이지로 보존한다. 벤더 중립 — 어떤 에이전트든 같은 그물을 읽는다.

## 0. schema 먼저 정독 (필수)

vault 루트 `schema.md` 를 **먼저 정독**한다. note 타입·frontmatter·링크 규칙은
schema 가 정본이다.

## 흐름

```
1. 질문 수령 — 호출 인자 또는 지시문
   ↓
2. 탐색      — index.md 에서 관련 페이지 찾기(필요 시 grep 보조) → 해당 페이지 정독
   ↓
3. 합성      — [[링크]] 인용을 달아 답 작성.
              vault 에 근거 없으면 "없다" 고 답한다 — 지어내지 말 것.
   ↓
4. (선택) 저장 — 재사용 가치가 있으면 note 페이지로 보존
```

## note 저장 시 git 규약 (필수)

note 를 저장하면 vault 가 변경되므로 git 규약을 적용한다:

- **시작 가드**: 저장하기로 결정하면 먼저 `git status --porcelain` 확인 —
  비어 있지 않으면 다른 실행 진행 중일 수 있으므로 **중단·보고**.
- `wiki/` 에 `note` 페이지 작성 — `sources:` 에 합성에 쓴 근거의 원 출처
  (raw/ 경로 또는 URL) 를 적는다.
- `index.md` 의 `## note` 섹션에 한 줄, `log.md` 에 `## [YYYY-MM-DD] query — <제목>` append.
- `cg knot lint` 로 ERROR 0 확인 후 `git add -A && git commit -m "query: <제목>"`.
  트레일러에 실제 모델명(`Co-Authored-By: <모델명>`). **push 금지**.

저장하지 않는 **읽기 전용 답변** 이면 커밋 없이 끝낸다(vault 변경 없음).

## 주의

- 날짜는 `date '+%Y-%m-%d'` 로 확인 — 암산 금지.
- 새 note 가 다른 페이지에서 링크되지 않으면 고아 WARN 이 뜨므로, 관련 페이지의
  본문/`## 관련` 절에서 새 note 로의 링크를 한 줄 추가한다.
