#!/usr/bin/env python3
"""CodeAudit: read-only recursive project metrics, independent of Git.

Run in the project's root directory:
    python project_metrics.py
or:
    python project_metrics.py /path/to/your-project

Counts physical lines and non-empty lines, not language-aware logical SLOC.
Does not modify any project file.
"""

from collections import Counter, defaultdict
from pathlib import Path
import os
import sys

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", ".venv-semantic",
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".tox", ".nox", ".next", ".turbo", ".parcel-cache",
    "dist", "build", "coverage", "htmlcov", ".coverage_html",
    "var", ".work", ".cache", ".idea", ".vscode-test",
}
SKIP_NAMES = {".DS_Store", ".coverage", "Thumbs.db"}
SKIP_SUFFIXES = {
    ".pyc", ".pyo", ".log", ".tmp", ".swp", ".swo", ".orig"
}
PYTHON = {".py"}
JAVASCRIPT = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
STYLE = {".css", ".scss", ".sass"}
HTML = {".html", ".htm"}
SCRIPTS = {".ps1", ".bat", ".cmd", ".sh"}
DOCS = {".md", ".mdx", ".rst"}
CONFIG = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml"}
ASSETS = {
    ".svg", ".png", ".jpg", ".jpeg", ".webp", ".avif",
    ".gif", ".ico", ".drawio", ".woff", ".woff2", ".ttf", ".gz"
}
DATABASES = {".db", ".sqlite", ".sqlite3"}

# Top-level directories treated as frontend application roots.
# Customise this set for your project structure.
FRONTEND_DIRS: set[str] = set()

# Category order and labels in the report.
LABELS = {
    "python_prod": "Python production (src/)",
    "python_tests": "Python tests (tests/)",
    "python_other": "Python tools / other",
    "frontend_prod": "Frontend JS/TS - code",
    "frontend_tests": "Frontend JS/TS - tests",
    "other_js": "JS/TS outside frontend",
    "styles": "CSS / SCSS",
    "html": "HTML",
    "scripts": "PowerShell / BAT / SH",
    "docs": "Documentation Markdown / RST",
    "config": "Config JSON / YAML / TOML / other",
    "assets": "Graphics and other assets",
    "databases": "Databases",
    "other": "Other files",
}
SOURCE_CATEGORIES = {
    "python_prod", "python_other", "frontend_prod", "other_js", "styles", "html", "scripts"
}
TEST_CATEGORIES = {"python_tests", "frontend_tests"}
TEXT_CODE_CATEGORIES = SOURCE_CATEGORIES | TEST_CATEGORIES


def is_test_js(relative: Path) -> bool:
    parts = [part.lower() for part in relative.parts]
    stem = relative.stem.lower()
    return (
        "tests" in parts or "__tests__" in parts
        or stem.endswith((".test", ".spec", ".browser"))
        or stem.startswith(("test_", "spec_"))
    )


def classify(relative: Path) -> str:
    suffix = relative.suffix.lower()
    parts = relative.parts
    top = parts[0] if len(parts) > 1 else "(root)"

    if suffix in PYTHON:
        if top == "src":
            return "python_prod"
        if top == "tests":
            return "python_tests"
        return "python_other"
    if suffix in JAVASCRIPT:
        if top in FRONTEND_DIRS or top == "tests" or is_test_js(relative):
            return "frontend_tests" if is_test_js(relative) else "frontend_prod"
        return "other_js"
    if suffix in STYLE:
        return "styles" if top != "docs" else "assets"
    if suffix in HTML:
        return "html" if top != "docs" else "assets"
    if suffix in SCRIPTS:
        return "scripts"
    if suffix in DOCS:
        return "docs"
    if suffix in DATABASES:
        return "databases"
    if suffix in ASSETS:
        return "assets"
    if suffix in CONFIG or relative.name in {".gitignore", ".gitattributes", "requirements.txt"}:
        return "config"
    return "other"


