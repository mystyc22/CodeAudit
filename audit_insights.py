"""CodeAudit 2.2 — wnioski i dane do wizualizacji (stdlib). Tylko odczyt projektu."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

PY_SCORED = {"py_prod", "py_other"}
JS_SCORED = {"js_prod", "js_other", "ts_prod"}
CODE_EXT = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}

RADAR_FORMULAS = {
    "cc": "udział funkcji Python CC A/B [%] (jak w indeksie głównym)",
    "mi": "mediana Maintainability Index plików Python (jak w indeksie głównym)",
    "eslint": "100 − 8 × alerty priorytetowe ESLint na 1000 linii JS (jak w indeksie głównym)",
    "jscc": "udział funkcji JS/TS (lizard) o CC ≤ 10 [%]",
    "sec": "100 − 10 × (5·HIGH + 2·MEDIUM + 0,5·LOW) na 1000 linii Pythona (bandit, bez testów)",
    "dead": "100 − 6 × kandydaci vulture na 1000 linii Pythona (bez testów)",
    "dup": "100 − 4 × % zduplikowanych linii (heurystyka okna 8 linii)",
    "cycles": "100 − 15 × liczba cykli importów (spójne składowe grafu)",
}


def _rank(cc: int) -> str:
    return "A" if cc <= 5 else "B" if cc <= 10 else "C" if cc <= 20 else "D" if cc <= 30 else "E" if cc <= 40 else "F"


def _clip(v):
    return None if v is None else round(max(0.0, min(100.0, float(v))), 1)


def _kp(p) -> str:
    return str(p).replace("\\", "/").casefold()


# ───────────────────────── podsumowanie rozszerzeń ─────────────────────────
def summarize_extras(data: dict) -> dict:
    ex = data.get("extras") or {}
    files = data.get("files", [])
    py_lines = sum(f.get("physical_lines") or 0 for f in files if f.get("category") in PY_SCORED)
    kloc = py_lines / 1000 if py_lines else None
    out = {"py_scored_lines": py_lines, "available": bool(ex)}

    liz = ex.get("lizard", {"status": "disabled"})
    fns = [f for f in liz.get("functions", []) if f.get("category") in JS_SCORED]
    ranks = Counter(_rank(f["cc"]) for f in fns)
    out["lizard"] = {
        "status": liz.get("status"), "version": liz.get("version"), "note": liz.get("note"),
        "files": liz.get("files", 0), "functions": len(fns),
        "ranks": {g: ranks.get(g, 0) for g in "ABCDEF"},
        "ab_percent": round(100 * (ranks["A"] + ranks["B"]) / len(fns), 1) if fns else None,
        "over15": sum(f["cc"] > 15 for f in fns), "max": max((f["cc"] for f in fns), default=None),
        "long": sum(f["nloc"] > 100 for f in fns), "many_params": sum(f["params"] > 5 for f in fns),
        "mean": round(sum(f["cc"] for f in fns) / len(fns), 2) if fns else None,
    }

    ban = ex.get("bandit", {"status": "disabled"})
    issues = ban.get("issues", [])
    prod = [i for i in issues if i["category"] in PY_SCORED]
    sev = Counter(i["severity"] for i in prod)
    weighted = 5 * sev["HIGH"] + 2 * sev["MEDIUM"] + 0.5 * sev["LOW"]
    per_file = Counter()
    for i in prod:
        per_file[i["file"]] += {"HIGH": 5, "MEDIUM": 2}.get(i["severity"], 0.5)
    out["security"] = {
        "status": ban.get("status"), "version": ban.get("version"), "note": ban.get("note"),
        "high": sev["HIGH"], "medium": sev["MEDIUM"], "low": sev["LOW"],
        "tests_total": len(issues) - len(prod), "files_affected": len(per_file),
        "weighted_per_k": round(weighted / kloc, 3) if kloc else None,
        "top_files": [{"file": f, "weight": w} for f, w in per_file.most_common(8)],
    }

    pa = ex.get("pip_audit", {"status": "disabled"})
    vul = pa.get("vulnerabilities", [])
    out["pip_audit"] = {
        "status": pa.get("status"), "version": pa.get("version"), "note": pa.get("note"),
        "packages": pa.get("packages", 0), "skipped": pa.get("skipped", 0), "vulnerabilities": len(vul),
        "vulnerable_packages": len({(v["package"], v["version"]) for v in vul}),
    }

    vul_ = ex.get("vulture", {"status": "disabled"})
    items = [i for i in vul_.get("items", []) if i["category"] in PY_SCORED]
    out["dead"] = {
        "status": vul_.get("status"), "version": vul_.get("version"), "note": vul_.get("note"),
        "count": len(items), "high_confidence": sum(i["confidence"] >= 80 for i in items),
        "per_k": round(len(items) / kloc, 3) if kloc else None,
        "by_type": dict(Counter(i["type"] for i in items)),
    }

    dup = ex.get("duplication", {"status": "disabled"})
    out["duplication"] = {"status": dup.get("status"), "percent": dup.get("percent"),
                          "blocks": len(dup.get("blocks", [])), "lines": dup.get("duplicated_lines"),
                          "window": dup.get("window")}

    dp = ex.get("deps", {"status": "disabled"})
    out["deps"] = {"status": dp.get("status"), "modules": dp.get("nodes_total"), "edges": dp.get("edges_total"),
                   "cycles": dp.get("cycles_total"), "python_modules": dp.get("python_modules"),
                   "js_modules": dp.get("js_modules")}
    return out


# ───────────────────────── radar ─────────────────────────
def build_radar(scope: dict, quality: dict, xs: dict) -> list[dict]:
    comp = quality.get("components", [])
    es = comp[2]["score"] if len(comp) > 2 else None
    sec = xs["security"]; dead = xs["dead"]; dup = xs["duplication"]; dp = xs["deps"]
    sec_ok = sec["status"] in {"ok", "partial"} and sec["weighted_per_k"] is not None
    dead_ok = dead["status"] == "ok" and dead["per_k"] is not None
    values = {
        "cc": scope.get("cc_AB_percent"), "mi": scope.get("mi_median"), "eslint": es,
        "jscc": xs["lizard"]["ab_percent"] if xs["lizard"]["status"] == "ok" else None,
        "sec": 100 - 10 * sec["weighted_per_k"] if sec_ok else None,
        "dead": 100 - 6 * dead["per_k"] if dead_ok else None,
        "dup": 100 - 4 * dup["percent"] if dup["status"] == "ok" and dup["percent"] is not None else None,
        "cycles": 100 - 15 * dp["cycles"] if dp["status"] == "ok" and dp["cycles"] is not None else None,
    }
    names = {"cc": "Złożoność Python", "mi": "Maintainability Python", "eslint": "ESLint (priorytety)",
             "jscc": "Złożoność JS/TS", "sec": "Bezpieczeństwo Python", "dead": "Martwy kod",
             "dup": "Duplikacja", "cycles": "Cykle importów"}
    return [{"key": k, "name": names[k], "value": _clip(values[k]), "formula": RADAR_FORMULAS[k]} for k in names]


def previous_radar(historical: dict, old_scope: dict, score_quality):
    """Wartości osi radaru z poprzedniego pomiaru (osie 2.2 tylko jeśli poprzedni audyt je miał)."""
    status = (historical.get("summary", {}).get("eslint", {}) or {}).get("status", "complete")
    q = score_quality(old_scope, status)
    comp = q.get("components", [])
    vals = {"cc": old_scope.get("cc_AB_percent"), "mi": old_scope.get("mi_median"),
            "eslint": comp[2]["score"] if len(comp) > 2 else None}
    for axis in historical.get("radar", []) or []:
        if axis.get("value") is not None:
            vals[axis["key"]] = axis["value"]
    return {k: _clip(v) for k, v in vals.items()}, q


# ───────────────────────── macierz plików ─────────────────────────
def build_file_matrix(data: dict, risks: list, git_info: dict | None) -> list[dict]:
    ex = data.get("extras") or {}
    py_cc = {}
    for f in data.get("files", []):
        cc = (f.get("radon") or {}).get("cc_max")
        if cc is not None:
            py_cc[_kp(f["path"])] = cc
    js_cc = defaultdict(int)
    for fn in (ex.get("lizard") or {}).get("functions", []):
        k = _kp(fn["file"])
        js_cc[k] = max(js_cc[k], fn["cc"])
    es = Counter(_kp(i["file"]) for i in data.get("eslint_issues", []))
    sec, sec_hm = Counter(), Counter()
    for i in (ex.get("bandit") or {}).get("issues", []):
        k = _kp(i["file"])
        sec[k] += {"HIGH": 5, "MEDIUM": 2}.get(i["severity"], 0.5)
        sec_hm[k] += i["severity"] in {"HIGH", "MEDIUM"}
    dead = Counter(_kp(i["file"]) for i in (ex.get("vulture") or {}).get("items", []))
    dupf = {_kp(k): v for k, v in ((ex.get("duplication") or {}).get("by_file") or {}).items()}
    churn = {_kp(p["file"]): p for p in (git_info or {}).get("all_changed_files", [])}
    risk = {_kp(r["file"]): r for r in risks}
    rows = []
    for f in data.get("files", []):
        if f.get("ext") not in CODE_EXT or not f.get("physical_lines"):
            continue
        k = _kp(f["path"])
        lines = f["physical_lines"]
        g = churn.get(k, {})
        r = risk.get(k, {})
        rows.append({
            "p": f["path"], "c": f.get("category"), "l": lines,
            "cc": py_cc.get(k, js_cc.get(k)), "mi": (f.get("radon") or {}).get("mi"),
            "es": es.get(k, 0), "sec": round(sec.get(k, 0), 1), "sh": sec_hm.get(k, 0),
            "dead": dead.get(k, 0), "dup": round(100 * dupf.get(k, 0) / lines, 1) if lines else 0,
            "n": g.get("commits", 0), "ch": g.get("churn", 0),
            "r": r.get("risk_index", 0), "pr": r.get("priority"),
        })
    return rows


# ───────────────────────── aktywność Git ─────────────────────────
def git_activity(git_info: dict | None) -> dict:
    commits = (git_info or {}).get("commits", [])
    daily, grid = Counter(), Counter()
    for c in commits:
        raw = str(c.get("date", ""))
        if len(raw) < 10:
            continue
        daily[raw[:10]] += 1
        try:
            d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            grid[(d.weekday(), d.hour)] += 1
        except ValueError:
            pass
    dates = sorted(daily)
    return {"daily": [[d, daily[d]] for d in dates], "grid": [[w, h, n] for (w, h), n in sorted(grid.items())],
            "first": dates[0] if dates else None, "last": dates[-1] if dates else None,
            "active_days": len(dates), "commits": sum(daily.values())}


# ───────────────────────── trend między audytami ─────────────────────────
def _entry_from_data(out_name: str, d: dict, xs: dict | None, scope: dict, quality: dict, commits=None) -> dict:
    return {
        "id": out_name, "t": d.get("metadata", {}).get("generated_at_utc"),
        "score": quality.get("score"), "grade": quality.get("grade"),
        "loc": scope.get("physical_lines"), "files": scope.get("files"),
        "cc_ab": scope.get("cc_AB_percent"), "mi": scope.get("mi_median"),
        "eslint": scope.get("eslint_total"), "eslint_err": scope.get("eslint_errors"),
        "sec_high": xs["security"]["high"] if xs and xs["security"]["status"] in {"ok", "partial"} else None,
        "sec_med": xs["security"]["medium"] if xs and xs["security"]["status"] in {"ok", "partial"} else None,
        "dead": xs["dead"]["count"] if xs and xs["dead"]["status"] == "ok" else None,
        "dup": xs["duplication"]["percent"] if xs and xs["duplication"]["status"] == "ok" else None,
        "cycles": xs["deps"]["cycles"] if xs and xs["deps"]["status"] == "ok" else None,
        "js_cc_over15": xs["lizard"]["over15"] if xs and xs["lizard"]["status"] == "ok" else None,
        "commits": commits,
    }


def update_trend(out: Path, root: Path, data: dict, xs: dict, scope: dict, quality: dict, summarize_dataset, score_quality, excluded) -> list:
    base = out.parent
    hist_path = base / f"history_{root.name}.json"
    entries = []
    try:
        if hist_path.is_file():
            entries = json.loads(hist_path.read_text(encoding="utf-8")).get("entries", [])
    except (OSError, ValueError):
        entries = []
    known = {e.get("id") for e in entries}
    # jednorazowe uzupełnienie z wcześniejszych raportów (np. CodeAudit 2.1)
    older = sorted((p for p in base.glob(f"{root.name}_*/metrics.json") if p.parent.name != out.name and p.parent.name not in known),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:12]
    for p in older:
        try:
            hd = json.loads(p.read_text(encoding="utf-8"))
            if Path(hd.get("metadata", {}).get("project", "")).resolve() != root.resolve():
                continue
            sc = hd.get("source_scope") or summarize_dataset(hd, excluded)
            q = hd.get("quality_assessment") or score_quality(sc, (hd.get("summary", {}).get("eslint", {}) or {}).get("status", "complete"))
            hxs = summarize_extras(hd) if hd.get("extras") else None
            gi = hd.get("git_history") or {}
            entries.append(_entry_from_data(p.parent.name, hd, hxs, sc, q, gi.get("commits_analyzed")))
            del hd
        except (OSError, ValueError, KeyError):
            continue
    entries = [e for e in entries if e.get("id") != out.name]
    entries.append(_entry_from_data(out.name, data, xs, scope, quality, (data.get("git_history") or {}).get("commits_analyzed")))
    entries.sort(key=lambda e: e.get("t") or "")
    entries = entries[-80:]
    try:
        hist_path.write_text(json.dumps({"project": root.name, "entries": entries}, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return entries


# ───────────────────────── streszczenie zarządcze ─────────────────────────
def build_executive_summary(data, scope, quality, risks, previous, xs) -> dict:
    facts, actions = [], []
    score, grade = quality.get("score"), quality.get("grade")
    head = f"Indeks utrzymywalności: {score}/100 (klasa {grade})." if score is not None else "Indeks utrzymywalności niedostępny (brak danych)."
    pq = (previous or {}).get("quality") if previous else None
    if pq and pq.get("score") is not None and score is not None:
        d = round(score - pq["score"], 1)
        head += f" Zmiana względem poprzedniego audytu: {'+' if d > 0 else ''}{d} pkt."
    n = lambda v: f"{v:,}".replace(",", "\u00a0")  # noqa: E731
    facts.append({"level": "info", "text": f"Zakres — linie kodu: {n(scope['physical_lines'])}; pliki kodu: {n(scope['code_files'])}; "
                                           f"pliki Python (produkcja): {n(scope['python_prod'])}; funkcje Python: {n(scope['cc_count'])}."})
    cr = scope.get("cc_ranks", {})
    hard = cr.get("D", 0) + cr.get("E", 0) + cr.get("F", 0)
    if scope.get("cc_count"):
        facts.append({"level": "warn" if hard else "ok",
                      "text": f"Python — funkcje o CC > 20 (klasy D–F): {hard}; udział klas A/B: {scope['cc_AB_percent']:.0f}%."})
    lz = xs["lizard"]
    if lz["status"] == "ok" and lz["functions"]:
        facts.append({"level": "warn" if lz["over15"] else "ok",
                      "text": f"Frontend (lizard) — funkcje JS/TS o CC > 15: {lz['over15']} z {lz['functions']}; najwyższe CC: {lz['max']}."})
    sc = xs["security"]
    if sc["status"] in {"ok", "partial"}:
        lvl = "warn" if sc["high"] else ("info" if sc["medium"] else "ok")
        facts.append({"level": lvl, "text": f"Bandit (bez testów) — HIGH: {sc['high']}, MEDIUM: {sc['medium']}, LOW: {sc['low']}. "
                                            "To sygnały do ręcznej weryfikacji; część może być fałszywym alarmem."})
        if sc["high"]:
            actions.append(f"Zweryfikuj znaleziska bandit o wysokiej wadze (liczba: {sc['high']}, sekcja „Bezpieczeństwo”) i ustal, które są realnym ryzykiem.")
    pa = xs["pip_audit"]
    if pa["status"] == "ok":
        facts.append({"level": "warn" if pa["vulnerabilities"] else "ok",
                      "text": f"pip-audit — znane podatności: {pa['vulnerabilities']} (pakiety dotknięte: {pa['vulnerable_packages']} z {pa['packages']} sprawdzonych"
                              + (f"; pominięto bez przypiętej wersji: {pa['skipped']}" if pa.get("skipped") else "") + ")."})
        if pa["vulnerabilities"]:
            actions.append("Rozważ aktualizację pakietów wskazanych przez pip-audit (tabela zawiera wersje naprawcze, jeśli są znane).")
    elif pa["status"] in {"unpinned", "error", "no_input"}:
        facts.append({"level": "info", "text": "pip-audit — zależności nie zostały sprawdzone: " + (pa.get("note") or pa["status"])})
    elif pa["status"] == "disabled":
        facts.append({"level": "info", "text": "Zależności nie były sprawdzane pod kątem podatności (pip-audit wyłączony — wymaga internetu)."})
    dd = xs["dead"]
    if dd["status"] == "ok":
        facts.append({"level": "info", "text": f"Vulture — kandydaci na martwy kod: {dd['count']} (pewność ≥ 80%: {dd['high_confidence']}). "
                                               "Wymagają weryfikacji, bo kod wywoływany dynamicznie bywa oznaczany błędnie."})
    du = xs["duplication"]
    if du["status"] == "ok" and du["percent"] is not None:
        facts.append({"level": "warn" if du["percent"] >= 10 else "ok", "text": f"Duplikacja (heurystyka) — około {du['percent']}% znaczących linii kodu produkcyjnego."})
        if du["percent"] >= 10:
            actions.append("Przejrzyj największe zduplikowane bloki (sekcja „Martwy kod i duplikacja”) pod kątem wspólnej abstrakcji.")
    dp = xs["deps"]
    if dp["status"] == "ok":
        facts.append({"level": "warn" if dp["cycles"] else "ok", "text": f"Zależności — moduły: {dp['modules']}, powiązania: {dp['edges']}, cykle importów: {dp['cycles']}."})
        if dp["cycles"]:
            actions.append("Sprawdź cykle importów — utrudniają testowanie i zmiany; lista w sekcji „Zależności”.")
    if scope.get("eslint_errors"):
        actions.append(f"Napraw błędy ESLint poziomu error (liczba: {scope['eslint_errors']}) — zwykle najtańsza poprawa w warstwie frontendu.")
    top = [r for r in risks if r["priority"] in {"P1", "P2"}][:3] or risks[:3]
    if top:
        actions.insert(0, "Zacznij ręczny przegląd od: " + ", ".join(r["file"] for r in top) + " (najwyższy indeks triage; to lista priorytetów, nie wykaz błędów).")
    if not actions:
        actions.append("Brak pilnych sygnałów w mierzonych obszarach — utrzymaj regularne audyty i obserwuj trend.")
    return {"headline": head, "facts": facts, "actions": actions[:5]}


# ───────────────────────── Markdown ─────────────────────────
def _t(headers, rows):
    def cell(v):
        return str(v).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(cell, headers)) + " |", "|" + "|".join(["---"] * len(headers)) + "|"] +
                     ["| " + " | ".join(map(cell, r)) + " |" for r in rows])


def write_markdown_extras(out: Path, data: dict) -> None:
    xs, ex = data["extras_summary"], data.get("extras") or {}
    L = ["", "## 13. Rozszerzenia CodeAudit 2.2", "",
         "> Poniższe wyniki to **sygnały do przeglądu**, nie wyroki. Analizatory mogą zgłaszać fałszywe alarmy (szczególnie bandit i vulture).", ""]
    es = data.get("executive_summary") or {}
    if es:
        L += ["### 13.1 Streszczenie zarządcze", "", f"**{es['headline']}**", ""]
        L += [f"- {f['text']}" for f in es["facts"]] + ["", "**Sugerowane działania:**", ""]
        L += [f"{i}. {a}" for i, a in enumerate(es["actions"], 1)] + [""]
    L += ["### 13.2 Radar zdrowia kodu (0–100, wyżej = lepiej)", ""]
    L += [_t(["Oś", "Wartość", "Sposób obliczenia"], [[a["name"], a["value"] if a["value"] is not None else "—", a["formula"]] for a in data.get("radar", [])]), ""]
    lz = xs["lizard"]
    L += ["### 13.3 Złożoność JS/TS (lizard)", ""]
    if lz["status"] == "ok":
        L += [f"Funkcji: {lz['functions']} · CC > 15: {lz['over15']} · najwyższe CC: {lz['max']} · funkcje > 100 NLOC: {lz['long']} · > 5 parametrów: {lz['many_params']}", ""]
        top = sorted([f for f in ex["lizard"]["functions"] if f["category"] in JS_SCORED], key=lambda f: -f["cc"])[:15]
        L += [_t(["CC", "NLOC", "Funkcja", "Plik:linia"], [[f["cc"], f["nloc"], f["name"], f"{f['file']}:{f['line']}"] for f in top]), ""]
    else:
        L += [f"Status: {lz['status']}. {lz.get('note') or ''}", ""]
    sc = xs["security"]
    L += ["### 13.4 Bezpieczeństwo (bandit, bez testów)", ""]
    if sc["status"] in {"ok", "partial"}:
        L += [f"HIGH: {sc['high']} · MEDIUM: {sc['medium']} · LOW: {sc['low']} · zgłoszenia w testach (pominięte w ocenie): {sc['tests_total']}", ""]
        top = [i for i in ex["bandit"]["issues"] if i["category"] in PY_SCORED]
        top.sort(key=lambda i: ({"HIGH": 0, "MEDIUM": 1}.get(i["severity"], 2), i["file"], i["line"]))
        L += [_t(["Waga", "Test", "Opis", "Plik:linia"], [[i["severity"], i["test_id"], i["text"][:110], f"{i['file']}:{i['line']}"] for i in top[:20]]), ""]
    else:
        L += [f"Status: {sc['status']}. {sc.get('note') or ''}", ""]
    pa = xs["pip_audit"]
    L += ["### 13.5 Podatności zależności (pip-audit)", ""]
    if pa["status"] == "ok":
        vs = ex["pip_audit"]["vulnerabilities"]
        L += [f"Sprawdzono {pa['packages']} pakietów; podatności: {pa['vulnerabilities']}." + (f" {pa['note']}" if pa.get("note") else ""), ""]
        if vs:
            L += [_t(["Pakiet", "Wersja", "ID", "Wersje naprawcze"], [[v["package"], v["version"], v["id"], ", ".join(v["fix_versions"]) or "—"] for v in vs[:30]]), ""]
    else:
        L += [f"Status: {pa['status']}. {pa.get('note') or ''}", ""]
    dd = xs["dead"]
    L += ["### 13.6 Kandydaci na martwy kod (vulture)", ""]
    if dd["status"] == "ok":
        items = [i for i in ex["vulture"]["items"] if i["category"] in PY_SCORED][:25]
        L += [f"Kandydatów: {dd['count']} (pewność ≥ 80%: {dd['high_confidence']}).", "",
              _t(["Pewność", "Typ", "Nazwa", "Plik:linia"], [[f"{i['confidence']}%", i["type"], i["name"], f"{i['file']}:{i['line']}"] for i in items]), ""]
    else:
        L += [f"Status: {dd['status']}. {dd.get('note') or ''}", ""]
    du = ex.get("duplication", {})
    L += ["### 13.7 Duplikacja kodu (heurystyka)", ""]
    if du.get("status") == "ok":
        L += [f"Zduplikowane znaczące linie: {du.get('percent')}% ({du.get('duplicated_lines')} z {du.get('significant_lines')}). Okno porównania: {du.get('window')} linii.", "",
              _t(["Linie", "Fragment A", "Fragment B"], [[b["lines"], f"{b['a']}:{b['a_from']}-{b['a_to']}", f"{b['b']}:{b['b_from']}-{b['b_to']}"] for b in du["blocks"][:15]]), ""]
    else:
        L += [f"Status: {du.get('status')}.", ""]
    dp = ex.get("deps", {})
    L += ["### 13.8 Zależności między modułami", ""]
    if dp.get("status") == "ok":
        L += [f"Moduły: {dp['nodes_total']} (Python {dp['python_modules']}, JS/TS {dp['js_modules']}) · powiązania: {dp['edges_total']} · cykle: {dp['cycles_total']}", ""]
        for c in dp["cycles"][:8]:
            L += [f"- Cykl ({len(c)} modułów): " + " ↔ ".join(f"`{x}`" for x in c[:6]) + (" …" if len(c) > 6 else "")]
        L += ["", "**Najwięcej importujących (fan-out):** " + ", ".join(f"`{x['path']}` ({x['value']})" for x in dp["top_fan_out"][:6]), "",
              "**Najczęściej importowane (fan-in):** " + ", ".join(f"`{x['path']}` ({x['value']})" for x in dp["top_fan_in"][:6]), ""]
    else:
        L += [f"Status: {dp.get('status')}.", ""]
    tr = data.get("trend") or []
    if len(tr) > 1:
        L += ["### 13.9 Trend między audytami", "",
              _t(["Audyt", "Indeks", "Klasa", "LOC", "ESLint", "Sec H/M", "Martwy kod", "Dup %"],
                 [[e["id"], e.get("score"), e.get("grade"), e.get("loc"), e.get("eslint"),
                   "—" if e.get("sec_high") is None else f"{e['sec_high']}/{e['sec_med']}",
                   e.get("dead") if e.get("dead") is not None else "—", e.get("dup") if e.get("dup") is not None else "—"] for e in tr[-12:]]), ""]
    with (out / "report.md").open("a", encoding="utf-8") as h:
        h.write("\n".join(L) + "\n")
