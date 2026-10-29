"""Professional CodeAudit 2 reporting (stdlib only, fully offline dashboard)."""
from __future__ import annotations
from collections import Counter, defaultdict
import csv
from datetime import datetime
import fnmatch
import html
import json
import math
from pathlib import Path
import statistics

CODE_CATS = {"py_prod", "py_tests", "py_other", "js_prod", "js_tests", "js_other", "ts_prod", "ts_tests", "styles", "html", "scripts", "other_code"}
JS_PROD_CATS = {"js_prod", "js_other", "ts_prod"}
PRIORITY_RULES = {
    "react-hooks/rules-of-hooks", "react-hooks/exhaustive-deps", "react-hooks/refs",
    "react-hooks/immutability", "react-hooks/set-state-in-effect",
    "react-hooks/purity", "react-hooks/unsupported-syntax", "react-hooks/error-boundaries",
    "no-undef", "no-eval", "no-implied-eval", "no-unsafe-optional-chaining",
    "sonarjs/code-eval", "sonarjs/no-hardcoded-passwords", "sonarjs/no-hardcoded-secrets",
}
# Uwaga: sygnały domenowe pomagają ustalić kolejność przeglądu, NIE dowodzą podatności.
SENSITIVE_SIGNALS = {
    "FINANSE / LEDGER": ("finance", "ledger", "wallet", "money", "payment", "transfer", "settlement", "settle", "cash", "vkes", "kes_", "reconcil", "account_store", "balance", "fund_hold"),
    "TOŻSAMOŚĆ / BEZPIECZEŃSTWO": ("auth", "credential", "permission", "secret", "jwt", "token", "hmac", "signature", "security", "crypto", "key_rotat", "access_control"),
    "PRZESYŁKI / TRASY": ("parcel", "checkpoint", "routing", "route", "courier_job", "redistribut", "relocation", "dispatch", "sorting", "bag_"),
    "HUB / TRANSAKCJE": ("hub", "reservation", "transaction", "intake", "delivery", "shipment", "operation"),
}


def fnum(value, places=0):
    if value is None: return "—"
    if isinstance(value, (int, float)):
        if not math.isfinite(value): return "—"
        return f"{value:,.{places}f}".replace(",", " ").replace(".", ",")
    return str(value)


def mean(nums):
    return statistics.mean(nums) if nums else None


def median(nums):
    return statistics.median(nums) if nums else None


def table(headers, rows):
    def cell(v): return str(v).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(cell,headers)) + " |", "|"+"|".join(["---"]*len(headers))+"|"]+
                     ["| " + " | ".join(map(cell,row))+" |" for row in rows])


def key_path(p): return str(p).replace("\\", "/").casefold()


def in_scope(path, exclusions):
    p=key_path(path)
    if p == "var" or p.startswith("var/"): return False
    for item in exclusions:
        pattern=key_path(item.get("path", ""))
        if pattern and (p==pattern or fnmatch.fnmatchcase(p, pattern)): return False
    return True


def summarize_dataset(payload, exclusions):
    """Re-normalize V1/V2 snapshots using the current source scope, no historic fixed figures."""
    filelist=[f for f in payload.get("files",[]) if in_scope(f.get("path",""),exclusions)]
    eligible={key_path(f["path"]) for f in filelist}
    source=[f for f in filelist if f.get("category") in CODE_CATS]
    pyprod=[f for f in filelist if f.get("category")=="py_prod"]
    pytest=[f for f in filelist if f.get("category")=="py_tests"]
    functions=[c for c in payload.get("cc_functions",[]) if key_path(c.get("file","")) in eligible and c.get("category")=="py_prod"]
    counts=Counter(c.get("rank","?") for c in functions)
    mi=[f["radon"]["mi"] for f in pyprod if isinstance(f.get("radon"),dict) and isinstance(f["radon"].get("mi"),(int,float))]
    issues=[m for m in payload.get("eslint_issues",[]) if key_path(m.get("file","")) in eligible]
    js_prod_lines=sum(f.get("physical_lines") or 0 for f in filelist if f.get("category") in JS_PROD_CATS)
    hook_issues=sum(m.get("rule","").startswith("react-hooks/") for m in issues)
    high_issues=sum(m.get("rule") in PRIORITY_RULES for m in issues)
    return {
        "files":len(filelist), "bytes":sum(f.get("bytes",0) for f in filelist),
        "code_files":len(source), "physical_lines":sum(f.get("physical_lines") or 0 for f in source),
        "test_lines":sum(f.get("physical_lines") or 0 for f in filelist if f.get("category") in {"py_tests","js_tests","ts_tests"}),
        "python_prod":len(pyprod), "python_tests":len(pytest),
        "ratio":len(pytest)/len(pyprod) if pyprod else None,
        "markdown":sum(f.get("ext")==".md" for f in filelist),
        "cc_count":len(functions), "cc_avg":mean([c["cc"] for c in functions]),
        "cc_median":median([c["cc"] for c in functions]), "cc_max":max((c["cc"] for c in functions),default=None),
        "cc_ranks":{grade:counts.get(grade,0) for grade in "ABCDEF"},
        "cc_AB_percent":100*(counts["A"]+counts["B"])/len(functions) if functions else None,
        "mi_mean":mean(mi), "mi_median":median(mi), "mi_count":len(mi),
        "eslint_total":len(issues), "eslint_errors":sum(m.get("severity")=="error" for m in issues),
        "eslint_warnings":sum(m.get("severity")=="warning" for m in issues),
        "eslint_high_priority":high_issues, "react_hooks":hook_issues,
        "js_prod_lines":js_prod_lines,
    }


