---
origin_model: claude-fable-5
review_by: 2026-10-26
---

# Domain Linter — AI 모델 무관 멱등성 강제

> 하네스 엔지니어링 패턴: 어떤 AI 모델을 사용하더라도 같은 코드 구조가 나오도록 도메인 규칙을 강제한다.
> 디자인 시스템이 디자이너를 바꿔도 일관된 UI를 보장하듯, 도메인 린터는 AI를 바꿔도 일관된 코드를 보장한다.

## 작동 방식

이 규칙은 `CLAUDE.md` 의 규칙 인덱스에서 참조된다. 코드 생성·리뷰·커밋 시 아래 규칙을 적용한다.

---

## 1. 파일명 규칙

### 페이지/스크린

**도메인 복수형 + _page 접미사를 사용한다.**

```
# GOOD
lessons_page.dart
practices_page.dart
students_page.dart
restaurants_page.dart

# BAD — 금지 접미사
lesson_list_page.dart      # "list" 금지
lesson_detail_page.dart    # "detail" 금지
lesson_search_page.dart    # "search" 금지
practice_history_page.dart # "history" 금지
```

**단수형은 개별 항목 페이지에만 사용:**
```
lesson_page.dart       # 단일 레슨 상세 (O)
lessons_page.dart      # 레슨 목록 (O)
```

### 위젯/컴포넌트

**도메인명 + _widget 또는 역할명:**
```
lesson_card.dart           # (O)
lesson_card_widget.dart    # (X) — 중복 접미사
practice_timer.dart        # (O)
```

### 프로바이더/서비스

**도메인명 + _provider 또는 _service:**
```
lesson_provider.dart       # (O)
lessons_provider.dart      # 복수형도 OK (컬렉션 관리)
```

---

## 2. 클래스명 규칙

**파일명에서 파생. 파일명이 결정되면 클래스명은 자동으로 결정된다.**

```dart
// lessons_page.dart → LessonsPage
class LessonsPage extends ConsumerWidget { ... }

// lesson_provider.dart → LessonProvider / LessonNotifier
class LessonNotifier extends AsyncNotifier<Lesson> { ... }

// lesson_card.dart → LessonCard
class LessonCard extends StatelessWidget { ... }
```

---

## 3. 임포트 규칙

### 순서 (알파벳 정렬 강제)

```dart
// 1. Dart SDK
import 'dart:async';
import 'dart:convert';

// 2. Flutter SDK
import 'package:flutter/material.dart';

// 3. 외부 패키지 (알파벳순)
import 'package:go_router/go_router.dart';
import 'package:riverpod/riverpod.dart';

// 4. 프로젝트 내부 (알파벳순)
import 'package:app/core/theme/app_colors.dart';
import 'package:app/features/lessons/domain/entities/lesson.dart';
```

### 임포트 제한

```
# 금지: 레거시 경로에서 직접 임포트
import 'package:app/models/...'       # (X) → features/[domain]/domain/entities/ 사용
import 'package:app/providers/...'    # (X) → features/[domain]/presentation/providers/ 사용
import 'package:app/repositories/...' # (X) → features/[domain]/data/repositories/ 사용
```

---

## 4. 폴더 구조 규칙

### Feature-Based Architecture 강제

```
features/[domain]/
├── domain/
│   ├── entities/       # 엔티티만 (데이터 모델)
│   └── repositories/   # 인터페이스만 (abstract class)
├── data/
│   └── repositories/   # 구현체만 (implements)
└── presentation/
    ├── screens/        # 페이지 위젯
    ├── widgets/        # 재사용 위젯
    └── providers/      # @riverpod 프로바이더
```

**금지:**
- `features/[domain]/` 외부에 새 도메인 파일 생성
- `lib/` 루트에 직접 파일 추가 (`core/` 제외)
- `presentation/` 안에 엔티티나 리포지토리 배치

### 배럴 파일 (index) 규칙

**각 domain 폴더에 배럴 파일을 두어 공개 API를 명시:**
```dart
// features/lessons/lessons.dart (배럴 파일)
export 'domain/entities/lesson.dart';
export 'presentation/screens/lessons_page.dart';
export 'presentation/providers/lesson_provider.dart';
// data/ 레이어는 export하지 않음 (내부 구현)
```

---

## 5. 검증 시점

| 시점 | 방법 | 자동화 |
|------|------|--------|
| 코드 생성 시 | 이 규칙을 참조하여 코드 생성 | 자동 (규칙 로딩) |
| `/code-review` 시 | 도메인 린터 위반 사항 보고 | 자동 |
| 커밋 시 | Merge Gate에서 구조 검증 | `hooks/code-quality-reminder.sh` |

---

## 6. 프로젝트별 커스터마이징

이 규칙은 **기본값**이다. 프로젝트별로 다른 컨벤션이 필요하면:

1. 프로젝트 루트의 `CLAUDE.md`에 오버라이드 규칙 작성
2. 프로젝트 `CLAUDE.md` 규칙이 이 글로벌 규칙보다 우선

```markdown
# 프로젝트 CLAUDE.md 예시
## 도메인 린터 오버라이드
- 페이지 접미사: _screen 사용 (Flutter 컨벤션)
- 프로바이더: _controller 접미사 허용
```

---

## 멱등성 원칙

> 이 규칙의 목적은 **멱등성**: 같은 요구사항을 주면 어떤 AI 모델이든 같은 파일 구조·클래스명·임포트 순서의 코드를 생성한다.
>
> 프롬프트만으로는 100% 일관성을 보장할 수 없다. 규칙 파일이 `CLAUDE.md` 를 통해 일관되게 참조되어야 한다.
