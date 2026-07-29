# .claude/skills/

Claude Code 가 로드하는 **7-phase 워크플로우 스킬** 모음. 각 스킬은 `SKILL.md` 를 엔트리 포인트로 갖습니다.

## 7-Phase (tenet 방식)

| # | Skill | 역할 |
|---|-------|------|
| 0 | `cg-brownfield-scan` | 기존 코드/프레임워크/이전 하네스 산출물 스캔 |
| 1 | `cg-interview` | 요구사항 인터뷰 — 기술 리서치 + 모호성 제거 |
| 2 | `cg-spec-and-harness` | 공식 스펙 + 품질 계약(harness/current.md) 작성 |
| 3 | `cg-visuals` | 아키텍처 다이어그램 + UI 목업 |
| 4 | `cg-decomposition` | 스펙을 DAG(의존성 그래프) 로 분해 |
| 5 | `cg-execution-loop` | 각 job 구현 + 커밋 + 검증 |
| 6 | `cg-evaluation` | 3-critic 평가 (code / test / e2e) |

## Matt Pocock Engineering Adapters

| Skill | 역할 |
|-------|------|
| `matt-grill-with-docs` | 요구사항을 집요하게 질문하고 glossary/ADR/spec로 정리 |
| `matt-zoom-out` | 로컬 코드나 기능을 전체 시스템 맥락에서 설명 |
| `matt-to-issues` | PRD/spec을 독립 실행 가능한 vertical slice 이슈로 분해 |

이 스킬들은 `mattpocock/skills`의 engineering 스킬에서 아이디어를 가져와 cg-harness 산출물 경로에 맞춘 어댑터입니다.

## 데이터 인덱싱

| Skill | 역할 |
|-------|------|
| `pdf-rag-ingest` | 한국어 PDF(스캔본 포함)를 OCRmyPDF + BGE-M3 + Qdrant 로 깨지지 않게 인덱싱 |

## 코드 품질 (lesson-app 운영 흡수)

| Skill | 역할 |
|-------|------|
| `clean-comments` | 디버그 흔적·주석 처리된 코드·자명한 주석 정리, 가치 있는 주석만 유지 |

## 원칙

- **Phase 를 건너뛰지 않는다**: 각 phase 는 다음 phase 의 입력. spec 없이 바로 execution 으로 가면 드리프트.
- **Oracle Problem**: Test critic 은 반드시 코드 작성 세션과 분리된 컨텍스트에서 평가.
- **Feature-scoped 네이밍**: 모든 feature 산출물은 `{YYYY-MM-DD}-{slug}.md`.
