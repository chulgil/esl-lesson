#!/usr/bin/env python3
"""Keyword/category detector hook for cg-harness (UserPromptSubmit).

사용자 입력을 stdin 으로 받아 **대화 카테고리**(계획·디버깅·검증·리팩토링·보안 등)를
키워드로 추정하고, 그 카테고리에 맞는 스킬을 원 프롬프트 뒤에 `<skill-suggestion>`
블록으로 덧붙여 stdout 으로 내보낸다. Claude 는 이 넛지를 보고 해당 스킬을 호출한다.

이것은 "명령어 없이 자동으로 스킬을 유도"하는 결정적(deterministic) 경로다.
또 다른 경로 — 모델이 스킬 description(트리거 조건)을 보고 스스로 호출하는 것 —
은 모델 판단이라 100% 보장이 아니므로, 이 훅이 결정적 보완재 역할을 한다.

매칭이 없으면 원본을 그대로 통과시킨다. stdlib only · 어떤 예외도 프롬프트를
삼키지 않도록 graceful (실패 시 원본 패스스루).

Adapted from Q00/ouroboros (MIT); v0.12.0 에서 카테고리 인식 + 상위 N 추천으로 확장.
"""

from __future__ import annotations

import re
import sys

# (카테고리 라벨, 트리거들, 추천 스킬들). 위에서부터 우선순위(동점 시).
CATEGORY_MAP: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    (
        "요구사항/새 기능",
        (
            "새 기능",
            "기능 추가",
            "만들어줘",
            "요구사항",
            "인터뷰",
            "뭘 만들",
            "feature",
            "requirement",
        ),
        ("cg-interview", "cg-spec-and-harness"),
    ),
    (
        "분해/계획",
        (
            "분해",
            "decompose",
            "dag",
            "작업 나눠",
            "job 으로",
            "계획 세워",
            "decomposition",
        ),
        ("cg-decomposition",),
    ),
    (
        "계획 검증(실행 전)",
        (
            "계획 검증",
            "계획 점검",
            "실행 전 점검",
            "plan check",
            "이 계획",
            "계획 맞나",
            "계획 리뷰",
        ),
        ("cg-plan-check",),
    ),
    (
        "디버깅",
        (
            "디버그",
            "debug",
            "왜 안 돼",
            "왜 안돼",
            "버그",
            "에러",
            "오류",
            "고장",
            "root cause",
            "근본 원인",
            "stack trace",
            "안 돼요",
            "재현",
        ),
        ("cg-debug",),
    ),
    (
        "교착 탈출",
        (
            "막혔",
            "stuck",
            "안 풀려",
            "측면 사고",
            "측면으로 생각",
            "lateral thinking",
            "다른 접근",
            "아이디어가 없",
        ),
        ("cg-unstuck",),
    ),
    (
        "검증/품질",
        (
            "검증",
            "verify",
            "테스트 통과",
            "빌드 확인",
            "품질 확인",
            "qa 판정",
            "qa verdict",
            "quality check",
            "확인해줘",
        ),
        ("cg-qa", "verification-engine"),
    ),
    (
        "TDD/테스트 작성",
        ("tdd", "테스트 먼저", "red green", "red-green", "테스트 작성", "테스트부터"),
        ("tdd-loop",),
    ),
    (
        "리뷰 피드백 수신",
        ("리뷰 피드백", "리뷰 반영", "코드 리뷰 결과", "review feedback", "리뷰어가"),
        ("cg-review-receive",),
    ),
    (
        "리팩토링/아키텍처",
        (
            "리팩토링",
            "refactor",
            "아키텍처",
            "구조 개선",
            "얕은 모듈",
            "deep module",
            "모듈 정리",
        ),
        ("improve-architecture",),
    ),
    (
        "보안",
        ("보안", "security", "취약점", "cwe", "stride", "owasp", "인증 검토", "암호화"),
        ("security-pipeline",),
    ),
    (
        "병렬 실행",
        (
            "병렬",
            "parallel",
            "동시에 해결",
            "독립 작업",
            "여러 작업 동시",
            "independent tasks",
        ),
        ("cg-parallel-dispatch",),
    ),
    (
        "서브에이전트 구현",
        ("서브에이전트", "subagent", "sdd", "태스크별 에이전트", "에이전트로 분배"),
        ("cg-subagent-dev",),
    ),
    (
        "워크트리/격리",
        ("worktree", "워크트리", "격리 브랜치", "isolated workspace", "병렬 개발"),
        ("cg-worktree",),
    ),
    (
        "브랜치 완료/PR",
        ("브랜치 완료", "작업 마무리", "pr 생성", "finish branch", "머지 준비"),
        ("cg-finish-branch",),
    ),
    (
        "영속 루프",
        (
            "ralph",
            "계속 돌려",
            "멈추지 마",
            "될 때까지",
            "실패하면 다시",
            "keep going",
            "don't stop",
            "until it works",
        ),
        ("cg-ralph",),
    ),
    (
        "상태/드리프트",
        (
            "drift",
            "드리프트",
            "상태 보고",
            "session status",
            "harness status",
            "내가 벗어나",
        ),
        ("cg-status",),
    ),
    (
        "세션 재개",
        (
            "resume",
            "이어서",
            "어디까지 했",
            "where was i",
            "컨텍스트 복원",
            "이어가기",
            "다시 시작",
        ),
        ("cg-resume",),
    ),
    (
        "지식 그물",
        ("지식 그물", "knot", "그물에 넣", "그물에서 찾", "위키에 정리", "inbox 처리"),
        ("cg-knot-query", "cg-knot-ingest"),
    ),
    (
        "평가/critic",
        ("평가해줘", "critic", "evaluation", "오라클", "3-critic"),
        ("cg-evaluation",),
    ),
]

