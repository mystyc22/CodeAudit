#!/usr/bin/env python3
"""CodeAudit: read-only local Python + JavaScript/React source-code audit.

Dependencies: Python 3.10+, radon 6.x, Node.js, ESLint 9 and plugins.
Optional (2.2): lizard, vulture, bandit, pip-audit (internet, only with --pip-audit), echarts.min.js.
Run: python audit.py "C:\path\to\your-project"

Output: report.md, metrics.json, issues.csv, functions.csv, files.csv.
All output goes to CodeAudit/reports/ (or --out), NEVER to the source project.
Git metadata are read-only (local only). No rewriting files, lint --fix, or eslint cache.
"""
from __future__ import annotations

import argparse
import fnmatch
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
    print("BRAK RADON: zainstaluj poleceniem: python -m pip install radon", file=sys.stderr)
    raise SystemExit(2)

VERSION = "2.2.0"
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
FRONTENDS = {"client-app", "hub-app", "courier-viz", "web-common"}
IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", ".tox", ".nox", ".next", ".nuxt", ".turbo",
    "dist", "build", "coverage", "htmlcov", ".cache", ".idea", ".work", "vendor",
    ".parcel-cache", ".svelte-kit", ".angular", ".gradle", "site-packages", "var",
}
IGNORE_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp", ".swp", ".swo", ".orig"}
TEXT_SUFFIXES = {".py"} | JS_EXT | TS_EXT | STYLE_EXT | HTML_EXT | SCRIPTS | DOCS | CONFIG | {".sql", ".graphql", ".gql", ".vue", ".svelte"}
CODE_CATS = {"py_prod", "py_tests", "py_other", "js_prod", "js_tests", "js_other", "ts_prod", "ts_tests", "styles", "html", "scripts", "other_code"}
GROUPS = [
    ("py_prod", "Python — produkcja"), ("py_tests", "Python — testy"),
    ("py_other", "Python — narzędzia"), ("js_prod", "JS/JSX — frontend"),
    ("js_tests", "JS/JSX — testy"), ("js_other", "JS/JSX — pozostałe"),
    ("ts_prod", "TypeScript — produkcja"), ("ts_tests", "TypeScript — testy"),
    ("styles", "CSS/SCSS"), ("html", "HTML"), ("scripts", "Skrypty systemowe"),
    ("other_code", "Inny kod/SQL"), ("docs", "Dokumentacja"),
    ("config", "Konfiguracja"), ("assets", "Zasoby binarne/grafika"),
    ("databases", "Bazy danych"), ("other", "Pozostałe"),
]
LABELS = dict(GROUPS)
DEFAULT_EXCLUDES = []


def load_settings() -> dict:
    path = HERE / "audit-settings.json"
    if not path.is_file():
        return {"excluded_files": list(DEFAULT_EXCLUDES)}
    try:
        settings = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(settings, dict):
            raise ValueError("konfiguracja musi być obiektem JSON")
        rules = settings.get("excluded_files", DEFAULT_EXCLUDES)
        if not isinstance(rules, list):
            raise ValueError("excluded_files musi być listą")
        return {"excluded_files": rules}
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Błędny audit-settings.json: {exc}")


def exclusion_reason(rel: Path, rules) -> str | None:
    rel_str = rel.as_posix().casefold()
    for rule in rules:
        if isinstance(rule, str):
            pattern, reason = rule, "Ręcznie wyłączony z audytu"
        elif isinstance(rule, dict):
            pattern = rule.get("pattern", "")
            reason = rule.get("reason") or "Ręcznie wyłączony z audytu"
        else:
            continue
        if pattern and fnmatch.fnmatchcase(rel_str, str(pattern).replace("\\", "/").casefold()):
            return str(reason)
    return None


