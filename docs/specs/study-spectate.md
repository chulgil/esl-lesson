# 스펙: 학습 관전 — 친구 기반 + 2중 동의

> 최종 검증: 2026-07-30 (코드 대조 완료) · P1 구현 완료

친구가 학습 중이면 관전을 요청하고, **학습자가 수락해야만** 실시간 화면을 본다.

## 동의 구조 (2중)

1. **친구 수락**: 이메일로 친구 요청 → 상대 수락 → 서로 친구 목록에 등장
2. **관전 수락**: 친구 목록에서 "학습 중" 친구에게 관전 요청 →
   학습자 화면에 수락/거절 프롬프트 → **수락한 관전자만** 스트림 수신

학습자 쪽 관전 노출 자체도 opt-in: 학습 화면 헤더의 **관전 ON/OFF 토글**
(기본 OFF). ON 이어야 친구 목록에 "학습 중"으로 표시된다.

## 친구 API

| 엔드포인트 | 동작 |
|---|---|
| POST `/api/friends/requests {email}` | 요청 (404 없음, 400 본인, 409 중복) |
| POST `/api/friends/requests/{id}/accept` · DELETE 같은 경로 | 수락 / 거절·취소 |
| GET `/api/friends` | friends(+`studying`, `watch_code`) · incoming · outgoing |
| DELETE `/api/friends/{user_id}` | 친구 삭제 |

`friendships` 테이블 (마이그레이션 e1f2a3b4c5d6, 쌍당 1행 pending→accepted).

## 관전 릴레이 (WS `st.*`, 서버는 릴레이만)

- 호스트: `st.host` → `st.hosting{code}` · 수락/거절 `st.allow{watcher_id,allow}` ·
  화면 상태 `st.event{payload}` (문항/선지/채점/진행 — 학습 페이지가 발행)
- 관전자: `st.request{code}` → `st.requested` → `st.approved`(+최근 화면 즉시 재생) /
  `st.denied` → 이후 `st.event` 스트림, 종료 시 `st.end`
- 구현: `services/game/spectate.py` `SpectateHub` (인메모리, DB 없음)
- **호스트 테마 동봉** (2026-07-30): `StEventPayload` 에 `theme?: string`
  (`frontend/src/lib/game-ws.ts`) — `stEvent` 전송 시 호스트의 `getAppTheme()` 을
  자동 첨부한다. `/study/watch` 는 이 값으로 `<html data-theme>` 만 **일시
  오버라이드**하고 언마운트 시 이전 값을 복원한다. `setAppTheme` 은 쓰지 않는다 —
  localStorage 에 저장되어 관전자의 테마 선택·엔타이틀먼트 가드(theme-mall.md)를
  오염시키기 때문.

## 화면

- 학습자: `SpectateHost` (헤더 토글 + 코드 칩 + 수락 프롬프트 오버레이)
- 친구 관리: `/friends` (단일 진입점 — 추가/수락/목록/학습 중 배지, 2026-07-14 IA 정리)
- 관전자: `/study/watch?code=` — 뷰어 전용 (친구 페이지에서 진입, 자동 요청 →
  수락 대기 → LIVE 뷰). 진입 동선: 학습 허브(/study) → 친구 카드(받은 요청 배지)

## 친구 게임 초대 (P2 경쟁 루프, 2026-07-16 푸시 폴백 추가)

- **프레즌스**: 로그인 시 `InviteToaster` 가 루트 레이아웃에서 게임 WS 를 상시 연결
  (`invite_hub` attach) — 어느 메뉴에 있든 초대 토스트 수신, 끊기면 15초 후 재접속
- **프로토콜**: 대기실에서 `iv.invite {to_user_id, game, code}` → 서버가
  **수락된 친구인지 검증** (`services/friends.py are_friends`, 임의 user_id 스팸 차단) 후
  - 접속 중: 친구의 모든 소켓에 `iv.invited {from, game, code}` 릴레이 → 토스트 [참가]
  - 미접속: **웹 푸시 폴백** (`push.send_to_user` + `invite_push_payload`,
    tag `game-invite`) — 알림 클릭 시 `/game/{game}?join={code}` 자동 입장
  - 응답 `iv.sent {ok, via: "ws"|"push"|null}`
- **게임 이름 단일 소스**: `services/game/invites.py GAME_LABELS` — `GAMES` 는 여기서 파생,
  새 게임 추가 시 한글 라벨 누락이 테스트로 잡힌다 (프론트 토스트 라벨은 별도 유지)
- **대기실 UI**: `InviteFriends` — 접속 중 친구는 초록 버튼(즉시 토스트), 미접속 친구는
  회색 "알림 초대" 버튼(푸시). 푸시 미구독 친구에게는 도달하지 않음 — 방 코드 공유로 보완

## 관전 채팅·응원 (2026-07-15)

- **보낼 수 있는 사람**: 호스트 + 수락된 관전자만 (`st.chat` {text} / `st.cheer` {kind}) — 대기자·비멤버 무시
- **응원 4종**: star/heart/party/paw — 클라이언트가 테마 브릭 색으로 렌더
- **도배 방지**: 서버 스로틀 — 채팅 1초당 1건, 응원 0.3초당 1건(연타 허용), 텍스트 100자·공백 정규화
- **집중 보호 설계**: 학습자(호스트) 화면에는 고정 채팅창·입력이 없다. 반투명 칩(bg-paper/75)이
  화면 하단에서 위로 떠오르며 4.5초 뒤 사라지고(cheer-float), pointer-events:none 으로 클릭을 막지 않는다.
  문항 카드 영역을 침범하지 않는 bottom 앵커. 채팅 참여는 관전 뷰어에서만.
- 저장 없음 — 게임 이벤트처럼 휘발성 릴레이
