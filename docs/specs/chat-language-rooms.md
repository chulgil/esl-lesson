# 스펙: 언어 학습 대화방 (Language Rooms)

> 작성: 2026-08-14 (기획 보완 + 설계). 목표: 채팅방을 **언어쌍 단위 학습 공간**으로
> 확장 — 내가 주언어로 쓰면 방의 학습언어로 자동 번역되어 **번역문이 본문**으로
> 보이고, 원문은 힌트로 확인한다. 랜덤 매칭 또는 친구 초대로 방을 만들며,
> 같은 두 사람이 언어쌍별로 복수의 방을 중복 없이 가진다.
> 연관: [chat.md](chat.md) · [chat-translation.md](chat-translation.md) · [my-phrases.md](my-phrases.md)

## 기획 보완 (누락 갭 → 결정)

| # | 발견한 누락 | 결정 |
|---|---|---|
| 1 | 방 정체성·중복 기준 미정의 | `conversations` 에 언어쌍(source→target) 컬럼 추가, unique(쌍, source, target). "한→영"과 "영→한"은 별개 방 |
| 2 | 기존 API 가 상대 기준(`/chat/with/{id}`) — 한 상대와 방 여러 개 불가 | 방(room) 기준 API 신설. 레거시 경로는 그 상대와의 **가장 오래된 활성 방**으로 위임 (웹푸시 구 딥링크 호환) |
| 3 | 랜덤 매칭 인프라 부재 (게임도 초대제뿐) | 인프로세스 대기열(언어쌍 키) + WS `chat.matched`. 단일 인스턴스 전제 — 채팅 캐시와 동일 원칙 |
| 4 | 낯선 매칭 상대 안전장치 없음 | v1: 방 나가기(종료) + 종료 후 24h 같은 상대 재매칭 회피. 신고·차단은 후속 |
| 5 | 번역 실패·예산 초과 시 표시 | 원문 그대로 표시(힌트 버튼 없음). 비용 방어 4계층(chat-translation.md) 그대로 |
| 6 | 학습언어로 직접 쓴 메시지 | 감지 언어 == target 이면 번역 없이 그대로 본문 (성장 루프의 목표 상태) |
| 7 | 개인 번역 토글(translate_mine 등)과 방 규칙 충돌 | 학습 방에서는 **방 규칙 우선**(본문=번역문). 방 헤더에서 사용자별 "원문 모드" 토글(localStorage) 허용 |
| 8 | 기존 방 처리 | 마이그레이션으로 전 대화 **ko→en 백필** (요구사항: 설정 단계를 안 거친 방의 디폴트) |
| 9 | 중복 생성 시도 UX | 에러가 아니라 **기존 방 열기** (get-or-create + "이미 있는 방" 토스트) |
| 10 | 내가 쓰는 말의 언어 귀속 기준 | 발화한 **방의 target_lang** 기준 (설정값 아님) — 언어별 덱으로 분리. [my-phrases.md](my-phrases.md) |
| 11 | 덱 100개 유지·장기기억 순환 미정의 | 활성(비장기기억) 100개 목표, 빈도순 승격·보충. [my-phrases.md](my-phrases.md) |
| 12 | 레벨별 학습카드 답변 방식 (2026-08-14 사용자 추가) | chat 덱 문장: 초급·중급=단어 칩 조립(클릭), 고급(4)만 전체 타이핑. 모든 레벨에서 출제 |
| 13 | 게임 풀 언어 미분리 (현재 언어 섞임) | 풀 쿼리에 콘텐츠 lang 필터 + 게임 언어 선택. 아래 §게임 언어 분리 |
| 14 | 알림 딥링크 | `/chat/room/{id}` 로 변경. 내용 없는 알림 정책(chat.md) 불변 |
| 15 | 위장 테마와 언어쌍 표기 충돌 | 배지는 ASCII 텍스트("한→영")·소형 태그 — 말풍선·국기 이모지 금지 유지 |

## 데이터 모델 (conversations 확장 — 신규 테이블 없음)

```
conversations (기존 컬럼 유지 + 추가)
  source_lang String(5)  default 'ko'   -- 원문(주로 쓰는) 언어
  target_lang String(5)  default 'en'   -- 학습(표시) 언어
  origin      String(8)  default 'friend'  -- 'friend' | 'match'
  status      String(8)  default 'active'  -- 'active' | 'closed'
  mode        String(8)  default 'learn'   -- 'learn'(번역 표시) | 'plain'(일반 대화)
  closed_by   BigInt FK users nullable / closed_at nullable
  unique(user_lo_id, user_hi_id, source_lang, target_lang, mode)
  check(source_lang != target_lang)
```

- 마이그레이션: 컬럼 추가(server_default) → 기존 유니크 제약 삭제 → 새 유니크 생성.
  기존 행은 ko→en·friend·active 로 백필.

## 일반 대화 방 (mode='plain', 2026-08-14 사용자 지시)