def inventory_var(root: Path) -> dict:
    """Tylko inwentaryzacja var — nie czyta treści plików, nie uruchamia ESLint/Radon."""
    folder = root / "var"
    result = {"path": "var", "present": folder.is_dir(), "files": 0, "directories": 0,
              "bytes": 0, "by_extension": {}, "top_subdirs": {}, "purpose": "Generated/runtime artifacts; excluded from source-code audit"}
    if not folder.is_dir():
        return result
    by_ext = Counter()
    by_top = Counter()
    for dirpath, dirnames, filenames in os.walk(folder, topdown=True, followlinks=False):
        dirnames[:] = [n for n in dirnames if not (Path(dirpath) / n).is_symlink()]
        result["directories"] += 1
        for name in filenames:
            fp = Path(dirpath) / name
            if fp.is_symlink():
                continue
            try:
                size = fp.stat().st_size
            except OSError:
                continue
            result["files"] += 1
            result["bytes"] += size
            by_ext[fp.suffix.lower() or "(bez rozszerzenia)"] += 1
            rel = fp.relative_to(folder)
            by_top[rel.parts[0] if len(rel.parts) > 1 else "(root)"] += 1
    result["by_extension"] = dict(by_ext.most_common(25))
    result["top_subdirs"] = dict(by_top.most_common(25))
    return result



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
        return (f"{v:,.{digits}f}" if digits else f"{round(v):,}").replace(",", " ")
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


def file_inventory(root: Path, output: Path, include_work: bool, include_hidden: bool, exclusions):
    files = []
    diagnostics = []
    hidden_dirs_ignored = 0
    excluded = []
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
                reason = exclusion_reason(rel, exclusions)
                if reason:
                    excluded.append({"path": rel.as_posix(), "reason": reason, "bytes": size})
                    continue
                files.append({"path": rel.as_posix(), "category": classify(rel),
                              "folder": rel.parts[0] if len(rel.parts) > 1 else "(root)",
                              "bytes": size, "ext": p.suffix.lower(), "physical_lines": None,
                              "nonempty_lines": None, "radon": None, "eslint": None})
            except OSError as exc:
                diagnostics.append(f"Stat {p}: {exc}")
    return files, diagnostics, dirs, hidden_dirs_ignored, excluded


def scan_files(root: Path, files, errors):
    functions = []
    python_analyzed = 0
    for idx, f in enumerate(files, start=1):
        ext = f["ext"]
        if ext not in TEXT_SUFFIXES:
            continue
        p = root / Path(f["path"])
        try:
            # 100MB docs aren't typical but code may include large generated blobs.
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
                    # Class and method are each returned by Radon; skip class aggregate
                    # and use a stable identity to prevent counting methods twice.
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
            errors.append(f"Odczyt {f['path']}: {type(exc).__name__}: {exc}")
        if idx % 500 == 0:
            print(f"  Przeskanowano {idx}/{len(files)} plików...", flush=True)
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
        why = f"Brak konfiguracji/node_modules/node: config={config.exists()}, eslint={cli.exists()}, node={bool(node)}"
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
    # File arguments relative to project root: ESLint config uses matching globs.
    for start in range(0, len(js), batch_size):
        batch = js[start:start + batch_size]
        args = [node, str(cli), "--no-cache", "--no-warn-ignored",
                "--no-error-on-unmatched-pattern", "--format", "json", "--config", str(config)]
        args.extend(f["path"] for f in batch)
        try:
            proc = subprocess.run(args, cwd=root, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=300)
            if proc.returncode not in (0, 1):
                errors.append(f"ESLint partia {start // batch_size + 1}, exit={proc.returncode}: {proc.stderr[:400] or proc.stdout[:400]}")
                failed += 1
                continue
            try:
                output = json.loads(proc.stdout)
                if not isinstance(output, list): raise ValueError("JSON to nie lista")
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(f"ESLint partia {start // batch_size + 1}, niepoprawny JSON: {exc}; {proc.stdout[:220]}")
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
            errors.append(f"ESLint partia {start // batch_size + 1}: {type(exc).__name__}: {exc}")
            failed += 1
        print(f"  ESLint: {min(start + batch_size, len(js))}/{len(js)} plików...", flush=True)
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


