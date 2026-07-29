---
name: cg-finish-branch
description: "개발 브랜치 완료 — 테스트 검증 → 4옵션(머지/PR/보류/폐기) 제시 → 실행. Adapted from superpowers (MIT)."
---

# Finishing a Development Branch

**Trigger Keywords**: "finish branch", "브랜치 완료", "머지", "PR 생성", "작업 마무리"

## Overview

개발 완료 후 테스트 검증 → 4가지 옵션 제시 → 선택 실행.

**Core Principle**: 테스트 통과 확인 → 옵션 제시 → 실행 → 정리.

## Process

### Step 1: 테스트 검증

```bash
# 프로젝트 테스트 스위트 실행
flutter test / pytest / npm test / go test ./...
```

**테스트 실패 시 → STOP.** 옵션 제시하지 않음.

### Step 2: 베이스 브랜치 확인

```bash
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null
```

### Step 3: 4옵션 제시

```
구현 완료. 어떻게 진행할까요?

1. <base-branch> 에 로컬 머지
2. 푸시 + Pull Request 생성
3. 브랜치 유지 (나중에 처리)
4. 작업 폐기
```

### Step 4: 선택 실행

#### Option 1: 로컬 머지
```bash
git checkout <base-branch> && git pull && git merge <feature-branch>
# 머지 후 테스트 재실행
```

#### Option 2: PR 생성
```bash
git push -u origin <feature-branch>
gh pr create --title "<title>" --body "## Summary
- ...

## Test Plan
- [ ] ..."
```

#### Option 3: 보류
"`<branch>` 브랜치 유지. 나중에 처리 가능."

#### Option 4: 폐기
"`<branch>` 작업 폐기. 브랜치 유지." (삭제는 명시 요청 시만)

## Red Flags

**Never:**
- 테스트 실패 상태로 머지/PR 진행
- 머지 결과에서 테스트 재검증 건너뛰기
- 사용자 요청 없이 force-push
- 사용자 요청 없이 worktree/브랜치 삭제

## Integration

- **입력**: `cg-subagent-dev`, `cg-execution-loop` 완료 후
- **관련**: `cg-worktree` — worktree 에서 작업한 경우 정리 포함
