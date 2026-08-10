# 스펙: 백오피스 (관리자)

> 최종 검증: 2026-07-30 (코드 대조 완료)

`esl.lessonaza.app/admin` 경로에서 admin 역할만 사용하는 관리 화면 (단일 도메인 통합 2026-07-12 — `esladmin.*` 는 rewrite 하위호환만). 콘텐츠 등록은 **관리자 전용**이다 (2026-07-27 거버넌스 전환 — [content-governance.md](content-governance.md), 사용자 등록 경로 제거). 핵심 업무는 (1) 콘텐츠 등록(CC 게이트·허락 증빙) (2) 추출 항목 사후 검수 (3) 사용자/테마 관리.

## 화면 목록

| 경로 | 화면 | 목적 |
|------|------|------|
| `/admin` | 대시보드 | 검수 대기 수, 파이프라인 실패 수, 최근 활동 |
| `/admin/contents` | 콘텐츠 목록 | 상태별 필터, 등록 진입점 |
| `/admin/contents/new` | 콘텐츠 등록 | 유튜브 URL / 수기 입력 |
| `/admin/contents/[id]` | 콘텐츠 상세 | 스크립트 확인, 추출 항목 검수, 재시도 |
| `/admin/items` | 항목 풀 관리 | 전역 항목 검색/수정 (콘텐츠 횡단) |
| `/admin/users` | 사용자 관리 | 역할 변경, 학습 현황 조회 |
| `/admin/themes` | 테마 몰 관리 | 제한 테마 지급/회수 — [theme-mall.md](theme-mall.md) |

## 콘텐츠 등록 (/admin/contents/new)

탭 2개: [유튜브 URL] / [수기 입력]

### 유튜브 URL 탭

```
+--------------------------------------------------+
| 유튜브 URL  [https://youtu.be/...        ] [등록] |
|                                                  |
| (등록 즉시 목록으로 이동, 카드에 진행 상태 표시)      |
|  pending -> 제목 조회 -> 자막 추출 -> 번역 -> 항목 추출 |
+--------------------------------------------------+
```

- URL 붙여넣기 → 등록 클릭이 전부. 제목은 파이프라인이 자동 기입 (요구사항).
- 유효하지 않은 URL은 즉시 인라인 에러. 중복 영상은 기존 콘텐츠로 링크 안내.
- 진행 상태는 목록/상세에서 단계별 표시 (extraction_jobs 기반), 5초 폴링.
- **CC 영상 찾기** (2026-07-29): 검색어로 `GET /api/admin/youtube/cc-search` —
  CC 라이선스 + 자막 보유 영상 후보를 보여주고 선택 시 URL 자동 채움.
- **CC 게이트**: 비 CC(미확인 포함) 영상은 409 `cc_required` — 허락 증빙 폼
  (`permission` 객체: 권리자·날짜·범위 3종 체크·증빙)을 입력해야 등록
  ([content-governance.md](content-governance.md)).
- **라이선스 3단 배지**: CC / 표준(허락 증빙) / 미확인 — 목록·상세에 표시 (5a97b48).

### 수기 입력 탭

| 필드 | 필수 | 비고 |
|------|------|------|
| 제목 | O | |
| 영어 스크립트 | O | 문장 단위 자동 분리 저장 |
| 한글 스크립트 | X | 비우면 AI 번역 자동 생성 |
| 원본 URL | X | 출처 기록용 |

저장 시 DB 저장 → 번역(필요 시)/추출 파이프라인은 유튜브 경로와 동일하게 진행.

## 콘텐츠 상세 = 검수 화면 (/admin/contents/[id])

```
+------------------------------------------------------------+
| [제목] (status 뱃지)              [재시도] [삭제]             |
|------------------------------------------------------------|
| 탭: [스크립트] [단어 12] [숙어 7] [패턴 4] [문장 9]           |
|------------------------------------------------------------|
| (항목 탭)                       [전체 승인] [pending만 승인]  |
|  en_text      | ko_text   | 난이도 | 출처문장 | 상태 | 액션   |
|  resilient    | 회복력 있는 | inter  | "...")  | pend | 승인/수정/제외 |
+------------------------------------------------------------+
```

- 항목 기본값은 **approved** (2026-07-30 전환 — 추출 즉시 학습 풀 편입,
  [content-pipeline.md](content-pipeline.md) 검수 게이트). 검수는 사후 교정 중심.
