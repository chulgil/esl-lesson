---
name: verify-spec
version: 1.0.0
description: 구현 완료 후 스펙 문서 대비 누락 기능/UX 위반/테스트 데이터 미연계를 검증하는 스킬
last_updated: 2026-03-27
---

# Verify Spec — 스펙 대비 구현 검증

## 목적

구현 완료 후 `docs/specs/[domain]/` 스펙 문서와 실제 코드를 대조하여 **누락된 기능, UX 규칙 위반, 테스트 데이터 미연계**를 검출한다. "구현 후에야 비로소 발견"되는 병목을 자동화한다.

## 사용법

```
/verify-spec [도메인명]
예: /verify-spec practice
예: /verify-spec lesson
예: /verify-spec student_home
```

## 프로세스

### 1단계: 스펙 로드

`docs/specs/[domain]/` 아래 모든 `.md` 파일을 로드한다.
- `docs/specs/old/` 는 **무시** (레거시, 현행 아님)
- 마스터 스펙 (`*_master.md`)이 있으면 우선 참조
- 의존 도메인 스펙도 확인 (스펙 내 다른 도메인 링크 추적)

### 2단계: 수용 기준 추출

각 스펙에서 다음을 추출:
- 체크박스 항목 (`- [ ]`, `- [x]`)
- "필수", "반드시", "MUST" 키워드가 포함된 문장
- 유저 스토리 형태 ("~하면 ~할 수 있다")
- 화면별 기능 목록 (표 형태로 정리된 것)

### 3단계: 코드 대조

각 수용 기준에 대해:

1. **화면 존재 여부**: `features/[domain]/presentation/screens/` 에서 관련 화면 검색
2. **기능 구현 여부**: 핵심 키워드로 grep (엔티티명, 메서드명, 라우트)
3. **상세 화면 링크**: 리스트 위젯에 `onTap` + `context.push/go` 존재하는지
4. **네비게이션**: `AppRoutes` 상수에 해당 라우트 등록되어 있는지

### 4단계: UX 규칙 체크

`.claude/rules/ux-rules.md` 기반으로 변경된 파일을 검증:

```bash
# 하드코딩 색상
grep -rn "Color(0x" --include="*.dart" features/[domain]/

# fontSize 직접 사용
grep -rn "fontSize:" --include="*.dart" features/[domain]/ | grep -v "AppTypography"

# EdgeInsets 숫자 직접 사용
grep -rn "EdgeInsets\." --include="*.dart" features/[domain]/ | grep -v "AppSpacing"

# 공통 위젯 미사용 (EmptyStateWidget 등)
grep -rn "Text('데이터가 없습니다')" --include="*.dart" features/[domain]/
```

### 5단계: 테스트 데이터 연계 확인

- Mock Repository에 새 기능의 데이터가 추가되었는지
- `docs/specs/dev/test_data.md`에 시나리오가 업데이트되었는지
- 새 Provider가 `_invalidateProviders()`에 등록되었는지

### 6단계: 반복 이슈 체크

`.claude/rules/tech-patterns.md`와 `.claude/rules/design-principles.md` 참조:

- 오디오 관련 변경 → iOS 백그라운드 복구 패턴 확인
- 설정 필드 추가 → 비즈니스 로직에서 실제 사용 여부 확인
- 새 CRUD 메서드 → 호출하는 곳이 존재하는지 확인
- 중복 설정 → 같은 개념이 2곳에서 설정 가능한지 확인

### 7단계: 보고서 출력

```markdown
# Verify Spec 보고서: [domain]

## 스펙 파일
- [파일 목록]

## 구현율: X/Y (Z%)

### 누락 기능 (CRITICAL)
| 스펙 항목 | 출처 파일:라인 | 상태 |
|----------|--------------|------|
| [항목] | [스펙파일:N] | 미구현 |

### UX 위반 (HIGH)
| 위반 | 파일:라인 | 수정 방법 |
|------|----------|----------|
| [위반 내용] | [파일:N] | [수정법] |

### 테스트 데이터 (MEDIUM)
- [ ] Mock 데이터 추가 여부
- [ ] 시나리오 테스트 업데이트 여부
- [ ] Provider 등록 여부

### 반복 이슈
- [해당 교훈 번호 + 요약]

## 판정: PASS / BLOCK
- CRITICAL 0건 → PASS
- CRITICAL 1건 이상 → BLOCK (수정 필요)
```

## 주의사항

- `docs/specs/old/` 는 절대 참조하지 않는다
- 스펙 자체가 불완전하면 "스펙 보완 필요" 로 별도 보고
- 새 교훈 발견 시 올바른 카테고리 규칙 파일에 추가
