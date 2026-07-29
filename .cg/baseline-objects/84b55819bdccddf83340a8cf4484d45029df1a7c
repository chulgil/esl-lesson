---
name: cg-knot-ingest
description: |
  Knot 지식 그물 — inbox 소스를 wiki 페이지로 컴파일(ingest)한다. 벤더 중립
  평문 md, schema 준수, 끝에 git commit(push 금지). 트리거: knot ingest,
  지식 흡수, inbox 처리, "이 자료 그물에 넣어줘".
---

# Skill — Knot Ingest (inbox → wiki 컴파일)

## 목적

vault `inbox/` 의 미처리 소스 1건을 정독하여 `wiki/` 의 `source`/`entity`/`concept`
페이지로 컴파일한다. 벤더 중립 — Claude·Codex·Gemini 가 같은 평문 그물을 읽고 쓴다.

## 0. schema 먼저 정독 (필수)

vault 루트 `schema.md` 를 **먼저 정독**한다. 이 스킬만 보고 시작하지 말 것.
타입 4종(source/entity/concept/note), frontmatter, `[[링크]]` 규칙은 schema 가 정본이다.

## git 규약 (필수)

- **시작 가드**: `git status --porcelain` 출력이 비어 있지 않으면 다른 실행이
  진행 중일 수 있으므로 **즉시 중단하고 보고**한다. 끝에 커밋하므로 시작은 깨끗해야 한다.
- **마무리 커밋**: 작업 끝에 `git add -A && git commit -m "ingest: <제목>"`.
  트레일러에 실행한 실제 모델명 — 예: `Co-Authored-By: <모델명>`.
- **push 금지** — 로컬 전용. 원격 연결은 사람이 결정한다.

## 흐름

```
1. 가드      — git status --porcelain 비어있지 않으면 중단·보고
   ↓
2. 소스 선택 — inbox/ 에서 가장 오래된 1건 (명시 지시 시만 최대 3건)
              비어 있으면 "할 일 없음" 으로 즉시 종료
   ↓
3. 컴파일    — wiki/ 에 source 페이지(요약·takeaway·## 열린 질문)
              본문 [[교차링크]] 로 entity/concept 생성·갱신
              생성/갱신 페이지의 ## 관련 절에 source 역링크 한 줄
   ↓
4. index/log — index.md 의 type 섹션에 한 줄, log.md 에 ## [날짜] ingest — 제목
   ↓
5. raw 이동  — 원본을 raw/YYYY-MM-DD-<원래이름> 으로 이동(내용 수정 금지)
   ↓
6. 검증·커밋 — cg knot lint → ERROR 기계 정정 → git commit
```

## 세부 규칙

- 텍스트(md·txt)가 벤더중립 기본. PDF·이미지 등 rich 포맷은 읽을 수 없으면 건너뛰고 보고한다.
- 날짜는 vault 시스템 시각(KST) 기준으로 `date '+%Y-%m-%d'` 로 확인 — 암산 금지.
- 깨진 `[[링크]]` 가 의도적이면(아직 없는 페이지) 그 줄에 `<!-- stub -->` 표기.
- `raw/` 이동이 처리 완료 표시다. 이동만 허용, 내용 수정 절대 금지.

## 검증

작업 후 `cg knot lint` (또는 `cg knot lint --vault <vault>`) 로 ERROR 0 을 확인한 뒤
커밋한다. 깨진 링크·index 정합·frontmatter 보정은 기계적 작업이므로 직접 정정한다.