MAX_SUGGESTIONS = 3


def _word_boundary_match(pattern: str, text: str) -> bool:
    """ASCII 경계 또는 한글 포함 시 서브스트링 매치."""
    if re.search(r"[^\x00-\x7f]", pattern):
        return pattern in text
    return bool(re.search(r"(?:^|\b)" + re.escape(pattern) + r"(?:\b|$)", text))


def detect_all(text: str) -> list[tuple[str, tuple[str, ...], int, str]]:
    """매칭된 카테고리를 (라벨, 스킬들, 매칭수, 첫키워드) 로, 매칭수 내림차순 반환."""
    lower = text.lower().strip()
    hits: list[tuple[str, tuple[str, ...], int, str]] = []
    for label, triggers, skills in CATEGORY_MAP:
        matched = [t for t in triggers if _word_boundary_match(t, lower)]
        if matched:
            hits.append((label, skills, len(matched), matched[0]))
    # 매칭수 내림차순, 동점은 CATEGORY_MAP 원순서 유지(stable sort).
    hits.sort(key=lambda h: -h[2])
    return hits[:MAX_SUGGESTIONS]


def _render(hits: list[tuple[str, tuple[str, ...], int, str]]) -> str:
    lines = [
        "",
        "",
        "<skill-suggestion>",
        "이 대화에 맞을 수 있는 스킬 (keyword-detector 자동 추천):",
    ]
    for label, skills, _count, kw in hits:
        skill_str = " / ".join(skills)
        lines.append(f'- [{label}] {skill_str} — "{kw}" 감지')
    lines.append("필요하면 위 스킬을 사용하세요. 무관하면 무시하고 진행하세요.")
    lines.append("</skill-suggestion>")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    try:
        user_input = sys.stdin.read()
    except OSError:
        return

    stripped = user_input.strip()
    hits = detect_all(stripped) if stripped else []

    if not hits:
        sys.stdout.write(user_input)
        return

    sys.stdout.write(user_input.rstrip() + _render(hits))


if __name__ == "__main__":
    main()
