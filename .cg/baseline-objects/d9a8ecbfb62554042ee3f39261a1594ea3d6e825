---
name: cg-brownfield-scan
description: Phase 0 — 기존 코드, 프레임워크, 이전 하네스 산출물을 스캔하여 `.harness/harness/current.md` 초안을 작성합니다. 새 feature 시작 전 항상 먼저 실행하세요.
---

# Phase 0 — Brownfield Scan

## 목적

새 feature 작업을 시작하기 전에 **현재 프로젝트 상태를 정확히 파악** 합니다. 기존 린팅 규칙, 테스트 프레임워크, 아키텍처 패턴을 놓치면 이후 spec 과 실행이 프로젝트와 충돌합니다.

## 입력

- 프로젝트 루트 전체
- 기존 `.harness/harness/current.md` (있으면 업데이트, 없으면 신규 작성)

## 출력

- `.harness/harness/current.md` (품질 계약 — 최신 상태)
- 발견 사항을 `.harness/knowledge/scan-{YYYY-MM-DD}.md` 에 기록

## 스캔 체크리스트

1. **빌드/패키지**
   - `package.json`, `pyproject.toml`, `pubspec.yaml`, `build.gradle`, `go.mod`
   - 스크립트 entrypoint, 최소 버전 요구사항
2. **린팅 / 포매팅**
   - ESLint/Ruff/analyzer/checkstyle/golangci-lint 설정
3. **테스트**
   - 단위 프레임워크, e2e 프레임워크, 커버리지 임계값
4. **CI/CD**
   - `.github/workflows/`, `.gitlab-ci.yml`
5. **아키텍처 힌트**
   - 폴더 구조 패턴 (features/, domain/, modules/)
   - 기존 `CLAUDE.md`, `ARCHITECTURE.md`, `docs/architecture.md`
6. **이전 하네스 산출물**
   - `.harness/spec/*.md` (이전 feature 들)
   - `.harness/journal/` (최근 활동)

## 수행 방법

1. `Glob` 과 `Read` 로 위 파일들을 탐색
2. 발견한 내용을 `harness/current.md` 에 반영 (기존 내용은 보존하되 최신 사실로 업데이트)
3. 발견 요약을 사용자에게 간단히 보고 (200단어 이내)

## 금지 사항

- 코드 변경 금지 — 읽기 전용 phase
- "추정" 금지 — 확인 안 된 규칙은 기록하지 않음
