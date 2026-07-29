---
name: cg-knot-lint
description: |
  Knot 지식 그물 — 기계 lint(cg knot lint)로 형식을 점검하고, AI 의미 진찰로
  모순·노후·중복·데이터 갭을 찾는다. 트리거: knot lint, 그물 건강검진,
  지식 정합성 검사.
---

# Skill — Knot Lint (그물 건강검진)

## 목적

두 층으로 그물을 점검한다: (1) `cg knot lint` 기계 검사(형식·링크·정합), (2) AI
의미 진찰(모순·노후·중복). 기계는 결정적·저비용, 의미는 사람 판단이 필요한 부분만.

## 0. schema 먼저 정독 (필수)

vault 루트 `schema.md` 를 **먼저 정독**한다.

## git 규약 (필수)

끝에 자동수정 결과를 커밋하므로 시작은 깨끗해야 한다:

- **시작 가드**: `git status --porcelain` 비어 있지 않으면 **중단·보고**.
- **마무리**: `cg knot lint` 재실행으로 ERROR 0 확인 후
  `git add -A && git commit -m "lint: <요약>"`. 모델명 트레일러. **push 금지**.
- 수정한 것이 없으면 커밋하지 않는다.

## 흐름

```
1. 가드      — git status --porcelain 비어있지 않으면 중단·보고
   ↓
2. 기계 lint — cg knot lint (또는 --vault <vault>)
              ERROR 는 직접 정정 — 깨진 링크·index 정합·frontmatter 보정은 기계 작업
   ↓
3. 의미 진찰 — wiki/ 전체를 훑으며:
              - 페이지 간 모순되는 주장
              - 낡았을 주장 (lint 의 stale 후보 INFO 참고)
              - 같은 주제인데 링크 없는 누락 상호참조
              - 합쳐야 할 중복 페이지
              - 있어야 할 페이지·절이 없는 데이터 갭
   ↓
4. 수정·기록 — 자명한 것은 직접 수정(updated 갱신!), 판단 필요한 것은 목록화
              log.md 에 ## [YYYY-MM-DD] lint — <요약> append
              (수정 목록 + "사람 검토 필요" 목록)
   ↓
5. 재검증·커밋 — cg knot lint 재실행 ERROR 0 확인 → git commit
```

## 기계 lint 가 점검하는 것

`cg knot lint` 는 vault 루트 `.knot.toml` 의 `[lint]` 프로파일을 따른다:

- **항상(프로파일 무관)**: 깨진 `[[링크]]`(stub 제외), inbox 적체(7일+, INFO).
- **strict(knot-native)**: frontmatter 필수 필드·type 4종·날짜 형식·sources 실재·
  index↔wiki 정합(누락/중복/파일없음)·스텁 schema 참조.
- **shared(기존 vault)**: 위 strict-전용 검사는 끄고 거짓 ERROR 0 으로 운영.
- 공통: 고아 페이지=WARN, stale(90일+)=INFO.

종료 코드: ERROR 있으면 1, `--strict` 면 WARN 도 3. `--json` 으로 기계 판독 가능.

## 주의

- 날짜는 `date '+%Y-%m-%d'` 로 확인 — 암산 금지.
- 판단이 필요한 의미 문제(모순 해소·페이지 병합)는 **고치지 말고 목록화** 하여 사람에게 넘긴다.
