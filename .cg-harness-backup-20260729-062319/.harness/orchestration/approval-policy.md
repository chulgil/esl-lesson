# Worker Approval Policy — 워커 호출 승인 게이트

## 원칙

**모든 워커 호출은 작업별로 명시적 승인 필요** (claude-main 포함 전체 pool 적용).
승인된 워커 목록(`workers_approved`)에 없으면 호출 금지.

**예외**: 오케스트레이터의 **내부 추론**은 워커 호출이 아니므로 승인 불필요. 다만 별도
claude-main 워커를 호출해 산출물을 `result.md` 로 받는 것은 승인 대상.

## 승인 절차

1. 오케스트레이터가 워커 필요성 판단 (`routing.md` 참조)
2. 사용자에게 다음과 함께 승인 요청: **어떤 워커를 / 무슨 목적으로 / 예상 호출 횟수**(쿼터 영향)
3. 승인 시 `workers_approved` 에 추가
4. `[APPROVAL]` 로그 기록
5. 이후 해당 작업 내에서 동일 워커 재승인 불필요

## 외부 쓰기 4조건 (워커가 작업 폴더 밖 repo 에 쓰려면 모두 충족)

1. brief 에 `target_repo` 절대 경로 + `write_scope` 패턴이 명시됨
2. 사용자가 그 `target_repo`/`write_scope` 를 명시적으로 승인함 (`workers_approved` 기록)
3. 대상 repo 가 git 워킹트리이고, 작업 시작 전 working tree 가 clean (동시성 안전망)
4. 워커가 `_shared/`·`templates/`·다른 작업 폴더는 건드리지 않음

`target_repo`/`write_scope` 가 바뀌면 **기존 승인은 무효** — 새 승인 없이는 외부 쓰기 금지
(artifacts diff 로 제한).

## 비용·쿼터 가이드 (참고)

| Worker | 예상 비용 | 쿼터 |
|--------|---------|------|
| claude-main | 중간 | Claude 구독/API |
| codex-main | 중간 | Codex 호출 |
| codex-critic | 낮음-중간 | Codex 호출 |
| gemini pro | 중간-높음 | Gemini(agy) |

claude-main 이 "내부 추론"과 같은 모델이라도 별도 호출이므로 쿼터·비용 발생.

## 승인 기록 형식

```yaml
workers_approved:
  - worker: claude-main
    approved_at: <YYYY-MM-DD>      # date +%Y-%m-%d
    purpose: 메인 코드 구현 및 디버깅
    approved_by: user
```
