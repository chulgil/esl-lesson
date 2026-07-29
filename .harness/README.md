# .harness/ — 살아있는 SSOT

이 디렉토리는 **Executable SSOT (Single Source of Truth)** 입니다. 에이전트와 사람이 동일한 파일을 읽고 쓰면서 장기 세션 동안 컨텍스트를 유지합니다.

## 디렉토리 역할

| 디렉토리 | 역할 | 수명 |
|---------|------|------|
| `interview/` | 인터뷰 전사 (`{YYYY-MM-DD}-{feature}.md`) | Feature 별 |
| `spec/` | 공식 스펙 (`{YYYY-MM-DD}-{feature}.md`) | Feature 별 |
| `harness/` | 품질 계약 (`current.md`: 린팅/테스팅/아키텍처 규칙) | 프로젝트 전역 |
| `knowledge/` | 재사용 가능한 기술 지식 스니펫 | 무기한 |
| `journal/` | 개발 활동 일지 (`{YYYY-MM-DD}.md`) | 날짜별 |
| `steer/` | Steer 메시지 inbox/processed | 일시적 |
| `visuals/` | 아키텍처 다이어그램, UI 목업 | Feature 별 |
| `status/` | 자동 생성 상태 파일 (커밋 제외) | 자동 |

## Feature-scoped 네이밍 규칙 (tenet 패턴)

`{YYYY-MM-DD}-{feature-slug}.md` 형식을 사용합니다. 예:
- `spec/2026-04-23-oauth.md`
- `interview/2026-05-01-payments.md`

이 네이밍으로 동일 feature 의 최신 문서를 쉽게 찾고, 여러 feature 가 병행되어도 충돌하지 않습니다.

## 프로젝트 전역 문서

다음은 단수형 유지:
- `harness/current.md` — 현재 품질 계약
- `steer/inbox.md` — 미처리 steer 메시지
