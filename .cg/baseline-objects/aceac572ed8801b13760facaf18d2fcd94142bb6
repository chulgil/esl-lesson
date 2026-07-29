---
origin_model: claude-fable-5
review_by: 2026-10-26
---

# Doc Sync — Spec ↔ Code 동기화

> 핵심 원칙: **코드 변경은 스펙 변경을 수반한다. 스펙 없이 머지 금지.**

## 동기화 대상

| 소스 | 타겟 |
|------|------|
| 새 API 엔드포인트 | `.harness/spec/{...}.md` §4 인터페이스 |
| DB 스키마 변경 | `.harness/spec/{...}.md` §4 스키마 + 마이그레이션 노트 |
| UI 컴포넌트 추가 | `.harness/visuals/{feature}/` |
| 아키텍처 결정 | 커밋 trailer `Lore-directive:` |
| 거절된 대안 | 커밋 trailer `Lore-rejected:` |

## 워크플로우

```
1. 스펙을 먼저 수정 (Phase 2)
2. 다이어그램 동기화 (Phase 3)
3. DAG 재계산 (Phase 4, 영향 받는 job 만)
4. 구현 (Phase 5)
5. 평가 (Phase 6)
```

**역순은 금지**: "코드부터 짜고 스펙은 나중에" = 의도가 구현에 오염됨.

## 체크 시점

| 시점 | 체크 |
|------|------|
| PR 생성 시 | 스펙 파일이 diff 에 포함되었는가? |
| 커밋 전 | 스펙의 §2 성공 기준과 구현이 일치하는가? |
| Phase 6 | Code Critic 이 "스펙의 모든 기준이 구현" 확인 |

## Drift 감지

다음은 "docs drift" 신호:
- 코드에는 있지만 스펙에 없는 엔드포인트
- 스펙에는 있지만 테스트에 없는 성공 기준
- 커밋 메시지에 "WIP", "TODO" 가 머지됨

발견 시 즉시 수정. 방치하면 하네스가 무너집니다.

## 예외

- 내부 리팩토링 (외부 동작 불변) → 스펙 변경 불필요, 커밋 메시지로만 기록
- 성능 튜닝 → §5 비기능 요구사항의 측정값만 갱신

## 상위 규칙과의 관계

doc-sync 는 스펙/문서 동기화만 담당한다. 품질·검증·커밋 관련은 각각 분리된 규칙을 따른다:

| 관심사 | 규칙 파일 |
|---|---|
| 코딩 원칙 (12개) | [golden-principles.md](golden-principles.md) |
| 증거 기반 완료, Red-Green 검증 | [verification.md](verification.md) |
| 4-기준 자가평가 (Phase 6) | [rubric-evaluation.md](rubric-evaluation.md) |
| 서브에이전트 결과 포맷 (200단어) | [subagent-output.md](subagent-output.md) |
| git trailer 결정 기록 | [lore-commit.md](lore-commit.md) |
| 완료 전 코드 품질 체크리스트 | [coding-style.md](coding-style.md) |
| 언어별 구현 패턴 (immutability·검증·디렉토리·테스트 배치) | [tech-patterns.md](tech-patterns.md) |
| 상호작용 (가정 명시, 결론 우선, 분석) | [interaction.md](interaction.md) |
| 보안 체크리스트, 시크릿 관리 | [security.md](security.md) |
| 2단계 스킬 로딩 (토큰 절약) | [skill-loading.md](skill-loading.md) |
| 날짜/시간 계산 (LLM 산술 금지) | [date-calculation.md](date-calculation.md) |

`Lore-directive:` 트레일러로 기록된 아키텍처 결정은 doc-sync 의 "아키텍처 결정" 항목과 일대일 대응된다.
