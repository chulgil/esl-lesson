# Steer Inbox

장기 자율 실행 중 에이전트에게 방향을 전달합니다. 한 번 처리된 항목은 `.harness/steer/processed/` 로 이동됩니다.

## 포맷

```
## {YYYY-MM-DD HH:MM} — {class}

{메시지 본문}
```

## Classes

| Class | 의미 | 예 |
|-------|------|----|
| `context` | 정보 제공 (계속 진행) | "참고로 API 응답 스키마가 변경될 수 있음" |
| `directive` | 우선순위 변경 | "프론트엔드는 나중, API 먼저" |
| `emergency` | 즉시 중단 | "production 에서 데이터 누수 발견 — 중단" |

---

(inbox 비어있음)
