"""CodeAudit 2.2 — dodatkowe analizatory. Tylko odczyt kodu projektu.

* lizard      — złożoność cyklomatyczna funkcji JS/JSX/TS/TSX (uzupełnia Radon, który liczy tylko Pythona)
* vulture     — kandydaci na martwy kod w Pythonie (to SYGNAŁY do przeglądu, nie dowód)
* bandit      — statyczna analiza bezpieczeństwa Pythona (lokalnie, bez sieci)
* pip-audit   — znane podatności zależności; WYMAGA INTERNETU, uruchamiany tylko z --pip-audit
* duplikacja  — własna, heurystyczna detekcja powielonych bloków kodu
* zależności  — własny graf importów Python/JS, cykle, fan-in / fan-out

Każdy analizator jest opcjonalny: brak biblioteki daje status "unavailable" i audyt trwa dalej.
Żaden z nich nie zapisuje niczego w analizowanym projekcie.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

JS_EXT = {".js", ".jsx", ".mjs", ".cjs"}
TS_EXT = {".ts", ".tsx"}          # lizard nie obsługuje .mts/.cts
PROD_CATS = {"py_prod", "py_other", "js_prod", "js_other", "ts_prod"}
TEST_CATS = {"py_tests", "js_tests", "ts_tests"}
MAX_FILE_BYTES = 1_500_000
SKIP_DIRS = {"node_modules", ".venv", "venv", ".git", "dist", "build", "__pycache__", "var", ".work"}

VULTURE_IGNORE_DECORATORS = [
    "@*.route", "@*.get", "@*.post", "@*.put", "@*.delete", "@*.patch", "@*.websocket",
    "@*.on_event", "@*.command", "@*.callback", "@*.fixture", "@pytest.fixture",
    "@*.setter", "@*.getter", "@*.deleter", "@*.validator", "@*.field_validator",
    "@*.expose", "@click.*", "@*.task", "@*.listener", "@*.errorhandler",
]
VULTURE_IGNORE_NAMES = ["test_*", "Test*", "setUp", "tearDown", "setUpClass", "tearDownClass",
                        "model_config", "Config", "Meta", "__all__"]


def _version(pkg: str):
    try:
        return importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        return None


def _status(name: str, version=None, status="ok", note=None, **extra):
    return {"status": status, "version": version, "note": note, **extra}


# ──────────────────────────────── lizard ────────────────────────────────
def run_lizard(root: Path, files, errors, disabled=False):
    if disabled:
        return _status("lizard", status="disabled", functions=[], files=0)
    try:
        import lizard
    except ImportError:
        return _status("lizard", status="unavailable", note="python -m pip install lizard", functions=[], files=0)
    functions, scanned = [], 0
    for f in files:
        ext = f["ext"]
        if ext not in JS_EXT and ext not in TS_EXT:
            continue
        if f.get("bytes", 0) > MAX_FILE_BYTES:   # np. wygenerowane bundle — pomijamy, by nie wydłużać audytu
            errors.append(f"Lizard {f['path']}: pominięto plik > {MAX_FILE_BYTES // 1000} kB (prawdopodobnie wygenerowany)")
            continue
        p = root / Path(f["path"])
        try:
            code = p.read_text(encoding="utf-8", errors="replace")
            # lizard wybiera język po rozszerzeniu; .mjs/.cjs są obsługiwane, ale ujednolicamy
            fake = f["path"] if ext not in {".mjs", ".cjs"} else f["path"][:-4] + ".js"
            info = lizard.analyze_file.analyze_source_code(fake, code)
        except Exception as exc:  # noqa: BLE001 — diagnostyka, nie przerywamy audytu
            errors.append(f"Lizard {f['path']}: {type(exc).__name__}: {exc}")
            continue
        scanned += 1
        for fn in info.function_list:
            functions.append({
                "file": f["path"], "category": f["category"], "name": fn.name,
                "line": int(fn.start_line), "end_line": int(fn.end_line),
                "cc": int(fn.cyclomatic_complexity), "nloc": int(fn.nloc),
                "params": int(fn.parameter_count), "tokens": int(fn.token_count),
            })
    return _status("lizard", _version("lizard"), functions=functions, files=scanned)


# ──────────────────────────────── vulture ────────────────────────────────
def run_vulture(root: Path, files, errors, disabled=False):
    if disabled:
        return _status("vulture", status="disabled", items=[])
    try:
        import vulture
    except ImportError:
        return _status("vulture", status="unavailable", note="python -m pip install vulture", items=[])
    cat = {f["path"]: f["category"] for f in files}
    abs_map = {str((root / Path(f["path"])).resolve()): f["path"] for f in files if f["ext"] == ".py"}
    if not abs_map:
        return _status("vulture", _version("vulture"), items=[])
    try:
        v = vulture.Vulture(ignore_names=VULTURE_IGNORE_NAMES, ignore_decorators=VULTURE_IGNORE_DECORATORS)
        v.scavenge(list(abs_map))
        found = v.get_unused_code(min_confidence=60)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Vulture: {type(exc).__name__}: {exc}")
        return _status("vulture", _version("vulture"), status="error", note=str(exc)[:300], items=[])
    items = []
    for it in found:
        rel = abs_map.get(str(Path(it.filename).resolve()))
        if rel is None:
            continue
        items.append({"file": rel, "category": cat.get(rel, ""), "line": int(it.first_lineno),
                      "type": it.typ, "name": it.name, "confidence": int(it.confidence)})
    items.sort(key=lambda x: (-x["confidence"], x["file"], x["line"]))
    return _status("vulture", _version("vulture"), items=items)


# ──────────────────────────────── bandit ────────────────────────────────
_SECRET_TESTS = {"B105", "B106", "B107"}
_QUOTED = re.compile(r"""(['"]).*?\1""")


def run_bandit(root: Path, files, errors, disabled=False, batch=60):
    if disabled:
        return _status("bandit", status="disabled", issues=[])
    if _version("bandit") is None:
        return _status("bandit", status="unavailable", note="python -m pip install bandit", issues=[])
    cat = {str((root / Path(f["path"])).resolve()): f for f in files if f["ext"] == ".py"}
    paths = list(cat)
    issues, failed = [], 0
    for i in range(0, len(paths), batch):
        chunk = paths[i:i + batch]
        # cwd poza projektem: bandit nie wczyta lokalnej konfiguracji ani niczego nie zapisze
        cmd = [sys.executable, "-m", "bandit", "-f", "json", "-q", "--exit-zero", *chunk]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=600, cwd=str(Path(__file__).resolve().parent))
            raw = proc.stdout.strip()
            start = raw.find("{")
            data = json.loads(raw[start:]) if start >= 0 else {}
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            errors.append(f"Bandit partia {i // batch + 1}: {type(exc).__name__}: {exc}")
            failed += 1
            continue
        for r in data.get("results", []):
            meta = cat.get(str(Path(r.get("filename", "")).resolve()))
            if not meta:
                continue
            text = r.get("issue_text", "")
            if r.get("test_id") in _SECRET_TESTS:      # nie kopiujemy wartości haseł do raportu
                text = _QUOTED.sub("'***'", text)
            issues.append({
                "file": meta["path"], "category": meta["category"], "line": int(r.get("line_number", 0)),
                "severity": str(r.get("issue_severity", "LOW")).upper(),
                "confidence": str(r.get("issue_confidence", "LOW")).upper(),
                "test_id": r.get("test_id"), "test_name": r.get("test_name"), "text": text[:300],
                "cwe": (r.get("issue_cwe") or {}).get("id"),
            })
    status = "ok" if not failed else ("partial" if issues else "error")
    return _status("bandit", _version("bandit"), status=status, issues=issues, files=len(paths))


# ──────────────────────────────── pip-audit ────────────────────────────────
def _requirement_files(root: Path):
    found = []
    for p in sorted(root.rglob("requirements*.txt")):
        rel = p.relative_to(root)
        if len(rel.parts) <= 3 and not (set(rel.parts[:-1]) & SKIP_DIRS):
            found.append(p)
    return found[:6]


_PIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*(\[[^\]]*\])?\s*==\s*[^\s;#=]+")


def _split_requirements(path: Path):
    """Dzieli linie pliku na przypięte (pakiet==wersja) i luźne; pomija komentarze i opcje (-r, -e, --hash)."""
    pinned, loose = [], []
    blob = path.read_bytes()
    # Windows PowerShell 5.1: `pip freeze > plik.txt` zapisuje UTF-16 z BOM — obsługujemy oba kodowania
    text = blob.decode("utf-16", errors="replace") if blob[:2] in (b"\xff\xfe", b"\xfe\xff") else blob.decode("utf-8-sig", errors="replace")
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith(("#", "-")):
            continue
        (pinned if _PIN.match(line) else loose).append(line)
    return pinned, loose


def run_pip_audit(root: Path, errors, enabled=False, req_files=None):
    if not enabled:
        return _status("pip-audit", status="disabled", vulnerabilities=[], packages=0,
                       note="Włącz flagą -PipAudit (wymaga internetu)")
    if _version("pip-audit") is None:
        return _status("pip-audit", status="unavailable", note="python -m pip install pip-audit", vulnerabilities=[], packages=0)
    reqs = [Path(p) for p in req_files] if req_files else _requirement_files(root)
    if not reqs:
        return _status("pip-audit", _version("pip-audit"), status="no_input", vulnerabilities=[], packages=0,
                       note="Nie znaleziono requirements*.txt w projekcie (pyproject.toml nie jest analizowany). "
                            "Możesz wskazać plik poza projektem opcją -Requirements.")
    import tempfile
    vulns, pkgs, skipped, infos, problems = [], 0, 0, [], []
    for req in reqs:
        try:
            label = req.relative_to(root).as_posix()
        except ValueError:
            label = req.name
        try:
            pinned, loose = _split_requirements(req)
        except OSError as exc:
            problems.append(f"{label}: {exc}")
            continue
        if loose:
            skipped += len(loose)
            names = [re.split(r"[<>=!~\[;@ ]", x, 1)[0] for x in loose]
            infos.append(f"{label}: pominięto {len(loose)} pakietów bez przypiętej wersji ({', '.join(names[:8])}{'…' if len(names) > 8 else ''})")
        if not pinned:
            continue
        # sprawdzamy tylko przypięte linie, z tymczasowej kopii poza projektem
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write("\n".join(pinned) + "\n")
            tmp_path = Path(tmp.name)
        cmd = [sys.executable, "-m", "pip_audit", "-r", str(tmp_path), "-f", "json",
               "--no-deps", "--disable-pip", "--progress-spinner", "off"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=300, cwd=str(Path(__file__).resolve().parent))
            raw = proc.stdout.strip()
            start = raw.find("{")
            if start < 0:
                problems.append(f"{label}: {(proc.stderr or 'brak wyniku').strip()[:240]}")
                continue
            data = json.loads(raw[start:])
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            problems.append(f"{label}: {type(exc).__name__}: {exc}")
            continue
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass
        deps = data.get("dependencies", []) if isinstance(data, dict) else data
        pkgs += len(deps)
        for d in deps:
            for vln in d.get("vulns", []) or []:
                vulns.append({"requirements": label, "package": d.get("name"),
                              "version": d.get("version"), "id": vln.get("id"),
                              "aliases": (vln.get("aliases") or [])[:4],
                              "fix_versions": vln.get("fix_versions") or [],
                              "description": (vln.get("description") or "")[:280]})
    errors.extend(f"pip-audit {n}" for n in problems)
    note = "; ".join(infos + problems)[:600] or None
    if pkgs:
        status = "ok"
    elif problems:
        status = "error"
    else:
        status = "unpinned"
        note = ((note or "") + " Żaden pakiet nie ma przypiętej wersji (pakiet==wersja), więc nie ma czego sprawdzić.").strip()
    return _status("pip-audit", _version("pip-audit"), status=status, vulnerabilities=vulns, packages=pkgs,
                   skipped=skipped, note=note)


# ──────────────────────────────── duplikacja ────────────────────────────────
_COMMENT = re.compile(r"^(#|//|/\*|\*|\*/|<!--)")
_IMPORTISH = re.compile(r"^(import |from \S+ import |export .* from |const .*require\()")


def run_duplication(root: Path, files, errors, disabled=False, window=8, max_blocks=120):
    if disabled:
        return _status("duplication", status="disabled", percent=None, blocks=[], by_file={})
    wanted = [f for f in files if f["category"] in PROD_CATS and f["ext"] in ({".py"} | JS_EXT | TS_EXT)
              and f.get("bytes", 0) <= MAX_FILE_BYTES]
    sig = {}                                    # path -> [(znormalizowana linia, nr linii)]
    for f in wanted:
        try:
            raw = (root / Path(f["path"])).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            errors.append(f"Duplikacja {f['path']}: {exc}")
            continue
        lines = []
        for n, text in enumerate(raw, start=1):
            s = " ".join(text.split())
            if len(s) <= 3 or _COMMENT.match(s):
                continue
            lines.append((s, n))
        if len(lines) >= window:
            sig[f["path"]] = lines
    occ = defaultdict(list)
    for path, lines in sig.items():
        for i in range(len(lines) - window + 1):
            chunk = [s for s, _ in lines[i:i + window]]
            if sum(bool(_IMPORTISH.match(s)) for s in chunk) > window // 2:
                continue
            h = hashlib.blake2b("\n".join(chunk).encode("utf-8", "replace"), digest_size=8).digest()
            occ[h].append((path, i))
    dup_idx, partner = defaultdict(set), {}
    for lst in occ.values():
        if len(lst) < 2:
            continue
        for p, i in lst:
            other = next(((q, j) for q, j in lst[:6] if (q, j) != (p, i) and (q != p or abs(j - i) >= window)), None)
            if other:
                dup_idx[p].add(i)
                partner[(p, i)] = other
    total = sum(len(v) for v in sig.values())
    by_file, covered_total, blocks, seen = {}, 0, [], set()
    for p, idxs in dup_idx.items():
        cov = set()
        for i in idxs:
            cov.update(range(i, i + window))
        by_file[p] = len(cov)
        covered_total += len(cov)
        ordered = sorted(idxs)
        k = 0
        while k < len(ordered):
            start = prev = ordered[k]
            q, j = partner[(p, start)]
            while (k + 1 < len(ordered) and ordered[k + 1] == prev + 1
                   and partner.get((p, prev + 1)) == (q, partner[(p, prev)][1] + 1)):
                k += 1
                prev = ordered[k]
            end_j = partner[(p, prev)][1]
            key = tuple(sorted([(p, start), (q, j)]))
            if key not in seen:
                seen.add(key)
                a, b = sig[p], sig[q]
                blocks.append({"a": p, "a_from": a[start][1], "a_to": a[prev + window - 1][1],
                               "b": q, "b_from": b[j][1], "b_to": b[end_j + window - 1][1],
                               "lines": prev - start + window})
            k += 1
    blocks.sort(key=lambda b: -b["lines"])
    percent = round(100 * covered_total / total, 2) if total else None
    return _status("duplication", "2.2-heurystyka", percent=percent, significant_lines=total,
                   duplicated_lines=covered_total, window=window, blocks=blocks[:max_blocks], by_file=by_file)


# ──────────────────────────────── graf zależności ────────────────────────────────
_JS_IMPORT = re.compile(
    r"""(?:import\s+(?:[^'"()]*?\s+from\s+)?|export\s+[^'"()]*?\s+from\s+|require\(\s*|import\(\s*)['"]([^'"]+)['"]""")


def _py_imports(source: str):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend((0, a.name, None) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            out.append((node.level or 0, node.module or "", [a.name for a in node.names]))
    return out


def _tarjan(nodes, adj):
    """Iteracyjny algorytm Tarjana — spójne składowe (cykle importów)."""
    index, low, on, stack, result, counter = {}, {}, set(), [], [], [0]
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(adj.get(root, ())))]
        index[root] = low[root] = counter[0]; counter[0] += 1
        stack.append(root); on.add(root)
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter[0]; counter[0] += 1
                    stack.append(w); on.add(w)
                    work.append((w, iter(adj.get(w, ()))))
                    advanced = True
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop(); on.discard(w); comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    result.append(sorted(comp))
    return result


