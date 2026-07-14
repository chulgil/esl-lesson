# 스펙: 학습 관전 — 친구 기반 + 2중 동의

> 최종 수정: 2026-07-14 · P1 구현 완료

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

## 화면

- 학습자: `SpectateHost` (헤더 토글 + 코드 칩 + 수락 프롬프트 오버레이)
- 관전자: `/study/watch` — 친구 목록(학습 중 배지·관전 요청·친구 추가/수락) +
  LIVE 뷰(문항·선지·정답 하이라이트·진행/점수). 홈 대시보드 "친구 학습 관전 →"
