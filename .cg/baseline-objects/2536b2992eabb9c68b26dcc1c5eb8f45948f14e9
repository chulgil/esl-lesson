---
name: clean-comments
description: 코드에서 불필요한 주석(디버그 흔적, 주석 처리된 코드, 자명한 주석)을 정리하고 가치 있는 주석만 유지합니다. 트리거: 주석 정리, 디버그 주석 제거, clean comments.
allowed-tools: Read, Grep, Edit
---

# Clean Comments Skill

코드 리뷰 또는 정리 시 **불필요한 주석을 제거**하고 **가치 있는 주석만 유지**합니다.

## 사용 시점

- 코드 리뷰 후 정리 작업
- 리팩토링 완료 후 마무리
- 디버그 코드 제거 요청 시

## 제거 대상

### 1. 디버그 주석
```dart
// print("debug: $value");  // 제거
// debugPrint("test");       // 제거
```

### 2. 주석 처리된 코드
```python
# old implementation:
# if condition:
#     do_something()
```

### 3. 자명한 주석
```go
// increment counter  ← 제거 (코드가 명확)
counter++
```

### 4. 오래된 TODO/FIXME
```java
// TODO: implement later (2024-01-15)  ← 오래된 TODO
// FIXME: temporary workaround         ← 해결된 경우
```

## 유지 대상

### 1. 비즈니스 로직 설명
```dart
// 20% 페널티: 연습 시간이 부족하면 점수 차감
final penalty = practiceTime < 30 ? 0.8 : 1.0;
```

### 2. 복잡한 알고리즘 설명
```python
# Floyd's cycle detection algorithm
slow, fast = head, head
```

### 3. API/외부 의존성 제약 설명
```dart
// Firebase requires minimum 6 characters for password
if (password.length < 6) throw ValidationError();
```

### 4. 문서화 주석 (dartdoc / docstring / javadoc / godoc)

공개 API 의 문서 주석은 항상 유지.

### 5. 앵커 주석
```
// {#anchor-id}  ← 문서 참조용 앵커는 유지
```

## 작업 순서

1. **탐색**: 대상 파일/폴더 내 주석 검색 (Grep)
2. **분류**: 제거/유지 대상 분류
3. **확인**: 제거 대상 목록 사용자에게 확인
4. **정리**: 승인된 주석만 제거
5. **검증**: `cg diagnose --gate lint` 또는 언어별 analyzer 실행

## 체크리스트

- [ ] 문서화 주석은 유지했는가?
- [ ] 비즈니스 로직 설명은 유지했는가?
- [ ] 앵커 주석 (`{#...}`)은 유지했는가?
- [ ] lint/analyze 통과하는가?
