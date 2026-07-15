# 웹 푸시 복습 리마인더 (P3 리텐션)

> 매일 저녁 8시(KST), 밀린 복습이 있는 사용자에게만 "복습 N개가 기다려요" 웹 푸시를 보낸다.
> 브라우저를 닫아도 도착한다 — 데일리 루프의 "복귀 트리거".

## 동작 규칙

| 규칙 | 값 | 이유 |
|---|---|---|
| 발송 시각 | 20:00 KST 이후, 10분 주기 평가 | 저녁 학습 골든타임 |
| 발송 조건 | due 카드 1개 이상 | 할 일 없는 알림은 이탈 유발 |
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
- **프론트**: `public/sw.js` (푸시 전용 서비스 워커, 캐싱 없음) + `public/manifest.json` + `src/lib/push.ts` + 설정 페이지 `PushReminderCard`

## 환경 변수 (서버 .env.api)

```
VAPID_PUBLIC_KEY=   # base64url — 브라우저 applicationServerKey 와 동일 값
VAPID_PRIVATE_KEY=  # base64url raw
VAPID_SUBJECT=mailto:rimanbackend@gmail.com
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