def locate_previous(root, out, requested, disabled):
    if disabled:return None
    if requested:
        p=Path(requested).expanduser().resolve()
        if p.is_dir():p=p/"metrics.json"
        if not p.is_file():raise ValueError(f"Nie znaleziono poprzedniego raportu: {p}")
        if p == out/"metrics.json":raise ValueError("Poprzedni raport nie może być bieżącym")
        return p
    base=out.parent
    candidates=[]
    for p in base.glob("*/metrics.json"):
        if p.resolve()==(out/"metrics.json").resolve():continue
        try:
            with p.open("r",encoding="utf-8") as h:
                # Avoid parsing every 29MB JSON just to find matching project;
                # use folder naming as prefilter then verify project after load.
                if not p.parent.name.startswith(root.name+"_"): continue
            candidates.append(p)
        except OSError:pass
    return max(candidates,key=lambda p:p.stat().st_mtime) if candidates else None


def build_risk_list(payload, chosen, git_info=None, exclusions=None):
    exclusions=exclusions or []
    files=[f for f in payload["files"] if in_scope(f.get("path", ""),exclusions) and f.get("category") in {"py_prod","js_prod","js_other","ts_prod"}]
    py_cc=defaultdict(list)
    for fn in payload.get("cc_functions",[]):
        if fn.get("category")=="py_prod":py_cc[key_path(fn.get("file",""))].append(fn)
    lint=defaultdict(list)
    for issue in payload.get("eslint_issues",[]):
        lint[key_path(issue.get("file",""))].append(issue)
    git_churn={p["file"].casefold():p for p in (git_info or {}).get("all_changed_files",[])}
    risks=[]
    for f in files:
        path=f.get("path",""); low=path.lower()
        signals=[label for label,words in SENSITIVE_SIGNALS.items() if any(word in low for word in words)]
        cc=max((x["cc"] for x in py_cc[key_path(path)]),default=None)
        mi=(f.get("radon") or {}).get("mi")
        crit=sum(m.get("rule") in PRIORITY_RULES for m in lint[key_path(path)])
        lint_n=len(lint[key_path(path)])
        recent=git_churn.get(key_path(path),{})
        lines=f.get("physical_lines") or 0
        # Triage heuristic only. Not a vulnerability or production-readiness grade.
        risk=(min(cc or 0,150)*0.52 +
              max(0,35-mi)*1.2 if mi is not None else min(cc or 0,150)*0.52)
        risk+=min(30,crit*3)+min(12,lint_n*.2)+min(14,lines/450)
        risk+=18 if any(s in signals for s in ("FINANSE / LEDGER","TOŻSAMOŚĆ / BEZPIECZEŃSTWO")) else (10 if signals else 0)
        # Churn only modulates triage moderately; Git history is not a vulnerability signal.
        if recent.get("commits",0)>=12: risk+=min(8, recent["commits"]/4)
        risk=round(risk,1)
        if not (risk>=23 or signals):continue
        priority="P1" if risk>=80 else "P2" if risk>=45 else "P3"
        reasons=[]
        if cc is not None and cc>20: reasons.append(f"CC {cc}")
        if mi is not None and mi<=19: reasons.append(f"MI {mi:.1f}")
        if crit:reasons.append(f"{crit} alertów priorytetowych ESLint")
        if lines>=1200:reasons.append(f"{lines} linii")
        if recent.get("commits",0)>=12:reasons.append(f"{recent['commits']} commitów z historią zmian")
        if not reasons and signals:reasons.append("moduł wrażliwy domenowo — przegląd okresowy")
        risks.append({"file":path,"priority":priority,"risk_index":risk,
                      "domains":signals,"reasons":reasons,"cc_max":cc,"mi":mi,
                      "lines":lines,"eslint_total":lint_n,"eslint_priority":crit,
                      "git_commits":recent.get("commits",0), "git_churn":recent.get("churn",0),
                      "is_sensitive":bool(signals)})
    risks.sort(key=lambda r:(-r["risk_index"],r["file"]))
    return risks


