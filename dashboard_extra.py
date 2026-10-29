"""CodeAudit 2.2 — rozszerzenie dashboardu: sekcje HTML, CSS i skrypt wykresów (Apache ECharts, offline).

Moduł nie zmienia logiki analitycznej; wstrzykuje nowe sekcje w znane punkty
(`inject`). Wszystkie sekcje obsługują wielojęzyczność (EN, PL, ZH).
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

CSS = r'''
.chart{width:100%;height:340px;min-width:0}.chart.tall{height:560px}.chart.mid{height:420px}.chart.short{height:260px}
.chartNote{padding:36px 14px;text-align:center;color:var(--muted);font-size:12px;line-height:1.7}
#exec{margin-bottom:16px}#radarSec,#kpi2{margin-top:16px}.execGrid{display:grid;grid-template-columns:1.35fr 1fr;gap:26px}
.execHead{font-size:clamp(17px,2vw,22px);font-weight:700;letter-spacing:-.02em;line-height:1.35;margin:8px 0 14px}
.execList{list-style:none;margin:0;padding:0}.execList li{display:flex;gap:11px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--line);font-size:13px;line-height:1.55}
.execList li:last-child{border-bottom:0}.edot{flex:none;width:9px;height:9px;border-radius:50%;margin-top:6px;background:var(--cyan)}
.edot.ok{background:var(--green)}.edot.warn{background:var(--amber)}.edot.info{background:var(--cyan)}.edot.bad{background:var(--red)}
.actions{counter-reset:a;list-style:none;margin:0;padding:0}.actions li{counter-increment:a;display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--line);font-size:13px;line-height:1.55}
.actions li:last-child{border-bottom:0}.actions li::before{content:counter(a);flex:none;width:22px;height:22px;border-radius:7px;background:linear-gradient(140deg,var(--cyan),var(--violet));color:#071526;font-weight:800;font-size:12px;display:grid;place-items:center;margin-top:1px}
.kpiRow{margin-top:16px}.kpi .metric small{font-size:.45em;font-weight:600;color:var(--muted);letter-spacing:0}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.toolbar label{font-size:12px;color:var(--muted)}
.toolbar select,.toolbar input[type=search]{background:var(--surface2);border:1px solid var(--line);color:var(--text);padding:8px 9px;border-radius:9px}
.legendBar{height:10px;border-radius:6px;background:linear-gradient(90deg,#2f9a7e,#d9a441 55%,#e0586a);margin:8px 0 3px;max-width:340px}
.legendTxt{display:flex;justify-content:space-between;max-width:340px;font-size:11px;color:var(--muted)}
.grey{display:inline-block;width:10px;height:10px;border-radius:2px;background:#51607a;margin-right:5px;vertical-align:middle}
.sevH{color:#ffc4cc;background:#cf39402b}.sevM{color:#ffcd94;background:#d38e3b29}.sevL{color:#a9dcf5;background:#3d8fc02b}
body.light .sevH{color:#a3202c}body.light .sevM{color:#8a540a}body.light .sevL{color:#1f5f8a}
.fl{cursor:pointer;border-bottom:1px dotted var(--cyan)}.fl:hover{color:var(--text)}
#riskRows code{cursor:pointer;border-bottom:1px dotted var(--cyan)}
.modalBack{position:fixed;inset:0;background:#02081280;backdrop-filter:blur(4px);z-index:60;display:none;align-items:flex-start;justify-content:center;padding:4vh 16px;overflow:auto}
.modalBack.open{display:flex}.modal{width:min(980px,100%);background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:24px}
.modal h3{font-size:17px;margin:0 0 4px;word-break:break-all}.modal h4{margin:20px 0 8px;font-size:13px;color:var(--muted);letter-spacing:.04em;text-transform:uppercase}
.fmStats{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px;margin-top:14px}.fmStat{background:var(--surface2);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.fmStat b{display:block;font-size:19px;font-variant-numeric:tabular-nums}.fmStat span{font-size:11px;color:var(--muted)}
.cyc{padding:10px 12px;border:1px solid var(--line);border-radius:10px;margin:8px 0;background:var(--surface2);font-size:12px;line-height:1.7}
.hint{font-size:11px;color:var(--muted);margin-top:8px}
.topActions{display:flex;gap:10px;align-items:center}
.langPicker{display:inline-flex;background:var(--surface2);border:1px solid var(--line);border-radius:10px;padding:2px;gap:2px}
.langBtn{background:transparent;border:0;color:var(--muted);font-size:12px;font-weight:750;padding:5px 10px;border-radius:8px;cursor:pointer;transition:all .18s}
.langBtn:hover{color:var(--text);border-color:transparent;background:rgba(255,255,255,.05)}
.langBtn.active{background:linear-gradient(140deg,var(--cyan),var(--violet));color:#071526;box-shadow:0 2px 8px rgba(99,199,250,.35)}
body.light .langBtn.active{color:#fff;background:linear-gradient(140deg,#1c86ca,#7955c4)}
@media(max-width:1100px){.execGrid{grid-template-columns:1fr}}
@media print{
 @page{size:A4;margin:11mm}
 *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
 body,body.light{--bg:#fff;--surface:#fff;--surface2:#f3f6fa;--line:#d5dce6;--text:#111827;--muted:#475569;--shadow:none;background:#fff!important;color:#111827!important}
 .top,.filters,.pager,#theme,#printBtn,.toolbar,.modalBack,button,.langPicker{display:none!important}
 .shell{max-width:none;padding:0}.hero{padding:6px 0 14px}.hero h1{font-size:34px}.hero h1 em{color:#1b7fb5;background:none;-webkit-text-fill-color:#1b7fb5}
 .card{box-shadow:none;animation:none!important;break-inside:avoid;background:#fff}.section{break-after:avoid;margin-top:26px}
 .fadein{opacity:1!important;transform:none!important}.tblWrap,.gitRecent{max-height:none!important;overflow:visible!important}
 table{white-space:normal!important;font-size:10px}td.path{max-width:none!important}code,.fl{color:#0b5f93!important;word-break:break-all}
 .minibar span,.bar,.gitBar{transition:none!important}.chart{break-inside:avoid}.chartNote{padding:12px}
}
'''

EXEC_HTML = '''<section class="layout" id="exec"><div class="card span12"><div class="execGrid"><div>
<div class="eyebrow" data-i18n="exec_title">EXECUTIVE SUMMARY</div><div class="execHead" id="execHead">—</div><ul class="execList" id="execFacts"></ul></div>
<div><div class="eyebrow" data-i18n="actions_title">RECOMMENDED ACTIONS</div><ol class="actions" id="execActions" style="margin-top:12px"></ol>
<p class="hint" data-i18n="exec_hint">Summary is generated automatically from the metrics below. Findings are triage signals, not absolute verdicts.</p></div></div></div></section>
'''

KPI2_HTML = '''<section class="layout kpiRow" id="kpi2">
<div class="card kpi"><div class="label" data-i18n="kpi_sec">Security · Bandit (excl. tests)</div><div class="metric" id="kSec">—</div><div class="sub" id="kSecSub"></div></div>
<div class="card kpi"><div class="label" data-i18n="kpi_dead">Dead code · Vulture candidates</div><div class="metric" id="kDead">—</div><div class="sub" id="kDeadSub"></div></div>
<div class="card kpi"><div class="label" data-i18n="kpi_dup">Code duplication (heuristic)</div><div class="metric" id="kDup">—</div><div class="sub" id="kDupSub"></div></div>
<div class="card kpi"><div class="label" data-i18n="kpi_deps">Dependencies · Import cycles</div><div class="metric" id="kDeps">—</div><div class="sub" id="kDepsSub"></div></div>
</section>
'''

RADAR_HTML = '''<section class="layout" id="radarSec">
<div class="card span6"><div class="panelHead"><div><h3 data-i18n="radar_title">Code Health Radar</h3><div class="muted small" data-i18n="radar_sub">Axes 0–100, higher = better. Independent of main score to allow historical comparability.</div></div>
<div class="toolbar"><select id="radarMode" aria-label="Radar mode"><option value="all" data-i18n="radar_mode_all">Current — all axes</option><option value="cmp" data-i18n="radar_mode_cmp">Comparison with previous audit</option></select></div></div>
<div class="chart mid" id="radarChart"></div><div class="hint" id="radarNote"></div></div>
<div class="card span6"><div class="panelHead"><div><h3 data-i18n="trend_title">Multi-Audit Trend</h3><div class="muted small" data-i18n="trend_sub">Data aggregated across historical metrics.json files in reports directory</div></div>
<div class="toolbar"><select id="trendMetric" aria-label="Trend metric"><option value="score">Maintainability Score</option><option value="loc">Lines of Code</option><option value="eslint">ESLint Issues</option><option value="sec">Bandit HIGH+MED</option><option value="dead">Dead Code</option><option value="dup">Duplication %</option><option value="cc_ab">CC A/B %</option><option value="js_cc_over15">JS Functions CC&gt;15</option><option value="cycles">Import Cycles</option></select></div></div>
<div class="chart mid" id="trendChart"></div><div class="hint" id="trendNote"></div></div>
</section>
'''

MAP_HTML = '''<div class="section" id="map"><div><h2 data-i18n="map_title">Codebase Map</h2><p data-i18n="map_sub">Visual distribution of complexity, defects, and churn — click any file for details</p></div></div>
<section class="layout">
<div class="card span12"><div class="panelHead"><div><h3 data-i18n="treemap_title">Project Treemap</h3><div class="muted small" data-i18n="treemap_sub">Area = line count, Color = selected metric (green → red). Click directories to zoom.</div></div>
<div class="toolbar"><label for="treeMetric" data-i18n="lbl_color">Color:</label><select id="treeMetric"><option value="r">Triage Index (Risk)</option><option value="cc">Complexity (Max CC)</option><option value="mi">Maintainability (Low MI)</option><option value="es">ESLint Alerts</option><option value="sec">Security (Bandit)</option><option value="dead">Dead Code</option><option value="dup">Duplication %</option><option value="n">Commit Count</option></select></div></div>
<div class="chart tall" id="treeChart"></div><div class="legendBar"></div><div class="legendTxt"><span data-i18n="legend_low">low</span><span id="treeLegendMax">high</span></div><div class="hint"><i class="grey"></i><span data-i18n="legend_no_data">no data for this metric (e.g. MI measured only for Python)</span></div></div>
<div class="card span12"><div class="panelHead"><div><h3 id="hotTitle" data-i18n="hotspot_title">Hotspots: Churn × Complexity</h3><div class="muted small" id="hotSub" data-i18n="hotspot_sub">Top-right quadrant shows files that are both highly complex and frequently modified — prime candidates for refactoring. Bubble size = lines.</div></div></div>
<div class="chart tall" id="hotChart"></div></div>
</section>
'''

JS_HTML = '''<div class="section" id="frontend"><div><h2 data-i18n="frontend_title">Frontend · JS/TS Complexity</h2><p data-i18n="frontend_sub">Lizard evaluates cyclomatic complexity of JavaScript and TypeScript functions</p></div></div>
<section class="layout"><div class="card span5"><h3 data-i18n="js_cc_dist">JS/TS Function CC Distribution</h3><div class="muted small" id="jsInfo"></div><div class="chart" id="jsRanksChart"></div></div>
<div class="card span7"><h3 data-i18n="js_len_cc">Function Length vs Complexity</h3><div class="muted small" data-i18n="js_len_cc_sub">Each dot is a function; functions with CC ≥ 6, long, or with many parameters are visible.</div><div class="chart" id="jsScatter"></div></div>
<div class="card span12"><div class="panelHead"><h3 data-i18n="js_top_funcs">Most Complex JS/TS Functions</h3><div class="filters"><input id="jsSearch" type="search" placeholder="Function or file…" data-i18n-ph="ph_func_or_file"/><select id="jsScope"><option value="prod" data-i18n="opt_prod_only">Production code only</option><option value="all" data-i18n="opt_all_incl_tests">Including tests</option></select></div></div>
<div class="tblWrap" style="max-height:420px"><table><thead><tr><th>CC</th><th>NLOC</th><th data-i18n="th_params">Params</th><th data-i18n="th_func">Function</th><th data-i18n="th_file_line">File:Line</th></tr></thead><tbody id="jsRows"></tbody></table></div><div class="hint" id="jsCount"></div></div></section>
'''

SEC_HTML = '''<div class="section" id="security"><div><h2 data-i18n="security_title">Security Analysis</h2><p data-i18n="security_sub">Bandit (Python code, local) and Pip-Audit (dependency CVEs, requires internet). Verification signals, not proofs.</p></div></div>
<section class="layout"><div class="card span4"><h3 data-i18n="sec_bandit_sev">Bandit Findings by Severity</h3><div class="muted small" id="secInfo"></div><div class="chart" id="secDonut"></div></div>
<div class="card span8"><h3 data-i18n="sec_bandit_rules">Top Bandit Rules</h3><div class="muted small" data-i18n="sec_bandit_rules_sub">Non-test code only</div><div class="chart" id="secRules"></div></div>
<div class="card span12"><div class="panelHead"><h3 data-i18n="sec_bandit_reg">Bandit Findings Registry</h3><div class="filters"><input id="secSearch" type="search" placeholder="File, test, description…" data-i18n-ph="ph_sec_search"/><select id="secSev"><option value="" data-i18n="opt_all_sev">All severities</option><option value="HIGH">HIGH</option><option value="MEDIUM">MEDIUM</option><option value="LOW">LOW</option></select><select id="secScope"><option value="prod" data-i18n="opt_prod_only">Excluding tests</option><option value="all" data-i18n="opt_all_incl_tests">Including tests</option></select></div></div>
<div class="tblWrap" style="max-height:420px"><table><thead><tr><th data-i18n="th_sev">Severity</th><th data-i18n="th_test">Test</th><th data-i18n="th_desc">Description</th><th data-i18n="th_file_line">File:Line</th></tr></thead><tbody id="secRows"></tbody></table></div><div class="hint" id="secCount"></div></div>
<div class="card span12"><h3 data-i18n="sec_audit_title">Dependency Vulnerabilities (Pip-Audit)</h3><div class="muted small" id="auditInfo"></div><div class="tblWrap" style="max-height:380px"><table><thead><tr><th data-i18n="th_pkg">Package</th><th data-i18n="th_ver">Version</th><th data-i18n="th_id">ID</th><th data-i18n="th_fix_ver">Fix Versions</th><th data-i18n="th_desc">Description</th></tr></thead><tbody id="auditRows"></tbody></table></div></div></section>
'''

DEBT_HTML = '''<div class="section" id="debt"><div><h2 data-i18n="debt_title">Dead Code & Duplication</h2><p data-i18n="debt_sub">Unused code candidates (Vulture) and duplicated blocks (heuristic 8-line sliding window)</p></div></div>
<section class="layout"><div class="card span5"><h3 data-i18n="debt_dead_types">Dead Code by Type</h3><div class="muted small" id="deadInfo"></div><div class="chart short" id="deadTypes"></div></div>
<div class="card span7"><h3 data-i18n="debt_dup_files">Files with Highest Duplication</h3><div class="muted small" id="dupInfo"></div><div class="chart short" id="dupFiles"></div></div>
<div class="card span7"><div class="panelHead"><h3 data-i18n="debt_dead_cand">Dead Code Candidates</h3><div class="filters"><input id="deadSearch" type="search" placeholder="Name or file…" data-i18n-ph="ph_name_or_file"/><select id="deadConf"><option value="60" data-i18n="opt_conf_60">Confidence ≥ 60%</option><option value="80" data-i18n="opt_conf_80">Confidence ≥ 80%</option><option value="100" data-i18n="opt_conf_100">Confidence 100%</option></select><select id="deadScope"><option value="prod" data-i18n="opt_prod_only">Excluding tests</option><option value="all" data-i18n="opt_all_incl_tests">Including tests</option></select></div></div>
<div class="tblWrap" style="max-height:380px"><table><thead><tr><th data-i18n="th_conf">Confidence</th><th data-i18n="th_type">Type</th><th data-i18n="th_name">Name</th><th data-i18n="th_file_line">File:Line</th></tr></thead><tbody id="deadRows"></tbody></table></div><div class="hint" id="deadCount"></div></div>
<div class="card span5"><h3 data-i18n="debt_dup_blocks">Largest Duplicated Blocks</h3><div class="tblWrap" style="max-height:380px"><table><thead><tr><th data-i18n="th_lines">Lines</th><th data-i18n="th_frag_a">Fragment A</th><th data-i18n="th_frag_b">Fragment B</th></tr></thead><tbody id="dupRows"></tbody></table></div></div></section>
'''

DEPS_HTML = '''<div class="section" id="deps"><div><h2 data-i18n="deps_title">Module Dependency Graph</h2><p data-i18n="deps_sub">Import relationships across Python and JS/TS. Red nodes belong to import cycles. Drag to pan, scroll to zoom.</p></div></div>
<section class="layout"><div class="card span12"><div class="panelHead"><div><h3 data-i18n="deps_graph_title">Dependency Graph</h3><div class="muted small" id="depInfo"></div></div></div><div class="chart tall" id="depGraph"></div></div>
<div class="card span4"><h3 data-i18n="deps_cycles">Import Cycles</h3><div id="cycleList"></div></div>
<div class="card span4"><h3 data-i18n="deps_fan_in">Most Imported (Fan-in)</h3><div class="tblWrap" style="max-height:300px"><table><thead><tr><th data-i18n="th_module">Module</th><th data-i18n="th_imports">Imports</th></tr></thead><tbody id="fanInRows"></tbody></table></div></div>
<div class="card span4"><h3 data-i18n="deps_fan_out">Most Importing (Fan-out)</h3><div class="tblWrap" style="max-height:300px"><table><thead><tr><th data-i18n="th_module">Module</th><th data-i18n="th_importing">Imports</th></tr></thead><tbody id="fanOutRows"></tbody></table></div></div></section>
'''

GIT_HTML = '''<section class="layout" style="margin-top:16px"><div class="card span12"><h3 data-i18n="git_cal_title">Activity Calendar</h3><div class="muted small" id="calInfo">Commit count per day (last 12 months of Git history).</div><div class="chart short" id="calChart" style="height:230px"></div></div>
<div class="card span12"><h3 data-i18n="git_hour_title">Punchcard (Hour vs Day)</h3><div class="muted small" data-i18n="git_hour_sub">Commits by weekday and hour (author local time).</div><div class="chart short" id="hourChart"></div></div></section>
'''

METHOD_HTML = '''<div class="section"><div><h2 data-i18n="method_ext_title">2.2 Extensions Methodology</h2></div></div><div class="card"><div class="tblWrap"><table><thead><tr><th data-i18n="th_radar_axis">Radar Axis</th><th data-i18n="th_calc_method">Calculation Method</th></tr></thead><tbody id="radarFormulas"></tbody></table></div>
<div class="callout" style="margin-top:14px" data-i18n="callout_method_22">Radar, trend, and treemap serve as navigation and review prioritization tools. Bandit and Vulture lack application framework context (dynamic calls, DI), while duplication and dependency graphs are CodeAudit heuristics — they do not replace code review, tests, or security audits. Pip-audit reflects the state of the vulnerability database at scan time.</div><p class="muted small" id="toolVersions"></p></div>
'''

MODAL_HTML = '''<div class="modalBack" id="fileModal" role="dialog" aria-modal="true" aria-labelledby="fmTitle"><div class="modal"><div class="panelHead"><div><div class="eyebrow" data-i18n="modal_title">FILE DETAILS</div><h3 id="fmTitle"></h3></div><button id="fmClose" data-i18n="modal_close">Close ✕</button></div><div id="fmBody"></div></div></div>
'''


def find_echarts():
    """Szuka echarts.min.js: vendor/ (z paczki) lub node_modules (npm install echarts)."""
    for p in (HERE / "vendor" / "echarts.min.js", HERE / "node_modules" / "echarts" / "dist" / "echarts.min.js"):
        if p.is_file():
            return p
    return None


def _before(tpl: str, marker: str, block: str) -> str:
    if tpl.count(marker) >= 1:
        return tpl.replace(marker, block + marker, 1)
    return tpl.replace("</main>", block + "</main>", 1)


def inject(tpl: str) -> str:
    """Wstrzykuje nowe sekcje, style, ECharts i skrypt do szablonu 2.1/2.2."""
    tpl = tpl.replace("</style></head>", CSS + "</style></head>", 1)
    tpl = tpl.replace("CodeAudit 2.1 · Engineering Intelligence", "CodeAudit 2.2 · Engineering Intelligence")
    tpl = tpl.replace("/ 2.1<", "/ 2.2<").replace("CodeAudit 2.1 · Radon", "CodeAudit 2.2 · Radon")
    if '<button id="printBtn"' not in tpl:
        tpl = tpl.replace('<button id="theme"', '<button id="printBtn" title="Print / PDF" data-i18n="btn_print">⎙ PDF</button><button id="theme"')
    tpl = tpl.replace('<a href="#quality" data-i18n="nav_quality">Quality</a>', '<a href="#quality" data-i18n="nav_quality">Quality</a><a href="#map" data-i18n="nav_map">Code Map</a>', 1)
    tpl = tpl.replace('<a href="#git" data-i18n="nav_git">Git</a>', '<a href="#frontend" data-i18n="nav_frontend">Frontend</a><a href="#security" data-i18n="nav_security">Security</a><a href="#debt" data-i18n="nav_debt">Debt</a><a href="#deps" data-i18n="nav_deps">Dependencies</a><a href="#git" data-i18n="nav_git">Git</a>', 1)
    tpl = _before(tpl, '<section class="layout" id="overview">', EXEC_HTML)
    tpl = _before(tpl, '<div class="section" id="compare">', KPI2_HTML + RADAR_HTML)
    tpl = _before(tpl, '<div class="section" id="sensitive">', MAP_HTML)
    tpl = _before(tpl, '<div class="section" id="structure">', JS_HTML + SEC_HTML + DEBT_HTML + DEPS_HTML)
    tpl = _before(tpl, '<div class="section" id="scope">', GIT_HTML)
    tpl = tpl.replace("</main>", METHOD_HTML + "</main>", 1)
    tpl = _before(tpl, "<footer", MODAL_HTML)
    lib = find_echarts()
    lib_js = lib.read_text(encoding="utf-8").replace("</script", "<\\/script") if lib else ""
    marker = '<script id="snapshot"'
    tpl = tpl.replace(marker, (f"<script>/* Apache ECharts (Apache-2.0), osadzone offline */\n{lib_js}\n</script>\n" if lib_js else "") + marker, 1)
    js = (HERE / "dashboard_charts.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
    tail = "</script></body></html>"
    assert tpl.count(tail) == 1, "nie znaleziono końca skryptu w szablonie 2.1"
    return tpl.replace(tail, js + "\n" + tail)
