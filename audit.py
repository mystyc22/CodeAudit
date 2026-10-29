#!/usr/bin/env python3
"""CodeAudit: read-only local Python + JavaScript/React source-code audit.

Dependencies: Python 3.10+, radon 6.x, Node.js, ESLint 9 and plugins.
Run: python audit.py "/path/to/project"

Output: report.md, metrics.json, issues.csv, functions.csv, files.csv.
All output goes to CodeAudit/reports/ (or --out), NEVER to the source project.
No git required, no rewriting files, no lint --fix, and no eslint cache.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tokenize

try:
    from radon.complexity import cc_rank, cc_visit
    from radon.metrics import h_visit, mi_rank, mi_visit
    from radon.raw import analyze as raw_analyze
except ImportError:
    print("RADON MISSING: install with: python -m pip install radon", file=sys.stderr)
    raise SystemExit(2)

VERSION = "1.0.0"
HERE = Path(__file__).resolve().parent
JS_EXT = {".js", ".jsx", ".mjs", ".cjs"}
TS_EXT = {".ts", ".tsx", ".mts", ".cts"}
STYLE_EXT = {".css", ".scss", ".sass", ".less"}
HTML_EXT = {".html", ".htm"}
SCRIPTS = {".ps1", ".bat", ".cmd", ".sh"}
DOCS = {".md", ".mdx", ".rst", ".txt"}
CONFIG = {".json", ".jsonc", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".xml", ".env.example"}
ASSETS = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".ico", ".woff", ".woff2", ".ttf", ".pdf", ".gz", ".zip"}
DATABASES = {".db", ".sqlite", ".sqlite3"}
FRONTENDS = {"client", "app", "web", "frontend", "ui", "src"}
IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", ".tox", ".nox", ".next", ".nuxt", ".turbo",
    "dist", "build", "coverage", "htmlcov", ".cache", ".idea", ".work", "vendor",
    ".parcel-cache", ".svelte-kit", ".angular", ".gradle", "site-packages",
}
IGNORE_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp", ".swp", ".swo", ".orig"}
TEXT_SUFFIXES = {".py"} | JS_EXT | TS_EXT | STYLE_EXT | HTML_EXT | SCRIPTS | DOCS | CONFIG | {".sql", ".graphql", ".gql", ".vue", ".svelte"}
CODE_CATS = {"py_prod", "py_tests", "py_other", "js_prod", "js_tests", "js_other", "ts_prod", "ts_tests", "styles", "html", "scripts", "other_code"}
GROUPS = [
    ("py_prod", "Python — Production"), ("py_tests", "Python — Tests"),
    ("py_other", "Python — Tools/Other"), ("js_prod", "JS/JSX — Frontend"),
    ("js_tests", "JS/JSX — Tests"), ("js_other", "JS/JSX — Other"),
    ("ts_prod", "TypeScript — Production"), ("ts_tests", "TypeScript — Tests"),
    ("styles", "CSS/SCSS"), ("html", "HTML"), ("scripts", "Shell/System Scripts"),
    ("other_code", "Other Code/SQL"), ("docs", "Documentation"),
    ("config", "Configuration"), ("assets", "Assets/Binary"),
    ("databases", "Databases"), ("other", "Other Files"),
]
LABELS = dict(GROUPS)


def is_test(rel: Path) -> bool:
    p = [s.lower() for s in rel.parts]
    name = rel.stem.lower()
    return (
        any(s in {"tests", "test", "__tests__", "spec", "specs", "e2e"} for s in p[:-1])
        or name.startswith(("test_", "spec_"))
        or name.endswith((".test", ".spec", ".browser", "_test", "_spec"))
    )


def classify(rel: Path) -> str:
    ext = rel.suffix.lower()
    top = rel.parts[0].lower() if len(rel.parts) > 1 else "(root)"
    test = is_test(rel)
    if ext == ".py":
        return "py_tests" if test else ("py_prod" if top == "src" else "py_other")
    if ext in JS_EXT:
        if test:
            return "js_tests"
        return "js_prod" if top in FRONTENDS else "js_other"
    if ext in TS_EXT:
        return "ts_tests" if test else "ts_prod"
    if ext in STYLE_EXT: return "styles"
    if ext in HTML_EXT: return "html"
    if ext in SCRIPTS: return "scripts"
    if ext in {".sql", ".graphql", ".gql", ".vue", ".svelte"}: return "other_code"
    if ext in DOCS: return "docs"
    if ext in CONFIG or rel.name.startswith((".env", ".prettier", ".editorconfig")): return "config"
    if ext in ASSETS: return "assets"
    if ext in DATABASES: return "databases"
    return "other"


def md(s) -> str:
    return str(s).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def fmt(v, digits=0) -> str:
    if v is None: return "—"
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not math.isfinite(v): return "—"
        return f"{v:,.{digits}f}" if digits else f"{round(v):,}"
    return str(v)


def avg(xs):
    return statistics.mean(xs) if xs else None


def median(xs):
    return statistics.median(xs) if xs else None


def safe_text(path: Path) -> str:
    if path.suffix.lower() == ".py":
        try:
            with tokenize.open(path) as f:
                return f.read()
        except (SyntaxError, UnicodeError, LookupError):
            pass
    return path.read_text(encoding="utf-8-sig", errors="replace")


def physical_lines(data: bytes) -> int:
    return len(data.splitlines())


def file_inventory(root: Path, output: Path, include_work: bool, include_hidden: bool):
    files = []
    diagnostics = []
    hidden_dirs_ignored = 0
    dirs = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        base = Path(dirpath)
        if base.is_symlink():
            dirnames[:] = []
            continue
        if base == output or output in base.parents:
            dirnames[:] = []
            continue
        kept = []
        for name in dirnames:
            p = base / name
            if name.lower() in IGNORE_DIRS and not (include_work and name.lower() == ".work"):
                continue
            if name.startswith(".") and not include_hidden and name not in {".github", ".vscode"}:
                hidden_dirs_ignored += 1
                continue
            if p.is_symlink() or p == output or output in p.parents:
                continue
            kept.append(name)
        dirnames[:] = sorted(kept)
        dirs += 1
        for name in sorted(filenames):
            p = base / name
            if p.is_symlink() or p.suffix.lower() in IGNORE_SUFFIXES:
                continue
            if name.startswith(".") and not include_hidden and name not in {".gitignore", ".env.example", ".editorconfig"}:
                continue
            try:
                size = p.stat().st_size
                rel = p.relative_to(root)
                files.append({"path": rel.as_posix(), "category": classify(rel),
                              "folder": rel.parts[0] if len(rel.parts) > 1 else "(root)",
                              "bytes": size, "ext": p.suffix.lower(), "physical_lines": None,
                              "nonempty_lines": None, "radon": None, "eslint": None})
            except OSError as exc:
                diagnostics.append(f"Stat {p}: {exc}")
    return files, diagnostics, dirs, hidden_dirs_ignored


def scan_files(root: Path, files, errors):
    functions = []
    python_analyzed = 0
    for idx, f in enumerate(files, start=1):
        ext = f["ext"]
        if ext not in TEXT_SUFFIXES:
            continue
        p = root / Path(f["path"])
        try:
            data = p.read_bytes()
            f["physical_lines"] = physical_lines(data)
            f["nonempty_lines"] = sum(bool(s.strip()) for s in data.splitlines())
            if ext != ".py":
                continue
            source = safe_text(p)
            stats = {"raw": None, "mi": None, "mi_rank": None, "halstead": None,
                     "cc_count": 0, "cc_mean": None, "cc_max": None, "cc_ranks": {}}
            try:
                raw = raw_analyze(source)
                stats["raw"] = {k: int(getattr(raw, k, 0)) for k in (
                    "loc", "lloc", "sloc", "comments", "single_comments", "multi", "blank")}
            except Exception as exc:
                errors.append(f"Radon RAW {f['path']}: {type(exc).__name__}: {exc}")
            try:
                mi = float(mi_visit(source, multi=True))
                stats["mi"] = round(mi, 4)
                stats["mi_rank"] = mi_rank(mi)
            except Exception as exc:
                errors.append(f"Radon MI {f['path']}: {type(exc).__name__}: {exc}")
            try:
                hal = h_visit(source)
                stats["halstead"] = {key: getattr(hal.total, key) for key in hal.total._fields}
                stats["halstead_functions"] = [
                    {"name": str(fn), **{k: getattr(h, k) for k in h._fields}}
                    for fn, h in hal.functions
                ]
            except Exception as exc:
                errors.append(f"Radon Halstead {f['path']}: {type(exc).__name__}: {exc}")
            try:
                blocks = cc_visit(source)
                ccs = []
                ranks = Counter()
                seen = set()
                def add_block(block, prefix=""):
                    if hasattr(block, "methods"):
                        return
                    identity = (block.lineno, block.name, getattr(block, "classname", None))
                    if identity in seen:
                        return
                    seen.add(identity)
                    score = int(block.complexity)
                    rank = cc_rank(score)
                    ranks[rank] += 1
                    ccs.append(score)
                    base_name = (f"{block.classname}.{block.name}"
                                 if getattr(block, "classname", None) else block.name)
                    qualified_name = f"{prefix}{base_name}" if prefix else base_name
                    functions.append({
                        "file": f["path"], "category": f["category"], "name": qualified_name,
                        "line": int(block.lineno), "end_line": getattr(block, "endline", None),
                        "cc": score, "rank": rank,
                        "kind": "method" if getattr(block, "is_method", False) else "function",
                    })
                    for nested in getattr(block, "closures", []):
                        add_block(nested, qualified_name + ".")
                for block in blocks:
                    add_block(block)
                stats["cc_count"] = len(ccs)
                stats["cc_mean"] = avg(ccs)
                stats["cc_max"] = max(ccs, default=None)
                stats["cc_ranks"] = dict(ranks)
            except Exception as exc:
                errors.append(f"Radon CC {f['path']}: {type(exc).__name__}: {exc}")
            f["radon"] = stats
            python_analyzed += 1
        except (OSError, ValueError, MemoryError) as exc:
            errors.append(f"Read error {f['path']}: {type(exc).__name__}: {exc}")
        if idx % 500 == 0:
            print(f"  Scanned {idx}/{len(files)} files...", flush=True)
    return functions, python_analyzed


def run_eslint(root: Path, files, errors, batch_size: int, disabled: bool):
    js = [f for f in files if f["ext"] in JS_EXT]
    if disabled:
        return {"status": "disabled", "files_eligible": len(js), "files_returned": 0,
                "failed_batches": 0, "issues": [], "summary": {}, "version": None}
    config = HERE / "eslint.config.mjs"
    cli = HERE / "node_modules" / "eslint" / "bin" / "eslint.js"
    node = shutil.which("node")
    if not config.is_file() or not cli.is_file() or not node:
        why = f"Missing config/node_modules/node: config={config.exists()}, eslint={cli.exists()}, node={bool(node)}"
        errors.append("ESLint: " + why)
        return {"status": "unavailable", "files_eligible": len(js), "files_returned": 0,
                "failed_batches": 0, "issues": [], "summary": {}, "version": None}
    try:
        version = subprocess.run([node, str(cli), "--version"], cwd=HERE, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=30).stdout.strip()
    except Exception:
        version = "unknown"
    messages = []
    file_count = 0
    failed = 0
    for start in range(0, len(js), batch_size):
        batch = js[start:start + batch_size]
        args = [node, str(cli), "--no-cache", "--no-warn-ignored",
                "--no-error-on-unmatched-pattern", "--format", "json", "--config", str(config)]
        args.extend(f["path"] for f in batch)
        try:
            proc = subprocess.run(args, cwd=root, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=300)
            if proc.returncode not in (0, 1):
                errors.append(f"ESLint batch {start // batch_size + 1}, exit={proc.returncode}: {proc.stderr[:400] or proc.stdout[:400]}")
                failed += 1
                continue
            try:
                output = json.loads(proc.stdout)
                if not isinstance(output, list): raise ValueError("Output is not a list")
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(f"ESLint batch {start // batch_size + 1}, invalid JSON: {exc}; {proc.stdout[:220]}")
                failed += 1
                continue
            for obj in output:
                raw_path = obj.get("filePath", "")
                try:
                    rel = Path(raw_path).resolve().relative_to(root).as_posix()
                except (ValueError, OSError):
                    rel = str(raw_path)
                file_count += 1
                for m in obj.get("messages", []):
                    messages.append({
                        "file": rel, "line": m.get("line"), "column": m.get("column"),
                        "end_line": m.get("endLine"), "end_column": m.get("endColumn"),
                        "severity": "error" if m.get("severity") == 2 else "warning",
                        "rule": m.get("ruleId") or "(parser/config)",
                        "message": m.get("message", ""), "fatal": bool(m.get("fatal", False)),
                    })
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"ESLint batch {start // batch_size + 1}: {type(exc).__name__}: {exc}")
            failed += 1
        print(f"  ESLint: {min(start + batch_size, len(js))}/{len(js)} files...", flush=True)
    counts = Counter(m["severity"] for m in messages)
    return {"status": "partial" if failed else "complete", "files_eligible": len(js),
            "files_returned": file_count, "failed_batches": failed,
            "issues": messages, "summary": dict(counts), "version": version}


def write_csv(path: Path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as h:
        writer = csv.DictWriter(h, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def table(headers, rows):
    return ["| " + " | ".join(map(md, headers)) + " |",
            "|" + "|".join(["---"] * len(headers)) + "|"] + [
                "| " + " | ".join(md(x) for x in row) + " |" for row in rows
            ]


def produce_report(root, out, files, functions, eslint, errors, dirs, hidden_dirs, python_analyzed, started):
    by_cat = defaultdict(list)
    by_folder = defaultdict(list)
    for f in files:
        by_cat[f["category"]].append(f)
        by_folder[f["folder"]].append(f)
    code_files = [f for f in files if f["category"] in CODE_CATS]
    py = [f for f in files if f["ext"] == ".py"]
    py_with_raw = [f for f in py if f["radon"] and f["radon"]["raw"]]
    mi_files = [f for f in py if f["radon"] and f["radon"]["mi"] is not None]
    hal_files = [f for f in py if f["radon"] and f["radon"]["halstead"]]
    all_cc = [x["cc"] for x in functions]
    rank_counts = Counter(x["rank"] for x in functions)
    loc_total = sum(f["physical_lines"] or 0 for f in code_files)
    lines_code_test = sum(f["physical_lines"] or 0 for f in code_files if f["category"] in {"py_tests", "js_tests", "ts_tests"})
    py_prod_n = len(by_cat["py_prod"])
    py_test_n = len(by_cat["py_tests"])
    ratio = py_test_n / py_prod_n if py_prod_n else None
    es_issues = eslint["issues"]
    rule_count = Counter(m["rule"] for m in es_issues)
    issue_by_file = Counter(m["file"] for m in es_issues)
    now = datetime.now(timezone.utc)
    duration = (now - started).total_seconds()
    raw_sums = {name: sum(f["radon"]["raw"].get(name, 0) for f in py_with_raw)
                for name in ("loc", "sloc", "lloc", "comments", "single_comments", "multi", "blank")}
    mi_values = [f["radon"]["mi"] for f in mi_files]
    hal_names = ["h1", "h2", "N1", "N2", "vocabulary", "length",
                 "calculated_length", "volume", "difficulty", "effort", "time", "bugs"]
    hal_stats = {}
    for key in hal_names:
        xs = [float(f["radon"]["halstead"].get(key, 0)) for f in hal_files]
        hal_stats[key] = {"file_mean": avg(xs), "file_median": median(xs),
                          "file_max": max(xs, default=None),
                          "file_sum_independent_estimates": sum(xs) if key in {"volume", "effort", "time", "bugs"} else None}
    metadata = {
        "generated_at_utc": now.isoformat(timespec="seconds"),
        "codeaudit_version": VERSION, "project": str(root), "output": str(out),
        "duration_seconds": round(duration, 2),
        "radon_version": importlib.metadata.version("radon") if "radon" in sys.modules else "unknown",
        "eslint_version": eslint["version"],
        "measurement_notes": {
            "code_lines": "physical lines in CODE_CATS, including blanks and comments; excluding docs",
            "python_sloc_lloc": "Radon only, not applicable to JavaScript",
            "ratio": "Python test files / Python src files; not test coverage",
            "halstead": "per-file metrics; distinct operators/operands should not be globally summed",
            "excluded_dirs": sorted(IGNORE_DIRS),
        },
    }
    payload = {
        "metadata": metadata,
        "summary": {
            "files": len(files), "directories_including_root": dirs,
            "hidden_dirs_ignored": hidden_dirs, "bytes": sum(f["bytes"] for f in files),
            "code_files": len(code_files), "code_physical_lines": loc_total,
            "test_physical_lines": lines_code_test,
            "python_prod_files": py_prod_n, "python_test_files": py_test_n,
            "python_test_file_ratio": ratio,
            "python_analyzed": python_analyzed, "python_raw_analyzed": len(py_with_raw),
            "python_mi_analyzed": len(mi_files), "python_halstead_analyzed": len(hal_files),
            "python_raw_totals": raw_sums,
            "cc": {"count_functions_methods": len(functions), "mean": avg(all_cc),
                   "median": median(all_cc), "max": max(all_cc, default=None),
                   "ranks": dict(rank_counts)},
            "mi": {"file_mean": avg(mi_values), "file_median": median(mi_values),
                   "file_min": min(mi_values, default=None), "file_max": max(mi_values, default=None)},
            "halstead": hal_stats,
            "eslint": {k: v for k, v in eslint.items() if k != "issues"},
            "errors_count": len(errors),
        },
        "categories": {k: {"files": len(v), "bytes": sum(f["bytes"] for f in v),
                          "physical_lines": sum(f["physical_lines"] or 0 for f in v)}
                       for k, v in by_cat.items()},
        "folders": {k: {"files": len(v), "bytes": sum(f["bytes"] for f in v),
                       "code_lines": sum(f["physical_lines"] or 0 for f in v if f["category"] in CODE_CATS),
                       "python_files": sum(f["ext"] == ".py" for f in v),
                       "js_files": sum(f["ext"] in JS_EXT for f in v)} for k, v in by_folder.items()},
        "files": files, "cc_functions": functions,
        "eslint_issues": es_issues, "diagnostics": errors,
    }
    (out / "metrics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    write_csv(out / "issues.csv", ["file", "line", "column", "end_line", "end_column", "severity", "rule", "message", "fatal"], es_issues)
    write_csv(out / "functions.csv", ["file", "category", "name", "kind", "line", "end_line", "cc", "rank"],
              sorted(functions, key=lambda r: (-r["cc"], r["file"], r["line"])))
    write_csv(out / "files.csv", ["path", "category", "folder", "bytes", "physical_lines", "nonempty_lines", "py_sloc", "py_lloc", "py_cc_max", "py_mi", "halstead_volume", "halstead_difficulty"], [
        {**f,
         "py_sloc": (f["radon"] or {}).get("raw", {}).get("sloc") if (f["radon"] or {}).get("raw") else None,
         "py_lloc": (f["radon"] or {}).get("raw", {}).get("lloc") if (f["radon"] or {}).get("raw") else None,
         "py_cc_max": (f["radon"] or {}).get("cc_max"),
         "py_mi": (f["radon"] or {}).get("mi"),
         "halstead_volume": ((f["radon"] or {}).get("halstead") or {}).get("volume"),
         "halstead_difficulty": ((f["radon"] or {}).get("halstead") or {}).get("difficulty"),
        } for f in files
    ])
    report = [
        "# CodeAudit — Detailed Source Code Quality Report", "",
        f"**Project:** `{md(root)}`  ",
        f"**Generated (UTC):** {now.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**CodeAudit:** {VERSION} · **Radon:** {metadata['radon_version']} · **ESLint:** {eslint['version'] or 'unavailable'}  ",
        f"**Scan Duration:** {fmt(duration, 1)} s · **ESLint Status:** {eslint['status']}  ",
        "", "> **Static analysis, read-only.** Findings represent static metrics and linting heuristics, not formal security proofs, dynamic testing results, or automated architecture verification.",
        "", "## 1. Summary", "",
    ]
    report.extend(table(["Metric", "Value"], [
        ["Files in scope", fmt(len(files))], ["Directories in scope (incl. root)", fmt(dirs)],
        ["Code and test files", fmt(len(code_files))],
        ["Physical code/test lines (all)", fmt(loc_total)],
        ["Lines in test files", fmt(lines_code_test)],
        ["Python production files (src/)", fmt(py_prod_n)],
        ["Python test files", fmt(py_test_n)],
        ["Python Test / Prod file ratio", fmt(ratio, 3)],
        ["Python files analyzed by Radon", fmt(python_analyzed)],
        ["Functions and methods analyzed (CC)", fmt(len(functions))],
        ["ESLint issues", fmt(len(es_issues))],
        ["Run diagnostics / warnings", fmt(len(errors))],
    ]))
    report.extend(["", "## 2. File Structure — Categories", ""])
    report.extend(table(["Category", "Files", "Physical Lines", "Size (MiB)"], [
        [label, fmt(len(by_cat[key])), fmt(sum(f["physical_lines"] or 0 for f in by_cat[key])),
         fmt(sum(f["bytes"] for f in by_cat[key]) / (1024 * 1024), 2)] for key, label in GROUPS
    ]))
    report.extend(["", "## 3. Directory Structure (Top Level)", ""])
    report.extend(table(["Directory", "Files", "Python", "JS/JSX", "Physical Code Lines"], [
        [f"`{md(folder)}`", fmt(len(items)), fmt(sum(f["ext"] == ".py" for f in items)),
         fmt(sum(f["ext"] in JS_EXT for f in items)),
         fmt(sum(f["physical_lines"] or 0 for f in items if f["category"] in CODE_CATS))]
        for folder, items in sorted(by_folder.items(), key=lambda item: -len(item[1]))
    ]))
    report.extend(["", "## 4. Radon RAW — Python Metrics", "",
                   f"Successfully analyzed RAW files: **{len(py_with_raw)}** out of **{len(py)}** `.py` files. SLOC/LLOC metrics apply **strictly to Python**.", ""])
    report.extend(table(["Radon Metric", "Total"], [[key.upper(), fmt(raw_sums[key])] for key in
                   ("loc", "sloc", "lloc", "comments", "single_comments", "multi", "blank")]))
    report.extend(["", "Breakdown by Python group:", ""])
    report.extend(table(["Group", "RAW Files", "LOC", "SLOC", "LLOC", "Comments", "Blank Lines"], [
        [LABELS[key], fmt(sum(bool(f["radon"] and f["radon"]["raw"]) for f in by_cat[key])),
         *[fmt(sum(f["radon"]["raw"][n] for f in by_cat[key] if f["radon"] and f["radon"]["raw"]))
           for n in ("loc", "sloc", "lloc", "comments", "blank")]]
        for key in ("py_prod", "py_tests", "py_other")
    ]))
    report.extend(["", "## 5. Cyclomatic Complexity (CC) — Functions and Methods", ""])
    report.extend(table(["Metric", "Value"], [
        ["Total Functions / Methods", fmt(len(functions))],
        ["Average CC", fmt(avg(all_cc), 2)], ["Median CC", fmt(median(all_cc), 2)],
        ["Highest CC", fmt(max(all_cc, default=None))],
    ] + [[f"Rank {r}", fmt(rank_counts[r])] for r in "ABCDEF"]))
    report.extend(["", "**Top 30 Most Complex Functions / Methods:**", ""])
    report.extend(table(["File", "Function/Method", "Line", "CC", "Rank"], [
        [f"`{x['file']}`", f"`{x['name']}`", x["line"], x["cc"], x["rank"]]
        for x in sorted(functions, key=lambda x: -x["cc"])[:30]
    ]))
    report.extend(["", "## 6. Maintainability Index (MI) — Python", "",
                   "Radon scale: A = MI > 19, B = 9 < MI ≤ 19, C = MI ≤ 9.", ""])
    report.extend(table(["Metric", "Value"], [
        ["Analyzed Files", fmt(len(mi_values))], ["Average MI (per file)", fmt(avg(mi_values), 2)],
        ["Median MI (per file)", fmt(median(mi_values), 2)],
        ["Minimum", fmt(min(mi_values, default=None), 2)],
        ["Maximum", fmt(max(mi_values, default=None), 2)],
    ] + [[f"Files in Rank {rank}", fmt(sum(f["radon"]["mi_rank"] == rank for f in mi_files))]
         for rank in "ABC"]))
    report.extend(["", "**Top 30 Files with Lowest MI:**", ""])
    report.extend(table(["File", "MI", "Rank", "SLOC"], [
        [f"`{x['path']}`", fmt(x["radon"]["mi"], 2), x["radon"]["mi_rank"],
         fmt((x["radon"]["raw"] or {}).get("sloc"))]
        for x in sorted(mi_files, key=lambda x: x["radon"]["mi"])[:30]
    ]))
    report.extend(["", "## 7. Halstead — Metrics (Python)", "",
                   "Metrics evaluated **per file**. Distinct operators/operands (h1/h2), vocabulary and difficulty must **not be summed** globally. `time` and `bugs` are model heuristics.", ""])
    description = {
        "h1": "h1 — Distinct Operators", "h2": "h2 — Distinct Operands",
        "N1": "N1 — Total Operators", "N2": "N2 — Total Operands",
        "vocabulary": "Vocabulary (h1+h2)", "length": "Length (N1+N2)",
        "calculated_length": "Calculated Length", "volume": "Volume (V)",
        "difficulty": "Difficulty (D)", "effort": "Effort (E)",
        "time": "Time (T) — Estimated Seconds", "bugs": "Bugs (B) — Estimated Defect Count",
    }
    report.extend(table(["Metric", "Mean/File", "Median/File", "Max/File"], [
        [description[key], fmt(hal_stats[key]["file_mean"], 2), fmt(hal_stats[key]["file_median"], 2),
         fmt(hal_stats[key]["file_max"], 2)] for key in hal_names
    ]))
    report.extend(["", "**Top 30 Files by Halstead Volume:**", ""])
    report.extend(table(["File", "Volume (V)", "Difficulty (D)", "Effort (E)", "Est. Bugs (B)"], [
        [f"`{f['path']}`", *[fmt(f["radon"]["halstead"][k], 2)
                             for k in ("volume", "difficulty", "effort", "bugs")]]
        for f in sorted(hal_files, key=lambda x: -x["radon"]["halstead"]["volume"])[:30]
    ]))
    report.extend(["", "## 8. ESLint, SonarJS & React Hooks", "",
                   f"Status: **{eslint['status']}** · Eligible Files: **{fmt(eslint['files_eligible'])}** · Returned Files: **{fmt(eslint['files_returned'])}** · Failed Batches: **{eslint['failed_batches']}**.", ""])
    report.extend(table(["Category", "Count"], [
        ["Total Issues", fmt(len(es_issues))],
        ["Errors", fmt(eslint["summary"].get("error", 0))],
        ["Warnings", fmt(eslint["summary"].get("warning", 0))],
        ["Fatal / Parser Errors", fmt(sum(bool(m["fatal"]) for m in es_issues))],
    ]))
    report.extend(["", "**Most Frequent Rules Triggered:**", ""])
    report.extend(table(["Rule", "Count"], [[f"`{rule}`", fmt(c)] for rule, c in rule_count.most_common(25)]))
    report.extend(["", "**Files with Highest Issue Count:**", ""])
    report.extend(table(["File", "Issues"], [[f"`{file}`", fmt(c)] for file, c in issue_by_file.most_common(25)]))
    report.extend(["", "**30 Example Issues (full list in `issues.csv`):**", ""])
    report.extend(table(["File:Line", "Severity", "Rule", "Message"], [
        [f"`{m['file']}:{m['line'] or '?'}`", m["severity"], f"`{m['rule']}`", md(m["message"])[:140]]
        for m in sorted(es_issues, key=lambda m: (m["severity"] != "error", m["file"], m["line"] or 0))[:30]
    ]))
    report.extend(["", "## 9. Observations & Scope", "",
                   "- Test/Prod ratio measures **file counts**, not line percentage or branch test coverage.",
                   "- MI is a heuristic maintainability index, not a strict architectural verdict.",
                   "- Cyclomatic Complexity (Python) and Cognitive Complexity (ESLint SonarJS) evaluate different dimensions.",
                   "- Halstead `time` and `bugs` are model-derived approximations.",
                   "- Physical code lines include comments and blank lines; Radon provides logical SLOC/LLOC specifically for Python.",
                   "- The scan is read-only and runs independently of Git status.",
                   "", "## 10. Diagnostics & Completeness", "",
                   f"Issues encountered during run: **{len(errors)}**. Full diagnostic details recorded in `metrics.json`.", ""])
    if errors:
        report.extend([f"- {md(e)[:260]}" for e in errors[:80]])
        if len(errors) > 80:
            report.append(f"- ... and {len(errors) - 80} additional warnings/errors (see JSON).")
    else:
        report.append("No errors encountered during execution.")
    report.extend(["", "## 11. Artifacts Generated", "",
                   "- `report.md` — comprehensive summary report.",
                   "- `metrics.json` — complete dataset including per-file Halstead metrics and per-function CC.",
                   "- `files.csv` — individual file-level metrics.",
                   "- `functions.csv` — all analyzed Python functions/methods with CC scores.",
                   "- `issues.csv` — full listing of ESLint/SonarJS findings.", ""])
    (out / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload["summary"]


def main():
    parser = argparse.ArgumentParser(description="CodeAudit — Local Radon/ESLint Source Code Quality Audit (No Git required)")
    parser.add_argument("project", type=Path, help="Path to the project directory to analyze")
    parser.add_argument("--out", type=Path, help="Output directory for reports (must be outside the target project)")
    parser.add_argument("--no-eslint", action="store_true", help="Skip JavaScript ESLint analysis")
    parser.add_argument("--include-work", action="store_true", help="Include .work directory in analysis")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden directories in analysis")
    parser.add_argument("--batch-size", type=int, default=40, help="Number of JS files per ESLint batch (default: 40)")
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    if not root.is_dir(): parser.error(f"Directory not found: {root}")
    if args.batch_size < 1 or args.batch_size > 100: parser.error("--batch-size must be between 1 and 100")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = (args.out.expanduser().resolve() if args.out else
           (HERE / "reports" / f"{root.name}_{stamp}").resolve())
    if out == root or root in out.parents:
        parser.error("--out cannot point to a path inside the scanned project")
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    print(f"CodeAudit {VERSION}\nTarget Project: {root}\nOutput Directory: {out}", flush=True)
    files, errors, dirs, hidden_dirs = file_inventory(root, out, args.include_work, args.include_hidden)
    print(f"Discovered files: {len(files)}; directories: {dirs}", flush=True)
    functions, pycount = scan_files(root, files, errors)
    print(f"Radon: analyzed {pycount} Python files, {len(functions)} functions/methods", flush=True)
    eslint = run_eslint(root, files, errors, args.batch_size, args.no_eslint)
    summary = produce_report(root, out, files, functions, eslint, errors, dirs, hidden_dirs, pycount, started)
    print("\nAudit completed.\n" + "\n".join(str(out / name) for name in
          ("report.md", "metrics.json", "files.csv", "functions.csv", "issues.csv")))
    print(f"Total files: {summary['files']}; Code lines: {summary['code_physical_lines']}; Scan diagnostics: {summary['errors_count']}")
    if errors or eslint["status"] in {"partial", "unavailable"}:
        print("NOTE: partial scan or diagnostics reported — see Section 10 of report.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
