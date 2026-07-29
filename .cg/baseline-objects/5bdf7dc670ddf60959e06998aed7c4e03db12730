---
origin_model: claude-fable-5
review_by: 2026-10-26
---

# Tech Patterns — 언어별 구현 패턴

> 보편 원칙은 [golden-principles.md](golden-principles.md) 가 정본. 이 문서는 그 원칙의 **언어별 구현 방법**과 디렉토리/테스트 배치만 담는다 (중복 제거).

## 1. Immutability — 언어별 (golden #1)

원본을 수정하지 말고 새 객체를 생성. 언어별 수단:
- Flutter: `copyWith` · Python: `dataclasses.replace` / `frozen=True` · Java: record · Go: new struct

## 2. 시스템 경계 검증 — 언어별 (golden #6)

외부 입력(사용자·API·파일)은 **반드시** 검증. 내부 함수는 신뢰 — 이중 검증은 안티패턴. 언어별 수단:
- Flutter: `freezed` + `json_serializable` custom validator
- Python: `pydantic` (zod 스타일 스키마)
- Java: Bean Validation (`@NotNull`, `@Size`)
- Go: struct tag 검증 (`go-playground/validator`)

## 3. Feature 기반 디렉토리

레이어별이 아닌 **도메인별** 폴더:
```
features/
├── {feature-a}/
│   ├── domain/       # 엔티티, 리포지토리 인터페이스
│   ├── data/         # 리포지토리 구현
│   └── presentation/ # UI, 프로바이더
```

## 4. 테스트 배치

- 단위 테스트: 소스 근처 또는 `tests/unit/`
- 통합 테스트: `tests/integration/`
- E2E 테스트: `tests/e2e/` 또는 `integration_test/` (Flutter)

## 5. 에러 처리

모든 외부 호출은 `try/catch` 또는 `Result<T, E>`. 조용히 삼키지 않는다. 사용자에게 보이는 에러 메시지에 기술 용어 금지.

> 파일/함수 크기는 golden #5, Secret 환경변수는 golden #2 + [security.md](security.md), Surgical Changes 는 golden #12 참조.