방 생성 시 종류를 고른다 — **[언어 학습](기본) | [일반 대화]**.

| 항목 | learn | plain |
|---|---|---|
| 본문 표시 | target 번역문 + [원문] 힌트 | 친 그대로 (번역 없음) |
| 배지 | "한→영" 등 언어쌍 | "일반" |
| 언어쌍 | 마법사에서 선택 | 미사용 — ko→en 정규화 저장 (쌍당 일반 방 1개) |
| 내가 쓰는 말 수집 | 대상 | **제외** (학습 문맥 아님) |
| 랜덤 매칭 | 같은 언어쌍끼리 | 일반 대기자끼리 (언어 무관 단일 버킷) |
| 입력 placeholder | "한국어로 쓰면 영어로 보여요" | 일반 문구 |

그 외(전송·읽음·나가기·알림·위장·접근 규칙)는 learn 과 동일.
- 메시지·읽음·공지·공유목표·업로드는 conversation_id FK 그대로 — 변경 없음.
- `chat_messages.body` 는 **항상 원문**(친 그대로). 번역은 전역 캐시
  (chat_translations) 를 읽기 시점에 붙인다 — 저장 이중화 없음.

## 접근 규칙 (친구 게이트 분리)

| origin | 생성 | 전송 허용 | 조회 |
|---|---|---|---|
| friend | 수락된 친구만 (기존 게이트) | 친구 유지 + status active | 멤버면 항상 (기록 보존) |
| match | 매칭 성사 시 자동 | status active | 멤버면 항상 |

- 나가기: 멤버 누구나 → `status='closed'` (양쪽 종료). 전송 403 `room_closed`,
  조회는 허용. 목록에서 흐리게 + "종료" 배지.
- 친구 삭제 시 friend 방 전송 403 `not_friends` (기존 동작 유지).

## 번역 규칙 (방 기준 — 표시 반전)

```
표시 본문 = target_lang 번역문 (있으면)
원문 힌트 = 내가/상대가 실제 친 텍스트 — [원문] 탭으로 본문 아래 토글
```

- 방향: `detect_lang(body) == target_lang` → 번역 없음(본문=원문).
  그 외 전부 → target_lang 으로 번역 (제3언어 포함).
- `translate_chat`(설정 기준)와 별개로 `translate_to(db, user_id, text, target)`
  를 추출해 방 기준 호출 — 캐시·예산·엔진 체인·이모티콘 제외는 공통.
- 전송 응답에 번역 동봉(낙관 렌더 치환용). WS 수신은 기존 단건 번역
  엔드포인트를 방 target 기준으로 재사용.
- TTS 스피커 = 본문(학습언어) — 기존 TranslationLine 의 스피커 이관.
- 개인 설정 `chat_translate` 는 전역 킬스위치로 유지하지 않는다 — 학습 방
  번역은 방의 존재 이유이므로 **항상 시도** (예산 캡이 최종 방어).
  `translate_mine/theirs` 는 학습 방 표시에 관여하지 않음 (설정 카드에서 제거).

## API

| 메서드/경로 | 역할 |
|---|---|
| GET `/api/chat/rooms` | 내 방 목록: 상대(닉네임·online)·언어쌍·origin·status·마지막 미리보기(**번역문 우선**)·unread. `last_message_at DESC` |
| POST `/api/chat/rooms` | 친구 초대 생성 `{peer_id, source_lang, target_lang}` → get-or-create. 신규면 상대에게 WS `chat.room_created` + 알림. `created: bool` 동봉 |
| GET `/api/chat/rooms/{id}` | 방 메타 (헤더·딥링크 진입용) |
| GET `/api/chat/rooms/{id}/messages?before&limit` | 기존 with/{user}/messages 와 동형 + 각 메시지 `translation:{lang,text}|null` (target=방 언어) |
| POST `/api/chat/rooms/{id}/read` | 읽음 (기존 with read 와 동형) |
| POST `/api/chat/rooms/{id}/leave` | 나가기 → closed. 멱등 204 |
| POST `/api/chat/messages` | `{room_id, body, ...}` 로 확장 — `to_user_id` 는 레거시(가장 오래된 활성 방으로 위임, 없으면 ko→en 생성). 응답에 `translation` 동봉 |
| POST `/api/chat/match` | 대기열 참가 `{source_lang, target_lang}` → 즉시 성사 시 `{room}`, 아니면 `{waiting: true}`. 재호출 = 대기열 갱신 |
| DELETE `/api/chat/match` | 대기 취소 |
| GET `/api/chat/match` | 대기 상태 폴링 (WS 유실 폴백) |

- 검증: source/target ∈ SUPPORTED_LANGS, source != target, peer != 나.
- 레거시 GET `/api/chat/with/{user_id}/messages`·read 는 유지(위임) — 프론트
  전환 후 제거 후보.

## 랜덤 매칭 (인프로세스)

