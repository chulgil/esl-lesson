---
origin_model: claude-fable-5
review_by: 2026-10-26
---

# Learning Loop — 같은 실수를 두 번 하지 않는다

> 출처: continuous-learning-v2(instinct 모델) + claude-reflect + CoEvoSkills(arXiv 2604.01687) 수렴 흡수 (2026-07-08).
> 목적: 사용자의 거절/교정이 세션과 함께 증발하지 않고, confidence 를 누적해 규칙/스킬로 승격되는 파이프라인을 강제한다.

## 파이프라인 (전 구간 LLM 비용 0, 휴먼게이트)

```
signal-capture 훅 (UserPromptSubmit, 자동)
  -> .harness/signals/observations.jsonl   # 거절/교정/승인 신호 적재 (레닥션 + 200자 캡)
cg instinct harvest                        # 신호 -> instinct 생성(0.3) / 강화(+0.1, 상한 0.9)
  -> .harness/instincts/instinct-*.md      # confidence + evidence 부착 학습단위
cg absorb propose --from instincts         # decay 반영 confidence >= 0.7 만 승격 후보
cg absorb promote <name>                   # 사람이 승인해야 rule/skill/hook 이 된다
```

- **decay**: 관찰이 끊기면 주당 0.02 씩 감쇠. `cg instinct prune` 이 effective < 0.2 + 30일 미관찰을 pruned/ 로 이동 — 규칙 엔트로피 방지.
- **재제안 방지**: promote 로 `.harness/steer/processed/` 에 간 후보는 다시 제안되지 않는다.

## Cue-Anchored 모델 — 저장이 아니라 배달 (arXiv 2607.20972)

메모리는 "조회하면 나오는 문서"가 아니라 **트리거 조건(cue)을 일급으로 갖고, 상황이 맞을 때 하네스가 밀어넣는** 속성이어야 한다. 선택적 리마인더 주입이 상시 주입·수동 노출보다 우수하다 (arXiv 2607.08716, +8.3pp).

- **cue 필드**: instinct frontmatter `cues:` (콤마 구분). 파일 글로브(`*.dart`, `frontend/**`) 또는 키워드(`commit`, `ui`). 비어 있으면 전역 instinct.
- **푸시 원칙**: 하네스가 상황에 맞을 때만 주입한다 — 상시 주입 금지.
  - 세션 시작: session-start 훅이 **cues 없는 전역 instinct** 중 confidence >= 0.7 상위 1~3건만 리마인드.
  - 작업 중: `cg instinct list --cue "<파일 경로·작업 설명>"` 으로 해당 컨텍스트에 cue 매칭되는 instinct(effective >= 0.5)만 회상.
- **cue 부여는 사람이**: `cg absorb promote` 검토 시점에 사람이 frontmatter 편집으로 부여한다. harvest 의 자동 cue 추출은 스코프 아님 (Phase 2 후보).

## 왜 즉석 승격을 금지하는가 (CoEvoSkills 정량 근거)

| 방식 | 성과 |
|---|---|
| 세션 내 즉석 스킬 생성 | 34.1% (무스킬 30.6% 과 사실상 동일 — 거의 무효) |
| **검증된 세션 간 학습** | **71.1%** |

한 세션의 교정 한 번은 우연일 수 있다. 같은 교정이 **세션을 넘어 반복**되어 confidence 임계에 도달했을 때만 하네스에 넣는다.

## Claude 행동 지침

| 상황 | 행동 |
|---|---|
| 사용자가 같은 교정을 반복한다고 느낄 때 | 즉석에서 규칙 파일을 만들지 말고 `cg instinct list` 로 누적 확인 후 임계 도달 시 `cg absorb propose --from instincts` 제안 |
| 세션 시작 시 (선택) | `cg instinct list` 로 고 confidence instinct 를 참고 — 반복 실수 사전 회피 |
| instinct 텍스트가 프로젝트 특수성이 없을 때 | 스캐폴드 역전파 후보로 표시 (cg-harness 리포로 harvest — Phase 2 예정) |

## 금지

- 훅/파이프라인 우회한 **세션 내 즉석 rule/skill 추가** (일시적 선호를 영구 규칙으로 오염)
- observations.jsonl 수동 편집 (원장 신뢰 훼손 — 잘못된 신호는 instinct prune 으로 처리)
- confidence 임계(0.7) 미달 instinct 의 승격 강행 (근거 부족)

## 상위 규칙과의 관계

- [verification.md](verification.md): 승격 전 "이 instinct 가 실제 반복인가" 증거 = evidence_count.
- [skill-authoring.md](skill-authoring.md): skill 로 승격 시 압박테스트(RED-GREEN) 적용.
- `cg-trace-analyzer` 스킬: journal/status 로그 분석 — 이 룰의 신호 파이프라인과 상호보완 (신호=사용자 반응, trace=에이전트 실패모드).
