# 스펙: 친구 1:1 채팅

> 최종 수정: 2026-07-27 · 설계 승인: 2026-07-27 (사용자)

수락된 친구끼리 1:1 대화. 기록은 무제한 보존, 읽음 표시·입력 중 표시·오프라인 웹푸시·학습 단어 공유 카드·카오모지 피커 포함. [study-spectate.md](study-spectate.md) 의 친구 관계와 프레즌스 인프라를 재사용한다.

## 아키텍처 결정

| 결정 | 근거 | 기각한 대안 |
|---|---|---|
| 기존 `/ws/game` 상시 연결에 chat 이벤트 추가 | `InviteToaster` 가 이미 로그인 시 전역 연결·재접속·프레즌스를 유지. 사용자당 소켓 1개 (2GB 서버) | 별도 `/ws/chat` — 소켓 2배 + 재접속 로직 중복 |
| 전송 = REST POST, 수신·읽음·입력중 = WS 푸시 | HTTP 재시도 의미론이 명확해 유실/중복 처리가 깔끔 (`client_msg_id` 멱등). WS 끊김 중에도 전송 가능. 테스트 용이 | 전송도 WS — 전달 보장을 자체 ACK 프로토콜로 재발명해야 함 |
| 인프로세스 캐시 (Redis 없음) | API 단일 인스턴스라 일관성 보장. 2GB 서버에 컨테이너 추가는 OOM 리스크 | Redis — **영구 제외 (2026-07-27 사용자 결정)**. 수평 확장이 필요해도 Postgres LISTEN/NOTIFY 로 해결 |
| 학습 카드 = 전송 시점 스냅샷(JSONB) | 원본 항목이 삭제·수정돼도 대화 기록 불변 ("기록은 남아야 한다") | item_id FK 참조 — 항목 삭제 시 기록 훼손 |

## 데이터 모델

```
conversations
  id, user_lo_id, user_hi_id   -- user_lo < user_hi 정규화, unique(lo,hi) → 쌍당 1행
  last_message_at              -- 비정규화: 대화 목록 정렬에 조인 불필요
  created_at

chat_messages
  id                           -- 커서 (BigInt PK, 시간순 단조)
  conversation_id FK
  sender_id FK
  body Text                    -- 텍스트+카오모지. 2,000자 제한 (API 검증)
  item_ref JSONB nullable      -- 학습 카드 스냅샷 {item_id, item_type, en_text, ko_text}
  client_msg_id Text           -- 멱등키. unique(conversation_id, client_msg_id)
  created_at

chat_reads
  conversation_id FK, user_id FK  -- unique(conversation_id, user_id)
  last_read_message_id            -- 읽음 표시·안읽음 카운트의 단일 근거
```

인덱스: `chat_messages(conversation_id, id DESC)` — 커서 페이지네이션 전용.

## API

| 메서드/경로 | 역할 |
|---|---|
| GET `/api/chat/conversations` | 대화 목록: 상대(닉네임·`online`)·마지막 메시지 미리보기·`unread` 카운트. `last_message_at DESC` |
| GET `/api/chat/unread-total` | 안읽음 합계 (네비 배지). 인프로세스 캐시 |
| GET `/api/chat/with/{user_id}/messages?before={id}&limit=50` | 히스토리 커서 페이지네이션 (id DESC → 클라에서 역순 렌더) |
| POST `/api/chat/messages` | 전송 `{to_user_id, body, client_msg_id, item_ref?}` → 저장·캐시 갱신·WS 푸시·오프라인이면 웹푸시. 같은 `client_msg_id` 재전송은 기존 행 반환 (멱등) |
| POST `/api/chat/with/{user_id}/read` | 읽음 갱신 → 상대에게 WS `chat.read` 푸시 |

- 상대가 **수락된 친구가 아니면 404** (존재 비노출). 친구 삭제 후에도 기존 대화 조회는 허용, **전송만 403** `not_friends` — 기록 보존 원칙.
- 대화 행은 첫 전송 시 get-or-create (정규화된 쌍으로 upsert).

## WS 이벤트 (기존 `/ws/game` 확장)

| 방향 | 이벤트 | 내용 |
|---|---|---|
| 서버→클라 | `chat.message` | 새 메시지 (본문 전체) — 수신자에게 |
| 서버→클라 | `chat.read` | `{conversation_id, user_id, last_read_message_id}` — 읽음 "1" 제거용 |
| 서버→클라 | `chat.typing` | `{from_user_id}` — 입력 중 표시 (5초 자동 소멸, 저장 안 함) |
| 서버→클라 | `presence` | `{user_id, online}` — 친구 접속 상태 실시간 갱신 |
| 클라→서버 | `chat.typing` | `{to_user_id}` — 스로틀 3초 (클라) |

- chat hub: `user_id → send 콜백` 레지스트리 (`invite_hub` 패턴). `game_ws` attach/detach 시 함께 등록·해제.
- presence 브로드캐스트: attach/detach 시 **온라인인 친구에게만** 전송 (친구 수 소규모 전제).

## 캐싱 (인프로세스 2계층)

