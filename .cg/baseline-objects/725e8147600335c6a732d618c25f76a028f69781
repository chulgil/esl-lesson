---
name: cg-companion-understand
description: |
  Understand-Anything 컴패니언 브리지 — tree-sitter 기반 코드 지식그래프 + 의존성
  시각화. 대규모 코드 이해/온보딩이 필요할 때 사용. 옵트인 외부 도구(번들 아님).
  트리거: 코드 지식그래프, 의존성 시각화, /understand, 코드베이스 온보딩.
---

# Skill — Understand-Anything 컴패니언 브리지

## 옵트인 컴패니언 (필독)

이 스킬은 **옵트인 외부 도구**의 브리지일 뿐이다. cg 코어는 이 도구에 의존하지
않으며 번들하지도 않는다. 사용 전 반드시:

```
cg companion doctor
```

- 가용성이 `UNKNOWN`(claude-plugin 은 정적 탐지 불가) → 아래 설치 확인 후 사용.
- 미설치면 install 안내만 하고, 도구 없이도 진행 가능한 대안(평문 vault·grep)을 제시한다.

설치:

```
/plugin marketplace add Egonex-AI/Understand-Anything
/plugin install understand-anything
```

## 언제 쓰나

- 대규모/낯선 코드베이스를 빠르게 이해해야 할 때 (온보딩).
- 모듈 간 의존성 구조를 시각적으로 파악해야 할 때.

호출:

```
/understand            # 코드 지식그래프 생성
/understand-knowledge  # 그래프 질의
```

## knot 과의 보완 관계

| 도구 | 성격 | 산출물 |
|------|------|--------|
| knot (cg 평문 vault) | **영속** 지식 그물 | git 추적되는 `.md` 페이지 |
| Understand-Anything | **일회성** 코드 그래프 | 세션 내 시각화·질의 |

knot 구성도 설치되어 있다면 — knot 은 의사결정·도메인 지식을 평문 md 로 **영속**
보존한다. Understand-Anything 은 현재 코드 구조를 **일회성**으로 그래프화한다.
코드 구조 파악은 understand 로, 보존 가치가 있는 결론은 knot note 로 옮겨 남긴다.

## 주의

- cg 코어 기능(스펙·드리프트·mechanical 게이트)은 이 도구 없이도 전부 동작한다.
- 그래프는 휘발성이므로, 재사용할 통찰은 반드시 spec 또는 (knot 구성 설치 시) knot 으로 옮길 것.