def produce_report(root, out, files, functions, eslint, errors, dirs, hidden_dirs, python_analyzed, started, extras=None):
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
    # Halstead metrics are evaluated PER FILE. Aggregate distinct-operator counts cannot
    # be added as if they were a global distinct vocabulary. Use per-file distributions.
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
        "radon_version": importlib.metadata.version("radon"),
        "eslint_version": eslint["version"],
        "measurement_notes": {
            "code_lines": "fizyczne linie plikow z CODE_CATS, z pustymi i komentarzami; bez dokumentacji",
            "python_sloc_lloc": "tylko Radon, nie dotyczy JavaScript",
            "ratio": "liczba plikow Python tests / liczba plikow Python src; NIE pokrycie testami",
            "halstead": "metryki na plik, nie sumowac h1/h2/vocabulary jako globalnych wartosci",
            "comparison": "tylko poprzedni metrics.json, dopasowany do aktualnych wyłączeń",
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
        "extras": extras or {},
    }
    for key, pkg in (("lizard", "lizard"), ("vulture", "vulture"), ("bandit", "bandit"), ("pip_audit", "pip-audit")):
        metadata[f"{key}_version"] = (extras or {}).get(key, {}).get("version")
    (out / "metrics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    write_csv(out / "issues.csv", ["file", "line", "column", "end_line", "end_column", "severity", "rule", "message", "fatal"], es_issues)
    write_csv(out / "functions.csv", ["file", "category", "name", "kind", "line", "end_line", "cc", "rank"],
              sorted(functions, key=lambda r: (-r["cc"], r["file"], r["line"])))
    ex = extras or {}
    if ex.get("lizard", {}).get("functions"):
        write_csv(out / "js_functions.csv", ["file", "category", "name", "line", "end_line", "cc", "nloc", "params", "tokens"],
                  sorted(ex["lizard"]["functions"], key=lambda r: (-r["cc"], r["file"], r["line"])))
    if ex.get("bandit", {}).get("issues"):
        write_csv(out / "security_bandit.csv", ["file", "category", "line", "severity", "confidence", "test_id", "test_name", "cwe", "text"],
                  sorted(ex["bandit"]["issues"], key=lambda r: ({"HIGH": 0, "MEDIUM": 1}.get(r["severity"], 2), r["file"], r["line"])))
    if ex.get("pip_audit", {}).get("vulnerabilities"):
        write_csv(out / "security_dependencies.csv", ["requirements", "package", "version", "id", "aliases", "fix_versions", "description"],
                  [{**v, "aliases": "; ".join(v["aliases"]), "fix_versions": "; ".join(v["fix_versions"])} for v in ex["pip_audit"]["vulnerabilities"]])
    if ex.get("vulture", {}).get("items"):
        write_csv(out / "dead_code.csv", ["file", "category", "line", "type", "name", "confidence"], ex["vulture"]["items"])
    if ex.get("duplication", {}).get("blocks"):
        write_csv(out / "duplication.csv", ["a", "a_from", "a_to", "b", "b_from", "b_to", "lines"], ex["duplication"]["blocks"])
    if ex.get("deps", {}).get("all_edges"):
        write_csv(out / "dependencies.csv", ["from", "to"], [{"from": a_, "to": b_} for a_, b_ in ex["deps"]["all_edges"]])
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
        "# CodeAudit — szczegółowy raport jakości kodu", "",
        f"**Projekt:** `{md(root)}`  ",
        f"**Data (UTC):** {now.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**CodeAudit:** {VERSION} · **Radon:** {metadata['radon_version']} · **ESLint:** {eslint['version'] or 'niedostępny'}  ",
        f"**Czas analizy:** {fmt(duration, 1)} s · **Status ESLint:** {eslint['status']}  ",
        "", "> **Analiza statyczna, tylko odczyt.** Wyniki nie dowodzą poprawności biznesowej, bezpieczeństwa ani pokrycia testami. Report nie jest automatyczną oceną Clean Architecture.",
        "", "## 1. Podsumowanie", "",
    ]
    report.extend(table(["Metryka", "Wynik"], [
        ["Pliki w zakresie", fmt(len(files))], ["Katalogi w zakresie (z root)", fmt(dirs)],
        ["Pliki kodu i testów", fmt(len(code_files))],
        ["Wszystkie fizyczne linie kodu/testów", fmt(loc_total)],
        ["Linie w plikach testowych", fmt(lines_code_test)],
        ["Python produkcyjny (pliki src/)", fmt(py_prod_n)],
        ["Python testy (pliki)", fmt(py_test_n)],
        ["Stosunek liczby plików testów/prod Python", fmt(ratio, 3)],
        ["Python — pliki przeanalizowane przez Radon", fmt(python_analyzed)],
        ["Funkcje i metody z CC", fmt(len(functions))],
        ["Problemy ESLint", fmt(len(es_issues))],
        ["Błędy/ostrzeżenia przebiegu", fmt(len(errors))],
    ]))
    report.extend(["", "## 3. Struktura plików — kategorie", ""])
    report.extend(table(["Kategoria", "Pliki", "Fizyczne linie", "Rozmiar MiB"], [
        [label, fmt(len(by_cat[key])), fmt(sum(f["physical_lines"] or 0 for f in by_cat[key])),
         fmt(sum(f["bytes"] for f in by_cat[key]) / (1024 * 1024), 2)] for key, label in GROUPS
    ]))
    report.extend(["", "## 4. Struktura katalogów (pierwszy poziom)", ""])
    report.extend(table(["Katalog", "Pliki", "Python", "JS/JSX", "Fizyczne linie kodu"], [
        [f"`{md(folder)}`", fmt(len(items)), fmt(sum(f["ext"] == ".py" for f in items)),
         fmt(sum(f["ext"] in JS_EXT for f in items)),
         fmt(sum(f["physical_lines"] or 0 for f in items if f["category"] in CODE_CATS))]
        for folder, items in sorted(by_folder.items(), key=lambda item: -len(item[1]))
    ]))
    report.extend(["", "## 5. Radon RAW — dokładne metryki Pythona", "",
                   f"Poprawnie przeanalizowanych plików RAW: **{len(py_with_raw)}** z **{len(py)}** plików `.py`. Metryki SLOC/LLOC dotyczą **wyłącznie Pythona**.", ""])
    report.extend(table(["Metryka Radon", "Łącznie"], [[key.upper(), fmt(raw_sums[key])] for key in
                   ("loc", "sloc", "lloc", "comments", "single_comments", "multi", "blank")]))
    report.extend(["", "Rozbicie według grup Pythona:", ""])
    report.extend(table(["Grupa", "Pliki RAW", "LOC", "SLOC", "LLOC", "Komentarze", "Wiersze puste"], [
        [LABELS[key], fmt(sum(bool(f["radon"] and f["radon"]["raw"]) for f in by_cat[key])),
         *[fmt(sum(f["radon"]["raw"][n] for f in by_cat[key] if f["radon"] and f["radon"]["raw"]))
           for n in ("loc", "sloc", "lloc", "comments", "blank")]]
        for key in ("py_prod", "py_tests", "py_other")
    ]))
    report.extend(["", "## 6. Cyclomatic Complexity — funkcje i metody", ""])
    report.extend(table(["Miara", "Wynik"], [
        ["Liczba funkcji i metod", fmt(len(functions))],
        ["Średnia CC", fmt(avg(all_cc), 2)], ["Mediana CC", fmt(median(all_cc), 2)],
        ["Najwyższa CC", fmt(max(all_cc, default=None))],
    ] + [[f"Klasa {r}", fmt(rank_counts[r])] for r in "ABCDEF"]))
    report.extend(["", "**30 najbardziej złożonych funkcji/metod:**", ""])
    report.extend(table(["Plik", "Funkcja/metoda", "Linia", "CC", "Ocena"], [
        [f"`{x['file']}`", f"`{x['name']}`", x["line"], x["cc"], x["rank"]]
        for x in sorted(functions, key=lambda x: -x["cc"])[:30]
    ]))
    report.extend(["", "## 7. Maintainability Index (MI) — Python", "",
                   "Radon: A = MI > 19, B = 9 < MI ≤ 19, C = MI ≤ 9. Wysoki MI nie dowodzi bezpieczeństwa ani poprawności.", ""])
    report.extend(table(["Miara", "Wynik"], [
        ["Przeanalizowane pliki", fmt(len(mi_values))], ["Średnia MI (na plik)", fmt(avg(mi_values), 2)],
        ["Mediana MI (na plik)", fmt(median(mi_values), 2)],
        ["Minimum", fmt(min(mi_values, default=None), 2)],
        ["Maksimum", fmt(max(mi_values, default=None), 2)],
    ] + [[f"Pliki w klasie {rank}", fmt(sum(f["radon"]["mi_rank"] == rank for f in mi_files))]
         for rank in "ABC"]))
    report.extend(["", "**30 plików o najniższym MI:**", ""])
    report.extend(table(["Plik", "MI", "Klasa", "SLOC"], [
        [f"`{x['path']}`", fmt(x["radon"]["mi"], 2), x["radon"]["mi_rank"],
         fmt((x["radon"]["raw"] or {}).get("sloc"))]
        for x in sorted(mi_files, key=lambda x: x["radon"]["mi"])[:30]
    ]))
    report.extend(["", "## 8. Halstead — pełny zestaw 12 metryk (Python)", "",
                   "Wartości liczone **osobno dla każdego pliku**. Unikalnych operatorów/operandów (h1/h2), słownika ani trudności **nie należy sumować** jako jednej miary całego projektu. `time` i `bugs` to wskaźniki heurystyczne, a nie realny nakład pracy lub przewidywana liczba defektów.", ""])
    description = {
        "h1": "h1 — unikalne operatory", "h2": "h2 — unikalne operandy",
        "N1": "N1 — operatory łącznie", "N2": "N2 — operandy łącznie",
        "vocabulary": "Vocabulary (h1+h2)", "length": "Length (N1+N2)",
        "calculated_length": "Calculated length", "volume": "Volume (V)",
        "difficulty": "Difficulty (D)", "effort": "Effort (E)",
        "time": "Time (T) — sekundy modelowe", "bugs": "Bugs (B) — estymator",
    }
    report.extend(table(["Metryka", "Średnia/plik", "Mediana/plik", "Maks./plik"], [
        [description[key], fmt(hal_stats[key]["file_mean"], 2), fmt(hal_stats[key]["file_median"], 2),
         fmt(hal_stats[key]["file_max"], 2)] for key in hal_names
    ]))
    report.extend(["", "**30 plików o największej objętości Halsteada:**", ""])
    report.extend(table(["Plik", "V", "D", "E", "B (heurystyka)"], [
        [f"`{f['path']}`", *[fmt(f["radon"]["halstead"][k], 2)
                            for k in ("volume", "difficulty", "effort", "bugs")]]
        for f in sorted(hal_files, key=lambda x: -x["radon"]["halstead"]["volume"])[:30]
    ]))
    report.extend(["", "## 9. ESLint, SonarJS i React Hooks", "",
                   f"Status: **{eslint['status']}** · Pliki kwalifikujące się do ESLint: **{fmt(eslint['files_eligible'])}** · Wyniki dla plików: **{fmt(eslint['files_returned'])}** · Nieudane partie: **{eslint['failed_batches']}**. Analiza obejmuje JS/JSX/MJS/CJS, **bez TS/TSX**, które wymagają osobnego parsera.", ""])
    report.extend(table(["Pozycja", "Liczba"], [
        ["Wszystkie zgłoszenia", fmt(len(es_issues))],
        ["Błędy", fmt(eslint["summary"].get("error", 0))],
        ["Ostrzeżenia", fmt(eslint["summary"].get("warning", 0))],
        ["Błędy fatalne / parsera", fmt(sum(bool(m["fatal"]) for m in es_issues))],
    ]))
    report.extend(["", "**Najczęściej zgłaszane reguły:**", ""])
    report.extend(table(["Reguła", "Liczba"], [[f"`{rule}`", fmt(c)] for rule, c in rule_count.most_common(25)]))
    report.extend(["", "**Pliki z największą liczbą zgłoszeń:**", ""])
    report.extend(table(["Plik", "Zgłoszenia"], [[f"`{file}`", fmt(c)] for file, c in issue_by_file.most_common(25)]))
    report.extend(["", "**30 przykładowych zgłoszeń (pełna lista w `issues.csv`):**", ""])
    report.extend(table(["Plik:linia", "Poziom", "Reguła", "Komunikat"], [
        [f"`{m['file']}:{m['line'] or '?'}`", m["severity"], f"`{m['rule']}`", md(m["message"])[:140]]
        for m in sorted(es_issues, key=lambda m: (m["severity"] != "error", m["file"], m["line"] or 0))[:30]
    ]))
    report.extend(["", "## 10. Obserwacje i interpretacja", "",
                   "- Test/Prod ratio mierzy **udział plików**, a nie procent pokrycia testami.",
                   "- MI jest heurystyczną oceną utrzymywalności, nie wynikiem audytu architektonicznego.",
                   "- CC i Cognitive Complexity mierzą różne właściwości: pierwszy pochodzi z Radona (Python), drugi z reguł SonarJS (JavaScript).",
                   "- Halstead `time`/`bugs` nie stanowią wiarygodnych prognoz czasu lub błędów w rzeczywistym projekcie.",
                   "- Statyczny audyt nie zastępuje uruchomienia testów, profilowania, audytu bezpieczeństwa ani przeglądu projektu systemowego.",
                   "- Fizyczne linie kodu obejmują komentarze i puste wiersze; dla Pythona dokładne SLOC/LLOC są podane osobno.",
                   "- Historyczne LOC mogły mieć inny zakres. Porównanie trendu wymaga uruchomienia tego samego analizatora na kolejnych rewizjach.",
                   "- W tabeli historycznej Dokumentacja oznacza wyłącznie pliki `.md`; sekcja struktury dokumentacji uwzględnia także inne formaty.",
                   "- Przebieg nie jest migawką atomową: jeśli inny agent jednocześnie edytuje pliki, część wyników może pochodzić z różnych chwil.",
                   "- ESLint stosuje zestaw reguł audytowych; nie wszystkie zgłoszenia muszą oznaczać błąd wykonania.",
                   "", "## 11. Diagnostyka kompletności analizy", "",
                   f"Problemy napotkane podczas skanowania: **{len(errors)}**. Pełne dane znajdują się w `metrics.json`.", ""])
    if errors:
        report.extend([f"- {md(e)[:260]}" for e in errors[:80]])
        if len(errors) > 80:
            report.append(f"- … i {len(errors) - 80} dalszych błędów (zobacz JSON).")
    else:
        report.append("Nie zgłoszono błędów podczas pomiaru.")
    report.extend(["", "## 12. Pliki wynikowe", "",
                   "- `report.md` — obszerny raport zbiorczy.",
                   "- `metrics.json` — wszystkie metryki, w tym Halstead per plik i CC per funkcja.",
                   "- `files.csv` — metryki pojedynczych plików.",
                   "- `functions.csv` — wszystkie funkcje/metody Python i ich złożoność CC.",
                   "- `issues.csv` — wszystkie wykryte problemy ESLint.", ""])
    (out / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload["summary"]


def main():
    parser = argparse.ArgumentParser(description="CodeAudit — Radon/ESLint code audit with local Git history and security analysis")
    parser.add_argument("project", type=Path, help="Path to the project directory to analyze")
    parser.add_argument("--out", type=Path, help="Output directory for reports (must be outside the target project)")
    parser.add_argument("--no-eslint", action="store_true", help="Skip JavaScript ESLint analysis")
    parser.add_argument("--include-work", action="store_true", help="Include .work directory in analysis")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden directories in analysis")
    parser.add_argument("--batch-size", type=int, default=40, help="Number of JS files per ESLint batch (default: 40)")
    parser.add_argument("--previous", type=Path, help="Path to metrics.json from a previous audit run for delta comparison")
    parser.add_argument("--no-previous", action="store_true", help="Do not compare against previous audit runs")
    parser.add_argument("--skip-var-inventory", action="store_true", help="Skip file inventory of var/ directory")
    parser.add_argument("--no-git", action="store_true", help="Skip local Git history analysis")
    parser.add_argument("--git-max-commits", type=int, default=800, help="Limit of non-merge Git commits to scan (1-5000)")
    parser.add_argument("--no-extras", action="store_true", help="Skip all v2.2 extra analyzers (lizard, vulture, bandit, duplication, dependencies)")
    parser.add_argument("--no-lizard", action="store_true", help="Skip JS/TS cyclomatic complexity analysis (lizard)")
    parser.add_argument("--no-vulture", action="store_true", help="Skip dead code detection (vulture)")
    parser.add_argument("--no-bandit", action="store_true", help="Skip Python security analysis (bandit)")
    parser.add_argument("--no-duplication", action="store_true", help="Skip duplicate code detection")
    parser.add_argument("--no-deps", action="store_true", help="Skip dependency graph and cycle analysis")
    parser.add_argument("--pip-audit", action="store_true", help="Run dependency vulnerability scan — REQUIRES INTERNET")
    parser.add_argument("--requirements", type=Path, action="append", help="Path to requirements file with pinned versions (can be outside project; can repeat)")
    args = parser.parse_args()
    reqs = [r.expanduser().resolve() for r in (args.requirements or [])]
    for r in reqs:
        if not r.is_file(): parser.error(f"Nie ma takiego pliku requirements: {r}")
    root = args.project.expanduser().resolve()
    if not root.is_dir(): parser.error(f"Nie ma takiego katalogu: {root}")
    if args.batch_size < 1 or args.batch_size > 100: parser.error("--batch-size musi być 1..100")
    if args.git_max_commits < 1 or args.git_max_commits > 5000: parser.error("--git-max-commits musi być 1..5000")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = (args.out.expanduser().resolve() if args.out else
           (HERE / "reports" / f"{root.name}_{stamp}").resolve())
    # No writes to project, even if user mistakenly sets output under source tree.
    if out == root or root in out.parents:
        parser.error("--out nie może wskazywać katalogu wewnątrz analizowanego projektu")
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    print(f"CodeAudit {VERSION}\nProjekt: {root}\nWyniki: {out}", flush=True)
    settings = load_settings()
    files, errors, dirs, hidden_dirs, excluded = file_inventory(root, out, args.include_work, args.include_hidden, settings["excluded_files"])
    print(f"Kod źródłowy: {len(files)} plików; wyłączone pliki: {len(excluded)}; katalogów: {dirs}", flush=True)
    print("Inwentaryzacja var (bez analizy kodu)...", flush=True)
    var_stats = {"present": False, "files": 0, "bytes": 0, "directories": 0} if args.skip_var_inventory else inventory_var(root)
    functions, pycount = scan_files(root, files, errors)
    print(f"Radon: przeanalizowano {pycount} plików Python, {len(functions)} funkcji/metod", flush=True)
    eslint = run_eslint(root, files, errors, args.batch_size, args.no_eslint)
    from extra_analyzers import run_extras
    if args.no_extras:
        extras = {}
    else:
        extras = run_extras(root, files, errors, {
            "lizard": not args.no_lizard, "vulture": not args.no_vulture, "bandit": not args.no_bandit,
            "duplication": not args.no_duplication, "deps": not args.no_deps, "pip_audit": args.pip_audit,
            "requirements": reqs})
    summary = produce_report(root, out, files, functions, eslint, errors, dirs, hidden_dirs, pycount, started, extras)
    # Historia lokalnego Git: tylko odczyt, bez sieci, bez zmiany indexu/repozytorium.
    from git_history import scan_git
    print("Git: analizowanie śledzonych plików i historii commitów...", flush=True)
    git_info = scan_git(root, files, excluded, args.git_max_commits, disabled=args.no_git)
    print(f"Git: {git_info['status']}; commity: {git_info['commits_analyzed']}; śledzone pliki: {git_info['tracked_files']}", flush=True)
    from audit_reporting import build_professional_reports
    build_professional_reports(root, out, var_stats, excluded, args.previous, args.no_previous, git_info)
    print("\nZakończono.\n" + "\n".join(str(p) for p in sorted(out.iterdir()) if p.suffix in {".html", ".md", ".json", ".csv"}))
    print(f"Pliki projektu: {summary['files']}; linie kodu: {summary['code_physical_lines']}; problemy pomiaru: {summary['errors_count']}")
    if errors or eslint["status"] in {"partial", "unavailable"}:
        print("UWAGA: pomiar częściowy lub zawiera diagnostykę — zobacz sekcję 11 raportu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