| 캐시 | 구조 | 무효화 |
|---|---|---|
| 대화별 최근 메시지 | `conversation_id → deque(maxlen=50)` | 전송 시 append. 콜드 스타트 시 DB 로드 후 채움 |
| 사용자 안읽음 합계 | `user_id → (합계, 만료시각)` TTL 30초 | 전송·읽음 갱신 시 양쪽 사용자 무효화 |

- 최신 50개 요청(before 없음)은 캐시 히트 시 DB 를 타지 않는다. `before` 커서 요청(과거 스크롤)은 항상 DB.
- 클라이언트: 대화별 메시지 메모리 캐시(뒤로가기 즉시 복원), 낙관적 렌더(전송 즉시 표시 → 서버 확정 시 치환, 실패 시 재시도 버튼).

## 알림 기획

| 상황 | 동작 |
|---|---|
| 접속 중 + 다른 화면 | 인앱 토스트 (보낸 사람·미리보기 40자, 탭 → 대화방) + 네비 배지 갱신 |
| 접속 중 + 해당 대화방 | 알림 없음. 메시지 추가 + 읽음 자동 갱신 |
| 미접속 | 웹푸시 (기존 VAPID `send_to_user`) — "{닉네임}: {미리보기 50자}", 클릭 → `/chat/{userId}`. **같은 대화 5분 스로틀** (인프로세스 마지막 발송 시각). `deliver_ws` 는 **최소 1개 소켓 전송 성공 시에만 delivered** — 좀비 소켓만 남으면 웹푸시로 폴백 (2026-07-28 수정) |
| 접속 중 + 탭 백그라운드 **또는 창 포커스 잃음** | **OS 알림** (Notification API, 알림 켜기 수락 시) — `document.hidden \|\| !document.hasFocus()`. hidden 만 보면 "브라우저는 보이는데 다른 앱 사용 중"에 알림을 놓친다 (2026-07-28). 오피스 테마는 "공유 문서 / 변경 사항 1건" 으로 위장 |

- **알림 켜기**: 대화 목록의 `NotifyEnableButton` — 기존 VAPID 푸시 구독(`subscribePush`) 재사용. 구독하면 탭을 닫아도 웹푸시 수신

## 위장 테마 (2026-07-27, 회사 화면 보호)

힐끗 봐도 채팅이 아닌 것처럼 보이는 것이 목표. 모든 테마에서 말풍선·아바타 사진 등 채팅 시그니처를 배제한다.

| 테마 | 대화방 위장 | 목록 위장 |
|---|---|---|
| 노트·캔디·레고·헤냥이 | **교환 노트** — 필기 줄 형식, 내 글 파란 잉크/상대 검정 잉크, 화면 우측 도킹(컴팩트 max-w-md) | 교환 노트 목록 |
| 오피스(`excel`, 신규 전역 테마) | **스프레드시트** (excelkospi 컨셉) — 타이틀바(자동저장·`재고관리_날짜.xlsx`)·리본 탭·가짜 수식줄·시트 탭·상태바는 화면 전체 폭 유지. 본문은 좌(빈 시트로 위장)+우(화면 우측 도킹 채팅 리스트) 2단. 입력중 = "공동 작성자가 셀을 편집하는 중", 읽음 = 메시지 헤더의 확인/미확인 | 공유 문서 목록 (파일명 = `{닉네임}_공유.xlsx`, 목록 자체는 전체 폭 표 유지) |

- 구조: 대화방 = `useChatRoom` 훅(데이터) + 테마별 스킨(`NoteSkin`/`ExcelSkin`). 새 위장 = 스킨 1개 추가
- **보스 긴급키**: 오피스 테마에서 Esc ×2 → 빈 시트 토글 (`ExcelChrome`)
- 브라우저 탭 제목도 위장: 오피스 = `재고관리_날짜.xlsx - 통합 문서`, 그 외 = `교환 노트`
- 게임 보드는 오피스 테마 스킨이 없어 노트 보드로 폴백

## 채팅 위젯: 플로팅 ↔ 도킹 (2026-07-28 확장)

excelkospi 우하단 버튼 컨셉 — 설정의 "플로팅" 체크(localStorage `chat.floating`, 기본 켬)로 표시 방식을 고른다.

- **플로팅(기본)**: 우하단 작은 팝업(360×480). 런처 = 오피스 초록 "메모" pill / 그 외 연필 아이콘 원형, 안읽음 배지 (WS 즉시 + 60초 폴링). **Esc 한 번 또는 바깥 클릭 = 즉시 닫기**
- **도킹(체크 해제)**: 화면 우측에 상시 고정 패널(excelkospi 채팅 레일 컨셉, `.dock-right-nav-safe` — AppNav 와 겹치지 않음). 런처·닫기 없음
- 패널: 목록 뷰 ↔ 대화 뷰(useChatRoom 재사용)
- `/chat` 전체 페이지는 유지 (웹푸시 딥링크·모바일 전체화면용). `/chat`·`/admin`·`/login` 에서는 위젯 숨김
- 보고 있는 대화(`setActiveChatRoom`)에는 토스트·OS 알림을 띄우지 않는다
- **파비콘 배지**: 안읽음 > 0 이면 파비콘 우상단에 개수(99 한도)를 캔버스로 얹는다 (`lib/favicon-badge.ts`). 탭 제목은 위장 유지를 위해 불변

