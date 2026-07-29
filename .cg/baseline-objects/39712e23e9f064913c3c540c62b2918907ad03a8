---
name: cg-worktree
description: "격리된 Git Worktree 작업 공간 생성 + 에이전트 파견. Adapted from superpowers (MIT)."
---

# Git Worktree Management

**Trigger Keywords**: "worktree", "격리", "isolated", "별도 브랜치에서"

## Overview

Git worktree 로 격리된 작업 공간을 만들어 메인 브랜치를 건드리지 않고 작업한다.

**Core Principle**: 체계적 디렉토리 선택 + 안전 검증 + 에이전트 프롬프트 = 안전한 격리.

## Workflow

### Step 1 — 기존 Worktree 확인

```bash
git worktree list
```

### Step 2 — .worktrees 디렉토리 무시 확인

```bash
git check-ignore -q .worktrees 2>/dev/null && echo "ignored" || echo "NOT ignored"
```

NOT ignored 면 `.gitignore` 에 추가 후 커밋:
```bash
echo ".worktrees" >> .gitignore
git add .gitignore && git commit -m "chore: .worktrees 디렉토리 무시"
```

### Step 3 — Worktree 생성

```bash
git worktree add .worktrees/<feature-name> -b <feature-name>
```

### Step 4 — 의존성 설치

worktree 에는 gitignored 파일이 없으므로:
```bash
cd .worktrees/<feature-name>
# Node: npm install
# Python: uv sync
# Flutter: flutter pub get
# Go: go mod download
```

### Step 5 — 작업 또는 에이전트 파견

직접 작업하거나 서브에이전트에게 worktree 경로와 프롬프트 전달.

## Completing Work

```bash
# 메인 리포에서 (worktree 내부 아님)
git checkout main && git merge <feature-name>

# worktree 정리 (선택)
git worktree remove .worktrees/<feature-name>
git branch -d <feature-name>
```

**기본값: worktree 유지.** 삭제는 사용자 명시 요청 시에만.

## Quick Reference

| 상황 | 명령 |
|------|------|
| 목록 확인 | `git worktree list` |
| 생성 | `git worktree add .worktrees/<name> -b <name>` |
| 머지 | `git checkout main && git merge <name>` |
| 삭제 (명시 요청 시) | `git worktree remove .worktrees/<name>` |

## Red Flags

**Never:**
- .worktrees 가 gitignore 안 된 상태로 생성
- worktree 내부에서 메인 브랜치 작업
- 사용자 요청 없이 worktree 삭제

## Integration

- **후속**: `cg-finish-branch` — 작업 완료 후 브랜치 처리
- **관련**: `cg-subagent-dev` — worktree 에서 SDD 실행 가능