def score_quality(scope, eslint_status):
    cc=scope["cc_AB_percent"]
    mi=scope["mi_median"]
    # Only high-priority ESLint rules, normalized per 1000 physical JS lines.
    js=None
    if scope["js_prod_lines"]>0 and eslint_status=="complete":
        alerts_per_k=1000*scope["eslint_high_priority"]/scope["js_prod_lines"]
        js=max(0,100-8*alerts_per_k)
    measures=[("Niska złożoność Python (udział CC A/B)",cc,0.40),
              ("Maintainability Python (mediana MI)",mi,0.35),
              ("Sygnały ESLint wysokiego priorytetu / 1000 linii",js,0.25)]
    usable=[(k,max(0,min(100,v)),w) for k,v,w in measures if v is not None]
    score=sum(v*w for _,v,w in usable)/sum(w for _,_,w in usable) if usable else None
    grade=("A" if score>=85 else "B" if score>=70 else "C" if score>=55 else "D" if score>=40 else "E") if score is not None else None
    return {"score":round(score,1) if score is not None else None,"grade":grade,
            "scope":"Indeks pomocniczy utrzymywalności CodeAudit, nie ocena architektury, bezpieczeństwa ani działania",
            "components":[{"name":name,"score":round(value,1) if value is not None else None,"weight":weight} for name,value,weight in measures],
            "formula":"40% udział funkcji produkcyjnych CC A/B + 35% mediana MI Python + 25% [100 - 8 × alerty priorytetowe ESLint na 1000 linii JS]; brakujące składniki wyłączane z wag.",
            "eslint_component_partial":js is None}


def compare_scopes(prev,cur):
    specs=[("Pliki źródłowe i dokumentacja","files",0), ("Pliki kodu i testów","code_files",0),
           ("Fizyczne linie kodu i testów","physical_lines",0), ("Python produkcja","python_prod",0),
           ("Python testy","python_tests",0), ("Test/Prod ratio","ratio",3),
           ("Pliki Markdown","markdown",0), ("Liczba funkcji Python prod","cc_count",0),
           ("Średnia CC Python prod","cc_avg",2), ("CC A/B [%]","cc_AB_percent",1),
           ("Mediana MI Python prod","mi_median",2),
           ("Zgłoszenia ESLint","eslint_total",0), ("Błędy ESLint","eslint_errors",0),
           ("Zgłoszenia React Hooks","react_hooks",0)]
    data=[]
    for label,key,places in specs:
        a=prev.get(key);b=cur.get(key)
        data.append({"metric":label,"key":key,"previous":a,"current":b,"delta":round(b-a,3) if isinstance(a,(int,float)) and isinstance(b,(int,float)) else None,
                     "places":places})
    return data


def safe(s):return str(s).replace("|","\\|").replace("\n"," ").replace("\r"," ")