## 이미지 전송 (2026-07-27)

- POST `/api/chat/uploads` (multipart) — jpeg/png/webp/gif, **5MB 이하** (2GB 서버 디스크 보호). 서버가 `uuid.ext` 파일명 발급
- 전송 시 `image_id` 귀속 → `chat_messages.image_path`. 서버 발급 형식 정규식만 통과 (경로 조작 차단)
- GET `/api/chat/uploads/{name}` — **대화 참여자만** 열람 (메시지 귀속 대화 소속 검사, 아니면 404)
- 저장: 컴포즈 볼륨 `./data/chat-uploads:/data/chat-uploads` (`CHAT_UPLOAD_DIR`)
- 클라: 선택 즉시 업로드 + 로컬 미리보기, 전송은 업로드 완료 후. 목록·푸시 미리보기 "[사진]"
- **클립보드 붙여넣기**: 입력창에 이미지 붙여넣기(Ctrl/Cmd+V) → 파일 선택과 같은 업로드 파이프라인 (2026-07-28)
- **입력줄 도구 통합**: 단어카드·사진·이모티콘 3버튼 → `ChatToolsMenu` "+" 1개 (입력창 폭 확보, 누르면 입력줄 위 플로팅 메뉴, 2026-07-28). 패널 내용은 `KaomojiPanel`/`WordSharePanel` 로 분리

## 프론트엔드

- `/chat` — 대화 목록: 아바타·접속 점(초록)·마지막 메시지·상대 시각·안읽음 배지
- `/chat/[userId]` — 대화방(플로팅 위젯이 아닌 전체 화면 모드): **화면 우측에 도킹**(테마 공통, excelkospi 참고), 왼쪽은 빈 종이/빈 시트로 남겨 위장. 메시지는 **[닉네임·시각] 헤더 줄 + 그 아래 내용 줄** 구조(닉네임이 본문 끝에 붙지 않음), 읽음 전 "1"(교환노트) / 미확인(오피스) 표시, 입력 중 표시, 하단 입력창 + 카오모지 피커 + 단어 공유("+" → 내 학습 단어 검색 → 카드 첨부). 플로팅 위젯의 대화 화면도 동일하게 닉네임을 메시지 위 헤더 줄에 배치(공간 제약으로 시각은 생략)
- **채팅은 주 메뉴 탭** (2026-07-28 변경 — "내 콘텐츠" 탭이 관리자 전용 사양 전환으로 빠지며 슬롯 확보). 데스크톱 헤더·모바일 하단 탭바 공통 5탭(홈·학습·라이브러리·채팅·게임). 안읽음 개수는 우상단 알림 벨 배지(알림+채팅 합산)와 벨 드롭다운 "새 메시지 N개" 행이 담당 — 탭·채팅 아이콘 개별 배지는 두지 않는다(배지 일원화). 보조 진입점: 친구 목록 "메시지" 버튼, 우하단 플로팅 위젯
- 전역 수신: `InviteToaster` 의 기존 소켓이 chat 이벤트도 수신 → `CustomEvent` 로 배지·토스트·대화방에 전파 (두 번째 소켓 금지)
- 카오모지: `lib/kaomoji.ts` — 카테고리(기쁨·응원·슬픔·동물·인사) 40여 개 상수, 최근 사용 8개 localStorage

## 에러·엣지

- 메시지 2,000자 초과 422 · 빈 본문(공백만) 422 (item_ref 만 있으면 허용)
- WS 끊김 중 수신분: 대화방 재진입·재연결 시 REST 최신 50개 재조회로 동기화
- XSS: React 기본 이스케이프. 링크 자동화는 하지 않는다 (1차 범위 밖)
- 자기 자신에게 전송 400

## 테스트

- 대화 정규화: A→B 와 B→A 가 같은 conversation 행
- 멱등: 같은 client_msg_id 재전송 → 새 행 없음, 동일 응답
- 커서: before 페이지네이션 경계 (중복·누락 없음)
- 읽음: unread 카운트 정확성, read 갱신 후 0
- 권한: 친구 아님 404, 친구 삭제 후 전송 403·조회 200
- 캐시: 전송 직후 목록 조회에 신규 메시지 반영 (stale 금지 — 레드-그린 필수)
- 푸시: 오프라인 상대에게만 발송, 5분 스로틀
- item_ref: 스냅샷 저장·원본 삭제 후에도 조회 무결

## 범위 밖 (후속)

- 그룹 채팅 · 이미지 첨부 · 메시지 삭제/수정 · 링크 미리보기
- 수평 확장 시 인스턴스 간 팬아웃·캐시 무효화 신호는 **Postgres LISTEN/NOTIFY** 사용
  (Redis 도입 금지 — 2026-07-27 사용자 결정. 이미 운영 중인 Postgres 에 pub/sub 이
  내장되어 있고, asyncpg `add_listener` 로 바로 구독 가능. 캐시·허브 인터페이스는 그대로)
