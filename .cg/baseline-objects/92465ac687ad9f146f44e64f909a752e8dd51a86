#!/usr/bin/env python3
"""Flutter architecture/i18n guard for cg-harness.

PostToolUse 단계에서 production Dart 파일의 직접 한글 UI 문자열을 감지한다.
초기 목적은 Flutter ARB 이전 단계에서도 AppStrings/AppLocalizations 같은
문자열 SSOT 를 우회하지 못하게 하는 것이다.

또한 domain/data 계층이 문자열/l10n 계층에 직접 의존하는 것을 막는다.
문자열 SSOT 는 유지하되 표시 변환은 presentation boundary 로 둔다.

추가로 feature 간 presentation provider 직접 import 를 감지한다.
다른 feature provider 는 source feature facade 를 통해서만 사용한다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HANGUL_RE = re.compile(r"[가-힣]")
UI_TEXT_RE = re.compile(
    r"\b(?:Text|SelectableText|RichText)\s*\(\s*(?:const\s+)?(?P<quote>['\"])(?P<text>[^'\"]*[가-힣][^'\"]*) (?P=quote)",
    re.VERBOSE,
)
INPUT_DECORATION_RE = re.compile(
    r"\b(?:labelText|hintText|helperText|errorText)\s*:\s*(?P<quote>['\"])(?P<text>[^'\"]*[가-힣][^'\"]*) (?P=quote)",
    re.VERBOSE,
)
L10N_DEP_RE = re.compile(r"\b(?:AppStrings|AppLocalizations)\b|/core/l10n/|core/l10n")
IMPORT_RE = re.compile(r"^\s*import\s+['\"](?P<uri>[^'\"]+)['\"]")
PRESENTATION_PROVIDER_RE = re.compile(
    r"/presentation/providers/|presentation/providers/"
)

ALLOWED_PATH_PARTS = {
    "l10n",
    "generated",
}


def find_project_root(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        if (parent / "pubspec.yaml").is_file() or (parent / ".harness").is_dir():
            return parent
    return None


def is_flutter_project(root: Path) -> bool:
    pubspec = root / "pubspec.yaml"
    if not pubspec.is_file():
        return False
    try:
        text = pubspec.read_text(encoding="utf-8")
    except OSError:
        return False
    return "flutter:" in text or "sdk: flutter" in text


def should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if path.name.endswith(".g.dart") or path.name.endswith(".freezed.dart"):
        return True
    if any(part in ALLOWED_PATH_PARTS for part in rel.parts):
        return True
    if rel.parts and rel.parts[0] != "lib":
        return True
    return False


def is_domain_or_data_path(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    parts = rel.parts
    if "presentation" in parts:
        return False
    if "domain" in parts or "data" in parts:
        return True
    if len(parts) >= 3 and parts[0] == "lib" and parts[1] == "core":
        return parts[2] in {"domain", "booking"}
    return False


def feature_name_for(path: Path, root: Path) -> str | None:
    rel = path.relative_to(root)
    parts = rel.parts
    if len(parts) >= 3 and parts[0] == "lib" and parts[1] == "features":
        return parts[2]
    return None


def normalized_import_path(path: Path, root: Path, uri: str) -> Path | None:
    if uri.startswith("dart:"):
        return None
    if uri.startswith("package:"):
        parts = uri.split("/", 1)
        if len(parts) != 2:
            return None
        return root / "lib" / parts[1]
    if uri.startswith("."):
        return (path.parent / uri).resolve()
    return None


def find_violations(root: Path) -> list[tuple[Path, int, str]]:
    lib = root / "lib"
    if not lib.is_dir():
        return []

    violations: list[tuple[Path, int, str]] = []
    for path in sorted(lib.rglob("*.dart")):
        if should_skip(path, root):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, start=1):
            if not HANGUL_RE.search(line):
                continue
            for pattern in (UI_TEXT_RE, INPUT_DECORATION_RE):
                match = pattern.search(line)
                if match:
                    violations.append(
                        (path.relative_to(root), line_no, match.group("text"))
                    )
                    break
    return violations


def find_layer_violations(root: Path) -> list[tuple[Path, int, str]]:
    lib = root / "lib"
    if not lib.is_dir():
        return []

    violations: list[tuple[Path, int, str]] = []
    for path in sorted(lib.rglob("*.dart")):
        if should_skip(path, root):
            continue
        if not is_domain_or_data_path(path, root):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, start=1):
            if L10N_DEP_RE.search(line):
                violations.append((path.relative_to(root), line_no, line.strip()))
                break
    return violations


def find_cross_feature_provider_imports(root: Path) -> list[tuple[Path, int, str]]:
    lib = root / "lib" / "features"
    if not lib.is_dir():
        return []

    violations: list[tuple[Path, int, str]] = []
    for path in sorted(lib.rglob("*.dart")):
        if should_skip(path, root) or path.name.endswith("_facade.dart"):
            continue
        source_feature = feature_name_for(path, root)
        if source_feature is None:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, start=1):
            match = IMPORT_RE.search(line)
            if match is None:
                continue
            uri = match.group("uri")
            if PRESENTATION_PROVIDER_RE.search(uri) is None:
                continue
            target_path = normalized_import_path(path, root, uri)
            if target_path is None:
                continue
            try:
                target_feature = feature_name_for(target_path, root)
            except ValueError:
                target_feature = None
            if target_feature is not None and target_feature != source_feature:
                violations.append((path.relative_to(root), line_no, uri))
    return violations


def main() -> None:
    root = find_project_root(Path.cwd())
    if root is None or not is_flutter_project(root):
        print("Success")
        return

    text_violations = find_violations(root)
    layer_violations = find_layer_violations(root)
    provider_import_violations = find_cross_feature_provider_imports(root)
    if not text_violations and not layer_violations and not provider_import_violations:
        print("Success")
        return

    print("[cg-harness] Flutter architecture/i18n 위반 감지")
    print("사용자-facing 문자열은 AppStrings 또는 AppLocalizations 를 통해 관리하세요.")
    if layer_violations:
        print(
            "domain/data 계층은 AppStrings/AppLocalizations/core/l10n 을 직접 의존하지 않습니다."
        )
        print("표시 문구 변환은 presentation extension/widget/provider 로 이동하세요.")
    if provider_import_violations:
        print(
            "다른 feature 의 presentation provider 는 직접 import 하지 말고 feature facade 를 사용하세요."
        )
    for path, line_no, text in layer_violations[:20]:
        print(f"- {path}:{line_no} domain/data l10n 의존: {text}")
    remaining_slots = max(0, 20 - min(len(layer_violations), 20))
    for path, line_no, text in provider_import_violations[:remaining_slots]:
        print(f"- {path}:{line_no} cross-feature provider import: {text}")
    remaining_slots = max(
        0,
        20
        - min(len(layer_violations), 20)
        - min(len(provider_import_violations), remaining_slots),
    )
    for path, line_no, text in text_violations[:remaining_slots]:
        print(f"- {path}:{line_no} 직접 문자열: {text}")
    total = (
        len(layer_violations) + len(provider_import_violations) + len(text_violations)
    )
    if total > 20:
        print(f"- 외 {total - 20}건")
    sys.exit(2)


if __name__ == "__main__":
    main()