def write_markdown(out,payload,scope,quality,risks,previous,comparison):
    meta=payload["metadata"]; summary=payload["summary"]
    var=payload["var_inventory"]; excluded=payload["excluded_files"]
    py=[f for f in payload["files"] if in_scope(f.get("path",""),excluded) and f.get("ext")==".py"]
    rad=[f for f in py if f.get("radon") and f["radon"].get("raw")]
    hfiles=[f for f in py if f.get("radon") and f["radon"].get("halstead")]
    fn=[f for f in payload.get("cc_functions",[]) if in_scope(f.get("file",""),excluded) and f.get("category")=="py_prod"]
    fn_counts=Counter(f.get("rank","") for f in fn)
    rawkeys=["loc","sloc","lloc","comments","single_comments","multi","blank"]
    rawtot={key:sum(f["radon"]["raw"].get(key,0) for f in rad) for key in rawkeys}
    raw_cats=defaultdict(list)
    for f in payload.get("files",[]):
        if in_scope(f.get("path",""),excluded):raw_cats[f.get("category","other")].append(f)
    cats={key:{"files":len(v),"bytes":sum(x.get("bytes",0) for x in v),"physical_lines":sum(x.get("physical_lines") or 0 for x in v)} for key,v in raw_cats.items()}
    issues=[m for m in payload.get("eslint_issues",[]) if in_scope(m.get("file",""),excluded)]
    rules=Counter(x.get("rule","(none)") for x in issues)
    issue_files=Counter(x.get("file","") for x in issues)
    mi=[f["radon"]["mi"] for f in py if f.get("radon") and f["radon"].get("mi") is not None]
    mi_rank=Counter((f.get("radon") or {}).get("mi_rank") for f in py)
    hkeys=["h1","h2","N1","N2","vocabulary","length","calculated_length","volume","difficulty","effort","time","bugs"]
    result=["# CodeAudit 2.2 — audyt techniczny i utrzymywalności projektu","",
            f"**Projekt:** `{safe(meta['project'])}`  ",f"**Data (UTC):** {meta['generated_at_utc']}  ",
            f"**Silniki:** Radon {meta['radon_version']} · ESLint {meta.get('eslint_version') or 'wyłączony'}  ",
            f"**Analiza:** tylko odczyt · wyniki zapisane poza projektem · bez Gita · bez automatycznych poprawek", "",
            "> **Zastrzeżenie:** to pomiar statyczny. Wskaźniki CC, MI, Halstead i ESLint nie dowodzą bezpieczeństwa, poprawności biznesowej, pokrycia testami ani zgodności z Clean Architecture.","",
            "## 1. Ocena i podsumowanie zarządcze","",
            f"**Indeks pomocniczy utrzymywalności CodeAudit: {fnum(quality['score'],1)}/100 — klasa {quality['grade'] or '—'}.**", "",
            "Jest to własny, jawny wskaźnik trendu, **nie** profesjonalna certyfikacja kodu ani wynik Clean Architecture. Wagi i składniki są w dalszej części raportu.","",
            table(["Metryka","Wynik"],[
                ("Pliki w głównym audycie",fnum(scope['files'])),
                ("Linie kodu/testów (fizyczne)",fnum(scope['physical_lines'])),
                ("Pliki Python produkcja",fnum(scope['python_prod'])),
                ("Pliki Python testy",fnum(scope['python_tests'])),
                ("Test/Prod — udział plików",fnum(scope['ratio'],3)),
                ("Funkcje Python produkcja",fnum(scope['cc_count'])),
                ("Średnia CC Python produkcja",fnum(scope['cc_avg'],2)),
                ("Odsetek CC A/B",f"{fnum(scope['cc_AB_percent'],1)}%"),
                ("Mediana MI Python produkcja",fnum(scope['mi_median'],2)),
                ("Problemy ESLint (źródła)",fnum(scope['eslint_total'])),
                ("Wrażliwe moduły do przeglądu",fnum(sum(r['is_sensitive'] for r in risks))),
                ("Katalog var (inwentaryzacja)",f"{fnum(var['files'])} plików / {fnum(var['bytes']/(1024**3),2)} GiB"),
                ("Pliki jawnie wyłączone",fnum(len(excluded))),
            ]),"",
            "## 2. Porównanie WYŁĄCZNIE z poprzednim audytem","" ]
    if previous:
        result.extend([f"**Poprzedni pomiar:** `{safe(previous['source'])}` · {previous['generated_at'] or 'data nieznana'}", "",
                       "**Metodologia porównania:** identyczny filtr `var/` i wyłączonych plików zastosowany także wstecz do poprzedniego `metrics.json`. Brak porównania z raportami historycznymi na sztywno. Wynik jest miarodajny w zakresie wspólnych definicji metryk; różne wersje narzędzia mogą mieć inne zasady klasyfikacji.","",
                       table(["Metryka","Poprzednio","Teraz","Zmiana"],[[row['metric'],fnum(row['previous'],row['places']),fnum(row['current'],row['places']),
                            (('+' if row['delta']>0 else '')+fnum(row['delta'],row['places'])) if row['delta'] is not None else '—'] for row in comparison]),""])
    else:
        result.extend(["Nie znaleziono wcześniejszego `metrics.json` dla tej samej ścieżki projektu. Raport jest migawką bazową; przy kolejnym uruchomieniu porównanie pojawi się automatycznie.",""])
    result.extend(["## 3. Rozdzielenie źródeł, `var` i plików wyłączonych","",
                   "`var/` jest traktowany jako **artefakty/runtime**: zliczany, lecz bez przetwarzania treści, Radona ani ESLint. Nie zwiększa liczb kodu źródłowego ani problemów ESLint.","",
                   table(["Zakres","Pliki","Bajty","Uwagi"],[
                       ["Kod, testy, dokumenty — główny audyt",fnum(scope['files']),fnum(scope['bytes']),"Radon + ESLint wg rodzaju pliku"],
                       ["`var/` — osobna inwentaryzacja",fnum(var['files']),fnum(var['bytes']),"Tylko statystyki plików"],
                       ["Jawnie wyłączone pliki",fnum(len(excluded)),fnum(sum(e['bytes'] for e in excluded)),"Bez CC/MI/ESLint i bez LOC"],
                   ]),"",
                   "**Pliki wyłączone z audytu:**","",
                   table(["Plik","Powód","Rozmiar (KiB)"],[[f"`{safe(e['path'])}`",safe(e['reason']),fnum(e['bytes']/1024,1)] for e in excluded]) if excluded else "Brak pasujących plików.","",
                   "**`var/` — największe katalogi:**","",
                   table(["Podkatalog","Pliki"],[[f"`{safe(k)}`",fnum(v)] for k,v in list(var.get('top_subdirs',{}).items())[:15]]) if var.get('top_subdirs') else "Katalog `var/` nie istnieje lub pominięto jego inwentaryzację.","",
                   "## 4. Struktura i rozmiary źródeł","",
                   table(["Kategoria","Pliki","Fizyczne linie","MiB"],[[k,fnum(v['files']),fnum(v['physical_lines']),fnum(v['bytes']/(1024*1024),2)] for k,v in sorted(cats.items(),key=lambda kv:-kv[1]['files'])]),"",
                   "## 5. Radon RAW — Python","",
                   table(["Miara","Łącznie"],[[k.upper(),fnum(rawtot[k])] for k in rawkeys]),"",
                   "> Radon `SLOC` i `LLOC` dotyczą wyłącznie Pythona. `comments`, `single_comments` i `multi` nie są niezależnymi rozłącznymi kategoriami, więc nie sumuj ich z LOC.","",
                   "## 6. Cyclomatic Complexity — kod produkcyjny Python","",
                   table(["Ocena","Liczba funkcji","Udział"],[[g,fnum(fn_counts[g]),f"{fnum(100*fn_counts[g]/len(fn) if fn else 0,2)}%"] for g in 'ABCDEF']),"",
                   "**Najbardziej złożone funkcje produkcyjne:**","",
                   table(["Plik","Funkcja","Linia","CC","Klasa"],[[f"`{safe(v['file'])}`",f"`{safe(v['name'])}`",v['line'],v['cc'],v['rank']] for v in sorted(fn,key=lambda x:-x['cc'])[:40]]),"",
                   "## 7. Maintainability Index — pliki Python","",
                   table(["Miara","Wartość"],[
                       ["Liczba plików z MI", fnum(len(mi))], ["Średnia MI",fnum(mean(mi),2)],
                       ["Mediana MI",fnum(median(mi),2)],
                       *[[f"Klasa {g}",fnum(mi_rank[g])] for g in 'ABC']]),"",
                   "**Najniższy MI — tylko aktywny kod produkcyjny:**","",
                   table(["Plik","MI","CC max","SLOC"],[[f"`{safe(f['path'])}`",fnum(f['radon']['mi'],2),
                       fnum(f['radon'].get('cc_max')),fnum((f['radon'].get('raw') or {}).get('sloc'))]
                       for f in sorted([f for f in py if f.get('category')=='py_prod' and f.get('radon') and f['radon'].get('mi') is not None],key=lambda v:v['radon']['mi'])[:35]]),"",
                   "## 8. Halstead — wszystkie 12 metryk","",
                   "Są to miary per plik. `time` i `bugs` to **heurystyki matematyczne**, a nie prognoza realnego czasu lub liczby błędów.","",
                   table(["Metryka","Średnia / plik","Mediana","Maksimum"],[[key,fnum(mean([f['radon']['halstead'][key] for f in hfiles]),2),
                          fnum(median([f['radon']['halstead'][key] for f in hfiles]),2),
                          fnum(max((f['radon']['halstead'][key] for f in hfiles),default=None),2)] for key in hkeys]),"",
                   "**Największe Halstead Volume:**","",
                   table(["Plik","Volume","Difficulty","Effort","Bugs (model)"],[[f"`{safe(f['path'])}`",*[fnum(f['radon']['halstead'][k],2) for k in ('volume','difficulty','effort','bugs')]] for f in sorted(hfiles,key=lambda v:-v['radon']['halstead']['volume'])[:25]]),"",
                   "## 9. ESLint / SonarJS / React Hooks — źródła","",
                   f"Status ESLint: **{summary['eslint']['status']}** · Pliki: **{fnum(summary['eslint']['files_eligible'])}** · Zgłoszenia: **{fnum(len(issues))}**, w tym **{fnum(scope['eslint_errors'])}** błędów i **{fnum(scope['eslint_warnings'])}** ostrzeżeń.","",
                   table(["Reguła","Liczba"],[[f"`{safe(k)}`",fnum(v)] for k,v in rules.most_common(35)]),"",
                   "**Pliki z największą liczbą zgłoszeń:**","",
                   table(["Plik","Zgłoszenia"],[[f"`{safe(k)}`",fnum(v)] for k,v in issue_files.most_common(30)]),"",
                   "## 10. WRAŻLIWE moduły i plan przeglądu","",
                   "Ocena priorytetu opiera się na **złożoności CC, MI, alertach ESLint, wielkości i słowach kluczowych domeny**. To ranking do ręcznego przeglądu, **nie wykryta podatność ani dowód błędu**.","",
                   table(["Priorytet","Plik","Sygnały","Powód","Indeks triage"],[[r['priority'],f"`{safe(r['file'])}`",", ".join(r['domains']) or "złożoność",", ".join(r['reasons']),fnum(r['risk_index'],1)] for r in risks[:70]]),"",
                   "## 11. Metodologia oceny i wizualizacji","",
                   f"**Wzór:** {quality['formula']}","",
                   table(["Komponent","Waga nominalna","Ocena 0–100"],[[c['name'],f"{int(c['weight']*100)}%",fnum(c['score'],1)] for c in quality['components']]),"",
                   "Interpretacja pomocnicza: A ≥85; B ≥70; C ≥55; D ≥40; E <40. Brakujące składniki nie są traktowane jako wynik zero. **Ocena Clean Architecture nie jest wyznaczana.**", "",
                   "Wskaźnik służy przede wszystkim do porównywania pomiarów tą samą konfiguracją narzędzi, nie do oceny bezpieczeństwa, gotowości produkcyjnej lub jakości pracy zespołu.","",
                   "## 12. Integralność pomiaru i ograniczenia","",
                   f"- Liczba zgłoszonych problemów samego pomiaru: **{fnum(len(payload.get('diagnostics',[])))}**.",
                   "- Rozmiar pliku lub jego klasa językowa nie dowodzą przydatności danego modułu.",
                   "- W razie równoległych zmian agenta raport nie jest migawką atomową — pliki mogły być czytane w różnym momencie.",
                   "- Statyczny audyt nie uruchamia testów i nie mierzy faktycznego pokrycia. Test/Prod to relacja liczby plików.",
                   "- Reguły ESLint mogą zależeć od projektu, jego środowiska testowego i przyjętych konwencji React.",
                   "- HTML jest samodzielny (offline): bez zewnętrznych CDN, bibliotek i wysyłania danych do sieci.","",
                   "## 13. Pliki wynikowe","",
                   "- `report.html` — interaktywny, animowany dashboard offline.",
                   "- `report.md` — pełna analiza w Markdown.",
                   "- `metrics.json` — dane szczegółowe, w tym komplet zgłoszeń i pomiarów.",
                   "- `files.csv`, `functions.csv`, `issues.csv` — dane do arkuszy i filtrowania.",
                   "- `sensitive_files.csv` — ranking plików wrażliwych do przeglądu.",""])
    git=payload.get("git_history",{})
    result.extend(["## 14. Historia kodu i struktura repozytorium Git", "",
                   "Lokalne `git log`, `git ls-files`, `git count-objects`, `git diff` (tylko odczyt). Historia Git jest niezależna od porównania z poprzednim pomiarem CodeAudit. Nie pobieramy danych z sieci i nie zmieniamy indexu.", "",
                   table(["Metryka Git", "Wynik"], [
                       ["Status analizy",git.get("status","brak")],
                       ["Gałąź",git.get("branch") or "—"],
                       ["HEAD",(git.get("head") or "—")[:16]],
                       ["Data HEAD",git.get("head_date") or "—"],
                       ["Śledzone pliki (wszystkie, także binaria)",fnum(git.get("tracked_files"))],
                       ["Śledzone pliki z zakresu głównego audytu",fnum(git.get("tracked_source_files"))],
                       ["Pliki lokalne w audycie bez śledzenia przez Git",fnum(git.get("working_copy_untracked_files"))],
                       ["Zmodyfikowane śledzone pliki (względem HEAD)",fnum(git.get("changed_tracked_files"))],
                       ["Pliki metadanych .git",fnum(git.get("git_metadata_files"))],
                       ["Rozmiar metadanych .git (MiB)",fnum(git.get("git_metadata_bytes",0)/1024**2,2)],
                       ["Commity w oknie historii (bez merge)",fnum(git.get("commits_analyzed"))],
                       ["Commity zmieniające kod źródłowy",fnum(git.get("source_commits"))],
                       ["Dodane linie w historii (churn)",fnum(git.get("line_additions"))],
                       ["Usunięte linie w historii (churn)",fnum(git.get("line_deletions"))],
                       ["Zmiana netto w historii (nie obecne LOC)",fnum(git.get("net_line_changes"))],
                   ]),"",
                   f"**Zakres historii:** {git.get('first_commit_date_in_window') or '—'} → {git.get('latest_commit_date_in_window') or '—'}. Limit: {git.get('commits_limit','—')} nie-merge commitów. {'Uwaga: historia ucięta limitem.' if git.get('history_may_be_truncated') else ''}","",
                   "### Miesięczny rozwój kodu", "",
                   table(["Miesiąc","Commity","Commity zmieniające kod","Dodane linie","Usunięte linie","Netto"], [
                       [x['month'],fnum(x.get('commits')),fnum(x.get('source_commits')),
                        fnum(x.get('additions')),fnum(x.get('deletions')),
                        fnum(x.get('additions',0)-x.get('deletions',0))]
                       for x in git.get('timeline_monthly',[])]) if git.get('timeline_monthly') else 'Brak dostępnej historii commitów.',"",
                   "### Aktywność autorów w historii lokalnej", "",
                   table(["Autor (z metadanych Git)", "Commity"], [
                       [safe(x["name"]),fnum(x["commits"])] for x in git.get("authors",[])
                   ]) if git.get("authors") else "Brak danych autorów.","",
                   "### Najczęściej zmieniane pliki źródłowe (Git churn)","",
                   table(["Plik","Zmieniające commity","Dodane linie","Usunięte linie","Churn łącznie"], [
                       [f"`{safe(x['file'])}`",fnum(x['commits']),fnum(x['additions']),fnum(x['deletions']),fnum(x['churn'])]
                       for x in git.get('top_changed_files',[])[:40]]) if git.get('top_changed_files') else 'Brak danych.',"",
                   "### Ostatnie commity w analizowanym oknie", "",
                   table(["SHA","Data","Autor","Opis","Zmiany kodu (+ / −)"], [
                       [f"`{x['sha'][:9]}`",safe(x['date'][:19]),safe(x['author']),safe(x['subject'])[:110],
                        f"+{fnum(x['additions'])} / −{fnum(x['deletions'])}"]
                       for x in git.get('recent_commits',[])]) if git.get('recent_commits') else 'Brak danych.',"",
                   "### Objaśnienia pomiaru Git", "",
                   *['- '+safe(n) for n in git.get('notes',[])],"",
                   "Git nie analizuje historii pracy niezapisanej w commitach. Lokalny katalog `var/` i pliki jawnie wyłączone nie wchodzą do miar churn. Liczba linii dodanych i usuniętych pochodzi z diffów i nie jest dokładną rekonstrukcją wielkości kodu w przeszłości.","",
                   "**Pliki CSV:** `git_commits.csv`, `git_monthly.csv`, `git_weekly.csv`, `git_hotspots.csv`. ",""])
    (out/"report.md").write_text("\n".join(result)+"\n",encoding="utf-8")


