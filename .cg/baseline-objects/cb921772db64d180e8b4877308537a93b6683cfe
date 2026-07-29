---
name: cg-welcome
description: "처음 cg-harness 프로젝트에 진입한 사용자에게 7-Phase 워크플로우와 디렉토리 구조를 1분 안에 설명. 트리거: 시작, 어디서부터, getting started, where do i start, 처음, 환영."
---

# cg-welcome — 신규 사용자 온보딩

## 트리거 키워드

`시작`, `어디서부터`, `getting started`, `where do i start`, `처음`,
`환영`, `welcome`, `cg 사용법`, `처음 사용`.

## 목적

cg-harness 프로젝트를 처음 연 사용자에게:
1. 7-Phase 워크플로우의 **현재 위치** 추정.
2. 다음에 호출할 **단 하나의 스킬** 추천.
3. `.harness/` 디렉토리 의미 1줄 설명.

기존 README 를 다시 읽지 않아도 30초 안에 다음 액션이 결정되도록.

## 절차

1. **현재 상태 스냅샷**
   - `.harness/spec/` 비어 있는가? → Phase 1 (cg-interview) 필요.
   - `spec/*.md` 있고 `decomposition-*.md` 없음 → Phase 2~4 진행.
   - `decomposition-*.md` 있고 journal 비어 있음 → Phase 5 (cg-execution-loop).
   - journal 있음 → Phase 6 (cg-evaluation) 또는 cg-status 로 점검.

2. **디렉토리 의미 1줄 매핑**

   | 경로 | 무엇을 담는가 |
   |---|---|
   | `.harness/spec/` | 단일 진실 원천 (SSOT). spec + decomposition + AC Tree |
   | `.harness/journal/{date}.md` | 매 커밋 = 한 줄 기록 |
   | `.harness/visuals/{feature}/` | 와이어프레임, 아키텍처 다이어그램 |
   | `.harness/status/` | drift.json, current.md (자동 생성) |
   | `.cg/mechanical.toml` | build/test/lint 명령 (ralph 구성 설치 시 cg-ralph 가 사용) |
   | `.claude/skills/cg-*/` | 11개 스킬 (이 폴더의 SKILL.md 가 진실) |

3. **다음 액션 1개만 추천**

   현재 위치별 추천 한 줄:

   - 신규 → `/cg-interview 의 새 기능 인터뷰 시작`
   - 인터뷰 완료 → `/cg-spec-and-harness 로 spec 작성`
   - spec 있음 → `/cg-decomposition 으로 AC Tree 구성`
   - 코드 작성 중 → `/cg-execution-loop` — ralph 구성도 설치되어 있다면 `/cg-ralph`
   - 막힘 → `/cg-unstuck` (5-persona, ralph 구성 설치 시)
   - 완료 검증 → `/cg-evaluation` (3-critic + Mechanical)
   - 길 잃음 → `/cg-status` (drift verdict)

## 출력 포맷

```
환영 — cg-harness 신규 사용자 안내
============================================================
현재 단계 추정: Phase 1 (Spec 없음)

.harness/ 폴더는:
  - spec/      → 모든 결정의 진실 원천
  - journal/   → 매일의 진행 기록
  - status/    → 드리프트 자동 추적

다음 단 하나의 액션:
  /cg-interview "<기능 한 줄>" 로 인터뷰 시작

5분 학습 코스: README.md의 "7-Phase 워크플로우" 섹션 참조.
```

## 원칙

- 스킬 11개를 한꺼번에 나열하지 않는다 (Stage 1 로딩 절약).
- 현재 위치에서 **다음 1개**만 추천. 파이프라인 전체 설명 금지.
- 사용자가 이미 spec/journal 을 가진 상태라면 "환영" 이 아니라 cg-status
  를 자동 추천 (잘못된 진입점 방지).
