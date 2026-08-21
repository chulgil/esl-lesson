# 웹 푸시 복습 리마인더 (P3 리텐션)

> 최종 검증: 2026-07-30 (코드 대조 완료)
> 2026-08-04 부분 갱신(코드 대조): 채팅 payload kind 표식

> 푸시 채널 공용화 (2026-07-16): `push.send_to_user(db, user_id, payload)` 가
> 유저 단위 발송 공용 함수 — 게임 친구 초대(`game-invite` 태그,
> [study-spectate.md](study-spectate.md) 친구 게임 초대)도 같은 채널·서비스 워커 계약
> (`{title, body, url, tag}`)을 사용한다.
>
> 내용 없는 알림 (2026-08-04): 채팅만 `kind: "chat"` 을 추가로 실어 워커가 발신자·본문
> 대신 테마 위장 문구를 표시한다 ([chat.md](chat.md) 내용 없는 채팅 알림). `kind` 없는
> payload(리마인더·게임 초대)는 문구를 그대로 표시 — 기본 동작은 바뀌지 않는다.

> 매일 저녁 8시(KST), 오늘 목표를 못 채운 사용자에게만 "오늘 목표까지 M개 — 지금 하면 금방이에요" 웹 푸시를 보낸다. M=min(due, 목표 잔여) — 밀린 전체 수는 위협적이라 싣지 않는다 (포기 방지 기획 2026-07-15).
> 브라우저를 닫아도 도착한다 — 데일리 루프의 "복귀 트리거".

## 동작 규칙

| 규칙 | 값 | 이유 |
|---|---|---|
| 발송 시각 | **사용자별 `user_settings.reminder_hour`(KST, 5-23시, 기본 20) 이후**, 10분 주기 평가. 새벽(5시 미만) 전역 금지 | 실행 의도 — 사용자의 생활 리듬에 맞춘 시각 (2026-08-04, user-journey-motivation P1). 설정: `PATCH /api/settings` + 알림 카드 시각 선택 |
| 발송 조건 | due 1개 이상 **그리고 오늘 목표 미달성** — due 는 큐와 같은 출제 범위(레벨 타입 + 길이 게이트, 2026-08-18 정합)로 센다 | 할 일 없는 알림은 이탈 유발(잠긴 카드만 있으면 세션이 빈다), 달성자에겐 달성감 보존 |
| 빈도 | 기기(구독)당 하루 1회 | `push_subscriptions.last_sent_on` (KST 날짜) dedup |
| due=0 처리 | dedup 마킹 안 함 | 저녁 늦게 due 가 생기면 같은 날에도 발송 |
| 만료 구독(404/410) | 행 즉시 삭제 | 죽은 endpoint 재시도 낭비 방지 |
| 일시 오류 | 구독 유지 | 다음 루프에서 재시도 |

## 구성 요소

- **모델**: `push_subscriptions` (user_id, endpoint UNIQUE, p256dh, auth, last_sent_on) — 마이그레이션 `f2a3b4c5d6e7`
- **서비스**: `app/services/push.py` — `send_review_reminders()` (발송 판단 + pywebpush 발송)
- **워커**: `app/workers/reminders.py` — 10분 주기 루프 (`ENABLE_WORKERS` + VAPID 키 존재 시)
- **API**: `app/api/push.py`
  - `GET /api/push/config` — `{enabled, public_key}` (공개키는 비밀 아님, 비로그인 허용)
  - `POST /api/push/subscriptions` — 구독 저장 (endpoint 기준 upsert, https 만)
  - `DELETE /api/push/subscriptions` — 내 구독 해지
  - `POST /api/push/test` — 내 전체 기기로 즉시 테스트 발송
- **프론트**: `public/sw.js` (푸시 전용 서비스 워커, 캐싱 없음) + `public/manifest.json` + `src/lib/push.ts` + 설정 페이지 `NotificationCard` (2026-07-31 통합 — 구독은 기기당 1개라 "복습 리마인더"/"새 글 알림" 이중 토글은 같은 스위치의 다른 이름이었음. 기기 단위 마스터 스위치 + 받는 알림 종류(채팅 새 글·게임 초대·복습 리마인더·주간 성적표 — weekly-report.md, 2026-08-07 추가) 목록 안내로 일원화. 채팅창 카드는 표시 방식만)

## 환경 변수 (서버 .env.api)

```
VAPID_PUBLIC_KEY=   # base64url — 브라우저 applicationServerKey 와 동일 값
VAPID_PRIVATE_KEY=  # base64url raw
VAPID_SUBJECT=mailto:lessonaza@gmail.com
```

키 생성 (1회):

```bash
uv run --with py-vapid python - <<'EOF'
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02, b64urlencode
v = Vapid02(); v.generate_keys()
pub = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
priv = v.private_key.private_numbers().private_value.to_bytes(32, "big")
print("VAPID_PUBLIC_KEY=" + b64urlencode(pub))
print("VAPID_PRIVATE_KEY=" + b64urlencode(priv))
EOF
```

키 미설정 시: config `enabled=false`, 설정 페이지 알림 섹션 자체가 숨음, 워커 루프 미기동 — 전체 기능이 조용히 꺼진다.

## 플랫폼 지원

- 데스크톱 Chrome/Edge/Firefox, Android Chrome: 즉시 동작
- iOS Safari 16.4+: "홈 화면에 추가" 후 PWA 에서만 가능 (설정 페이지에 안내 문구)
- 미지원 브라우저: 안내 문구 표시, 토글 숨김
