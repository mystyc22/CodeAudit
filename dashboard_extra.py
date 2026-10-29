"""CodeAudit 2.2 — rozszerzenie dashboardu: sekcje HTML, CSS i skrypt wykresów (Apache ECharts, offline).

Moduł nie zmienia dotychczasowego szablonu 2.1; wstrzykuje nowe sekcje w znane punkty
(`inject`). Jeśli którykolwiek punkt nie zostanie znaleziony, sekcja trafia na koniec <main>.
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
@media(max-width:1100px){.execGrid{grid-template-columns:1fr}}
@media print{
 @page{size:A4;margin:11mm}
 *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
 body,body.light{--bg:#fff;--surface:#fff;--surface2:#f3f6fa;--line:#d5dce6;--text:#111827;--muted:#475569;--shadow:none;background:#fff!important;color:#111827!important}
 .top,.filters,.pager,#theme,#printBtn,.toolbar,.modalBack,button{display:none!important}
 .shell{max-width:none;padding:0}.hero{padding:6px 0 14px}.hero h1{font-size:34px}.hero h1 em{color:#1b7fb5;background:none;-webkit-text-fill-color:#1b7fb5}
 .card{box-shadow:none;animation:none!important;break-inside:avoid;background:#fff}.section{break-after:avoid;margin-top:26px}
 .fadein{opacity:1!important;transform:none!important}.tblWrap,.gitRecent{max-height:none!important;overflow:visible!important}
 table{white-space:normal!important;font-size:10px}td.path{max-width:none!important}code,.fl{color:#0b5f93!important;word-break:break-all}
 .minibar span,.bar,.gitBar{transition:none!important}.chart{break-inside:avoid}.chartNote{padding:12px}
}
'''

EXEC_HTML = '''<section class="layout" id="exec"><div class="card span12"><div class="execGrid"><div>
<div class="eyebrow">STRESZCZENIE ZARZĄDCZE</div><div class="execHead" id="execHead">—</div><ul class="execList" id="execFacts"></ul></div>
<div><div class="eyebrow">OD CZEGO ZACZĄĆ</div><ol class="actions" id="execActions" style="margin-top:12px"></ol>
<p class="hint">Streszczenie jest generowane automatycznie z liczb poniżej. Wyniki to sygnały do przeglądu, nie wyroki — szczególnie bandit i vulture dają fałszywe alarmy.</p></div></div></div></section>
'''

KPI2_HTML = '''<section class="layout kpiRow" id="kpi2">
<div class="card kpi"><div class="label">Bezpieczeństwo · bandit (bez testów)</div><div class="metric" id="kSec">—</div><div class="sub" id="kSecSub"></div></div>
<div class="card kpi"><div class="label">Martwy kod · kandydaci vulture</div><div class="metric" id="kDead">—</div><div class="sub" id="kDeadSub"></div></div>
<div class="card kpi"><div class="label">Duplikacja kodu (heurystyka)</div><div class="metric" id="kDup">—</div><div class="sub" id="kDupSub"></div></div>
<div class="card kpi"><div class="label">Zależności · cykle importów</div><div class="metric" id="kDeps">—</div><div class="sub" id="kDepsSub"></div></div>
</section>
'''

RADAR_HTML = '''<section class="layout" id="radarSec">
<div class="card span6"><div class="panelHead"><div><h3>Radar zdrowia kodu</h3><div class="muted small">Osie 0–100, wyżej = lepiej. Indeks główny powyżej pozostaje bez zmian, by dało się porównywać audyty.</div></div>
<div class="toolbar"><select id="radarMode" aria-label="Tryb radaru"><option value="all">Bieżący — wszystkie osie</option><option value="cmp">Porównanie z poprzednim audytem</option></select></div></div>
<div class="chart mid" id="radarChart"></div><div class="hint" id="radarNote"></div></div>
<div class="card span6"><div class="panelHead"><div><h3>Trend między audytami</h3><div class="muted small">Dane z folderu reports (history_*.json oraz wcześniejsze metrics.json tego projektu)</div></div>
<div class="toolbar"><select id="trendMetric" aria-label="Metryka trendu"><option value="score">Indeks utrzymywalności</option><option value="loc">Linie kodu</option><option value="eslint">Zgłoszenia ESLint</option><option value="sec">Bandit HIGH+MEDIUM</option><option value="dead">Martwy kod</option><option value="dup">Duplikacja %</option><option value="cc_ab">CC A/B %</option><option value="js_cc_over15">Funkcje JS CC&gt;15</option><option value="cycles">Cykle importów</option></select></div></div>
<div class="chart mid" id="trendChart"></div><div class="hint" id="trendNote"></div></div>
</section>
'''

MAP_HTML = '''<div class="section" id="map"><div><h2>Mapa kodu</h2><p>Gdzie dokładnie w projekcie koncentrują się złożoność, błędy i zmiany — kliknij plik, aby zobaczyć szczegóły</p></div></div>
<section class="layout">
<div class="card span12"><div class="panelHead"><div><h3>Treemap projektu</h3><div class="muted small">Powierzchnia = liczba linii, kolor = wybrana miara (zielony → czerwony). Kliknij katalog, aby przybliżyć.</div></div>
<div class="toolbar"><label for="treeMetric">Kolor:</label><select id="treeMetric"><option value="r">Indeks triage (ryzyko)</option><option value="cc">Złożoność (CC maks.)</option><option value="mi">Maintainability (niski MI)</option><option value="es">Zgłoszenia ESLint</option><option value="sec">Bezpieczeństwo (bandit)</option><option value="dead">Martwy kod</option><option value="dup">Duplikacja %</option><option value="n">Liczba commitów</option></select></div></div>
<div class="chart tall" id="treeChart"></div><div class="legendBar"></div><div class="legendTxt"><span>niski</span><span id="treeLegendMax">wysoki</span></div><div class="hint"><i class="grey"></i>brak danych dla tej miary (np. MI liczone tylko dla Pythona)</div></div>
<div class="card span12"><div class="panelHead"><div><h3 id="hotTitle">Hotspoty: zmiany × złożoność</h3><div class="muted small" id="hotSub">Prawy górny róg to pliki jednocześnie złożone i często zmieniane — dobre kandydaty do przeglądu. Wielkość bąbla = liczba linii.</div></div></div>
<div class="chart tall" id="hotChart"></div></div>
</section>
'''

JS_HTML = '''<div class="section" id="frontend"><div><h2>Frontend · złożoność JS/TS</h2><p>Lizard liczy złożoność cyklomatyczną funkcji JavaScript i TypeScript — uzupełnia Radon, który mierzy tylko Pythona</p></div></div>
<section class="layout"><div class="card span5"><h3>Rozkład CC funkcji JS/TS</h3><div class="muted small" id="jsInfo"></div><div class="chart" id="jsRanksChart"></div></div>
<div class="card span7"><h3>Długość a złożoność funkcji</h3><div class="muted small">Każdy punkt to funkcja; widoczne są funkcje o CC ≥ 6, długie lub z wieloma parametrami.</div><div class="chart" id="jsScatter"></div></div>
<div class="card span12"><div class="panelHead"><h3>Najbardziej złożone funkcje JS/TS</h3><div class="filters"><input id="jsSearch" type="search" placeholder="Funkcja lub plik…"/><select id="jsScope"><option value="prod">Tylko kod produkcyjny</option><option value="all">Wraz z testami</option></select></div></div>
<div class="tblWrap" style="max-height:420px"><table><thead><tr><th>CC</th><th>NLOC</th><th>Param.</th><th>Funkcja</th><th>Plik:linia</th></tr></thead><tbody id="jsRows"></tbody></table></div><div class="hint" id="jsCount"></div></div></section>
'''

SEC_HTML = '''<div class="section" id="security"><div><h2>Bezpieczeństwo</h2><p>Bandit (kod Python, lokalnie) i pip-audit (podatności zależności, wymaga internetu). Sygnały do weryfikacji, nie dowód podatności.</p></div></div>
<section class="layout"><div class="card span4"><h3>Znaleziska bandit wg wagi</h3><div class="muted small" id="secInfo"></div><div class="chart" id="secDonut"></div></div>
<div class="card span8"><h3>Najczęstsze reguły bandit</h3><div class="muted small">Tylko kod nie-testowy</div><div class="chart" id="secRules"></div></div>
<div class="card span12"><div class="panelHead"><h3>Rejestr znalezisk bandit</h3><div class="filters"><input id="secSearch" type="search" placeholder="Plik, test, opis…"/><select id="secSev"><option value="">Wszystkie wagi</option><option value="HIGH">HIGH</option><option value="MEDIUM">MEDIUM</option><option value="LOW">LOW</option></select><select id="secScope"><option value="prod">Bez testów</option><option value="all">Wraz z testami</option></select></div></div>
<div class="tblWrap" style="max-height:420px"><table><thead><tr><th>Waga</th><th>Test</th><th>Opis</th><th>Plik:linia</th></tr></thead><tbody id="secRows"></tbody></table></div><div class="hint" id="secCount"></div></div>
<div class="card span12"><h3>Podatności zależności (pip-audit)</h3><div class="muted small" id="auditInfo"></div><div class="tblWrap" style="max-height:380px"><table><thead><tr><th>Pakiet</th><th>Wersja</th><th>Identyfikator</th><th>Wersje naprawcze</th><th>Opis</th></tr></thead><tbody id="auditRows"></tbody></table></div></div></section>
'''

DEBT_HTML = '''<div class="section" id="debt"><div><h2>Martwy kod i duplikacja</h2><p>Kandydaci na kod nieużywany (vulture) oraz powielone fragmenty (własna heurystyka okna 8 znaczących linii)</p></div></div>
<section class="layout"><div class="card span5"><h3>Martwy kod wg typu</h3><div class="muted small" id="deadInfo"></div><div class="chart short" id="deadTypes"></div></div>
<div class="card span7"><h3>Pliki z największą duplikacją</h3><div class="muted small" id="dupInfo"></div><div class="chart short" id="dupFiles"></div></div>
<div class="card span7"><div class="panelHead"><h3>Kandydaci na martwy kod</h3><div class="filters"><input id="deadSearch" type="search" placeholder="Nazwa lub plik…"/><select id="deadConf"><option value="60">Pewność ≥ 60%</option><option value="80">Pewność ≥ 80%</option><option value="100">Pewność 100%</option></select><select id="deadScope"><option value="prod">Bez testów</option><option value="all">Wraz z testami</option></select></div></div>
<div class="tblWrap" style="max-height:380px"><table><thead><tr><th>Pewność</th><th>Typ</th><th>Nazwa</th><th>Plik:linia</th></tr></thead><tbody id="deadRows"></tbody></table></div><div class="hint" id="deadCount"></div></div>
<div class="card span5"><h3>Największe zduplikowane bloki</h3><div class="tblWrap" style="max-height:380px"><table><thead><tr><th>Linie</th><th>Fragment A</th><th>Fragment B</th></tr></thead><tbody id="dupRows"></tbody></table></div></div></section>
'''

DEPS_HTML = '''<div class="section" id="deps"><div><h2>Zależności między modułami</h2><p>Graf importów Python i JS/TS (własny parser). Czerwone węzły leżą w cyklach importów. Przeciągaj węzły, przewijaj, aby przybliżyć.</p></div></div>
<section class="layout"><div class="card span12"><div class="panelHead"><div><h3>Graf zależności</h3><div class="muted small" id="depInfo"></div></div></div><div class="chart tall" id="depGraph"></div></div>
<div class="card span4"><h3>Cykle importów</h3><div id="cycleList"></div></div>
<div class="card span4"><h3>Najczęściej importowane (fan-in)</h3><div class="tblWrap" style="max-height:300px"><table><thead><tr><th>Moduł</th><th>Importów</th></tr></thead><tbody id="fanInRows"></tbody></table></div></div>
<div class="card span4"><h3>Najwięcej importujące (fan-out)</h3><div class="tblWrap" style="max-height:300px"><table><thead><tr><th>Moduł</th><th>Importuje</th></tr></thead><tbody id="fanOutRows"></tbody></table></div></div></section>
'''

GIT_HTML = '''<section class="layout" style="margin-top:16px"><div class="card span12"><h3>Kalendarz aktywności</h3><div class="muted small" id="calInfo">Liczba commitów dziennie (ostatnie 12 miesięcy historii).</div><div class="chart short" id="calChart" style="height:230px"></div></div>
<div class="card span12"><h3>Kiedy powstaje kod</h3><div class="muted small">Commity wg dnia tygodnia i godziny (czas lokalny autora commita).</div><div class="chart short" id="hourChart"></div></div></section>
'''

METHOD_HTML = '''<div class="section"><div><h2>Metodologia rozszerzeń 2.2</h2></div></div><div class="card"><div class="tblWrap"><table><thead><tr><th>Oś radaru</th><th>Sposób obliczenia</th></tr></thead><tbody id="radarFormulas"></tbody></table></div>
<div class="callout" style="margin-top:14px">Radar, trend i treemap służą do orientacji i ustalania kolejności przeglądu. Bandit i vulture nie znają kontekstu aplikacji (frameworki, wywołania dynamiczne), a duplikacja i graf zależności to heurystyki własne CodeAudit — nie zastępują przeglądu kodu, testów ani audytu bezpieczeństwa. pip-audit korzysta z internetowej bazy podatności i odzwierciedla jej stan z chwili audytu.</div><p class="muted small" id="toolVersions"></p></div>
'''

MODAL_HTML = '''<div class="modalBack" id="fileModal" role="dialog" aria-modal="true" aria-labelledby="fmTitle"><div class="modal"><div class="panelHead"><div><div class="eyebrow">SZCZEGÓŁY PLIKU</div><h3 id="fmTitle"></h3></div><button id="fmClose">Zamknij ✕</button></div><div id="fmBody"></div></div></div>
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
    """Wstrzykuje nowe sekcje, style, ECharts i skrypt do szablonu 2.1."""
    tpl = tpl.replace("</style></head>", CSS + "</style></head>", 1)
    tpl = tpl.replace("CodeAudit 2.1 · Engineering Intelligence", "CodeAudit 2.2 · Engineering Intelligence")
    tpl = tpl.replace("/ 2.1<", "/ 2.2<").replace("CodeAudit 2.1 · Radon", "CodeAudit 2.2 · Radon")
    tpl = tpl.replace('<button id="theme">', '<button id="printBtn" title="Drukuj / zapisz jako PDF">⎙ PDF</button><button id="theme">', 1)
    tpl = tpl.replace('<a href="#quality">Jakość</a>', '<a href="#quality">Jakość</a><a href="#map">Mapa kodu</a>', 1)
    tpl = tpl.replace('<a href="#git">Git</a>', '<a href="#frontend">Frontend</a><a href="#security">Bezpieczeństwo</a><a href="#debt">Dług</a><a href="#deps">Zależności</a><a href="#git">Git</a>', 1)
    tpl = _before(tpl, '<section class="layout" id="overview">', EXEC_HTML)
    tpl = _before(tpl, '<div class="section" id="compare">', KPI2_HTML + RADAR_HTML)
    tpl = _before(tpl, '<div class="section" id="sensitive">', MAP_HTML)
    tpl = _before(tpl, '<div class="section" id="structure">', JS_HTML + SEC_HTML + DEBT_HTML + DEPS_HTML)
    tpl = _before(tpl, '<div class="section" id="scope">', GIT_HTML)
    tpl = tpl.replace("</main>", METHOD_HTML + "</main>", 1)
    tpl = tpl.replace("</body></html>", MODAL_HTML + "</body></html>", 1) if False else tpl
    tpl = _before(tpl, "<footer", MODAL_HTML)
    lib = find_echarts()
    lib_js = lib.read_text(encoding="utf-8").replace("</script", "<\\/script") if lib else ""
    marker = '<script id="snapshot"'
    tpl = tpl.replace(marker, (f"<script>/* Apache ECharts (Apache-2.0), osadzone offline */\n{lib_js}\n</script>\n" if lib_js else "") + marker, 1)
    js = (HERE / "dashboard_charts.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
    tail = "</script></body></html>"
    assert tpl.count(tail) == 1, "nie znaleziono końca skryptu w szablonie 2.1"
    return tpl.replace(tail, js + "\n" + tail)