def build_professional_reports(root,out,var_stats,excluded,previous_arg,disable_prev,git_info=None):
    def write_csv(path, fieldnames, rows):
        with path.open("w", encoding="utf-8-sig", newline="") as h:
            writer=csv.DictWriter(h, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    path=out/"metrics.json"
    data=json.loads(path.read_text(encoding="utf-8"))
    current=summarize_dataset(data, excluded)
    previous_path=locate_previous(root,out,previous_arg,disable_prev)
    previous=None; comparison=[]
    if previous_path:
        historical=json.loads(previous_path.read_text(encoding="utf-8"))
        previous_meta=historical.get("metadata",{})
        if Path(previous_meta.get("project","")).resolve()!=root.resolve():
            raise ValueError("Poprzedni raport dotyczy innego katalogu projektu: " + previous_meta.get("project", "(brak)"))
        old_scope=summarize_dataset(historical,excluded)
        comparison=compare_scopes(old_scope,current)
        previous={"source":str(previous_path),"generated_at":previous_meta.get("generated_at_utc"),"scope":old_scope}
        from audit_insights import previous_radar
        previous["radar"],previous["quality"]=previous_radar(historical,old_scope,score_quality)
        del historical
    risk=build_risk_list(data,current,git_info,excluded)
    quality=score_quality(current,data["summary"]["eslint"]["status"])
    data["metadata"]["scope_policy"]="Source excludes var/ and excluded_files; var inventory only"
    data["metadata"]["previous_policy"]="only last matching metrics.json, normalized to current exclusions"
    data["var_inventory"]=var_stats
    data["git_history"]=git_info or {"status":"disabled", "commits_analyzed":0}
    data["excluded_files"]=excluded
    data["source_scope"]=current
    data["quality_assessment"]=quality
    data["review_candidates"]=risk
    data["previous_audit"]=previous
    data["comparison_previous_only"]=comparison
    # CodeAudit 2.2: wnioski, radar, trend, macierz plików, aktywność Git
    from audit_insights import (summarize_extras,build_radar,build_file_matrix,git_activity,
                                update_trend,build_executive_summary,write_markdown_extras)
    xs=summarize_extras(data)
    data["extras_summary"]=xs
    data["radar"]=build_radar(current,quality,xs)
    data["file_matrix"]=build_file_matrix(data,risk,git_info)
    data["git_activity"]=git_activity(git_info)
    data["trend"]=update_trend(out,root,data,xs,current,quality,summarize_dataset,score_quality,excluded)
    data["executive_summary"]=build_executive_summary(data,current,quality,risk,previous,xs)
    # Extend JSON data; original history is intentionally not carried forward.
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    write_csv(out/"sensitive_files.csv",["file","priority","risk_index","domains","reasons","cc_max","mi","lines","eslint_total","eslint_priority","is_sensitive"],
              [{**r,"domains":"; ".join(r['domains']),"reasons":"; ".join(r['reasons'])} for r in risk])
    git=git_info or {}
    write_csv(out/"git_commits.csv", ["sha","date","author","subject","files","source_files","additions","deletions"],git.get("commits",[]))
    write_csv(out/"git_monthly.csv",["month","commits","source_commits","additions","deletions"],git.get("timeline_monthly",[]))
    write_csv(out/"git_weekly.csv",["week","commits","source_commits","additions","deletions"],git.get("timeline_weekly",[]))
    write_csv(out/"git_hotspots.csv",["file","commits","additions","deletions","churn"],git.get("all_changed_files",[]))
    write_markdown(out,data,current,quality,risk,previous,comparison)
    write_markdown_extras(out,data)
    from html_dashboard import write_dashboard
    write_dashboard(out,data)
    print(f"Oddzielny var/: {var_stats.get('files',0)} plików, {var_stats.get('bytes',0)/(1024**3):.2f} GiB",flush=True)
    print(f"Wrażliwe/krytyczne moduły w rankingu: {len(risk)}; poprzedni pomiar: {previous_path or 'brak'}",flush=True)
