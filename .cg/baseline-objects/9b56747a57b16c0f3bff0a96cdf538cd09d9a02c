---
origin_model: claude-fable-5
review_by: 2026-10-26
---

# Issue 기반 작업 워크플로우

> lesson-app 운영에서 흡수한 패턴. GitHub Issues (또는 동급 트래커) 를 작업 단위 SSOT 로 사용한다.

## Claude 행동 지침

사용자가 간단히 요청해도 다음을 수행:
1. 관련 코드/스펙 파악
2. 상세 본문 작성 (문제, 관련 파일, 예상 원인)
3. 라벨 자동 선택 후 이슈 생성

## 라벨 체계

| 카테고리 | 라벨 |
|----------|------|
| 타입 | `bug`, `feature`, `enhancement`, `refactor`, `docs`, `test`, `claude` |
| 우선순위 | `priority: critical/high/medium/low` |
| 도메인 | `domain: <프로젝트 도메인명>` — `.harness/knowledge/glossary.md` 의 공식 용어 사용 |
| 상태 | `status: todo/in-progress/blocked/review/done` |

## 워크플로우

```
1. 이슈 생성 + 라벨 지정
2. 브랜치: fix/42-description, feat/15-description, refactor/28-description
3. 커밋: "fix(도메인): 설명\n\nRefs #42"
4. 구현 완료 → status: review (사용자 확인 대기)
5. 사용자 확인 후 → status: done + 이슈 닫기
```

> 기능 구현 후 사용자가 테스트/확인하기 전까지 이슈를 닫지 않는다 (CLAUDE.md "Never" 항목과 동일).

## 복잡한 작업 (3시간+)

Phase 기반 분해(`cg-decomposition`) 후 각 job 을 이슈로 등록 — Issue 참조, 세션별 Phase 진행, 완료 시 Issue 에 코멘트.

## 상위 규칙과의 관계

- [worktree-parallel-workflow.md](worktree-parallel-workflow.md): 이슈 → 브랜치 → worktree 1:1 매핑
- [git-workflow-v2.md](git-workflow-v2.md): 커밋 메시지/PR 규칙
- `matt-to-issues` 스킬: 스펙 산출물을 이슈로 변환하는 실행 절차