- 검수 액션: **승인**(approved) / **수정 후 승인**(en/ko/힌트 인라인 편집) / **제외**(rejected).
- 문장 탭은 `hint_thinking`(영어식 사고) 열 추가 — 비어 있으면 승인 불가(레벨 4 퀴즈 필수 필드).
- 스크립트 탭: 세그먼트 영/한 나란히, 인라인 수정 가능 (번역 오류 교정).
- 이미 다른 콘텐츠에서 approved된 전역 항목은 "기존 항목" 뱃지로 표시 (검수 불필요).

## 항목 풀 관리 (/admin/items) — 구현됨 (2026-07-30)

- 전역 learning_items 검색: 타입(word/idiom/pattern/sentence)·상태(pending/approved/rejected)·영/한 키워드 필터 + 페이지네이션(50/페이지, 총 건수 표시).
- 행별 승인/거절 버튼 — **승인 opt-out 모델의 사후 거절 창구** (추출 항목은 기본 approved, [content-governance.md](content-governance.md)). 문장 승인은 hint_thinking 필수(서버 422 메시지 그대로 노출).
- 용도: 부적절 항목 사후 거절, 거절 복구. 텍스트 인라인 수정은 콘텐츠 상세 화면 담당. 수정 이력은 updated_at만 기록(감사 로그는 범위 외).

## 사용자 관리 (/admin/users)

| 기능 | 상세 |
|------|------|
| 목록 | 이메일, 이름, 역할, 가입일, 최근 로그인, 총 복습 수 |
| 역할 변경 | learner ↔ admin (본인 강등 금지) |
| 학습 현황 | 사용자별 카드 수/정답률 요약 (읽기 전용) |

## API (admin 전용, 전체 role=admin DB 재확인)

| 메서드/경로 | 설명 |
|-------------|------|
| POST `/api/admin/contents` | 등록 (유튜브/수기) — [content-pipeline.md](content-pipeline.md) |
| GET `/api/admin/contents?status=&page=` | 목록 |
| GET `/api/admin/contents/{id}` | 상세 (세그먼트+항목+잡 로그) |
| POST `/api/admin/contents/{id}/retry` | 실패 단계 재시도 |
| DELETE `/api/admin/contents/{id}` | 삭제 |
| PATCH `/api/admin/segments/{id}` | 스크립트 세그먼트 수정 |
| PATCH `/api/admin/items/{id}` | 항목 수정/상태 변경 `{en_text?, ko_text?, hint_thinking?, review_status?}` |
| POST `/api/admin/contents/{id}/approve-all` | 콘텐츠 내 pending 일괄 승인 |
| GET `/api/admin/items?type=&status=&q=&page=` | 전역 항목 검색 (50/페이지) |
| PATCH `/api/admin/themes/{key}` | 테마 무료/제한 전환 — [theme-mall.md](theme-mall.md) |
| GET `/api/admin/users` / PATCH `/api/admin/users/{id}` | 사용자 목록/역할 변경 |
| GET `/api/admin/dashboard` | 대시보드 집계 — 공급 리듬 포함 (2026-08-10 P0-B): `weekly_supply`(이번 주 월요일 KST 기준 공용 등록 수)·`supply_goal`(2)·`levels`(ready 공용의 파생 난이도별 수). 대시보드 카드가 주 2편 미달·초급 5편 미달 시 빨간 강조, 등록 화면 CC 검색엔 초급 키워드 프리셋 5종 |
| GET `/api/admin/youtube/cc-search?q=` | CC 영상 검색 (등록 후보) |
| `/api/admin/themes*` | 테마 카탈로그·지급/회수 — [theme-mall.md](theme-mall.md) |

## 접근 제어

- 프론트: `middleware.ts` 는 `esladmin.*` 호스트를 `/admin` 으로 rewrite 만 하고 차단하지 않는다 — 비관리자 안내는 `AdminLayout` 담당.
- 백엔드: `/api/admin/*` 전 라우트에 admin 가드 의존성 (JWT + DB role 재확인) — 보안 경계는 여기.

## 검수 UX 원칙

- 기본 흐름은 "일괄 승인 후 예외만 제외" — 항목당 클릭 1회 이하를 목표 (콘텐츠당 30-70개 항목을 매번 개별 승인하는 것은 비현실적).
- 파이프라인 실패는 대시보드 최상단에 노출 — 방치 방지.
