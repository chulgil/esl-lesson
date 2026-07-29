---
name: cg-companion-rtk
description: |
  rtk(Rust Token Killer) 컴패니언 브리지 — Bash 출력을 압축해 LLM 토큰 60~90%↓.
  옵트인 외부 도구(Apache-2.0 Rust 바이너리, jq 필요). 컨텍스트 비용이 큰 대형
  리포에서만 권장. 트리거: 토큰 절감, rtk, bash 출력 압축, 컨텍스트 다이어트.
---

# Skill — rtk 컴패니언 브리지

## 옵트인 컴패니언 (필독)

이 스킬은 **옵트인 외부 도구**의 브리지다. cg 코어는 rtk 에 의존하지 않으며
번들하지 않는다(의존성0·벤더중립 유지). 사용 전:

```
cg companion doctor
```

- `YES` → rtk 설치됨. 아래로 진행.
- `NO` → 미설치. 설치 안내만 하고 **압축 없이 평소대로 진행**한다.

## rtk 란

Bash 명령(`ls`·`cat`·`grep`·`git`·`gh`·test/lint 등 100+)의 출력을 필터·dedup·절단해
LLM 컨텍스트 토큰을 60~90% 줄이는 프록시. `Read`/`Grep`/`Glob` 내장 도구는 거치지
않는다(Bash 만 가로챈다).

## 설치

```
brew install rtk          # 또는: cargo install --git https://github.com/rtk-ai/rtk
# jq 필요 (rtk 훅이 사용)
```

## 자동 사용 (auto-use)

rtk 자체가 PreToolUse(Bash) 훅을 settings.json 에 심어 자동 동작시킨다:

```
rtk init -g     # 전역(~/.claude) 훅 설치 — 모든 프로젝트
rtk init        # 프로젝트(.claude/settings.json) 훅 설치 — 이 프로젝트만
```

설치 후 Bash 출력이 자동 압축된다. 끄려면 rtk 문서의 비활성화 절차를 따른다.

> cg 와의 경계: cg 는 rtk 를 **탐지·안내만** 한다. 훅 설치는 rtk 의 `init` 이
> 수행한다(외부 도구가 자기 훅을 관리). cg scaffold 의 settings.json 에 rtk 훅을
> 하드코딩하지 않는다 — rtk 미설치 환경에서 깨지기 때문.

## 언제 쓰나

- 대형 모노레포에서 Bash 출력(빌드 로그·git diff·test 출력)이 컨텍스트를 잡아먹을 때.
- 작은 프로젝트면 효과가 작으니 옵트인하지 않아도 된다.

## 주의

- 출력 압축은 정보 손실을 동반한다 — 디버깅 시 원본이 필요하면 일시 비활성화.
- cg 코어 기능은 rtk 없이도 전부 동작한다(의존성0 유지).
