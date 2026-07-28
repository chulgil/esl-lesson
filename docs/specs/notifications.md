# 스펙: 알림 센터

> 최종 수정: 2026-07-28

Jira/Confluence 스타일 개인 알림함. 친구 요청·수락·게임 초대를 행으로 적재하고 네비 벨에서 확인한다. 토스트(휘발)와 달리 놓친 알림을 나중에 볼 수 있다. [chat.md](chat.md) 의 WS 인프라(`/ws/game` 단일 소켓 + `deliver_ws`)를 재사용한다.

## 기획

| 항목 | 결정 |
|---|---|
| 소스 | `friend_request` · `friend_accepted` · `game_invite` 3종 — 각 API 가 커밋 전에 `notify()` 호출 |
| 읽음 모델 | 행별 `read_at` (null = 안읽음) — 개별 클릭 읽음 + "모두 읽음". 배지 = 안읽음 총수 |
| 실시간 | 기존 소켓으로 `notif.new` 푸시 → 벨 즉시 재조회 (60초 폴링은 유실 대비 보조) |
| 클릭 이동 | friend_request/friend_accepted → `/friends`, game_invite → `/game/{game}?join={code}` |
| payload | 발생 시점 스냅샷(닉네임 등) — 원본이 바뀌어도 알림 문구 불변 (`chat_messages.item_ref` 패턴) |
| 채팅 | 벨 배지에 합산하지 않는다 (채팅 배지는 `ChatNavButton` 담당 — 이중 계산 금지). 드롭다운 첫 행 "새 메시지 N개" 요약만 |

## 데이터 모델

```
notifications
  id BigInt PK              -- id DESC = 최신순
  user_id FK (CASCADE)      -- 탈퇴 시 즉시 파기 (delete_me 명시 삭제 목록 포함)
  type String(32)           -- friend_request | friend_accepted | game_invite
  payload JSONB             -- 스냅샷 {from_name, ...}
  read_at nullable
  created_at
```

인덱스: `notifications(user_id, id)` — 내 알림 최신순 조회 전용.

## API

| 메서드/경로 | 역할 |
|---|---|
| GET `/api/notifications?limit=30` | 내 알림 id DESC (limit 1~100) + `unread` 안읽음 총수 |
| POST `/api/notifications/read` | `{all?: bool, ids?: int[]}` — 내 알림만 `read_at=now`. 타인 id 는 조용히 무시 |

## WS 이벤트 (기존 `/ws/game` 확장)

| 방향 | 이벤트 | 내용 |
|---|---|---|
| 서버→클라 | `notif.new` | `{type, ...payload}` — 적재 직후 수신자에게. 벨은 수신 시 목록 재조회 |

- 적재: `services/notifications.notify(db, user_id, type, payload)` — add + flush 후 WS 전달, **커밋은 호출자 책임**. 오프라인이어도 행은 남는다.

## 프론트엔드

- `NotificationBell` — AppNav 데스크톱 헤더, `ChatNavButton` 왼쪽. 빨간 배지(99+ 규칙)
- 드롭다운(w-80, 바깥 클릭 닫기): 헤더("알림" + "모두 읽음") → 채팅 요약 행 → 알림 행(안읽음 파란 점 · `timeAgo` · 클릭 시 읽음+이동) → 비면 "새 알림이 없어요"
- 갱신: 마운트 + 60초 폴링 + `notif.new`/`chat.message`/`chat.read` 이벤트

- 모바일: 상단 미니바(AppNav `mobile-topbar` — 로고·벨·채팅·설정, 2026-07-28 UX 개편)에 표시. 하단 탭바는 이동 5탭 전용
- **배지 일원화** (2026-07-28): 벨 배지 = 알림 unread + 채팅 unread 합산. 채팅 메뉴(ChatNavButton)의 숫자 배지는 제거 — 헤더에 숫자 배지 두 개면 시선 분산·중복 계산 혼란

## 범위 밖 (후속)

- 업적 달성 적재
- 채팅을 요약 행이 아닌 개별 알림 항목으로 적재
