# System Invariants — 멀티에이전트 자산 자가 점검 정본

> `cg orchestrate validate` 가 참조하는 불변식 정본. 자산을 수정한 뒤 전면
> 재감사 대신 이 점검만 돌려 모순 재발을 잡는다. 통과해야 커밋.
> 이 자산들은 `cg new`/`cg upgrade` 가 생성하므로 **정상 PASS 가 기준선**이다 —
> 이후 사용자 편집이 일관성을 깨면 FLAG.

## 점검 대상 불변식 (Python validator 가 강제)

| ID | 불변식 | 깨지면 |
|----|--------|--------|
| INV1 | `write_scope` 값 집합(`none`/`tasks-only`)이 `.cg/backends.json`·`routing.md`·`templates/worker-brief.md` 에서 일치 | 어디든 한 곳만 다르면 시스템 자체 모순 |
| INV3 | log 태그 = 정확히 `DECISION` `WORKER_CALL` `VERIFICATION` `ERROR` `APPROVAL` `COMPLETE` 6종 | 파서·일관성 깨짐 |
| INV9 | gemini 백엔드가 `.cg/backends.json` 에서 `agy` CLI(`cli.command == "agy"`)이고 기본 모델 `gemini-3.1-pro-high`(`pro-high`) | 정본이 폐기 프록시/known-bad 경로 호출 |
| INV11 | `routing.md` 에 4토폴로지(`Pipeline`/`Fan-out/Fan-in`/`Expert Pool`/`Producer-Reviewer`) 모두 존재 + `Supervisor`·`Hierarchical` 은 "배제" 줄에만 등장 | 패턴 규정 유실 또는 배제 패턴 부활 |
| INV12 | `orchestrator-rules.md` 에 "운영 원칙" 섹션 + `templates/worker-brief.md` 에 "Worker 행동 규약" 고정 블록 존재 + **블록 안에 사용자 질문 지시(질문/ask) 없음** | 워커 one-shot 구조와 모순 (워커 규약 유실) |

## log 태그 정의 (INV3)

오케스트레이터 로그에 쓰는 태그는 정확히 6종:
`DECISION` | `WORKER_CALL` | `VERIFICATION` | `ERROR` | `APPROVAL` | `COMPLETE`.

- `DECISION` — 분기·충돌 해소 등 의사결정
- `WORKER_CALL` — 워커 호출 시작
- `VERIFICATION` — 결과 검증
- `ERROR` — 실패·타임아웃·상충
- `APPROVAL` — 워커 승인
- `COMPLETE` — 작업 완료

## 점검 실행

```bash
cg orchestrate validate           # 위반 리스트 출력 (정상이면 위반 0건)
cg orchestrate validate --json    # CI/스크립트용
cg orchestrate validate --strict  # 위반 시 종료코드 3 (CI 게이트)
```

## 유지보수자/외부 매뉴얼 전용 (이 점검에서 제외)

netwaif 원본의 INV2·INV4·INV5·INV6·INV7·INV8·INV10 중 외부 매뉴얼/manual-repo
비교 항목과 한도 수치 동기화는 **공개 설치본에 매뉴얼이 없으므로 제외**한다.
INV8(인터랙티브 전용·worktree 금지)은 `orchestrator-rules.md` §1 에 규칙으로 존재한다.
