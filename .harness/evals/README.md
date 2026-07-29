# .harness/evals/ — Per-feature 회귀 eval 슬롯

기능이 늘 때마다 그 기능의 **수용 기준이 재실행 가능한 회귀 eval** 로 남는 곳입니다.
스펙 문서는 잊히지만 eval 은 매번 다시 돌아간다 — 새 기능이 옛 기능의 수용 기준을
깨면 여기서 잡힙니다. (eval-harness EDD + superpowers drill 무가이드 대조군 +
Anthropic 하네스 연구에서 흡수.)

## 흐름

```
Phase 2 (cg-spec-and-harness)
  spec §2 성공 기준 중 기계 검증 가능한 항목
    -> .harness/evals/<feature>.toml    # 기능별 eval 정의 (_template.toml 복사)
python3 .harness/evals/run.py           # 전체 회귀 재실행 (stdlib only)
  또는 cg diagnose --gate eval          # .cg/mechanical.toml 의 opt-in eval 게이트
    -> Phase 6 (cg-evaluation) Stage 1  # 결과가 rubric(견고성) 입력이 된다
```

## 파일 규약

| 파일 | 역할 |
|------|------|
| `<feature>.toml` | 기능 1개의 수용 기준 eval (`_template.toml` 포맷) |
| `_template.toml` | 포맷 정본 — `_` 로 시작하는 파일은 러너가 건너뜀 |
| `run.py` | stdlib 러너 — 케이스별 PASS/FAIL 출력, 하나라도 FAIL 이면 exit 1 |

## 케이스 포맷 (요약)

- `[eval]` — `name` / `description` (+ 선택 `spec` 경로)
- `[[case]]` — `cmd`(셸 명령, 프로젝트 루트에서 실행) / `expect_exit`(기본 0) /
  `expect_contains`(선택, stdout 부분일치) / `timeout`(선택, 초)

## 운영 규칙

- eval 은 **검증자산**: FAIL 을 통과시키려고 케이스를 삭제·완화하지 않는다
  (frontend-verify 의 골든 갱신 규칙과 동일 — 수용 기준 변경은 spec 변경과 함께만).
- 게이트 편입은 opt-in: `.cg/mechanical.toml` 의
  `#eval = "python3 .harness/evals/run.py"` 주석 해제 후 `cg diagnose --gate eval`.
- eval 파일이 하나도 없으면 러너는 PASS (빈 슬롯은 실패가 아니다).