def run_dependencies(root: Path, files, errors, disabled=False, graph_limit=220):
    if disabled:
        return _status("deps", status="disabled", nodes=[], edges=[], cycles=[])
    code = [f for f in files if f["category"] in PROD_CATS and f["ext"] in ({".py"} | JS_EXT | TS_EXT)]
    paths = {f["path"] for f in code}
    modmap = {}
    for f in code:
        if f["ext"] != ".py":
            continue
        parts = f["path"][:-3].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            continue
        modmap.setdefault(".".join(parts), f["path"])
        if parts[0] in {"src", "lib", "app"} and len(parts) > 1:
            modmap.setdefault(".".join(parts[1:]), f["path"])

    def py_lookup(name):
        bits = name.split(".")
        while bits:
            hit = modmap.get(".".join(bits))
            if hit:
                return hit
            bits.pop()
        return None

    edges = set()
    for f in code:
        p = root / Path(f["path"])
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"Zależności {f['path']}: {exc}")
            continue
        if f["ext"] == ".py":
            pkg = f["path"].split("/")[:-1]
            for level, module, names in _py_imports(text):
                if level:
                    base = pkg[:len(pkg) - (level - 1)] if level - 1 <= len(pkg) else []
                    full = ".".join(base + ([module] if module else []))
                    cands = [f"{full}.{n}" if full else n for n in (names or [])] + [full]
                else:
                    cands = [f"{module}.{n}" for n in (names or [])] + [module]
                hit = next((h for h in (py_lookup(c) for c in cands if c) if h), None)
                if hit and hit != f["path"]:
                    edges.add((f["path"], hit))
        else:
            folder = f["path"].rsplit("/", 1)[0] if "/" in f["path"] else ""
            for spec in _JS_IMPORT.findall(text):
                if not spec.startswith("."):
                    continue
                parts = [x for x in (folder + "/" + spec).split("/") if x not in ("", ".")]
                norm = []
                for x in parts:
                    if x == "..":
                        if norm:
                            norm.pop()
                    else:
                        norm.append(x)
                base = "/".join(norm)
                for cand in [base] + [base + e for e in sorted(JS_EXT | TS_EXT)] + [f"{base}/index{e}" for e in sorted(JS_EXT | TS_EXT)]:
                    if cand in paths and cand != f["path"]:
                        edges.add((f["path"], cand))
                        break
    adj = defaultdict(set)
    fan_in, fan_out = Counter(), Counter()
    for a, b in edges:
        adj[a].add(b); fan_out[a] += 1; fan_in[b] += 1
    nodes_all = sorted(paths)
    cycles = _tarjan(nodes_all, adj)
    in_cycle = {n for c in cycles for n in c}

    def group(path):
        parts = path.split("/")
        if len(parts) == 1:
            return "(root)"
        return "/".join(parts[:2]) if parts[0] in {"src", "lib", "app"} and len(parts) > 2 else parts[0]

    degree = {n: fan_in[n] + fan_out[n] for n in nodes_all}
    keep = sorted([n for n in nodes_all if degree[n] > 0], key=lambda n: (-(n in in_cycle), -degree[n], n))[:graph_limit]
    kept = set(keep)
    gnodes = [{"path": n, "group": group(n), "fan_in": fan_in[n], "fan_out": fan_out[n], "cycle": n in in_cycle} for n in keep]
    gedges = [[a, b] for a, b in sorted(edges) if a in kept and b in kept]
    top = lambda c: [{"path": k, "value": v} for k, v in c.most_common(12)]  # noqa: E731
    return _status("deps", "2.2-własny", nodes_total=len(nodes_all), edges_total=len(edges),
                   python_modules=sum(1 for n in nodes_all if n.endswith(".py")),
                   js_modules=sum(1 for n in nodes_all if not n.endswith(".py")),
                   cycles=[c[:14] for c in sorted(cycles, key=len, reverse=True)[:25]], cycles_total=len(cycles),
                   top_fan_in=top(fan_in), top_fan_out=top(fan_out),
                   graph={"nodes": gnodes, "edges": gedges},
                   all_edges=[[a, b] for a, b in sorted(edges)])