def count_lines(path: Path) -> tuple[int, int]:
    """Number of physical lines, and non-empty physical lines."""
    physical = 0
    nonempty = 0
    # Standard library only. Ignore broken characters, never display contents.
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            physical += 1
            nonempty += bool(line.strip())
    return physical, nonempty


def fmt(number: int) -> str:
    return f"{number:,}".replace(",", " ")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"Directory not found: {root}")

    stats = defaultdict(Counter)
    folders = defaultdict(Counter)
    script_path = Path(__file__).resolve()
    errors = []
    directories = 0

    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (current_path / d).is_symlink())
        files.sort()
        rel_dir = current_path.relative_to(root)
        if rel_dir != Path("."):
            directories += 1
        for filename in files:
            path = current_path / filename
            if path.is_symlink() or path.resolve() == script_path or filename in SKIP_NAMES or path.suffix.lower() in SKIP_SUFFIXES:
                continue
            if filename.endswith((".db-wal", ".db-shm", ".sqlite-wal", ".sqlite-shm")):
                continue
            relative = path.relative_to(root)
            category = classify(relative)
            top = relative.parts[0] if len(relative.parts) > 1 else "(root)"

            try:
                size = path.stat().st_size
                lines, nonempty = count_lines(path) if category in TEXT_CODE_CATEGORIES else (0, 0)
            except (OSError, UnicodeError) as exc:
                errors.append((str(relative), str(exc)))
                continue

            for target in (stats[category], folders[top]):
                target["files"] += 1
                target["bytes"] += size
                target["lines"] += lines
                target["nonempty"] += nonempty

    def total(keys: set[str], metric: str) -> int:
        return sum(stats[key][metric] for key in keys)

    total_files = sum(row["files"] for row in stats.values())
    pyprod = stats["python_prod"]["files"]
    pytests = stats["python_tests"]["files"]
    ratio = f"{pytests / pyprod:.2f}" if pyprod else "n/a"
    code_lines = total(TEXT_CODE_CATEGORIES, "lines")
    code_nonempty = total(TEXT_CODE_CATEGORIES, "nonempty")
    source_lines = total(SOURCE_CATEGORIES, "lines")
    test_lines = total(TEST_CATEGORIES, "lines")

    print(f"# CodeAudit - project metrics (filesystem scan)\n")
    print(f"**Directory:** `{root}`  ")
    print("**Method:** no Git; recursive walk, skipping dependencies/cache/build/var/.work.  ")
    print("**LOC:** physical lines, including blanks and comments.\n")
    print(f"**Files: {fmt(total_files)} | Subdirectories: {fmt(directories)}**  ")
    print(f"**Code + test lines: {fmt(code_lines)}** ")
    print(f"(non-empty: {fmt(code_nonempty)}; excludes docs, databases, graphics, and config).  ")
    print(f"**Production/tools code: {fmt(source_lines)} | Tests: {fmt(test_lines)}**\n")

    print("## A. Breakdown by file type\n")
    print("| Category | Files | Size (MB) | Physical lines | Non-empty |")
    print("|---|---:|---:|---:|---:|")
    for category, label in LABELS.items():
        row = stats[category]
        print(f"| {label} | {fmt(row['files'])} | {row['bytes']/1024**2:.2f} | {fmt(row['lines'])} | {fmt(row['nonempty'])} |")
    print(f"| **Total files** | **{fmt(total_files)}** | **{sum(s['bytes'] for s in stats.values())/1024**2:.2f}** | - | - |\n")

    print("## B. Breakdown by top-level directory\n")
    print("| Directory | Files (recursive) | Size (MB) | Code + test lines |")
    print("|---|---:|---:|---:|")
    for name, row in sorted(folders.items(), key=lambda item: (-item[1]["files"], item[0])):
        print(f"| `{name}` | {fmt(row['files'])} | {row['bytes']/1024**2:.2f} | {fmt(row['lines'])} |")
    print()

    if errors:
        print(f"\n## Warnings: could not read {len(errors)} files\n")
        for name, message in errors[:15]:
            print(f"- `{name}`: {message}")


if __name__ == "__main__":
    main()
