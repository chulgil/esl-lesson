---
description: 특정 phase 스킬을 직접 호출. 예 /phase 2 feature-slug.
---

# /phase

## 용도

7-phase 중 특정 phase 로 직접 진입할 때.
일반 흐름은 `/new-feature` 를 쓰고, 재작업/부분 실행 시 이 명령 사용.

## 사용법

```
/phase <번호> <feature-slug>
```

예:
```
/phase 3 lesson-booking     # visuals 부터 다시
/phase 6 lesson-booking     # 평가만 재실행
```

## 매핑

| 번호 | 스킬 |
|------|------|
| 0 | cg-brownfield-scan |
| 1 | cg-interview |
| 2 | cg-spec-and-harness |
| 3 | cg-visuals |
| 4 | cg-decomposition |
| 5 | cg-execution-loop |
| 6 | cg-evaluation |

## 주의

- Phase 선행 산출물이 없으면 중단 (예: spec 없이 Phase 4 불가)
- Phase 6 는 반드시 별개 서브에이전트 컨텍스트로
