/* CodeAudit 2.2 — wykresy i widoki rozszerzone. Wstrzykiwane do report.html.
   Korzysta z globali szablonu 2.1: DATA, $, nf, escapeHTML, addRow, grades. Bez sieci. */
(function () {
  'use strict';
  const ECH = (typeof echarts !== 'undefined') ? echarts : null;
  const EX = DATA.ex || {};
  const XS = DATA.xs || {};
  const charts = {};
  let printing = false;
  const kp = s => String(s || '').replace(/\\/g, '/').toLowerCase();
  const css = v => getComputedStyle(document.body).getPropertyValue(v).trim();
  const C = { cyan: '#4fb8ea', violet: '#9b87f5', green: '#3fc79a', amber: '#e8a93c', red: '#ef6a7b', grey: '#6b7a94' };
  const PRODJS = new Set(['js_prod', 'js_other', 'ts_prod']);
  const PRODPY = new Set(['py_prod', 'py_other']);
  const WD = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So', 'Nd'];
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

  function pal() {
    if (printing) return { text: '#111827', muted: '#475569', line: '#d5dce6', surface: '#ffffff', surface2: '#f1f5f9', bg: '#ffffff' };
    return { text: css('--text') || '#eaf0fb', muted: css('--muted') || '#94a7c5', line: css('--line') || '#283650',
             surface: css('--surface') || '#121c31', surface2: css('--surface2') || '#18243c', bg: css('--bg') || '#0a1020' };
  }
  const tip = extra => Object.assign({ backgroundColor: pal().surface2, borderColor: pal().line,
    textStyle: { color: pal().text, fontSize: 12 }, extraCssText: 'max-width:440px;white-space:normal;word-break:break-all;' }, extra || {});
  const rankOf = cc => cc <= 5 ? 'A' : cc <= 10 ? 'B' : cc <= 20 ? 'C' : cc <= 30 ? 'D' : cc <= 40 ? 'E' : 'F';
  const base = p => String(p).split('/').pop();
  const loc = (f, l) => `${f}:${l}`;
  const fileCell = p => `<code class="fl" data-file="${escapeHTML(p)}" title="${escapeHTML(p)}">${escapeHTML(p)}</code>`;
  function statusText(o) {
    if (!o || !o.status) return 'Brak danych.';
    if (o.status === 'disabled') return 'Analiza wyłączona w tym przebiegu.';
    if (o.status === 'unavailable') return 'Narzędzie niedostępne' + (o.note ? ': ' + escapeHTML(o.note) : '') + '.';
    return escapeHTML(o.status) + (o.note ? ': ' + escapeHTML(o.note) : '');
  }
  const safe = f => { try { f(); } catch (e) { console.error('CodeAudit 2.2 /', f.name, e); } };

  /* ───── podstawy ECharts ───── */
  function mk(id) {
    const el = $(id); if (!el) return null;
    if (!ECH) {
      if (!el.dataset.msg) { el.dataset.msg = '1'; el.innerHTML = '<div class="chartNote">Brak biblioteki ECharts w raporcie. Umieść <code>echarts.min.js</code> w <code>C:\\Tools\\CodeAudit\\vendor\\</code> (lub wykonaj <code>npm install echarts@5</code> w C:\\Tools\\CodeAudit) i uruchom audyt ponownie.</div>'; }
      return null;
    }
    let c = charts[id];
    if (!c) { el.innerHTML = ''; c = ECH.init(el, null, { renderer: 'canvas' }); charts[id] = c; }
    return c;
  }
  function put(id, opt, onClick) {
    const c = mk(id); if (!c) return null;
    opt.animation = !printing && !reduceMotion;
    opt.backgroundColor = 'transparent';
    opt.textStyle = { color: pal().muted, fontFamily: 'system-ui,"Segoe UI",sans-serif' };
    c.setOption(opt, true);
    c.off('click'); if (onClick) c.on('click', onClick);
    if (printing) c.getZr().flush();
    return c;
  }
  function note(id, html) {
    const el = $(id); if (!el) return;
    if (charts[id]) { charts[id].dispose(); delete charts[id]; }
    el.innerHTML = '<div class="chartNote">' + html + '</div>';
  }

  /* ───── streszczenie i KPI ───── */
  function xExec() {
    const e = DATA.exec;
    if (!e) { $('exec').style.display = 'none'; return; }
    $('execHead').textContent = e.headline;
    $('execFacts').innerHTML = e.facts.map(f => `<li><span class="edot ${escapeHTML(f.level)}"></span><span>${escapeHTML(f.text)}</span></li>`).join('');
    $('execActions').innerHTML = e.actions.map(a => `<li><span>${escapeHTML(a)}</span></li>`).join('');
  }
  function xKpi() {
    const s = XS.security || {}, d = XS.dead || {}, u = XS.duplication || {}, p = XS.deps || {}, a = XS.pip_audit || {};
    const okS = ['ok', 'partial'].includes(s.status);
    $('kSec').innerHTML = okS ? `${nf(s.high)}<small> HIGH</small> · ${nf(s.medium)}<small> MED</small>` : '—';
    $('kSecSub').textContent = okS ? `LOW: ${nf(s.low)} · zależności: ${a.status === 'ok' ? nf(a.vulnerabilities) + ' znanych podatności (sprawdzono pakietów: ' + nf(a.packages) + (a.skipped ? ', pominięto: ' + nf(a.skipped) : '') + ')' : 'nie sprawdzano (pip-audit)'}`
      : (s.status === 'unavailable' ? 'bandit niedostępny' : 'analiza wyłączona');
    $('kDead').textContent = d.status === 'ok' ? nf(d.count) : '—';
    $('kDeadSub').textContent = d.status === 'ok' ? `w tym pewność ≥ 80%: ${nf(d.high_confidence)} · wymaga weryfikacji` : (d.status === 'unavailable' ? 'vulture niedostępny' : 'analiza wyłączona');
    $('kDup').innerHTML = u.status === 'ok' && u.percent != null ? `${nf(u.percent, 1)}<small> %</small>` : '—';
    $('kDupSub').textContent = u.status === 'ok' ? `${nf(u.blocks)} największych bloków na liście` : 'analiza wyłączona';
    $('kDeps').textContent = p.status === 'ok' ? nf(p.cycles) : '—';
    $('kDepsSub').textContent = p.status === 'ok' ? `${nf(p.modules)} modułów · ${nf(p.edges)} powiązań` : 'analiza wyłączona';
  }

  /* ───── radar i trend ───── */
  function xRadar() {
    const axes = (DATA.radar || []).filter(a => a.value != null);
    const mode = $('radarMode').value;
    const prev = (DATA.previous && DATA.previous.radar) || null;
    const use = mode === 'cmp' ? axes.filter(a => prev && prev[a.key] != null) : axes;
    if (use.length < 3) {
      note('radarChart', mode === 'cmp' ? `Za mało wspólnych osi z poprzednim audytem (${use.length}). Porównanie wymaga co najmniej 3 — poprzedni audyt mógł pochodzić ze starszej wersji CodeAudit.` : 'Za mało danych do narysowania radaru.');
      $('radarNote').textContent = ''; return;
    }
    const P = pal();
    const data = [{ name: 'Bieżący', value: use.map(a => a.value), areaStyle: { opacity: .28 }, lineStyle: { width: 2 }, itemStyle: { color: C.cyan } }];
    if (mode === 'cmp') data.push({ name: 'Poprzedni', value: use.map(a => prev[a.key]), areaStyle: { opacity: .08 }, lineStyle: { width: 2, type: 'dashed' }, itemStyle: { color: C.violet } });
    put('radarChart', {
      tooltip: tip({ trigger: 'item', formatter: p => `<b>${escapeHTML(p.name)}</b><br/>` + use.map((a, i) => `${escapeHTML(a.name)}: <b>${nf(p.value[i], 1)}</b>`).join('<br/>') }),
      legend: mode === 'cmp' ? { bottom: 0, textStyle: { color: P.muted } } : undefined,
      radar: { indicator: use.map(a => ({ name: a.name, max: 100 })), radius: '62%', splitNumber: 4, axisName: { color: P.text, fontSize: 11 },
               splitLine: { lineStyle: { color: P.line } }, splitArea: { show: false }, axisLine: { lineStyle: { color: P.line } } },
      series: [{ type: 'radar', data, symbolSize: 5 }]
    });
    const miss = (DATA.radar || []).filter(a => a.value == null).map(a => a.name);
    $('radarNote').textContent = (miss.length ? 'Osie bez danych w tym pomiarze: ' + miss.join(', ') + '. ' : '') + (mode === 'cmp' ? 'Pokazano tylko osie zmierzone w obu audytach.' : '');
  }
  function xTrend() {
    const tr = DATA.trend || [], m = $('trendMetric').value;
    const val = e => m === 'sec' ? (e.sec_high == null ? null : e.sec_high + (e.sec_med || 0)) : e[m];
    const pts = tr.map(e => ({ id: e.id, t: (e.t || '').slice(0, 16).replace('T', ' '), v: val(e) }));
    if (!pts.length || pts.every(p => p.v == null)) {
      note('trendChart', 'Brak danych tej metryki w zapisanych audytach (starsze wersje CodeAudit jej nie mierzyły).'); $('trendNote').textContent = ''; return;
    }
    const P = pal();
    put('trendChart', {
      grid: { left: 52, right: 22, top: 26, bottom: 44 },
      tooltip: tip({ trigger: 'axis', formatter: ps => { const p = ps[0], q = pts[p.dataIndex]; return `<b>${escapeHTML(q.t)}</b><br/>${escapeHTML(q.id)}<br/>${p.marker} ${q.v == null ? '—' : nf(q.v, 2)}`; } }),
      xAxis: { type: 'category', data: pts.map(p => new Set(pts.map(q => q.t.slice(0, 10))).size < pts.length ? p.t.slice(5) : p.t.slice(0, 10)), axisLabel: { color: P.muted }, axisLine: { lineStyle: { color: P.line } } },
      yAxis: { type: 'value', min: m === 'score' ? 0 : undefined, max: m === 'score' || m === 'cc_ab' ? 100 : undefined, axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .6 } } },
      series: [{ type: 'line', data: pts.map(p => p.v), smooth: .25, symbolSize: 9, connectNulls: true, lineStyle: { width: 3, color: C.cyan }, itemStyle: { color: C.cyan },
                 areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(79,184,234,.35)' }, { offset: 1, color: 'rgba(79,184,234,0)' }] } } }]
    });
    $('trendNote').textContent = tr.length < 2 ? 'To pierwszy zapisany pomiar — trend pojawi się po kolejnych audytach.' : `Zapisanych audytów: ${tr.length}. Puste punkty = metryka niemierzona w starszej wersji.`;
  }

  /* ───── treemap ───── */
  const STOPS = ['#2f9a7e', '#d9a441', '#e0586a'].map(h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)));
  function heat(t) {
    t = Math.max(0, Math.min(1, t)); const k = t < .55 ? 0 : 1, u = k === 0 ? t / .55 : (t - .55) / .45;
    const a = STOPS[k], b = STOPS[k + 1];
    return 'rgb(' + a.map((x, i) => Math.round(x + (b[i] - x) * u)).join(',') + ')';
  }
  const METRICS = {
    r: { label: 'Indeks triage', v: r => r.r || 0, fmt: v => nf(v, 1) },
    cc: { label: 'CC maks.', v: r => r.cc, fmt: v => nf(v) },
    mi: { label: 'MI (niższy = gorszy)', v: r => r.mi, t: v => (70 - v) / 50, fmt: v => nf(v, 1), hi: 'MI ≤ 20' },
    es: { label: 'Zgłoszenia ESLint', v: r => r.es || 0, fmt: v => nf(v) },
    sec: { label: 'Bandit (suma wag)', v: r => (r.c && PRODPY.has(r.c)) || r.sec ? r.sec || 0 : null, fmt: v => nf(v, 1) },
    dead: { label: 'Martwy kod', v: r => PRODPY.has(r.c) ? r.dead || 0 : null, fmt: v => nf(v) },
    dup: { label: 'Duplikacja %', v: r => r.dup || 0, t: v => v / 40, fmt: v => nf(v, 1) + '%', hi: '≥ 40%' },
    n: { label: 'Commity', v: r => r.n || 0, fmt: v => nf(v) }
  };
  function scaler(key) {
    const M = METRICS[key]; if (M.t) return { f: M.t, hi: M.hi };
    const vals = (DATA.matrix || []).map(M.v).filter(v => v != null && v > 0).sort((a, b) => a - b);
    const hi = vals.length ? vals[Math.min(vals.length - 1, Math.floor(vals.length * .95))] : 1;
    return { f: v => v / (hi || 1), hi: '≥ ' + M.fmt(hi) };
  }
  function buildTree(key) {
    const M = METRICS[key], S = scaler(key);
    const root = { name: 'projekt', kids: new Map() };
    for (const r of DATA.matrix || []) {
      const parts = r.p.split('/'); let node = root;
      for (let i = 0; i < parts.length - 1; i++) {
        if (!node.kids.has(parts[i])) node.kids.set(parts[i], { name: parts[i], kids: new Map() });
        node = node.kids.get(parts[i]);
      }
      node.kids.set(parts[parts.length - 1], { name: parts[parts.length - 1], leaf: r });
    }
    const P = pal();
    function conv(n) {
      if (n.leaf) {
        const r = n.leaf, v = M.v(r);
        return { name: n.name, value: r.l, path: r.p, row: r, itemStyle: { color: v == null ? '#51607a' : heat(S.f(v)) } };
      }
      let kids = [...n.kids.values()].map(conv), name = n.name;
      while (kids.length === 1 && !kids[0].path) { name += '/' + kids[0].name; kids = kids[0].children; }
      return { name, children: kids, itemStyle: { color: P.surface2 } };
    }
    return { tree: [...root.kids.values()].map(conv), hi: S.hi };
  }
  function xTree() {
    if (!(DATA.matrix || []).length) { note('treeChart', 'Brak plików kodu do pokazania.'); return; }
    const key = $('treeMetric').value, M = METRICS[key], P = pal();
    const { tree, hi } = buildTree(key);
    $('treeLegendMax').textContent = 'wysoki (' + hi + ')';
    put('treeChart', {
      tooltip: tip({ formatter: p => {
        const r = p.data && p.data.row;
        if (!r) return `<b>${escapeHTML(p.name)}</b><br/>Linie: ${nf(p.value)}`;
        const v = M.v(r);
        return `<b>${escapeHTML(r.p)}</b><br/>Linie: ${nf(r.l)} · ${escapeHTML(M.label)}: <b>${v == null ? '—' : M.fmt(v)}</b><br/>CC maks.: ${nf(r.cc)} · MI: ${nf(r.mi, 1)} · ESLint: ${nf(r.es)}<br/>Bandit: ${nf(r.sec, 1)} · Martwy kod: ${nf(r.dead)} · Dup.: ${nf(r.dup, 1)}%<br/>Commity: ${nf(r.n)} · Triage: ${nf(r.r, 1)} ${r.pr ? '(' + r.pr + ')' : ''}`;
      } }),
      series: [{
        type: 'treemap', data: tree, left: 0, right: 0, top: 4, bottom: 30, roam: false, nodeClick: 'zoomToNode', squareRatio: .9,
        breadcrumb: { show: true, bottom: 2, height: 22, itemStyle: { color: P.surface2, borderColor: P.line, textStyle: { color: P.text } }, emphasis: { itemStyle: { color: P.line } } },
        label: { show: true, formatter: '{b}', fontSize: 11, color: '#fff', overflow: 'truncate' },
        upperLabel: { show: true, height: 22, color: P.text, fontSize: 11, fontWeight: 600 },
        itemStyle: { borderColor: P.bg, borderWidth: 1, gapWidth: 1 },
        levels: [{ itemStyle: { borderWidth: 0, gapWidth: 4 } }, { itemStyle: { gapWidth: 3, borderWidth: 2, borderColor: P.line } }, { itemStyle: { gapWidth: 1, borderWidth: 1, borderColor: P.bg } }]
      }]
    }, p => { if (p.data && p.data.path) xOpenFile(p.data.path); });
  }

  /* ───── hotspoty ───── */
  function xHot() {
    const rows = (DATA.matrix || []).filter(r => r.cc != null);
    if (!rows.length) { note('hotChart', 'Brak plików ze zmierzoną złożonością.'); return; }
    const git = (DATA.matrix || []).some(r => r.n > 0), xk = git ? 'n' : 'l', P = pal();
    $('hotTitle').textContent = git ? 'Hotspoty: zmiany × złożoność' : 'Złożoność × rozmiar (brak historii Git)';
    $('hotSub').textContent = 'Prawy górny róg = pliki jednocześnie złożone i duże/często zmieniane — dobre kandydaty do przeglądu. Rozmiar bąbla = linie. Kolor = priorytet triage (P1 czerwony, P2 bursztynowy, P3 niebieski, szary = poniżej progu).';
    const col = r => r.pr === 'P1' ? C.red : r.pr === 'P2' ? C.amber : r.pr === 'P3' ? C.cyan : C.grey;
    const data = rows.map(r => ({ value: [r[xk], r.cc, r.l, r.p, r.r, r.es, r.pr || '—'], itemStyle: { color: col(r), opacity: .8, borderColor: P.bg, borderWidth: 1 } }));
    const maxX = Math.max(1, ...rows.map(r => r[xk])) * 1.1, maxY = Math.max(25, Math.max(...rows.map(r => r.cc)) * 1.12);
    const xThr = git ? 12 : 600;
    put('hotChart', {
      grid: { left: 56, right: 24, top: 24, bottom: 52 },
      tooltip: tip({ formatter: p => `<b>${escapeHTML(p.value[3])}</b><br/>${git ? 'Commity' : 'Linie'}: ${nf(p.value[0])} · CC maks.: ${nf(p.value[1])}<br/>Linie: ${nf(p.value[2])} · ESLint: ${nf(p.value[5])} · Triage: ${nf(p.value[4], 1)} (${escapeHTML(p.value[6])})` }),
      xAxis: { type: 'value', name: git ? 'liczba commitów (okno historii)' : 'liczba linii', nameLocation: 'middle', nameGap: 32, nameTextStyle: { color: P.muted }, max: maxX, axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } } },
      yAxis: { type: 'value', name: 'CC maks. w pliku', nameTextStyle: { color: P.muted }, max: maxY, axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } } },
      series: [{
        type: 'scatter', data, symbolSize: v => Math.max(7, Math.min(50, Math.sqrt(v[2]) * 1.5)),
        markArea: { silent: true, itemStyle: { color: 'rgba(239,106,123,.08)' }, label: { show: true, position: 'insideTopRight', color: P.muted, fontSize: 11, formatter: 'strefa przeglądu' }, data: [[{ xAxis: xThr, yAxis: 20 }, { xAxis: maxX, yAxis: maxY }]] },
        markLine: { silent: true, symbol: 'none', lineStyle: { color: P.muted, type: 'dashed', opacity: .6 }, label: { color: P.muted, fontSize: 10 }, data: [{ xAxis: xThr, label: { formatter: git ? '12 commitów' : '600 linii' } }, { yAxis: 20, label: { formatter: 'CC 20' } }] }
      }]
    }, p => { if (p.value) xOpenFile(p.value[3]); });
  }

  /* ───── JS/TS (lizard) ───── */
  function xJsCharts() {
    const L = XS.lizard || {}, P = pal();
    if (L.status !== 'ok' || !L.functions) { const m = L.status === 'ok' ? 'Nie znaleziono funkcji JS/TS w kodzie produkcyjnym.' : statusText(L); note('jsRanksChart', m); note('jsScatter', m); $('jsInfo').textContent = ''; return; }
    $('jsInfo').textContent = `Funkcji: ${nf(L.functions)} · CC>15: ${nf(L.over15)} · >100 NLOC: ${nf(L.long)} · >5 parametrów: ${nf(L.many_params)} · najwyższe CC: ${nf(L.max)}`;
    const g = 'ABCDEF'.split('');
    put('jsRanksChart', {
      grid: { left: 48, right: 16, top: 24, bottom: 30 }, tooltip: tip({ trigger: 'axis' }),
      xAxis: { type: 'category', data: g, axisLabel: { color: P.muted }, axisLine: { lineStyle: { color: P.line } } },
      yAxis: { type: 'value', axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } } },
      series: [{ type: 'bar', barMaxWidth: 42, data: g.map(k => ({ value: L.ranks[k] || 0, itemStyle: { color: grades[k], borderRadius: [6, 6, 0, 0] } })), label: { show: true, position: 'top', color: P.text } }]
    });
    const fns = ((EX.lizard || {}).functions || []).filter(f => PRODJS.has(f.category));
    put('jsScatter', {
      grid: { left: 52, right: 20, top: 24, bottom: 46 },
      tooltip: tip({ formatter: p => `<b>${escapeHTML(p.value[2])}</b><br/>${escapeHTML(p.value[3])}:${p.value[4]}<br/>CC ${p.value[1]} · NLOC ${p.value[0]} · parametry ${p.value[5]}` }),
      xAxis: { type: 'value', name: 'NLOC funkcji', nameLocation: 'middle', nameGap: 28, nameTextStyle: { color: P.muted }, axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } } },
      yAxis: { type: 'value', name: 'CC', nameTextStyle: { color: P.muted }, axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } } },
      series: [{ type: 'scatter', symbolSize: 9, data: fns.map(f => ({ value: [f.nloc, f.cc, f.name, f.file, f.line, f.params], itemStyle: { color: grades[rankOf(f.cc)], opacity: .8 } })),
                 markLine: { silent: true, symbol: 'none', lineStyle: { color: P.muted, type: 'dashed', opacity: .6 }, label: { color: P.muted, fontSize: 10 }, data: [{ yAxis: 15, label: { formatter: 'CC 15' } }] } }]
    }, p => { if (p.value) xOpenFile(p.value[3]); });
  }
  function xJsRows() {
    const L = XS.lizard || {};
    if (L.status !== 'ok') { $('jsRows').innerHTML = `<tr><td colspan="5">${statusText(L)}</td></tr>`; $('jsCount').textContent = ''; return; }
    const term = $('jsSearch').value.toLowerCase(), prod = $('jsScope').value === 'prod';
    const d = ((EX.lizard || {}).functions || []).filter(f => (!prod || PRODJS.has(f.category)) && `${f.name} ${f.file}`.toLowerCase().includes(term)).sort((a, b) => b.cc - a.cc);
    $('jsRows').innerHTML = d.slice(0, 60).map(f => `<tr><td class="numeric"><span class="badge" style="background:${grades[rankOf(f.cc)]}33;color:${grades[rankOf(f.cc)]}">${f.cc}</span></td><td class="numeric">${nf(f.nloc)}</td><td class="numeric">${nf(f.params)}</td><td>${escapeHTML(f.name)}</td><td>${fileCell(f.file)}:${f.line}</td></tr>`).join('') || '<tr><td colspan="5">Brak funkcji spełniających filtr.</td></tr>';
    $('jsCount').textContent = `Pokazano ${Math.min(60, d.length)} z ${nf(d.length)} pasujących funkcji (raport zawiera funkcje o CC ≥ 6, długie lub z wieloma parametrami; komplet w js_functions.csv).`;
  }

  /* ───── bezpieczeństwo ───── */
  const sevCls = s => s === 'HIGH' ? 'sevH' : s === 'MEDIUM' ? 'sevM' : 'sevL';
  function xSecCharts() {
    const S = XS.security || {}, P = pal();
    if (!['ok', 'partial'].includes(S.status)) { note('secDonut', statusText(S)); note('secRules', statusText(S)); $('secInfo').textContent = ''; return; }
    $('secInfo').textContent = `Pliki ze zgłoszeniami: ${nf(S.files_affected)} · zgłoszenia w testach (pominięte w ocenie): ${nf(S.tests_total)}`;
    const total = S.high + S.medium + S.low;
    if (!total) { note('secDonut', 'Bandit nie zgłosił uwag w kodzie nie-testowym.'); }
    else put('secDonut', {
      tooltip: tip({ trigger: 'item' }), legend: { bottom: 0, textStyle: { color: P.muted } },
      series: [{ type: 'pie', radius: ['48%', '72%'], center: ['50%', '45%'], avoidLabelOverlap: true, label: { color: P.text, formatter: '{b}: {c}' }, itemStyle: { borderColor: P.bg, borderWidth: 3 },
                 data: [{ name: 'HIGH', value: S.high, itemStyle: { color: C.red } }, { name: 'MEDIUM', value: S.medium, itemStyle: { color: C.amber } }, { name: 'LOW', value: S.low, itemStyle: { color: C.cyan } }].filter(x => x.value) }]
    });
    const by = {};
    ((EX.bandit || {}).issues || []).filter(i => PRODPY.has(i.category)).forEach(i => { const k = i.test_id; by[k] = by[k] || { n: 0, name: i.test_name, sev: i.severity }; by[k].n++; });
    const top = Object.entries(by).sort((a, b) => b[1].n - a[1].n).slice(0, 10).reverse();
    if (!top.length) { note('secRules', 'Brak zgłoszeń do pokazania.'); return; }
    put('secRules', {
      grid: { left: 190, right: 30, top: 10, bottom: 24 }, tooltip: tip({ trigger: 'axis', axisPointer: { type: 'shadow' } }),
      xAxis: { type: 'value', axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } }, minInterval: 1 },
      yAxis: { type: 'category', data: top.map(([k, v]) => `${k} ${v.name}`), axisLabel: { color: P.text, fontSize: 11, width: 175, overflow: 'truncate' } },
      series: [{ type: 'bar', barMaxWidth: 18, data: top.map(([k, v]) => ({ value: v.n, itemStyle: { color: v.sev === 'HIGH' ? C.red : v.sev === 'MEDIUM' ? C.amber : C.cyan, borderRadius: [0, 5, 5, 0] } })), label: { show: true, position: 'right', color: P.text } }]
    });
  }
  function xSecRows() {
    const S = XS.security || {};
    if (!['ok', 'partial'].includes(S.status)) { $('secRows').innerHTML = `<tr><td colspan="4">${statusText(S)}</td></tr>`; $('secCount').textContent = ''; return; }
    const term = $('secSearch').value.toLowerCase(), sev = $('secSev').value, prod = $('secScope').value === 'prod';
    const rank = { HIGH: 0, MEDIUM: 1, LOW: 2 };
    const d = ((EX.bandit || {}).issues || []).filter(i => (!prod || PRODPY.has(i.category)) && (!sev || i.severity === sev) && `${i.file} ${i.test_id} ${i.test_name} ${i.text}`.toLowerCase().includes(term))
      .sort((a, b) => rank[a.severity] - rank[b.severity] || a.file.localeCompare(b.file) || a.line - b.line);
    $('secRows').innerHTML = d.slice(0, 80).map(i => `<tr><td><span class="badge ${sevCls(i.severity)}">${escapeHTML(i.severity)}</span></td><td class="small"><b>${escapeHTML(i.test_id)}</b><div class="muted">${escapeHTML(i.test_name)}${i.cwe ? ' · CWE-' + i.cwe : ''}</div></td><td class="small" style="white-space:normal;min-width:260px">${escapeHTML(i.text)}</td><td>${fileCell(i.file)}:${i.line}</td></tr>`).join('') || '<tr><td colspan="4">Brak zgłoszeń spełniających filtr.</td></tr>';
    $('secCount').textContent = `Pokazano ${Math.min(80, d.length)} z ${nf(d.length)}. Wartości podejrzanych haseł są w raporcie zastąpione znakami ***.`;
  }
  function xAudit() {
    const A = EX.pip_audit || {}, X = XS.pip_audit || {};
    let msg = '';
    if (X.status === 'disabled') msg = 'pip-audit nie był uruchomiony. Aby sprawdzić zależności (wymaga internetu): <code>.\\Run-CodeAudit.ps1 -ProjectPath "…" -PipAudit</code>.';
    else if (X.status === 'unavailable') msg = 'pip-audit nie jest zainstalowany: <code>python -m pip install pip-audit</code>.';
    else if (X.status === 'no_input') msg = escapeHTML(X.note || 'Nie znaleziono pliku requirements*.txt.');
    else if (X.status === 'unpinned') msg = 'Nie sprawdzono zależności — brak przypiętych wersji. ' + escapeHTML(X.note || '') + ' Wygeneruj listę z dokładnymi wersjami (<code>pip freeze</code>) i wskaż ją opcją <code>-Requirements</code>.';
    else if (X.status === 'error') msg = 'pip-audit nie zwrócił wyniku' + (X.note ? ': ' + escapeHTML(X.note) : '') + '. Pliki requirements muszą mieć przypięte wersje (pakiet==wersja).';
    else msg = `Sprawdzono pakiety: ${nf(X.packages)} · znane podatności: ${nf(X.vulnerabilities)} · dotknięte pakiety: ${nf(X.vulnerable_packages)}. Wynik odzwierciedla bazę podatności z chwili audytu.` + (X.note ? ' <br/><span class="muted">' + escapeHTML(X.note) + '</span>' : '');
    $('auditInfo').innerHTML = msg;
    const v = A.vulnerabilities || [];
    $('auditRows').innerHTML = v.length ? v.map(x => `<tr><td><b>${escapeHTML(x.package)}</b></td><td>${escapeHTML(x.version)}</td><td class="small">${escapeHTML(x.id)}<div class="muted">${escapeHTML((x.aliases || []).join(', '))}</div></td><td class="small">${escapeHTML((x.fix_versions || []).join(', ') || '—')}</td><td class="small" style="white-space:normal;min-width:260px">${escapeHTML(x.description)}</td></tr>`).join('')
      : `<tr><td colspan="5">${X.status === 'ok' ? 'Nie znaleziono znanych podatności w sprawdzonych pakietach.' : 'Brak danych.'}</td></tr>`;
  }

  /* ───── martwy kod i duplikacja ───── */
  function xDeadCharts() {
    const D = XS.dead || {}, P = pal();
    if (D.status !== 'ok') { note('deadTypes', statusText(D)); $('deadInfo').textContent = ''; return; }
    $('deadInfo').textContent = `Kandydatów: ${nf(D.count)} (pewność ≥ 80%: ${nf(D.high_confidence)}). Funkcje wywoływane dynamicznie mogą być oznaczone błędnie.`;
    const t = Object.entries(D.by_type || {}).sort((a, b) => b[1] - a[1]);
    if (!t.length) { note('deadTypes', 'Vulture nie zgłosił kandydatów.'); return; }
    put('deadTypes', {
      grid: { left: 90, right: 36, top: 10, bottom: 20 }, tooltip: tip({ trigger: 'axis', axisPointer: { type: 'shadow' } }),
      xAxis: { type: 'value', axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } }, minInterval: 1 },
      yAxis: { type: 'category', inverse: true, data: t.map(x => x[0]), axisLabel: { color: P.text } },
      series: [{ type: 'bar', barMaxWidth: 20, data: t.map(x => ({ value: x[1], itemStyle: { color: C.violet, borderRadius: [0, 5, 5, 0] } })), label: { show: true, position: 'right', color: P.text } }]
    });
  }
  function xDupCharts() {
    const U = XS.duplication || {}, P = pal();
    if (U.status !== 'ok') { note('dupFiles', statusText(U)); $('dupInfo').textContent = ''; return; }
    $('dupInfo').textContent = `Zduplikowane znaczące linie: ok. ${nf(U.percent, 1)}% (${nf(U.lines)}). Heurystyka: okno ${U.window} linii, pomijane importy i komentarze.`;
    const rows = (DATA.matrix || []).filter(r => r.dup > 0).map(r => ({ p: r.p, n: Math.round(r.dup * r.l / 100), pct: r.dup })).sort((a, b) => b.n - a.n).slice(0, 8);
    if (!rows.length) { note('dupFiles', 'Nie wykryto powielonych bloków.'); return; }
    put('dupFiles', {
      grid: { left: 200, right: 40, top: 10, bottom: 20 }, tooltip: tip({ formatter: p => `<b>${escapeHTML(rows[p.dataIndex].p)}</b><br/>ok. ${rows[p.dataIndex].n} linii (${nf(rows[p.dataIndex].pct, 1)}% pliku)` }),
      xAxis: { type: 'value', axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } } },
      yAxis: { type: 'category', inverse: true, data: rows.map(r => r.p), axisLabel: { color: P.text, fontSize: 11, width: 185, overflow: 'truncate' } },
      series: [{ type: 'bar', barMaxWidth: 18, data: rows.map(r => ({ value: r.n, itemStyle: { color: C.amber, borderRadius: [0, 5, 5, 0] } })), label: { show: true, position: 'right', color: P.text } }]
    }, p => xOpenFile(rows[p.dataIndex].p));
  }
  function xDeadRows() {
    const D = XS.dead || {};
    if (D.status !== 'ok') { $('deadRows').innerHTML = `<tr><td colspan="4">${statusText(D)}</td></tr>`; $('deadCount').textContent = ''; return; }
    const term = $('deadSearch').value.toLowerCase(), conf = +$('deadConf').value, prod = $('deadScope').value === 'prod';
    const d = ((EX.vulture || {}).items || []).filter(i => i.confidence >= conf && (!prod || PRODPY.has(i.category)) && `${i.name} ${i.file}`.toLowerCase().includes(term));
    $('deadRows').innerHTML = d.slice(0, 80).map(i => `<tr><td class="numeric">${i.confidence}%</td><td>${escapeHTML(i.type)}</td><td><b>${escapeHTML(i.name)}</b></td><td>${fileCell(i.file)}:${i.line}</td></tr>`).join('') || '<tr><td colspan="4">Brak wyników.</td></tr>';
    $('deadCount').textContent = `Pokazano ${Math.min(80, d.length)} z ${nf(d.length)}. Pełna lista w dead_code.csv.`;
  }
  function xDupRows() {
    const U = EX.duplication || {};
    if (U.status !== 'ok') { $('dupRows').innerHTML = `<tr><td colspan="3">${statusText(U)}</td></tr>`; return; }
    $('dupRows').innerHTML = (U.blocks || []).slice(0, 40).map(b => `<tr><td class="numeric">${b.lines}</td><td>${fileCell(b.a)}:${b.a_from}–${b.a_to}</td><td>${fileCell(b.b)}:${b.b_from}–${b.b_to}</td></tr>`).join('') || '<tr><td colspan="3">Brak zduplikowanych bloków.</td></tr>';
  }

  /* ───── graf zależności ───── */
  function xDeps() {
    const D = EX.deps || {}, P = pal();
    if (D.status !== 'ok') { note('depGraph', statusText(D)); $('depInfo').textContent = ''; return; }
    const g = D.graph || { nodes: [], edges: [] };
    $('depInfo').textContent = `Moduły: ${nf(D.nodes_total)} (Python ${nf(D.python_modules)}, JS/TS ${nf(D.js_modules)}) · powiązania: ${nf(D.edges_total)} · cykle: ${nf(D.cycles_total)}. Na grafie: ${nf(g.nodes.length)} najbardziej powiązanych modułów.`;
    if (!g.nodes.length) { note('depGraph', 'Nie znaleziono wewnętrznych importów między modułami.'); return; }
    const gc = {}; g.nodes.forEach(n => gc[n.group] = (gc[n.group] || 0) + 1);
    const groups = Object.entries(gc).sort((a, b) => b[1] - a[1]).map(x => x[0]);
    const pcol = [C.cyan, C.violet, C.green, C.amber, '#e07bb5', '#5fd0d8', '#9ac55a', '#f08a5d', '#7d93f0', '#c0a0e8'];
    const idx = n => Math.min(groups.indexOf(n.group), pcol.length - 1);
    const cyc = {}; (D.cycles || []).forEach((c, i) => c.forEach(m => cyc[m] = i));
    const nodes = g.nodes.map(n => { const deg = n.fan_in + n.fan_out; return { id: n.path, name: base(n.path), value: deg, category: idx(n), symbolSize: 12 + Math.sqrt(deg) * 5,
      itemStyle: { color: pcol[idx(n)], borderColor: n.cycle ? C.red : P.bg, borderWidth: n.cycle ? 3 : 1 }, label: { show: g.nodes.length <= 40 || deg >= 4 || n.cycle, color: P.text, fontSize: 10 }, path: n.path, fan_in: n.fan_in, fan_out: n.fan_out }; });
    const edges = g.edges.map(([a, b]) => ({ source: a, target: b, lineStyle: (a in cyc && b in cyc && cyc[a] === cyc[b]) ? { color: C.red, width: 2, opacity: .9 } : { color: P.muted, opacity: .35, width: 1 } }));
    put('depGraph', {
      tooltip: tip({ formatter: p => p.dataType === 'node' ? `<b>${escapeHTML(p.data.path)}</b><br/>importowany przez: ${p.data.fan_in} · importuje: ${p.data.fan_out}` : `${escapeHTML(p.data.source)}<br/>→ ${escapeHTML(p.data.target)}` }),
      legend: { type: 'scroll', top: 0, textStyle: { color: P.muted }, data: groups.slice(0, 10) },
      series: [{ type: 'graph', layout: 'force', roam: true, draggable: true, top: 28, categories: groups.slice(0, 10).map(n => ({ name: n, itemStyle: { color: pcol[groups.indexOf(n)] } })),
                 data: nodes, links: edges, edgeSymbol: ['none', 'arrow'], edgeSymbolSize: 5, lineStyle: { curveness: .08 }, emphasis: { focus: 'adjacency' },
                 force: { repulsion: 150, gravity: .07, edgeLength: [35, 130], layoutAnimation: !printing && !reduceMotion } }]
    }, p => { if (p.dataType === 'node') xOpenFile(p.data.path); });
  }
  function xDepTables() {
    const D = EX.deps || {};
    const rows = (a, c) => (a || []).map(x => `<tr><td>${fileCell(x.path)}</td><td class="numeric">${x.value}</td></tr>`).join('') || `<tr><td colspan="2">${c}</td></tr>`;
    $('fanInRows').innerHTML = rows(D.top_fan_in, 'Brak danych.'); $('fanOutRows').innerHTML = rows(D.top_fan_out, 'Brak danych.');
    const cy = D.cycles || [];
    $('cycleList').innerHTML = D.status !== 'ok' ? `<p class="muted small">${statusText(D)}</p>`
      : (cy.length ? cy.map(c => `<div class="cyc"><b>${c.length} modułów w cyklu</b><br/>${c.slice(0, 8).map(fileCell).join(' ↔ ')}${c.length > 8 ? ' …' : ''}</div>`).join('') + '<p class="hint">Cykle utrudniają testowanie i zmiany; to sygnał architektoniczny, nie błąd działania.</p>'
        : '<p class="muted small">Nie wykryto cykli importów.</p>');
  }

  /* ───── aktywność Git ───── */
  function xGit() {
    const A = DATA.activity || {}, P = pal();
    if (!A.daily || !A.daily.length) { note('calChart', 'Brak historii Git.'); note('hourChart', 'Brak historii Git.'); return; }
    const iso = d => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    const end = new Date(A.last + 'T12:00:00'), start = new Date(end); start.setDate(start.getDate() - 364);
    const from = iso(start), data = A.daily.filter(x => x[0] >= from);
    $('calInfo').textContent = `Liczba commitów dziennie · okres ${from} – ${A.last} · dni z aktywnością w całej historii: ${nf(A.active_days)}.`;
    put('calChart', {
      tooltip: tip({ formatter: p => `${escapeHTML(p.value[0])}: <b>${p.value[1]}</b> commit(ów)` }),
      visualMap: { type: 'piecewise', orient: 'horizontal', left: 'center', bottom: 0, itemWidth: 14, itemHeight: 14, textStyle: { color: P.muted },
                   pieces: [{ min: 1, max: 1, color: '#25757c', label: '1' }, { min: 2, max: 2, color: '#2fa0a6', label: '2' }, { min: 3, max: 4, color: '#4fd1a5', label: '3–4' }, { min: 5, color: '#c6f48f', label: '5+' }], outOfRange: { color: P.surface2 } },
      calendar: { top: 30, left: 36, right: 12, bottom: 38, cellSize: ['auto', 14], range: [from, A.last], itemStyle: { borderWidth: 3, borderColor: P.bg, color: P.surface2 }, splitLine: { show: false }, yearLabel: { show: false },
                  monthLabel: { color: P.muted, nameMap: ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru'] }, dayLabel: { firstDay: 1, color: P.muted, nameMap: ['Nd', 'Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So'] } },
      series: [{ type: 'heatmap', coordinateSystem: 'calendar', data }]
    });
    const grid = (A.grid || []).map(x => [x[1], x[0], x[2]]), mx = Math.max(1, ...grid.map(x => x[2]));
    put('hourChart', {
      grid: { left: 44, right: 20, top: 14, bottom: 50 }, tooltip: tip({ formatter: p => `${WD[p.value[1]]}, ${p.value[0]}:00 — <b>${p.value[2]}</b> commit(ów)` }),
      xAxis: { type: 'category', data: Array.from({ length: 24 }, (_, i) => i), splitArea: { show: true }, axisLabel: { color: P.muted }, axisLine: { lineStyle: { color: P.line } } },
      yAxis: { type: 'category', data: WD, inverse: true, axisLabel: { color: P.muted }, axisLine: { lineStyle: { color: P.line } } },
      visualMap: { min: 0, max: mx, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, itemHeight: 120, textStyle: { color: P.muted }, inRange: { color: [P.surface2, '#2fa0a6', '#c6f48f'] } },
      series: [{ type: 'heatmap', data: grid, itemStyle: { borderColor: P.bg, borderWidth: 2, borderRadius: 3 } }]
    });
  }

  /* ───── modal pliku ───── */
  function tbl(head, rows) { return rows.length ? `<div class="tblWrap" style="max-height:260px"><table><thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>` : '<p class="muted small">Brak pozycji.</p>'; }
  function xOpenFile(path) {
    const k = kp(path), m = (DATA.matrix || []).find(r => kp(r.p) === k) || { p: path };
    $('fmTitle').textContent = path;
    const st = (l, v) => `<div class="fmStat"><b>${v}</b><span>${escapeHTML(l)}</span></div>`;
    let h = '<div class="fmStats">' + [st('Linie', nf(m.l)), st('Kategoria', escapeHTML(m.c || '—')), st('CC maks.', nf(m.cc)), st('MI', nf(m.mi, 1)), st('ESLint', nf(m.es || 0)),
      st('Bandit (waga)', nf(m.sec || 0, 1)), st('Martwy kod', nf(m.dead || 0)), st('Duplikacja', nf(m.dup || 0, 1) + '%'), st('Commity', nf(m.n || 0)), st('Indeks triage', nf(m.r || 0, 1))].join('') + '</div>';
    const py = (DATA.functions || []).filter(f => kp(f.file) === k).sort((a, b) => b.cc - a.cc).slice(0, 12);
    if (py.length) h += '<h4>Funkcje Python wg CC</h4>' + tbl(['CC', 'Klasa', 'Funkcja', 'Linia'], py.map(f => `<tr><td class="numeric">${f.cc}</td><td>${escapeHTML(f.rank)}</td><td>${escapeHTML(f.name)}</td><td>${f.line}</td></tr>`));
    const js = ((EX.lizard || {}).functions || []).filter(f => kp(f.file) === k).sort((a, b) => b.cc - a.cc).slice(0, 12);
    if (js.length) h += '<h4>Funkcje JS/TS wg CC (lizard)</h4>' + tbl(['CC', 'NLOC', 'Param.', 'Funkcja', 'Linia'], js.map(f => `<tr><td class="numeric">${f.cc}</td><td class="numeric">${f.nloc}</td><td class="numeric">${f.params}</td><td>${escapeHTML(f.name)}</td><td>${f.line}</td></tr>`));
    const es = (DATA.issues || []).filter(i => kp(i.file) === k);
    if (es.length) h += `<h4>ESLint (${es.length})</h4>` + tbl(['Linia', 'Reguła', 'Komunikat'], es.slice(0, 15).map(i => `<tr><td>${i.line || '?'}</td><td><b>${escapeHTML(i.rule)}</b></td><td class="small" style="white-space:normal">${escapeHTML(i.message).slice(0, 240)}</td></tr>`));
    const bn = ((EX.bandit || {}).issues || []).filter(i => kp(i.file) === k);
    if (bn.length) h += `<h4>Bandit (${bn.length})</h4>` + tbl(['Waga', 'Test', 'Opis', 'Linia'], bn.slice(0, 15).map(i => `<tr><td><span class="badge ${sevCls(i.severity)}">${i.severity}</span></td><td>${escapeHTML(i.test_id)}</td><td class="small" style="white-space:normal">${escapeHTML(i.text)}</td><td>${i.line}</td></tr>`));
    const vt = ((EX.vulture || {}).items || []).filter(i => kp(i.file) === k);
    if (vt.length) h += `<h4>Kandydaci na martwy kod (${vt.length})</h4>` + tbl(['Pewność', 'Typ', 'Nazwa', 'Linia'], vt.slice(0, 15).map(i => `<tr><td class="numeric">${i.confidence}%</td><td>${escapeHTML(i.type)}</td><td>${escapeHTML(i.name)}</td><td>${i.line}</td></tr>`));
    const du = ((EX.duplication || {}).blocks || []).filter(b => kp(b.a) === k || kp(b.b) === k);
    if (du.length) h += '<h4>Zduplikowane bloki</h4>' + tbl(['Linie', 'Fragment A', 'Fragment B'], du.slice(0, 10).map(b => `<tr><td class="numeric">${b.lines}</td><td>${escapeHTML(b.a)}:${b.a_from}–${b.a_to}</td><td>${escapeHTML(b.b)}:${b.b_from}–${b.b_to}</td></tr>`));
    const dp = EX.deps || {};
    if (dp.files && dp.edges) {
      const i = dp.files.findIndex(f => kp(f) === k);
      if (i >= 0) {
        const out = dp.edges.filter(e => e[0] === i).map(e => dp.files[e[1]]), inn = dp.edges.filter(e => e[1] === i).map(e => dp.files[e[0]]);
        h += `<h4>Zależności</h4><div class="small"><b>Importuje (${out.length}):</b> ${out.slice(0, 14).map(fileCell).join(', ') || '—'}<br/><b>Importowany przez (${inn.length}):</b> ${inn.slice(0, 14).map(fileCell).join(', ') || '—'}</div>`;
      }
    }
    $('fmBody').innerHTML = h; $('fileModal').classList.add('open'); $('fmClose').focus();
  }
  function xClose() { $('fileModal').classList.remove('open'); }

  /* ───── start ───── */
  function renderCharts() { [xRadar, xTrend, xTree, xHot, xJsCharts, xSecCharts, xDeadCharts, xDupCharts, xDeps, xGit].forEach(safe); }
  function renderTables() { [xJsRows, xSecRows, xAudit, xDeadRows, xDupRows, xDepTables].forEach(safe); }
  safe(xExec); safe(xKpi);
  $('radarFormulas').innerHTML = (DATA.radar || []).map(a => addRow([a.name, a.formula])).join('');
  const mt = DATA.meta || {};
  $('toolVersions').textContent = 'Narzędzia: Radon ' + (mt.radon_version || '—') + ' · ESLint ' + (mt.eslint_version || '—') + ' · lizard ' + (mt.lizard_version || '—') + ' · vulture ' + (mt.vulture_version || '—') + ' · bandit ' + (mt.bandit_version || '—') + ' · pip-audit ' + (mt.pip_audit_version || 'nie uruchomiono') + ' · ECharts ' + (ECH ? ECH.version : 'niedostępny');
  renderTables(); renderCharts();

  ['radarMode'].forEach(id => $(id).addEventListener('change', () => safe(xRadar)));
  $('trendMetric').addEventListener('change', () => safe(xTrend));
  $('treeMetric').addEventListener('change', () => safe(xTree));
  ['jsSearch', 'jsScope'].forEach(id => $(id).addEventListener('input', () => safe(xJsRows)));
  ['secSearch', 'secSev', 'secScope'].forEach(id => $(id).addEventListener('input', () => safe(xSecRows)));
  ['deadSearch', 'deadConf', 'deadScope'].forEach(id => $(id).addEventListener('input', () => safe(xDeadRows)));
  $('fmClose').addEventListener('click', xClose);
  $('fileModal').addEventListener('click', e => { if (e.target === $('fileModal')) xClose(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') xClose(); });
  document.addEventListener('click', e => {
    const f = e.target.closest('[data-file]'); if (f) { xOpenFile(f.dataset.file); return; }
    const r = e.target.closest('#riskRows code'); if (r) xOpenFile(r.textContent);
  });
  $('theme').addEventListener('click', () => setTimeout(renderCharts, 40));
  $('printBtn').addEventListener('click', () => window.print());
  let rz = null;
  window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => Object.values(charts).forEach(c => c.resize()), 120); });
  window.addEventListener('beforeprint', () => { printing = true; document.querySelectorAll('.chart').forEach(el => { if (el.id === 'treeChart' || el.id === 'hotChart' || el.id === 'depGraph') el.style.height = '440px'; });
    Object.values(charts).forEach(c => c.resize({ width: Math.min(760, document.querySelector('.shell').clientWidth) })); renderCharts(); });
  window.addEventListener('afterprint', () => { printing = false; document.querySelectorAll('.chart').forEach(el => el.style.height = ''); Object.values(charts).forEach(c => c.resize({ width: 'auto' })); renderCharts(); });
})();
