"""Offline, standalone HTML dashboard for CodeAudit 2.2 (no CDN, no external assets)."""
from __future__ import annotations
import json
from pathlib import Path


def compact_extras(ex:dict)->dict:
    """Zmniejsza dane analizatorów do rozmiaru sensownego w pliku HTML (komplet jest w metrics.json i CSV)."""
    if not ex: return {}
    liz=ex.get("lizard",{}); fns=[f for f in liz.get("functions",[]) if f["cc"]>=6 or f["nloc"]>=60 or f["params"]>=6]
    fns=sorted(fns,key=lambda f:-f["cc"])[:1500]
    dp=ex.get("deps",{}) or {}
    edges=dp.get("all_edges",[]); files=sorted({x for e in edges for x in e}); pos={f:i for i,f in enumerate(files)}
    return {
      "lizard":{**{k:v for k,v in liz.items() if k!="functions"},"functions":fns},
      "bandit":{**{k:v for k,v in ex.get("bandit",{}).items() if k!="issues"},"issues":ex.get("bandit",{}).get("issues",[])[:4000]},
      "pip_audit":ex.get("pip_audit",{}),
      "vulture":{**{k:v for k,v in ex.get("vulture",{}).items() if k!="items"},"items":ex.get("vulture",{}).get("items",[])[:3000]},
      "duplication":{k:v for k,v in ex.get("duplication",{}).items() if k!="by_file"},
      "deps":{**{k:v for k,v in dp.items() if k!="all_edges"},"files":files,"edges":[[pos[a],pos[b]] for a,b in edges[:20000]]},
    }