- 대기열: `{(source,target): [(user_id, joined_at)]}` — 같은 쌍끼리 선착순 매칭.
- 성사: 방 get-or-create(재회 허용) → 양쪽 WS `chat.matched {room}` → 클라 이동.
- 제외: 자기 자신 / 24h 내 같은 쌍으로 종료(closed)한 상대.
- 사용자당 대기 1건 (새 참가가 이전 대기 대체). 서버 재시작 시 대기열 소실 허용
  (클라 폴링이 waiting 해제 감지 → 재시도 UI).

## WS 이벤트 (기존 /ws/game 확장)

| 이벤트 | 내용 |
|---|---|
| `chat.matched` | `{room}` — 매칭 성사, 양쪽에 |
| `chat.room_created` | `{room}` — 친구 초대로 방 생성, 상대에게 |
| `chat.room_closed` | `{room_id}` — 나가기, 상대에게 |
| 기존 chat.* | conversation_id 그대로 사용 — 변경 없음 |

## UX (생성 → 진입 2탭 이내)

- **목록(/chat)**: 상단 [+ 새 노트](테마 라벨) 버튼. 방 행 = 상대 닉네임 +
  언어쌍 배지("한→영" 텍스트 태그) + 번역문 미리보기 + unread. 종료 방은 흐리게.
- **생성 마법사** (바텀시트/모달 1장):
  1) 상대: [친구에서 선택] | [랜덤 매칭]
  2) 언어: "내가 쓰는 언어 → 배우는 언어" 프리필(설정 primary→learning[0]),
     칩으로 변경·스왑. 동일 쌍 기존 방 있으면 버튼이 "방 열기"로 바뀜
  3) [만들기] → 방 진입 (랜덤은 대기 화면: 스피너+취소, 성사 시 자동 이동)
- **대화방(/chat/room/[id])**: 헤더 = 상대 + 쌍 배지 + (match) 나가기.
  본문 = 번역문, 그 아래 [원문] 소형 토글(탭 시 회색 원문 줄 — TranslationLine
  반전 재사용). 입력 placeholder "한국어로 쓰면 영어로 보여요"(테마 중립).
  내 메시지도 동일(전송 즉시 원문 표시 → 응답 번역으로 치환).
- **레거시 /chat/[userId]**: 그 상대와의 방 목록 조회 → 1개면 즉시 리다이렉트,
  복수면 방 선택 시트.
- 플로팅 위젯·도킹: 목록/대화 뷰가 room 단위로 동작 (useChatRoom 이 room_id 기준).
- 위장 계약(chat.md) 불변: 말풍선·아바타 금지, 알림은 내용 없음.

## 게임 언어 분리

- `visibility.lang_item_clause(lang)`: 항목이 lang 콘텐츠에 속하는지 EXISTS 필터.
  문장 게임 3종(타자·받아쓰기·어순)·단어 게임(퀴즈로얄·빙고·테트리스) 풀 쿼리에 적용.
- 게임 언어 선택: 게임 허브 상단 언어 칩 (기본 = learning_langs[0],
  localStorage `game.lang`). 솔로 게임은 시작 파라미터, 멀티 방은 생성 시
  `lang` 저장(방장 선택) — 참가자 풀도 그 언어로.
- 풀 부족(`sentences_insufficient` 등) 시 "이 언어의 콘텐츠가 아직 부족해요 —
  채팅으로 모아보세요" 안내.

## 비기능·엣지

- 예산: 방 번역도 translate 예산 원장 공유 (하드캡 시 원문 표시로 자연 강등).
- 시스템 줄(kind != NULL)·이모티콘 전용은 번역·힌트 제외 (기존 규칙).
- 방 100+ 목록: 페이지네이션 불필요 (친구 소규모 전제 유지).
- 매칭 대기 TTL 10분 — 초과 시 서버가 대기 해제(클라 안내 후 재시도 버튼).

## 테스트 (필수 케이스)

- 쌍+언어쌍 유니크: 같은 쌍 ko→en 재생성 = 기존 방 반환(created=false)
- ko→en 과 en→ko 는 별개 방 · 마이그레이션 백필 ko→en
- 방 메시지 응답의 translation target = 방 target (뷰어 설정 무관)
- target 언어로 친 메시지는 translation null
- 매칭: 같은 쌍 2명 → 같은 방, 다른 쌍은 미성사 / 취소 / 24h 재매칭 회피
- 나가기: closed 후 전송 403, 조회 200, 재나가기 멱등
- match 방은 친구 아님에도 전송 가능, friend 방은 친구 삭제 시 403
- 레거시 to_user_id 전송 → 가장 오래된 활성 방 위임

## 범위 밖 (후속)

- 신고·차단, 역방향 쌍 매칭(탠덤: ko→en ↔ en→ko), 그룹 학습 방,
  주언어가 서로 다른 유저 간 힌트 이중 번역, `translate_mine/theirs` 설정 정리
