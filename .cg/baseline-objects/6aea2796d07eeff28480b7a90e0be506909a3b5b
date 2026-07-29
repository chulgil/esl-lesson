---
origin_model: claude-fable-5
review_by: 2026-10-26
---

# Flutter Architecture — 확장형 앱 계층 계약

> 핵심 원칙: **business/domain 값은 순수하게 유지하고, 화면 표시·문자열·라우팅·플랫폼 의존은 바깥 계층에서 조립한다.**

## 기준 구조

Flutter feature 는 기본적으로 다음 구조를 따른다.

```text
features/<feature>/
  data/           # repository implementation, API/Hive/Firebase/platform adapter
  domain/         # entity, value object, repository interface, pure service
  presentation/   # screen, widget, provider, presentation extension
```

의존성 방향은 항상 다음과 같다.

```text
presentation -> domain <- data
```

## 금지

- `domain` 또는 `data` 에서 `/presentation/` import/export 금지
- `domain` 에서 `/data/` import/export 금지
- feature 내부가 아닌 코드에서 다른 feature 의 `/presentation/providers/` 직접 import 금지
- `domain` 에서 Flutter widget/material, Riverpod `Ref`, Firebase/Hive/API client, `EnvironmentConfig` 직접 의존 금지
- `domain/data` 에서 `AppStrings`, `AppLocalizations`, `core/l10n` 직접 의존 금지
- enum/entity 에 `label`, `title`, `emoji`, `statusLabel`, `displayText`, `homeRoute` 같은 화면 표시 getter 추가 금지

## 허용 위치

사용자-facing 문자열과 표시 변환은 다음 위치에 둔다.

- `presentation/widgets`, `presentation/screens`
- `presentation/providers`
- `presentation/extensions`
- 앱 공통 UI helper 또는 l10n facade

예:

```dart
// domain: pure value only
enum LessonStatus { pending, confirmed }

// presentation/extensions/lesson_status_visuals.dart
extension LessonStatusVisuals on LessonStatus {
  String get label => switch (this) {
    LessonStatus.pending => AppStrings.lessonPending,
    LessonStatus.confirmed => AppStrings.lessonConfirmed,
  };
}
```

## Riverpod 기준

- 신규/수정 provider 는 `riverpod_annotation` codegen 을 기본으로 한다.
- repository provider 와 앱 단위 singleton 은 `@Riverpod(keepAlive: true)` 를 사용한다.
- 화면/검색/상세/필터 상태는 기본 autoDispose 로 둔다.
- `StateProvider` 는 bool/string/enum/date/int 같은 단순 UI state 에만 쓴다.
- 검증, 비동기, 복합 상태, workflow 는 `Notifier` 또는 `AsyncNotifier` 로 승격한다.

## Feature Facade 기준

다른 feature 의 기능을 재사용할 때는 source feature 의 public facade 를 통한다.

- 허용: `features/onboarding/onboarding_facade.dart` 처럼 feature root facade import
- 금지: `features/onboarding/presentation/providers/foo_provider.dart` 직접 import
- facade 는 repository provider, read-only query provider, application service provider 처럼 외부 계약으로 인정된 API만 export한다.
- screen/widget 내부 상태, 임시 form 상태, private orchestration provider 는 facade 로 export하지 않는다.
- legacy direct import 를 제거하면 architecture test baseline 도 함께 줄인다.

## 로컬 저장소와 UI 플래그

Hive/SharedPreferences/SecureStorage 는 domain entity 에 직접 섞지 않는다.

- 새 domain entity 에 Hive annotation 추가 금지
- box/key 는 data adapter 또는 presentation/application storage provider 안에 캡슐화
- 온보딩 완료, 최초 오버레이 dismiss, 사용자별 UI preference 는 `AsyncNotifier` storage provider 로 관리
- 사용자별 상태는 `teacher:<userId>:...`, `student:<userId>:...` 같은 user id scoped key 사용
- 다른 feature 에서 읽어야 하면 source feature facade 에서 좁게 export

## Cross-Feature Service Wiring

여러 feature 의 repository/service 를 조합하는 workflow 는 application/domain service 로 분리한다.

- service 는 repository interface 와 순수 service interface 를 constructor 로 받는다.
- service 내부에서 Riverpod provider/facade/presentation provider 를 import하지 않는다.
- service provider 는 presentation layer 에 두고 각 dependency 를 feature facade 또는 local provider 로 주입한다.
- domain model 에 없는 UI 편의 필드를 가정하지 않는다. 회차, request id, 남은 변경권 같은 값은 repository 조회나 mapper/service helper 에서 계산한다.

## 코딩 전 체크

Flutter 코드를 작성하기 전 반드시 확인한다.

1. 새 파일 위치가 `data/domain/presentation` 역할과 맞는가?
2. 문구가 필요하면 `AppStrings` 또는 `AppLocalizations` 를 presentation 쪽에서만 쓰는가?
3. n8n/automation 메시지는 문장 하드코딩 대신 stable key + payload 로 전달되는가?
4. 여러 화면에서 같은 workflow 를 쓰면 usecase/application service 로 분리했는가?
5. 같은 UI 단위는 하나의 공통 widget/facade 로 재사용되는가?
6. cross-feature provider 의존이 facade 를 통하는가?
7. 로컬 UI flag 가 user id scoped key 로 저장되고 테스트되는가?

## 검증

프로젝트에 architecture test 가 있으면 우선 실행한다.

```bash
flutter test test/architecture
flutter analyze
```

cg-harness 기본 훅인 `.claude/hooks/scripts/i18n-l10n-guard.py` 는 직접 한글 UI 문자열과 domain/data 의 l10n 의존을 감지한다.