def write_dashboard(out:Path, payload:dict):
    compact = {
      "meta":payload["metadata"],
      "scope":payload["source_scope"],
      "quality":payload["quality_assessment"],
      "var":payload["var_inventory"],
      "git":{k:v for k,v in payload.get("git_history",{}).items() if k not in {"commits","all_changed_files"}},
      "excluded":payload["excluded_files"],
      "previous":payload["previous_audit"],
      "comparison":payload["comparison_previous_only"],
      "categories":payload["categories"],
      "folders":payload["folders"],
      "risks":payload["review_candidates"],
      "issues":payload["eslint_issues"],
      "functions":[f for f in payload["cc_functions"] if f["category"]=="py_prod"],
      "files":[{"path":f["path"], "category":f["category"],"physical_lines":f.get("physical_lines"),
                "mi":(f.get("radon") or {}).get("mi"),"cc_max":(f.get("radon") or {}).get("cc_max"),
                "halstead":((f.get("radon") or {}).get("halstead") or {}).get("volume")}
               for f in payload["files"] if f["category"].startswith("py_")],
      "status":payload["summary"].get("eslint",{}),
      "errors":payload.get("diagnostics",[]),
      # CodeAudit 2.2
      "xs":payload.get("extras_summary",{}), "radar":payload.get("radar",[]),
      "exec":payload.get("executive_summary"), "trend":payload.get("trend",[]),
      "matrix":payload.get("file_matrix",[]), "activity":payload.get("git_activity",{}),
      "ex":compact_extras(payload.get("extras") or {}),
    }
    packed=json.dumps(compact,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template = r'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="dark light"><title>CodeAudit 2.1 · Engineering Intelligence</title>
<style>
:root{--bg:#0a1020;--surface:#121c31;--surface2:#18243c;--line:#283650;--text:#eaf0fb;--muted:#94a7c5;--cyan:#63c7fa;--violet:#aa98ff;--green:#55d6ad;--amber:#f6bf65;--red:#ff7a8a;--shadow:0 20px 65px #01081770;--radius:17px}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 75% -9%,#1a2b61 0,transparent 38%),radial-gradient(circle at -10% 18%,#15384b 0,transparent 35%),var(--bg);color:var(--text);font:14px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;min-width:320px}body.light{--bg:#eef4fb;--surface:#fff;--surface2:#f1f5fc;--line:#d7e1ec;--text:#15243b;--muted:#526681;--shadow:0 15px 48px #344f7719;background:#f1f5fb}a{color:inherit;text-decoration:none}.shell{max-width:1560px;margin:auto;padding:0 28px}.top{position:sticky;top:0;z-index:25;background:#0a1020de;backdrop-filter:blur(20px);border-bottom:1px solid #2b3a54}body.light .top{background:#f2f6f9e6}.topinner{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:70px}.brand{display:flex;gap:12px;align-items:center;font-weight:750;letter-spacing:.06em}.mark{width:35px;height:35px;background:linear-gradient(140deg,var(--cyan),var(--violet));color:#071526;border-radius:11px;display:grid;place-items:center;font-weight:900}.nav{display:flex;gap:17px;flex-wrap:wrap}.nav a{color:var(--muted);font-size:13px}.nav a:hover{color:var(--cyan)}button,input,select{font:inherit}button{cursor:pointer;color:var(--text);background:var(--surface2);border:1px solid var(--line);border-radius:10px;padding:9px 12px}button:hover{border-color:var(--cyan)}.hero{padding:62px 0 30px;display:grid;grid-template-columns:1fr auto;gap:20px;align-items:end}.eyebrow{text-transform:uppercase;letter-spacing:.2em;color:var(--cyan);font-size:11px;font-weight:750}.hero h1{font-size:clamp(36px,5vw,64px);line-height:1.06;letter-spacing:-.05em;margin:12px 0 14px}.hero h1 em{font-style:normal;background:linear-gradient(90deg,var(--cyan),var(--violet));background-clip:text;-webkit-background-clip:text;color:transparent}.desc{max-width:820px;color:var(--muted);font-size:15px}.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:20px}.chip{border:1px solid var(--line);border-radius:30px;padding:5px 10px;color:var(--muted);font-size:11px}.layout{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px}.card{background:linear-gradient(145deg,var(--surface),var(--surface2));border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:22px;min-width:0;animation:rise .55s both}.kpi{grid-column:span 3;min-height:138px}.kpi .metric{font-size:clamp(25px,3vw,40px);font-weight:760;letter-spacing:-.055em;margin:14px 0 4px;font-variant-numeric:tabular-nums}.kpi .sub{font-size:12px;color:var(--muted)}.card h3{font-size:15px;margin:0 0 6px;font-weight:700}.section{margin:40px 0 14px;display:flex;align-items:center;justify-content:space-between;gap:12px}.section h2{font-size:22px;letter-spacing:-.02em;margin:0}.section p{margin:5px 0 0;color:var(--muted);font-size:12px}.span4{grid-column:span 4}.span5{grid-column:span 5}.span6{grid-column:span 6}.span7{grid-column:span 7}.span8{grid-column:span 8}.span12{grid-column:span 12}.muted{color:var(--muted)}.label{font-size:12px;letter-spacing:.03em;color:var(--muted)}.scoreArea{display:flex;gap:24px;align-items:center;flex-wrap:wrap}.gauge{position:relative;width:178px;height:178px;flex:none}.gauge svg{width:100%;height:100%;transform:rotate(-90deg)}.gauge circle{fill:none;stroke:var(--line);stroke-width:12}.gauge .progress{stroke:url(#scoregrad);stroke-linecap:round;stroke-dasharray:439.82;stroke-dashoffset:439.82;transition:stroke-dashoffset 1.5s cubic-bezier(.2,.8,.2,1)}.gaugeVal{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;align-items:center}.gaugeVal strong{font-size:45px;font-weight:790;line-height:1}.gaugeVal span{font-size:12px;color:var(--muted)}.scoreExplanation{flex:1;min-width:200px}.bigLetter{display:inline-flex;align-items:center;gap:8px;font-size:26px;font-weight:800}.legend{display:flex;gap:15px;flex-wrap:wrap;margin:13px 0}.legend span{font-size:12px;color:var(--muted)}.dot{display:inline-block;width:8px;height:8px;border-radius:3px;margin-right:5px}.stacked{display:flex;width:100%;height:26px;overflow:hidden;border-radius:6px;background:var(--surface2);margin:24px 0 10px}.stacked>div{height:100%;width:0;transition:width 1.2s ease-out;position:relative}.chartBars{display:flex;align-items:flex-end;gap:13px;min-height:210px;margin:22px 0 0;border-bottom:1px solid var(--line);padding:10px 4px 0}.barCol{flex:1;display:flex;flex-direction:column;align-items:center;gap:6px;justify-content:flex-end;height:194px;min-width:0}.barNum{font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}.bar{width:min(100%,54px);height:0;border-radius:7px 7px 0 0;transition:height 1.2s cubic-bezier(.12,.7,.27,1)}.barGrade{font-size:11px;padding:5px}.minibar{background:var(--line);height:8px;border-radius:8px;overflow:hidden;margin-top:7px}.minibar span{display:block;height:100%;background:linear-gradient(90deg,var(--cyan),var(--violet));width:0;transition:width 1s ease}.tblWrap{overflow:auto;max-width:100%;border-radius:12px}table{width:100%;border-collapse:collapse;font-size:12px;white-space:nowrap}thead{position:sticky;top:0;background:var(--surface2);z-index:2}th,td{text-align:left;padding:12px 11px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-weight:630}tbody tr:hover{background:#6682b412}td.numeric{text-align:right;font-variant-numeric:tabular-nums}td.path{max-width:480px;overflow:hidden;text-overflow:ellipsis}code{font:12px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;color:var(--cyan)}.badge{font-size:10px;font-weight:790;letter-spacing:.04em;padding:5px 8px;border-radius:7px}.P1{color:#ffc4cc;background:#cf39402b}.P2{color:#ffcd94;background:#d38e3b29}.P3{color:#90d8fa;background:#448ccc25}.panelHead{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:14px}.filters{display:flex;gap:8px;flex-wrap:wrap}.filters input,.filters select{background:var(--surface2);border:1px solid var(--line);color:var(--text);padding:9px;border-radius:9px;outline:none;min-width:140px}.filters input:focus{border-color:var(--cyan)}.callout{border:1px solid #c89e4545;border-left:3px solid var(--amber);border-radius:8px;padding:13px 16px;background:#f5b9530b;color:var(--muted);line-height:1.65}.callout b{color:var(--text)}.listitem{border-bottom:1px solid var(--line);padding:12px 0}.listitem:last-child{border:0}.small{font-size:12px}.unit{color:var(--muted);font-size:11px}.delta.plus{color:var(--amber)}.delta.minus{color:var(--green)}.pager{display:flex;align-items:center;justify-content:flex-end;gap:10px;padding-top:12px}.pager button{padding:5px 12px}.pager button:disabled{opacity:.4;cursor:not-allowed}.footer{padding:36px 0 80px;text-align:center;color:var(--muted);font-size:12px}.fadein{opacity:0;transform:translateY(11px);transition:opacity .6s,transform .6s}.fadein.visible{opacity:1;transform:none}.pill{border-radius:20px;padding:5px 9px;font-size:11px;background:var(--surface2);border:1px solid var(--line);color:var(--muted)}.pill b{color:var(--text)}@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}@media(max-width:1100px){.kpi{grid-column:span 6}.span4,.span5,.span6,.span7,.span8{grid-column:span 12}.nav{display:none}}@media(max-width:600px){.shell{padding:0 15px}.kpi{grid-column:span 6;padding:16px}.hero{padding:35px 0;grid-template-columns:1fr}.card{padding:17px}.gauge{width:145px;height:145px}.scoreArea{gap:10px}.kpi .metric{font-size:24px}.section h2{font-size:19px}}@media(prefers-reduced-motion:reduce){*,*::after,*::before{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
.gitKPIs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:14px}.gitKPI{background:var(--surface2);padding:18px;border-radius:12px;border:1px solid var(--line)}.gitKPI b{display:block;font-size:24px;line-height:1.2;margin:8px 0;font-variant-numeric:tabular-nums}.gitGraph{display:flex;align-items:flex-end;height:230px;gap:5px;padding:10px 4px 0;border-bottom:1px solid var(--line);overflow-x:auto}.gitGroup{display:flex;gap:2px;align-items:end;min-width:18px;height:100%;flex:1;position:relative}.gitBar{display:block;width:50%;min-height:2px;border-radius:4px 4px 0 0;transition:height .85s cubic-bezier(.12,.8,.22,1);height:0}.gitBar.add{background:linear-gradient(0deg,#20768f,#62caed)}.gitBar.del{background:linear-gradient(0deg,#995075,#f0949c)}.gitXAxis{display:flex;justify-content:space-between;color:var(--muted);font-size:10px;margin-top:10px;gap:5px;flex-wrap:wrap}.gitLegend{display:flex;gap:16px;align-items:center;font-size:12px;color:var(--muted);margin:13px 0}.gitLegend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}.gitRecent{max-height:380px;overflow:auto} .gitGroup:hover{filter:brightness(1.35)}@media(max-width:900px){.gitKPIs{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:480px){.gitKPIs{grid-template-columns:1fr}}</style></head><body>
<header class="top"><div class="shell topinner"><div class="brand"><div class="mark">C</div><span>CODEAUDIT <span style="color:var(--muted)">/ 2.1</span></span></div><nav class="nav"><a href="#overview">Podsumowanie</a><a href="#quality">Jakość</a><a href="#compare">Porównanie</a><a href="#sensitive">Przegląd</a><a href="#eslint">ESLint</a><a href="#git">Git</a><a href="#scope">Zakres</a></nav><button id="theme">☼ Motyw</button></div></header>
<main class="shell"><section class="hero"><div><div class="eyebrow">ENGINEERING INTELLIGENCE / STATIC ANALYSIS</div><h1>Stan kodu. <em>Bez domysłów.</em></h1><p class="desc">Profesjonalny raport jakości, struktury i długu technicznego. Radon × Halstead × ESLint × SonarJS. Osobna inwentaryzacja plików generowanych i jawne wyłączenia z audytu.</p><div class="chips" id="metaChips"></div></div><div class="pill">● OFFLINE · ZERO CDN</div></section>
<section class="layout" id="overview"><div class="card kpi"><div class="label">Fizyczne linie kodu</div><div class="metric" data-count="0" id="kLines">0</div><div class="sub">Tylko źródła i testy</div></div><div class="card kpi"><div class="label">Pliki w audycie</div><div class="metric" id="kFiles">0</div><div class="sub">Bez var i plików wyłączonych</div></div><div class="card kpi"><div class="label">Funkcje Python prod</div><div class="metric" id="kFunctions">0</div><div class="sub">Metryka CC</div></div><div class="card kpi"><div class="label">Alerty ESLint</div><div class="metric" id="kEslint">0</div><div class="sub" id="kEslintSub">Błędy / ostrzeżenia</div></div></section>
<div class="section" id="quality"><div><h2>Ocena utrzymywalności</h2><p>Jawny indeks trendu CodeAudit — nie ocena bezpieczeństwa ani Clean Architecture</p></div></div><section class="layout"><div class="card span5"><div class="scoreArea"><div class="gauge"><svg viewBox="0 0 180 180" aria-hidden="true"><defs><linearGradient id="scoregrad"><stop offset="0%" stop-color="#58cffb"/><stop offset="100%" stop-color="#ad93ff"/></linearGradient></defs><circle cx="90" cy="90" r="70"/><circle class="progress" cx="90" cy="90" r="70" id="gaugeProgress"/></svg><div class="gaugeVal"><strong id="qScore">—</strong><span>/ 100</span></div></div><div class="scoreExplanation"><div class="label">Maintenance signal</div><div class="bigLetter" id="qGrade">—</div><p class="muted small" id="qExplain"></p></div></div><div id="scoreComponents"></div></div>
<div class="card span7"><div class="panelHead"><div><h3>Rozkład Cyclomatic Complexity</h3><div class="muted small">Funkcje Python w kodzie produkcyjnym · A/B oznacza niższą złożoność</div></div></div><div class="stacked" id="complexStack"></div><div class="legend" id="ccLegend"></div><div class="chartBars" id="ccChart"></div></div></section>
<div class="section" id="compare"><div><h2>Porównanie z poprzednim audytem</h2><p>Dokładnie jeden poprzedni metrics.json — bez tabeli historycznej wpisanej na stałe</p></div></div><div class="card"><div id="previousLabel" class="muted small"></div><div class="tblWrap"><table><thead><tr><th>Metryka</th><th>Poprzednio</th><th>Obecnie</th><th>Zmiana</th></tr></thead><tbody id="compareRows"></tbody></table></div></div>
<div class="section" id="sensitive"><div><h2>Wrażliwe i złożone moduły</h2><p>Lista priorytetów ręcznego code review na podstawie CC, MI, Hooks i wrażliwości domenowej</p></div></div><div class="card"><div class="callout"><b>Interpretacja:</b> podwyższony indeks triage nie jest podatnością. Moduły finansowe, autoryzacja, rozliczenia i przesyłki są dodatkowo flagowane do okresowego przeglądu ze względu na ich znaczenie biznesowe.</div><div class="panelHead" style="margin-top:18px"><div class="filters"><input id="riskSearch" type="search" placeholder="Szukaj pliku / domeny…" aria-label="Szukaj wrażliwych plików"/><select id="riskLevel"><option value="">Wszystkie priorytety</option><option>P1</option><option>P2</option><option>P3</option></select><select id="riskKind"><option value="">Wszystkie</option><option value="sensitive">Tylko domenowo wrażliwe</option><option value="complex">CC &gt; 20</option></select></div><span class="muted small" id="riskCount"></span></div><div class="tblWrap"><table><thead><tr><th>Priorytet</th><th>Plik</th><th>Domena / sygnały</th><th>CC</th><th>MI</th><th>Indeks</th></tr></thead><tbody id="riskRows"></tbody></table></div><div class="pager"><button id="riskPrev">←</button><span id="riskPage" class="muted small"></span><button id="riskNext">→</button></div></div>
<div class="section" id="eslint"><div><h2>ESLint · SonarJS · React</h2><p>Wyszukiwalne zgłoszenia z plików źródłowych; pełne dane także w issues.csv</p></div></div><section class="layout"><div class="card span5"><h3>Najczęściej zgłaszane reguły</h3><div class="tblWrap"><table><thead><tr><th>Reguła</th><th>Ostrzeżenia / błędy</th></tr></thead><tbody id="ruleRows"></tbody></table></div></div><div class="card span7"><div class="panelHead"><h3>Rejestr zgłoszeń</h3><div class="filters"><input id="issueSearch" type="search" placeholder="Ścieżka, reguła, treść…"/><select id="issueSeverity"><option value="">Wszystkie</option><option value="error">Błędy</option><option value="warning">Ostrzeżenia</option></select><select id="issueFocus"><option value="">Wszystkie reguły</option><option value="priority">Priorytetowe</option><option value="react-hooks/">React Hooks</option></select></div></div><div class="tblWrap" style="max-height:560px"><table><thead><tr><th>Poziom</th><th>Plik : linia</th><th>Reguła / komunikat</th></tr></thead><tbody id="issueRows"></tbody></table></div><div class="pager"><span id="issueCount" class="muted small"></span><button id="issuePrev">←</button><span id="issuePage" class="muted small"></span><button id="issueNext">→</button></div></div></section>
<div class="section" id="structure"><div><h2>Architektura plików</h2><p>Podział na warstwy, testy i zasoby; metryki z fizycznego systemu plików</p></div></div><section class="layout"><div class="card span6"><h3>Największe grupy plików</h3><div id="catBars"></div></div><div class="card span6"><h3>Największe katalogi</h3><div class="tblWrap"><table><thead><tr><th>Katalog</th><th>Pliki</th><th>Linie kodu</th></tr></thead><tbody id="folderRows"></tbody></table></div></div></section>
<div class="section" id="git"><div><h2>Historia Git · ewolucja kodu</h2><p>Commity, tempo prac, przyrosty i usunięcia kodu, aktywność repozytorium — wyłącznie lokalne dane Git</p></div></div>
<section class="layout"><div class="card span12">
  <div class="panelHead"><h3>Historia projektu</h3><span class="chip" id="gitBranch">—</span></div>
  <p class="muted small" id="gitNote"></p>
  <div class="gitKPIs"><div class="gitKPI"><div class="label">Commity w analizowanym zakresie</div><b id="gitCommits">—</b><span class="muted small" id="gitWindow">—</span></div>
  <div class="gitKPI"><div class="label">Pliki śledzone przez Git</div><b id="gitTracked">—</b><span class="muted small">Obejmuje również pliki poza audytem źródłowym</span></div>
  <div class="gitKPI"><div class="label">Dodane linie kodu (diffy)</div><b id="gitAdded" style="color:var(--cyan)">—</b><span class="muted small">W oknie historii Git</span></div>
  <div class="gitKPI"><div class="label">Usunięte linie kodu (diffy)</div><b id="gitRemoved" style="color:var(--red)">—</b><span class="muted small">Churn ≠ obecne LOC</span></div></div>
  <div class="panelHead"><h3>Tempo rozwoju kodu</h3><select id="gitFreq" aria-label="Agregacja osi czasu"><option value="monthly">Miesiące</option><option value="weekly">Tygodnie</option></select></div>
  <div class="gitLegend"><span><i style="background:#62caed"></i>Dodane linie</span><span><i style="background:#f0949c"></i>Usunięte linie</span></div>
  <div class="gitGraph" id="gitGraph" role="img" aria-label="Wykres przyrostu i usuwania linii w Git"></div><div class="gitXAxis" id="gitAxis"></div>
  <p class="muted small">Wykres przedstawia zmiany w commitach, a nie przyrost obecnej liczby LOC. Nie uwzględnia zmian niezatwierdzonych.</p>
</div>
<div class="card span6"><h3>Najczęściej zmieniane pliki źródłowe</h3><div class="tblWrap"><table><thead><tr><th>Plik</th><th>Commity</th><th>Linie ±</th></tr></thead><tbody id="gitHotRows"></tbody></table></div></div>
<div class="card span6"><h3>Ostatnie commity</h3><div class="gitRecent tblWrap"><table><thead><tr><th>Data</th><th>Commit</th><th>Zmiany kodu</th></tr></thead><tbody id="gitRecentRows"></tbody></table></div><p class="muted small">Więcej danych: git_commits.csv, git_hotspots.csv, git_monthly.csv oraz git_weekly.csv.</p></div>
<div class="card span12"><h3>Aktywność według autora — na podstawie metadanych commitów</h3><div class="tblWrap"><table><thead><tr><th>Autor w historii Git</th><th>Commity</th></tr></thead><tbody id="gitAuthorRows"></tbody></table></div><p class="muted small">Różne imiona/adresy w konfiguracji Git mogą oznaczać tę samą osobę; nie jest to ocena pracy autorów.</p></div></section>
<div class="section" id="scope"><div><h2>Zakres i wyłączenia</h2><p>Audyt źródłowy oddzielony od artefaktów środowiskowych</p></div></div><section class="layout"><div class="card span6"><h3>Katalog var/ — osobna inwentaryzacja</h3><div class="metric" id="varFiles" style="font-size:36px;font-weight:750">—</div><div class="muted small" id="varSize"></div><div class="tblWrap"><table><thead><tr><th>Podkatalog</th><th>Pliki</th></tr></thead><tbody id="varRows"></tbody></table></div></div><div class="card span6"><h3>Pliki wyłączone z audytu</h3><div class="muted small">Nie wchodzą do LOC, Radon, ESLint ani oceny jakości. Obowiązuje jawna lista w audit-settings.json.</div><div id="excludedRows"></div></div></section>
<div class="section"><div><h2>Metodologia i ograniczenia</h2></div></div><div class="card"><p id="formula" class="small muted"></p><div class="callout">Analiza statyczna nie dowodzi, że kod działa poprawnie. Testy, pomiar pokrycia, analiza zależności, profilowanie i przegląd bezpieczeństwa pozostają osobnymi czynnościami. Halstead „Bugs” i „Time” to wskaźniki modelowe, nie prognozy realnych błędów i godzin. Wskaźniki są najbardziej wiarygodne jako trend przy tej samej konfiguracji.</div><p class="muted small" id="integrity"></p></div></main><footer class="footer">CodeAudit 2.1 · Radon + ESLint + SonarJS + Git · Wygenerowane lokalnie · Bez telemetrii, zewnętrznych skryptów i połączeń sieciowych</footer>
<script id="snapshot" type="application/json">__EMBEDDED_DATA__</script><script>
'use strict';
const DATA=JSON.parse(document.getElementById('snapshot').textContent);
const $=id=>document.getElementById(id);
const number=new Intl.NumberFormat('pl-PL',{maximumFractionDigits:2});
const nf=(v,d=0)=>v==null?'—':Number(v).toLocaleString('pl-PL',{maximumFractionDigits:d,minimumFractionDigits:d});
const escapeHTML=x=>String(x??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const addRow=(cells,types=[])=>'<tr>'+cells.map((c,i)=>`<td class="${types[i]||''}" title="${escapeHTML(c)}">${escapeHTML(c)}</td>`).join('')+'</tr>';
const grades={A:'#4bdfad',B:'#8cd3a5',C:'#f1c56e',D:'#f79b6c',E:'#ee7b83',F:'#c45c86'};
function animateNumber(el,target){if(matchMedia('(prefers-reduced-motion: reduce)').matches){el.textContent=nf(target);return;}let start=null;function step(ts){if(start===null)start=ts;let p=Math.min(1,(ts-start)/1000);el.textContent=nf(Math.round(target*(1-Math.pow(1-p,3))));if(p<1)requestAnimationFrame(step);}requestAnimationFrame(step)}
function initialize(){
 const s=DATA.scope,q=DATA.quality;
 $('metaChips').innerHTML=[DATA.meta.project,DATA.meta.generated_at_utc,'Radon '+DATA.meta.radon_version,'ESLint '+(DATA.meta.eslint_version||'—')].map(v=>`<span class="chip">${escapeHTML(v)}</span>`).join('');
 animateNumber($('kLines'),s.physical_lines);animateNumber($('kFiles'),s.files);animateNumber($('kFunctions'),s.cc_count);animateNumber($('kEslint'),s.eslint_total);
 $('kEslintSub').textContent=`${nf(s.eslint_errors)} błędów / ${nf(s.eslint_warnings)} ostrzeżeń`;
 $('qScore').textContent=nf(q.score,1);$('qGrade').textContent=`Klasa ${q.grade||'—'}`;
 $('qExplain').textContent=q.scope+' · '+(q.eslint_component_partial?'Wynik częściowy: ESLint niekompletny.':'3 składniki aktywne.');
 const ring=$('gaugeProgress');setTimeout(()=>ring.style.strokeDashoffset=(439.82*(1-(q.score||0)/100)).toFixed(2),250);
 $('scoreComponents').innerHTML=q.components.map(x=>`<div style="margin:15px 0"><div style="display:flex;justify-content:space-between;gap:10px;font-size:12px"><span>${escapeHTML(x.name)}</span><strong>${nf(x.score,1)} / 100</strong></div><div class="minibar"><span data-width="${x.score||0}%"></span></div></div>`).join('');
 let cc=s.cc_ranks||{},ccTotal=Object.values(cc).reduce((a,b)=>a+b,0)||1;
 $('complexStack').innerHTML='ABCDEF'.split('').map(g=>`<div title="${g}: ${nf(cc[g]||0)}" data-width="${(cc[g]||0)/ccTotal*100}%" style="background:${grades[g]}"></div>`).join('');
 $('ccLegend').innerHTML='ABCDEF'.split('').map(g=>`<span><i class="dot" style="background:${grades[g]}"></i>${g}: ${nf(cc[g]||0)}</span>`).join('');
 let maxcc=Math.max(1,...Object.values(cc));$('ccChart').innerHTML='ABCDEF'.split('').map(g=>`<div class="barCol"><div class="barNum">${nf(cc[g]||0)}</div><div class="bar" style="background:${grades[g]}" data-height="${Math.max(2,(cc[g]||0)/maxcc*165)}px"></div><div class="barGrade">${g}</div></div>`).join('');
 let prev=DATA.previous;
 $('previousLabel').textContent=prev?`Źródło: ${prev.source} · ${prev.generated_at||''}`:'Nie znaleziono wcześniejszego audytu. Bieżący pomiar będzie punktem odniesienia dla następnego.';
 $('compareRows').innerHTML=DATA.comparison.length?DATA.comparison.map(r=>addRow([r.metric,nf(r.previous,r.places),nf(r.current,r.places),r.delta==null?'—':(r.delta>0?'+':'')+nf(r.delta,r.places)])).join(''):'<tr><td colspan="4">Brak danych do porównania.</td></tr>';
 const rules={};DATA.issues.forEach(m=>rules[m.rule]=(rules[m.rule]||0)+1);
 $('ruleRows').innerHTML=Object.entries(rules).sort((a,b)=>b[1]-a[1]).slice(0,30).map(([n,v])=>addRow([n,nf(v)])).join('');
 $('catBars').innerHTML=Object.entries(DATA.categories).sort((a,b)=>b[1].files-a[1].files).slice(0,12).map(([k,v],_,arr)=>`<div style="margin:13px 0"><div style="display:flex;justify-content:space-between;font-size:12px;gap:10px"><span>${escapeHTML(k)}</span><b>${nf(v.files)}</b></div><div class="minibar"><span data-width="${Math.max(2,100*v.files/arr[0][1].files)}%"></span></div></div>`).join('');
 $('folderRows').innerHTML=Object.entries(DATA.folders).sort((a,b)=>b[1].files-a[1].files).slice(0,18).map(([k,v])=>addRow([k,nf(v.files),nf(v.code_lines)])).join('');
 $('varFiles').textContent=nf(DATA.var.files)+' plików';$('varSize').textContent=(DATA.var.bytes/(1024**3)).toLocaleString('pl-PL',{maximumFractionDigits:2})+' GiB · wyłączone z analizy jakości';
 $('varRows').innerHTML=Object.entries(DATA.var.top_subdirs||{}).slice(0,20).map(([k,v])=>addRow([k,nf(v)])).join('');
 $('excludedRows').innerHTML=DATA.excluded.length?DATA.excluded.map(e=>`<div class="listitem"><code>${escapeHTML(e.path)}</code><div class="muted small">${escapeHTML(e.reason)} · ${(e.bytes/1024).toFixed(1)} KiB</div></div>`).join(''):'<p class="muted">Brak pasujących wyłączeń.</p>';
 $('formula').textContent=q.formula;
 $('integrity').textContent='Diagnostyka przebiegu: '+DATA.errors.length+' zgłoszeń · ESLint: '+DATA.status.status+' · '+nf(DATA.status.files_returned)+' plików JS.';
 document.querySelectorAll('[data-width]').forEach(el=>setTimeout(()=>el.style.width=el.dataset.width,280));
 document.querySelectorAll('[data-height]').forEach(el=>setTimeout(()=>el.style.height=el.dataset.height,280));
}

function renderGitChart(){
 const g=DATA.git||{};const freq=$('gitFreq').value;
 const source=freq==='weekly'?g.timeline_weekly:g.timeline_monthly;
 const items=(source||[]).slice(freq==='weekly'?-32:-24);
 if(!items.length){$('gitGraph').innerHTML='<span class="muted">Brak historii Git dla bieżącego repozytorium.</span>';$('gitAxis').textContent='';return;}
 const max=Math.max(1,...items.map(x=>Math.max(x.additions||0,x.deletions||0)));
 $('gitGraph').innerHTML=items.map(x=>{let add=Math.max(2,(x.additions||0)/max*204),del=Math.max(2,(x.deletions||0)/max*204);
 let label=escapeHTML(x.month||x.week||'');return `<div class="gitGroup" title="${label}: +${nf(x.additions||0)} / −${nf(x.deletions||0)} linii, ${nf(x.commits||0)} commitów"><span class="gitBar add" data-git-height="${add}px"></span><span class="gitBar del" data-git-height="${del}px"></span></div>`}).join('');
 const indices=[0,Math.floor((items.length-1)/3),Math.floor(2*(items.length-1)/3),items.length-1];
 $('gitAxis').innerHTML=[...new Set(indices)].map(i=>`<span>${escapeHTML(items[i].month||items[i].week||'')}</span>`).join('');
 requestAnimationFrame(()=>{document.querySelectorAll('[data-git-height]').forEach(x=>x.style.height=x.dataset.gitHeight)});
}
function initializeGit(){const g=DATA.git||{};
 $('gitBranch').textContent=g.branch||'Brak repozytorium';$('gitCommits').textContent=nf(g.commits_analyzed||0);
 $('gitTracked').textContent=nf(g.tracked_files||0);$('gitAdded').textContent='+'+nf(g.line_additions||0);
 $('gitRemoved').textContent='−'+nf(g.line_deletions||0);
 $('gitWindow').textContent=`Limit: ${nf(g.commits_limit||0)} commitów`;
 $('gitNote').textContent=(g.status==='complete'?'Odczytano lokalną historię aktualnej gałęzi.':`Status Git: ${g.status||'niedostępny'}.`)+
 (g.history_may_be_truncated?' Historia starszych commitów ucięta limitem.':'')+'  HEAD: '+(g.head||'—').slice(0,12);
 $('gitHotRows').innerHTML=(g.top_changed_files||[]).slice(0,18).map(x=>addRow([x.file,nf(x.commits),nf(x.churn)])).join('')||'<tr><td colspan="3">Brak danych Git.</td></tr>';
 $('gitRecentRows').innerHTML=(g.recent_commits||[]).slice(0,15).map(x=>addRow([x.date.slice(0,10),x.sha.slice(0,9)+' · '+x.subject.slice(0,76),'+'+nf(x.additions)+' / −'+nf(x.deletions)])).join('')||'<tr><td colspan="3">Brak commitów.</td></tr>';
 $('gitAuthorRows').innerHTML=(g.authors||[]).map(x=>addRow([x.name,nf(x.commits)])).join('')||'<tr><td colspan="2">Brak danych.</td></tr>';
 $('gitFreq').addEventListener('change',renderGitChart);renderGitChart();
}

let riskPage=0,issuePage=0;
function renderRisks(){const term=$('riskSearch').value.toLowerCase(),level=$('riskLevel').value,kind=$('riskKind').value;
 const d=DATA.risks.filter(r=>(!level||r.priority===level)&&(!kind||(kind==='sensitive'?r.is_sensitive:(r.cc_max||0)>20))&&(`${r.file} ${r.domains.join(' ')} ${r.reasons.join(' ')}`.toLowerCase().includes(term)));
 const per=25,pages=Math.max(1,Math.ceil(d.length/per));riskPage=Math.min(riskPage,pages-1);
 $('riskRows').innerHTML=d.slice(riskPage*per,(riskPage+1)*per).map(r=>`<tr><td><span class="badge ${r.priority}">${r.priority}</span></td><td class="path"><code title="${escapeHTML(r.file)}">${escapeHTML(r.file)}</code></td><td class="small">${escapeHTML(r.domains.join(', ')||r.reasons.join(', '))}</td><td class="numeric">${nf(r.cc_max)}</td><td class="numeric">${nf(r.mi,1)}</td><td class="numeric">${nf(r.risk_index,1)}</td></tr>`).join('')||'<tr><td colspan="6">Brak pasujących plików.</td></tr>';
 $('riskCount').textContent=nf(d.length)+' pozycji';$('riskPage').textContent=`${riskPage+1} / ${pages}`;
 $('riskPrev').disabled=riskPage===0;$('riskNext').disabled=riskPage>=pages-1;
}
const important=new Set(['react-hooks/rules-of-hooks','react-hooks/exhaustive-deps','react-hooks/refs','react-hooks/immutability','react-hooks/set-state-in-effect','react-hooks/purity','react-hooks/unsupported-syntax','react-hooks/error-boundaries','no-undef','no-eval','no-implied-eval','no-unsafe-optional-chaining','sonarjs/code-eval','sonarjs/no-hardcoded-passwords','sonarjs/no-hardcoded-secrets']);
function renderIssues(){const term=$('issueSearch').value.toLowerCase(),sev=$('issueSeverity').value,focus=$('issueFocus').value;
 const d=DATA.issues.filter(m=>(!sev||m.severity===sev)&&(!focus||(focus==='priority'?important.has(m.rule):m.rule.startsWith(focus)))&&(`${m.file} ${m.rule} ${m.message}`.toLowerCase().includes(term)));
 const per=25,pages=Math.max(1,Math.ceil(d.length/per));issuePage=Math.min(issuePage,pages-1);
 $('issueRows').innerHTML=d.slice(issuePage*per,(issuePage+1)*per).map(m=>`<tr><td><span class="badge ${m.severity==='error'?'P1':'P3'}">${escapeHTML(m.severity)}</span></td><td><code>${escapeHTML(m.file)}:${m.line||'?'}</code></td><td class="small"><b>${escapeHTML(m.rule)}</b><div class="muted">${escapeHTML(m.message).slice(0,550)}</div></td></tr>`).join('')||'<tr><td colspan="3">Brak pasujących zgłoszeń.</td></tr>';
 $('issueCount').textContent=nf(d.length)+' wyników';$('issuePage').textContent=`${issuePage+1} / ${pages}`;$('issuePrev').disabled=issuePage===0;$('issueNext').disabled=issuePage>=pages-1;
}
initialize();initializeGit();renderRisks();renderIssues();
['riskSearch','riskLevel','riskKind'].forEach(id=>$(id).addEventListener('input',()=>{riskPage=0;renderRisks()}));
['issueSearch','issueSeverity','issueFocus'].forEach(id=>$(id).addEventListener('input',()=>{issuePage=0;renderIssues()}));
$('riskPrev').onclick=()=>{riskPage--;renderRisks()};$('riskNext').onclick=()=>{riskPage++;renderRisks()};
$('issuePrev').onclick=()=>{issuePage--;renderIssues()};$('issueNext').onclick=()=>{issuePage++;renderIssues()};
$('theme').onclick=()=>document.body.classList.toggle('light');
</script></body></html>'''
    from dashboard_extra import inject
    (out/'report.html').write_text(inject(template).replace('__EMBEDDED_DATA__',packed),encoding='utf-8')