# ──────────────────────────────── wejście ────────────────────────────────
def run_extras(root: Path, files, errors, opts: dict):
    """opts: lizard, vulture, bandit, duplication, deps, pip_audit — wartości bool (True = uruchom)."""
    def step(label, fn):
        print(f"{label}...", flush=True)
        res = fn()
        print(f"  -> {res['status']}" + (f" ({res['note']})" if res.get("note") and res["status"] != "ok" else ""), flush=True)
        return res
    extras = {
        "lizard": step("Lizard: złożoność JS/TS", lambda: run_lizard(root, files, errors, not opts.get("lizard", True))),
        "vulture": step("Vulture: martwy kod Python", lambda: run_vulture(root, files, errors, not opts.get("vulture", True))),
        "bandit": step("Bandit: bezpieczeństwo Python", lambda: run_bandit(root, files, errors, not opts.get("bandit", True))),
        "pip_audit": step("pip-audit: podatności zależności", lambda: run_pip_audit(root, errors, bool(opts.get("pip_audit", False)), opts.get("requirements"))),
        "duplication": step("Duplikacja kodu (heurystyka)", lambda: run_duplication(root, files, errors, not opts.get("duplication", True))),
        "deps": step("Graf zależności i cykle", lambda: run_dependencies(root, files, errors, not opts.get("deps", True))),
    }
    return extras
