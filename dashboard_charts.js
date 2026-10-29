/* CodeAudit 2.2 — wykresy i widoki rozszerzone. Wstrzykiwane do report.html.
   Korzysta z globali szablonu: DATA, $, nf, escapeHTML, addRow, grades. Bez sieci.
   W pełni wspiera przełączanie języków (EN, PL, ZH). */
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
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

  const CAL_MONTHS = {
    en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    pl: ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru'],
    zh: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
  };
  const CAL_DAYS = {
    en: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
    pl: ['Nd', 'Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So'],
    zh: ['日', '一', '二', '三', '四', '五', '六']
  };
  const WD_MAP = {
    en: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    pl: ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So', 'Nd'],
    zh: ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  };

  function getLang() {
    return window.currentLang || DATA.current_lang || 'en';
  }

  function t(k, fallback) {
    const lang = getLang();
    if (DATA.i18n && DATA.i18n[lang] && DATA.i18n[lang][k] != null) return DATA.i18n[lang][k];
    return fallback != null ? fallback : k;
  }

  function pal() {
    if (printing) return { text: '#111827', muted: '#475569', line: '#d5dce6', surface: '#ffffff', surface2: '#f1f5f9', bg: '#ffffff' };
    return { text: css('--text') || '#eaf0fb', muted: css('--muted') || '#94a7c5', line: css('--line') || '#283650',
             surface: css('--surface') || '#121c31', surface2: css('--surface2') || '#18243c', bg: css('--bg') || '#0a1020' };
  }
  const tip = extra => Object.assign({ backgroundColor: pal().surface2, borderColor: pal().line,
    textStyle: { color: pal().text, fontSize: 12 }, extraCssText: 'max-width:440px;white-space:normal;word-break:break-all;' }, extra || {});
  const rankOf = cc => cc <= 5 ? 'A' : cc <= 10 ? 'B' : cc <= 20 ? 'C' : cc <= 30 ? 'D' : cc <= 40 ? 'E' : 'F';
  const base = p => String(p).split('/').pop();
  const fileCell = p => `<code class="fl" data-file="${escapeHTML(p)}" title="${escapeHTML(p)}">${escapeHTML(p)}</code>`;

  function statusText(o) {
    const lang = getLang();
    if (!o || !o.status) return lang === 'pl' ? 'Brak danych.' : (lang === 'zh' ? '暂无数据。' : 'No data.');
    if (o.status === 'disabled') return lang === 'pl' ? 'Analiza wyłączona w tym przebiegu.' : (lang === 'zh' ? '本轮审计已禁用该分析。' : 'Analysis disabled in this run.');
    if (o.status === 'unavailable') {
      const u = lang === 'pl' ? 'Narzędzie niedostępne' : (lang === 'zh' ? '工具不可用' : 'Tool unavailable');
      return u + (o.note ? ': ' + escapeHTML(o.note) : '') + '.';
    }
    return escapeHTML(o.status) + (o.note ? ': ' + escapeHTML(o.note) : '');
  }
  const safe = f => { try { f(); } catch (e) { console.error('CodeAudit 2.2 /', f.name, e); } };

  /* ───── podstawy ECharts ───── */
  function mk(id) {
    const el = $(id); if (!el) return null;
    if (!ECH) {
      if (!el.dataset.msg) {
        el.dataset.msg = '1';
        const lang = getLang();
        const msg = lang === 'pl' ? 'Brak biblioteki ECharts w raporcie. Umieść <code>echarts.min.js</code> w <code>C:\\Tools\\CodeAudit\\vendor\\</code> i uruchom audyt ponownie.' :
          (lang === 'zh' ? '报告中未内嵌 Apache ECharts 库。请将 <code>echarts.min.js</code> 放置于 <code>C:\\Tools\\CodeAudit\\vendor\\</code> 后重新执行审计。' :
          'Apache ECharts library not found in report. Place <code>echarts.min.js</code> in <code>C:\\Tools\\CodeAudit\\vendor\\</code> and rerun audit.');
        el.innerHTML = `<div class="chartNote">${msg}</div>`;
      }
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
    const lang = getLang();
    const e = (DATA.exec_i18n && DATA.exec_i18n[lang]) || DATA.exec;
    if (!e) { if ($('exec')) $('exec').style.display = 'none'; return; }
    if ($('execHead')) $('execHead').textContent = e.headline;
    if ($('execFacts')) $('execFacts').innerHTML = (e.facts || []).map(f => `<li><span class="edot ${escapeHTML(f.level)}"></span><span>${escapeHTML(f.text)}</span></li>`).join('');
    if ($('execActions')) $('execActions').innerHTML = (e.actions || []).map(a => `<li><span>${escapeHTML(a)}</span></li>`).join('');
  }
  function xKpi() {
    const lang = getLang();
    const s = XS.security || {}, d = XS.dead || {}, u = XS.duplication || {}, p = XS.deps || {}, a = XS.pip_audit || {};
    const okS = ['ok', 'partial'].includes(s.status);
    if ($('kSec')) $('kSec').innerHTML = okS ? `${nf(s.high)}<small> HIGH</small> · ${nf(s.medium)}<small> MED</small>` : '—';
    if ($('kSecSub')) {
      if (okS) {
        let sub = `LOW: ${nf(s.low)} · `;
        if (a.status === 'ok') {
          sub += lang === 'pl' ? `zależności: ${nf(a.vulnerabilities)} znanych podatności (sprawdzono pakietów: ${nf(a.packages)}${a.skipped ? ', pominięto: ' + nf(a.skipped) : ''})` :
                 (lang === 'zh' ? `依赖项: ${nf(a.vulnerabilities)} 个已知漏洞 (已检查 ${nf(a.packages)} 个包${a.skipped ? '，跳过: ' + nf(a.skipped) : ''})` :
                 `dependencies: ${nf(a.vulnerabilities)} known CVEs (checked: ${nf(a.packages)}${a.skipped ? ', skipped: ' + nf(a.skipped) : ''})`);
        } else {
          sub += lang === 'pl' ? 'nie sprawdzano (pip-audit)' : (lang === 'zh' ? '未检查 (pip-audit)' : 'not checked (pip-audit)');
        }
        $('kSecSub').textContent = sub;
      } else {
        $('kSecSub').textContent = s.status === 'unavailable' ? (lang === 'pl' ? 'bandit niedostępny' : (lang === 'zh' ? 'bandit 不可用' : 'bandit unavailable')) : (lang === 'pl' ? 'analiza wyłączona' : (lang === 'zh' ? '已禁用' : 'analysis disabled'));
      }
    }
    if ($('kDead')) $('kDead').textContent = d.status === 'ok' ? nf(d.count) : '—';
    if ($('kDeadSub')) {
      if (d.status === 'ok') {
        $('kDeadSub').textContent = lang === 'pl' ? `w tym pewność ≥ 80%: ${nf(d.high_confidence)} · wymaga weryfikacji` :
          (lang === 'zh' ? `其中置信度 ≥ 80%: ${nf(d.high_confidence)} · 需人工核验` :
          `confidence ≥ 80%: ${nf(d.high_confidence)} · requires review`);
      } else {
        $('kDeadSub').textContent = d.status === 'unavailable' ? (lang === 'pl' ? 'vulture niedostępny' : (lang === 'zh' ? 'vulture 不可用' : 'vulture unavailable')) : (lang === 'pl' ? 'analiza wyłączona' : (lang === 'zh' ? '已禁用' : 'analysis disabled'));
      }
    }
    if ($('kDup')) $('kDup').innerHTML = u.status === 'ok' && u.percent != null ? `${nf(u.percent, 1)}<small> %</small>` : '—';
    if ($('kDupSub')) {
      if (u.status === 'ok') {
        $('kDupSub').textContent = lang === 'pl' ? `${nf(u.blocks)} największych bloków na liście` :
          (lang === 'zh' ? `列表中 ${nf(u.blocks)} 个最大代码块` : `${nf(u.blocks)} largest blocks in list`);
      } else {
        $('kDupSub').textContent = lang === 'pl' ? 'analiza wyłączona' : (lang === 'zh' ? '已禁用' : 'analysis disabled');
      }
    }
    if ($('kDeps')) $('kDeps').textContent = p.status === 'ok' ? nf(p.cycles) : '—';
    if ($('kDepsSub')) {
      if (p.status === 'ok') {
        $('kDepsSub').textContent = lang === 'pl' ? `${nf(p.modules)} modułów · ${nf(p.edges)} powiązań` :
          (lang === 'zh' ? `${nf(p.modules)} 个模块 · ${nf(p.edges)} 条依赖边` : `${nf(p.modules)} modules · ${nf(p.edges)} edges`);
      } else {
        $('kDepsSub').textContent = lang === 'pl' ? 'analiza wyłączona' : (lang === 'zh' ? '已禁用' : 'analysis disabled');
      }
    }
  }

  /* ───── radar i trend ───── */
  function xRadar() {
    const lang = getLang();
    const axes = (DATA.radar || []).filter(a => a.value != null);
    const mode = $('radarMode') ? $('radarMode').value : 'all';
    const prev = (DATA.previous && DATA.previous.radar) || null;
    const use = mode === 'cmp' ? axes.filter(a => prev && prev[a.key] != null) : axes;
    if (use.length < 3) {
      note('radarChart', mode === 'cmp' ?
        (lang === 'pl' ? `Za mało wspólnych osi z poprzednim audytem (${use.length}). Porównanie wymaga co najmniej 3.` :
         (lang === 'zh' ? `与上一版本共有指标轴不足 (${use.length})，对比至少需要 3 个。` :
         `Too few common axes with previous audit (${use.length}). Comparison requires at least 3.`)) :
        (lang === 'pl' ? 'Za mało danych do narysowania radaru.' : (lang === 'zh' ? '数据不足，无法绘制雷达图。' : 'Insufficient data to render radar.')));
      if ($('radarNote')) $('radarNote').textContent = ''; return;
    }
    const P = pal();
    const axName = a => (DATA.radar_i18n && DATA.radar_i18n[lang] && DATA.radar_i18n[lang][a.key]) || a.name;
    const curLabel = lang === 'pl' ? 'Bieżący' : (lang === 'zh' ? '本期审计' : 'Current');
    const prevLabel = lang === 'pl' ? 'Poprzedni' : (lang === 'zh' ? '上期审计' : 'Previous');
    const data = [{ name: curLabel, value: use.map(a => a.value), areaStyle: { opacity: .28 }, lineStyle: { width: 2 }, itemStyle: { color: C.cyan } }];
    if (mode === 'cmp') data.push({ name: prevLabel, value: use.map(a => prev[a.key]), areaStyle: { opacity: .08 }, lineStyle: { width: 2, type: 'dashed' }, itemStyle: { color: C.violet } });
    put('radarChart', {
      tooltip: tip({ trigger: 'item', formatter: p => `<b>${escapeHTML(p.name)}</b><br/>` + use.map((a, i) => `${escapeHTML(axName(a))}: <b>${nf(p.value[i], 1)}</b>`).join('<br/>') }),
      legend: mode === 'cmp' ? { bottom: 0, textStyle: { color: P.muted } } : undefined,
      radar: { indicator: use.map(a => ({ name: axName(a), max: 100 })), radius: '62%', splitNumber: 4, axisName: { color: P.text, fontSize: 11 },
               splitLine: { lineStyle: { color: P.line } }, splitArea: { show: false }, axisLine: { lineStyle: { color: P.line } } },
      series: [{ type: 'radar', data, symbolSize: 5 }]
    });
    const miss = (DATA.radar || []).filter(a => a.value == null).map(axName);
    if ($('radarNote')) {
      $('radarNote').textContent = (miss.length ? (lang === 'pl' ? 'Osie bez danych: ' : (lang === 'zh' ? '暂无数据维度: ' : 'Axes without data: ')) + miss.join(', ') + '. ' : '') +
        (mode === 'cmp' ? (lang === 'pl' ? 'Pokazano tylko osie zmierzone w obu audytach.' : (lang === 'zh' ? '仅显示两次审计均测量的维度。' : 'Showing only axes measured in both audits.')) : '');
    }
  }
  function xTrend() {
    const lang = getLang();
    const tr = DATA.trend || [], m = $('trendMetric') ? $('trendMetric').value : 'score';
    const val = e => m === 'sec' ? (e.sec_high == null ? null : e.sec_high + (e.sec_med || 0)) : e[m];
    const pts = tr.map(e => ({ id: e.id, t: (e.t || '').slice(0, 16).replace('T', ' '), v: val(e) }));
    if (!pts.length || pts.every(p => p.v == null)) {
      note('trendChart', lang === 'pl' ? 'Brak danych tej metryki w zapisanych audytach.' : (lang === 'zh' ? '历史审计记录中暂无该指标数据。' : 'No historical data for this metric in recorded audits.'));
      if ($('trendNote')) $('trendNote').textContent = ''; return;
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
    if ($('trendNote')) {
      $('trendNote').textContent = tr.length < 2 ? (lang === 'pl' ? 'To pierwszy zapisany pomiar — trend pojawi się po kolejnych audytach.' : (lang === 'zh' ? '这是首次记录的审计 — 趋势将在后续审计中呈现。' : 'Baseline measurement — trend graph will populate after subsequent audits.')) :
        (lang === 'pl' ? `Zapisanych audytów: ${tr.length}. Puste punkty = metryka niemierzona w starszej wersji.` : (lang === 'zh' ? `已记录审计数: ${tr.length}。空白点代表旧版本未度量。` : `Recorded audits: ${tr.length}. Blank points denote unmeasured metrics in legacy runs.`));
    }
  }

  /* ───── treemap ───── */
  const STOPS = ['#2f9a7e', '#d9a441', '#e0586a'].map(h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)));
  function heat(t) {
    t = Math.max(0, Math.min(1, t)); const k = t < .55 ? 0 : 1, u = k === 0 ? t / .55 : (t - .55) / .45;
    const a = STOPS[k], b = STOPS[k + 1];
    return 'rgb(' + a.map((x, i) => Math.round(x + (b[i] - x) * u)).join(',') + ')';
  }
  const METRICS = {
    r: { label: 'Triage index', v: r => r.r || 0, fmt: v => nf(v, 1) },
    cc: { label: 'CC max', v: r => r.cc, fmt: v => nf(v) },
    mi: { label: 'MI (lower = worse)', v: r => r.mi, t: v => (70 - v) / 50, fmt: v => nf(v, 1), hi: 'MI ≤ 20' },
    es: { label: 'ESLint issues', v: r => r.es || 0, fmt: v => nf(v) },
    sec: { label: 'Bandit (severity)', v: r => (r.c && PRODPY.has(r.c)) || r.sec ? r.sec || 0 : null, fmt: v => nf(v, 1) },
    dead: { label: 'Dead code', v: r => PRODPY.has(r.c) ? r.dead || 0 : null, fmt: v => nf(v) },
    dup: { label: 'Duplication %', v: r => r.dup || 0, t: v => v / 40, fmt: v => nf(v, 1) + '%', hi: '≥ 40%' },
    n: { label: 'Commits', v: r => r.n || 0, fmt: v => nf(v) }
  };
  function scaler(key) {
    const M = METRICS[key]; if (M.t) return { f: M.t, hi: M.hi };
    const vals = (DATA.matrix || []).map(M.v).filter(v => v != null && v > 0).sort((a, b) => a - b);
    const hi = vals.length ? vals[Math.min(vals.length - 1, Math.floor(vals.length * .95))] : 1;
    return { f: v => v / (hi || 1), hi: '≥ ' + M.fmt(hi) };
  }
  function buildTree(key) {
    const M = METRICS[key], S = scaler(key);
    const root = { name: 'root', kids: new Map() };
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
    const lang = getLang();
    if (!(DATA.matrix || []).length) {
      note('treeChart', lang === 'pl' ? 'Brak plików kodu do pokazania.' : (lang === 'zh' ? '暂无可展示的代码文件。' : 'No code files to display.'));
      return;
    }
    const key = $('treeMetric') ? $('treeMetric').value : 'r', M = METRICS[key], P = pal();
    const { tree, hi } = buildTree(key);
    if ($('treeLegendMax')) $('treeLegendMax').textContent = (lang === 'pl' ? 'wysoki' : (lang === 'zh' ? '高' : 'high')) + ' (' + hi + ')';
    put('treeChart', {
      tooltip: tip({ formatter: p => {
        const r = p.data && p.data.row;
        if (!r) return `<b>${escapeHTML(p.name)}</b><br/>${lang === 'pl' ? 'Linie' : (lang === 'zh' ? '代码行' : 'Lines')}: ${nf(p.value)}`;
        const v = M.v(r);
        const linesLbl = lang === 'pl' ? 'Linie' : (lang === 'zh' ? '代码行' : 'Lines');
        const triageLbl = lang === 'pl' ? 'Triage' : (lang === 'zh' ? '审查指数' : 'Triage');
        return `<b>${escapeHTML(r.p)}</b><br/>${linesLbl}: ${nf(r.l)} · ${escapeHTML(M.label)}: <b>${v == null ? '—' : M.fmt(v)}</b><br/>CC max: ${nf(r.cc)} · MI: ${nf(r.mi, 1)} · ESLint: ${nf(r.es)}<br/>Bandit: ${nf(r.sec, 1)} · ${t('kpi_dead','Dead code')}: ${nf(r.dead)} · ${t('kpi_dup','Dup')}: ${nf(r.dup, 1)}%<br/>${t('git_kpi_commits','Commits')}: ${nf(r.n)} · ${triageLbl}: ${nf(r.r, 1)} ${r.pr ? '(' + r.pr + ')' : ''}`;
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
    const lang = getLang();
    const rows = (DATA.matrix || []).filter(r => r.cc != null);
    if (!rows.length) {
      note('hotChart', lang === 'pl' ? 'Brak plików ze zmierzoną złożonością.' : (lang === 'zh' ? '暂无具有复杂度度量的数据。' : 'No files with measured complexity.'));
      return;
    }
    const git = (DATA.matrix || []).some(r => r.n > 0), xk = git ? 'n' : 'l', P = pal();
    if ($('hotTitle')) {
      $('hotTitle').textContent = git ?
        (lang === 'pl' ? 'Hotspoty: zmiany × złożoność' : (lang === 'zh' ? '热点分析：代码变动 × 圈复杂度' : 'Hotspots: Churn × Complexity')) :
        (lang === 'pl' ? 'Złożoność × rozmiar (brak historii Git)' : (lang === 'zh' ? '复杂度 × 规模 (无 Git 历史)' : 'Complexity × Size (no Git history)'));
    }
    if ($('hotSub')) {
      $('hotSub').textContent = lang === 'pl' ?
        'Prawy górny róg = pliki jednocześnie złożone i duże/często zmieniane — dobre kandydaty do przeglądu. Rozmiar bąbla = linie. Kolor = priorytet triage (P1 czerwony, P2 bursztynowy, P3 niebieski).' :
        (lang === 'zh' ?
        '右上角象限 = 兼具高复杂度与高频修改/大体积特征的文件 — 重点重构候选对象。气泡大小 = 代码行。颜色 = 审查优先级 (P1 红色, P2 琥珀色, P3 蓝色)。' :
        'Top-right quadrant = files that are both complex and large/frequently modified — prime candidates for refactoring. Bubble size = lines. Color = triage priority (P1 red, P2 amber, P3 blue).');
    }
    const col = r => r.pr === 'P1' ? C.red : r.pr === 'P2' ? C.amber : r.pr === 'P3' ? C.cyan : C.grey;
    const data = rows.map(r => ({ value: [r[xk], r.cc, r.l, r.p, r.r, r.es, r.pr || '—'], itemStyle: { color: col(r), opacity: .8, borderColor: P.bg, borderWidth: 1 } }));
    const maxX = Math.max(1, ...rows.map(r => r[xk])) * 1.1, maxY = Math.max(25, Math.max(...rows.map(r => r.cc)) * 1.12);
    const xThr = git ? 12 : 600;
    const xName = git ? (lang === 'pl' ? 'liczba commitów (okno historii)' : (lang === 'zh' ? '提交次数 (分析窗口)' : 'commit count (history window)')) :
      (lang === 'pl' ? 'liczba linii' : (lang === 'zh' ? '代码行数' : 'line count'));
    const yName = lang === 'pl' ? 'CC maks. w pliku' : (lang === 'zh' ? '文件内 CC 最大值' : 'Max CC in file');
    const reviewZone = lang === 'pl' ? 'strefa przeglądu' : (lang === 'zh' ? '重点审查区' : 'review zone');
    put('hotChart', {
      grid: { left: 56, right: 24, top: 24, bottom: 52 },
      tooltip: tip({ formatter: p => `<b>${escapeHTML(p.value[3])}</b><br/>${git ? (lang === 'pl' ? 'Commity' : (lang === 'zh' ? '提交' : 'Commits')) : (lang === 'pl' ? 'Linie' : (lang === 'zh' ? '行数' : 'Lines'))}: ${nf(p.value[0])} · CC max: ${nf(p.value[1])}<br/>${lang === 'pl' ? 'Linie' : (lang === 'zh' ? '行数' : 'Lines')}: ${nf(p.value[2])} · ESLint: ${nf(p.value[5])} · Triage: ${nf(p.value[4], 1)} (${escapeHTML(p.value[6])})` }),
      xAxis: { type: 'value', name: xName, nameLocation: 'middle', nameGap: 32, nameTextStyle: { color: P.muted }, max: maxX, axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } } },
      yAxis: { type: 'value', name: yName, nameTextStyle: { color: P.muted }, max: maxY, axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } } },
      series: [{
        type: 'scatter', data, symbolSize: v => Math.max(7, Math.min(50, Math.sqrt(v[2]) * 1.5)),
        markArea: { silent: true, itemStyle: { color: 'rgba(239,106,123,.08)' }, label: { show: true, position: 'insideTopRight', color: P.muted, fontSize: 11, formatter: reviewZone }, data: [[{ xAxis: xThr, yAxis: 20 }, { xAxis: maxX, yAxis: maxY }]] },
        markLine: { silent: true, symbol: 'none', lineStyle: { color: P.muted, type: 'dashed', opacity: .6 }, label: { color: P.muted, fontSize: 10 }, data: [{ xAxis: xThr, label: { formatter: git ? (lang === 'pl' ? '12 commitów' : (lang === 'zh' ? '12 次提交' : '12 commits')) : (lang === 'pl' ? '600 linii' : (lang === 'zh' ? '600 行' : '600 lines')) } }, { yAxis: 20, label: { formatter: 'CC 20' } }] }
      }]
    }, p => { if (p.value) xOpenFile(p.value[3]); });
  }

  /* ───── JS/TS (lizard) ───── */
  function xJsCharts() {
    const lang = getLang();
    const L = XS.lizard || {}, P = pal();
    if (L.status !== 'ok' || !L.functions) {
      const m = L.status === 'ok' ? (lang === 'pl' ? 'Nie znaleziono funkcji JS/TS w kodzie produkcyjnym.' : (lang === 'zh' ? '生产代码中未发现 JS/TS 函数。' : 'No JS/TS functions detected in production code.')) : statusText(L);
      note('jsRanksChart', m); note('jsScatter', m); if ($('jsInfo')) $('jsInfo').textContent = ''; return;
    }
    if ($('jsInfo')) {
      $('jsInfo').textContent = lang === 'pl' ? `Funkcji: ${nf(L.functions)} · CC>15: ${nf(L.over15)} · >100 NLOC: ${nf(L.long)} · >5 parametrów: ${nf(L.many_params)} · najwyższe CC: ${nf(L.max)}` :
        (lang === 'zh' ? `函数总数: ${nf(L.functions)} · CC>15: ${nf(L.over15)} · >100行: ${nf(L.long)} · >5个参数: ${nf(L.many_params)} · 最大CC: ${nf(L.max)}` :
        `Functions: ${nf(L.functions)} · CC>15: ${nf(L.over15)} · >100 NLOC: ${nf(L.long)} · >5 params: ${nf(L.many_params)} · Max CC: ${nf(L.max)}`);
    }
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
      tooltip: tip({ formatter: p => `<b>${escapeHTML(p.value[2])}</b><br/>${escapeHTML(p.value[3])}:${p.value[4]}<br/>CC ${p.value[1]} · NLOC ${p.value[0]} · ${t('th_params','Params')} ${p.value[5]}` }),
      xAxis: { type: 'value', name: 'NLOC', nameLocation: 'middle', nameGap: 28, nameTextStyle: { color: P.muted }, axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } } },
      yAxis: { type: 'value', name: 'CC', nameTextStyle: { color: P.muted }, axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } } },
      series: [{ type: 'scatter', symbolSize: 9, data: fns.map(f => ({ value: [f.nloc, f.cc, f.name, f.file, f.line, f.params], itemStyle: { color: grades[rankOf(f.cc)], opacity: .8 } })),
                 markLine: { silent: true, symbol: 'none', lineStyle: { color: P.muted, type: 'dashed', opacity: .6 }, label: { color: P.muted, fontSize: 10 }, data: [{ yAxis: 15, label: { formatter: 'CC 15' } }] } }]
    }, p => { if (p.value) xOpenFile(p.value[3]); });
  }
  function xJsRows() {
    const lang = getLang();
    const L = XS.lizard || {};
    if (L.status !== 'ok') { if ($('jsRows')) $('jsRows').innerHTML = `<tr><td colspan="5">${statusText(L)}</td></tr>`; if ($('jsCount')) $('jsCount').textContent = ''; return; }
    const term = $('jsSearch') ? $('jsSearch').value.toLowerCase() : '', prod = $('jsScope') ? $('jsScope').value === 'prod' : true;
    const d = ((EX.lizard || {}).functions || []).filter(f => (!prod || PRODJS.has(f.category)) && `${f.name} ${f.file}`.toLowerCase().includes(term)).sort((a, b) => b.cc - a.cc);
    if ($('jsRows')) {
      $('jsRows').innerHTML = d.slice(0, 60).map(f => `<tr><td class="numeric"><span class="badge" style="background:${grades[rankOf(f.cc)]}33;color:${grades[rankOf(f.cc)]}">${f.cc}</span></td><td class="numeric">${nf(f.nloc)}</td><td class="numeric">${nf(f.params)}</td><td>${escapeHTML(f.name)}</td><td>${fileCell(f.file)}:${f.line}</td></tr>`).join('') || `<tr><td colspan="5">${lang === 'pl' ? 'Brak funkcji spełniających filtr.' : (lang === 'zh' ? '无匹配函数。' : 'No matching functions.')}</td></tr>`;
    }
    if ($('jsCount')) {
      $('jsCount').textContent = lang === 'pl' ? `Pokazano ${Math.min(60, d.length)} z ${nf(d.length)} pasujących funkcji (komplet w js_functions_*.csv).` :
        (lang === 'zh' ? `显示 ${Math.min(60, d.length)} / ${nf(d.length)} 个匹配函数 (完整明细请见 js_functions_*.csv)。` :
        `Showing ${Math.min(60, d.length)} of ${nf(d.length)} matching functions (complete data in js_functions_*.csv).`);
    }
  }

  /* ───── bezpieczeństwo ───── */
  const sevCls = s => s === 'HIGH' ? 'sevH' : s === 'MEDIUM' ? 'sevM' : 'sevL';
  function xSecCharts() {
    const lang = getLang();
    const S = XS.security || {}, P = pal();
    if (!['ok', 'partial'].includes(S.status)) { note('secDonut', statusText(S)); note('secRules', statusText(S)); if ($('secInfo')) $('secInfo').textContent = ''; return; }
    if ($('secInfo')) {
      $('secInfo').textContent = lang === 'pl' ? `Pliki ze zgłoszeniami: ${nf(S.files_affected)} · zgłoszenia w testach (pominięte): ${nf(S.tests_total)}` :
        (lang === 'zh' ? `受影响文件数: ${nf(S.files_affected)} · 测试代码告警 (已忽略): ${nf(S.tests_total)}` :
        `Affected files: ${nf(S.files_affected)} · test issues (excluded): ${nf(S.tests_total)}`);
    }
    const total = S.high + S.medium + S.low;
    if (!total) {
      note('secDonut', lang === 'pl' ? 'Bandit nie zgłosił uwag w kodzie nie-testowym.' : (lang === 'zh' ? 'Bandit 在非测试代码中未发现安全问题。' : 'Bandit reported no issues in non-test code.'));
    } else {
      put('secDonut', {
        tooltip: tip({ trigger: 'item' }), legend: { bottom: 0, textStyle: { color: P.muted } },
        series: [{ type: 'pie', radius: ['48%', '72%'], center: ['50%', '45%'], avoidLabelOverlap: true, label: { color: P.text, formatter: '{b}: {c}' }, itemStyle: { borderColor: P.bg, borderWidth: 3 },
                   data: [{ name: 'HIGH', value: S.high, itemStyle: { color: C.red } }, { name: 'MEDIUM', value: S.medium, itemStyle: { color: C.amber } }, { name: 'LOW', value: S.low, itemStyle: { color: C.cyan } }].filter(x => x.value) }]
      });
    }
    const by = {};
    ((EX.bandit || {}).issues || []).filter(i => PRODPY.has(i.category)).forEach(i => { const k = i.test_id; by[k] = by[k] || { n: 0, name: i.test_name, sev: i.severity }; by[k].n++; });
    const top = Object.entries(by).sort((a, b) => b[1].n - a[1].n).slice(0, 10).reverse();
    if (!top.length) {
      note('secRules', lang === 'pl' ? 'Brak zgłoszeń do pokazania.' : (lang === 'zh' ? '暂无展示项。' : 'No findings to display.'));
      return;
    }
    put('secRules', {
      grid: { left: 190, right: 30, top: 10, bottom: 24 }, tooltip: tip({ trigger: 'axis', axisPointer: { type: 'shadow' } }),
      xAxis: { type: 'value', axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } }, minInterval: 1 },
      yAxis: { type: 'category', data: top.map(([k, v]) => `${k} ${v.name}`), axisLabel: { color: P.text, fontSize: 11, width: 175, overflow: 'truncate' } },
      series: [{ type: 'bar', barMaxWidth: 18, data: top.map(([k, v]) => ({ value: v.n, itemStyle: { color: v.sev === 'HIGH' ? C.red : v.sev === 'MEDIUM' ? C.amber : C.cyan, borderRadius: [0, 5, 5, 0] } })), label: { show: true, position: 'right', color: P.text } }]
    });
  }
  function xSecRows() {
    const lang = getLang();
    const S = XS.security || {};
    if (!['ok', 'partial'].includes(S.status)) { if ($('secRows')) $('secRows').innerHTML = `<tr><td colspan="4">${statusText(S)}</td></tr>`; if ($('secCount')) $('secCount').textContent = ''; return; }
    const term = $('secSearch') ? $('secSearch').value.toLowerCase() : '', sev = $('secSev') ? $('secSev').value : '', prod = $('secScope') ? $('secScope').value === 'prod' : true;
    const rank = { HIGH: 0, MEDIUM: 1, LOW: 2 };
    const d = ((EX.bandit || {}).issues || []).filter(i => (!prod || PRODPY.has(i.category)) && (!sev || i.severity === sev) && `${i.file} ${i.test_id} ${i.test_name} ${i.text}`.toLowerCase().includes(term))
      .sort((a, b) => rank[a.severity] - rank[b.severity] || a.file.localeCompare(b.file) || a.line - b.line);
    if ($('secRows')) {
      $('secRows').innerHTML = d.slice(0, 80).map(i => `<tr><td><span class="badge ${sevCls(i.severity)}">${escapeHTML(i.severity)}</span></td><td class="small"><b>${escapeHTML(i.test_id)}</b><div class="muted">${escapeHTML(i.test_name)}${i.cwe ? ' · CWE-' + i.cwe : ''}</div></td><td class="small" style="white-space:normal;min-width:260px">${escapeHTML(i.text)}</td><td>${fileCell(i.file)}:${i.line}</td></tr>`).join('') || `<tr><td colspan="4">${lang === 'pl' ? 'Brak zgłoszeń spełniających filtr.' : (lang === 'zh' ? '无匹配问题。' : 'No matching issues.')}</td></tr>`;
    }
    if ($('secCount')) {
      $('secCount').textContent = lang === 'pl' ? `Pokazano ${Math.min(80, d.length)} z ${nf(d.length)}. Podejrzane hasła są zamaskowane (***).` :
        (lang === 'zh' ? `显示 ${Math.min(80, d.length)} / ${nf(d.length)} 条记录。疑似密码凭据已被掩码脱敏 (***)。` :
        `Showing ${Math.min(80, d.length)} of ${nf(d.length)}. Suspicious password literals masked with (***).`);
    }
  }
  function xAudit() {
    const lang = getLang();
    const A = EX.pip_audit || {}, X = XS.pip_audit || {};
    let msg = '';
    if (X.status === 'disabled') {
      msg = lang === 'pl' ? 'pip-audit nie był uruchomiony. Aby sprawdzić zależności (wymaga internetu): <code>.\\Run-CodeAudit.ps1 -ProjectPath "…" -PipAudit</code>.' :
        (lang === 'zh' ? 'pip-audit 未运行。如需检查依赖项安全漏洞 (需联网): <code>.\\Run-CodeAudit.ps1 -ProjectPath "…" -PipAudit</code>。' :
        'pip-audit was not executed. To verify dependency CVEs (requires internet): <code>.\\Run-CodeAudit.ps1 -ProjectPath "…" -PipAudit</code>.');
    } else if (X.status === 'unavailable') {
      msg = lang === 'pl' ? 'pip-audit nie jest zainstalowany: <code>python -m pip install pip-audit</code>.' :
        (lang === 'zh' ? '未安装 pip-audit: <code>python -m pip install pip-audit</code>。' :
        'pip-audit is not installed: <code>python -m pip install pip-audit</code>.');
    } else if (X.status === 'no_input') {
      msg = escapeHTML(X.note || (lang === 'pl' ? 'Nie znaleziono pliku requirements*.txt.' : (lang === 'zh' ? '未找到 requirements*.txt 文件。' : 'requirements*.txt file not found.')));
    } else if (X.status === 'unpinned') {
      msg = (lang === 'pl' ? 'Nie sprawdzono zależności — brak przypiętych wersji. ' : (lang === 'zh' ? '未检查依赖项 — 缺少锁定版本。 ' : 'Dependencies not checked — unpinned versions. ')) +
        escapeHTML(X.note || '') + (lang === 'pl' ? ' Wygeneruj listę z dokładnymi wersjami (<code>pip freeze</code>) i wskaż ją opcją <code>-Requirements</code>.' :
        (lang === 'zh' ? ' 请使用 <code>pip freeze</code> 导出准确版本并传入 <code>-Requirements</code>。' : ' Generate exact versions via <code>pip freeze</code> and supply with <code>-Requirements</code>.'));
    } else if (X.status === 'error') {
      msg = (lang === 'pl' ? 'pip-audit nie zwrócił wyniku' : (lang === 'zh' ? 'pip-audit 执行未返回结果' : 'pip-audit returned no results')) + (X.note ? ': ' + escapeHTML(X.note) : '') + '.';
    } else {
      msg = (lang === 'pl' ? `Sprawdzono pakiety: ${nf(X.packages)} · znane podatności: ${nf(X.vulnerabilities)} · dotknięte pakiety: ${nf(X.vulnerable_packages)}.` :
        (lang === 'zh' ? `已检查软件包: ${nf(X.packages)} · 已知漏洞: ${nf(X.vulnerabilities)} · 受影响包: ${nf(X.vulnerable_packages)}。` :
        `Checked packages: ${nf(X.packages)} · known CVEs: ${nf(X.vulnerabilities)} · affected packages: ${nf(X.vulnerable_packages)}.`)) +
        (X.note ? ' <br/><span class="muted">' + escapeHTML(X.note) + '</span>' : '');
    }
    if ($('auditInfo')) $('auditInfo').innerHTML = msg;
    const v = A.vulnerabilities || [];
    if ($('auditRows')) {
      $('auditRows').innerHTML = v.length ? v.map(x => `<tr><td><b>${escapeHTML(x.package)}</b></td><td>${escapeHTML(x.version)}</td><td class="small">${escapeHTML(x.id)}<div class="muted">${escapeHTML((x.aliases || []).join(', '))}</div></td><td class="small">${escapeHTML((x.fix_versions || []).join(', ') || '—')}</td><td class="small" style="white-space:normal;min-width:260px">${escapeHTML(x.description)}</td></tr>`).join('')
        : `<tr><td colspan="5">${X.status === 'ok' ? (lang === 'pl' ? 'Nie znaleziono znanych podatności w sprawdzonych pakietach.' : (lang === 'zh' ? '在所检查的依赖包中未发现已知安全漏洞。' : 'No known CVE vulnerabilities detected in audited packages.')) : (lang === 'pl' ? 'Brak danych.' : (lang === 'zh' ? '暂无数据。' : 'No data.'))}</td></tr>`;
    }
  }

  /* ───── martwy kod i duplikacja ───── */
  function xDeadCharts() {
    const lang = getLang();
    const D = XS.dead || {}, P = pal();
    if (D.status !== 'ok') { note('deadTypes', statusText(D)); if ($('deadInfo')) $('deadInfo').textContent = ''; return; }
    if ($('deadInfo')) {
      $('deadInfo').textContent = lang === 'pl' ? `Kandydatów: ${nf(D.count)} (pewność ≥ 80%: ${nf(D.high_confidence)}). Funkcje wywoływane dynamicznie mogą być fałszywymi alarmami.` :
        (lang === 'zh' ? `候选代码块: ${nf(D.count)} (置信度 ≥ 80%: ${nf(D.high_confidence)})。动态调用的函数可能存在误报。` :
        `Candidates: ${nf(D.count)} (confidence ≥ 80%: ${nf(D.high_confidence)}). Dynamically dispatched functions may be false positives.`);
    }
    const t = Object.entries(D.by_type || {}).sort((a, b) => b[1] - a[1]);
    if (!t.length) {
      note('deadTypes', lang === 'pl' ? 'Vulture nie zgłosił kandydatów.' : (lang === 'zh' ? 'Vulture 未报告冗余代码候选。' : 'Vulture reported no candidates.'));
      return;
    }
    put('deadTypes', {
      grid: { left: 90, right: 36, top: 10, bottom: 20 }, tooltip: tip({ trigger: 'axis', axisPointer: { type: 'shadow' } }),
      xAxis: { type: 'value', axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } }, minInterval: 1 },
      yAxis: { type: 'category', inverse: true, data: t.map(x => x[0]), axisLabel: { color: P.text } },
      series: [{ type: 'bar', barMaxWidth: 20, data: t.map(x => ({ value: x[1], itemStyle: { color: C.violet, borderRadius: [0, 5, 5, 0] } })), label: { show: true, position: 'right', color: P.text } }]
    });
  }
  function xDupCharts() {
    const lang = getLang();
    const U = XS.duplication || {}, P = pal();
    if (U.status !== 'ok') { note('dupFiles', statusText(U)); if ($('dupInfo')) $('dupInfo').textContent = ''; return; }
    if ($('dupInfo')) {
      $('dupInfo').textContent = lang === 'pl' ? `Zduplikowane znaczące linie: ok. ${nf(U.percent, 1)}% (${nf(U.lines)}). Heurystyka: okno ${U.window} linii.` :
        (lang === 'zh' ? `重复有效代码行: 约 ${nf(U.percent, 1)}% (${nf(U.lines)} 行)。启发式滑动窗口: ${U.window} 行。` :
        `Duplicated significant lines: ~${nf(U.percent, 1)}% (${nf(U.lines)} lines). Heuristic window: ${U.window} lines.`);
    }
    const rows = (DATA.matrix || []).filter(r => r.dup > 0).map(r => ({ p: r.p, n: Math.round(r.dup * r.l / 100), pct: r.dup })).sort((a, b) => b.n - a.n).slice(0, 8);
    if (!rows.length) {
      note('dupFiles', lang === 'pl' ? 'Nie wykryto powielonych bloków.' : (lang === 'zh' ? '未检测到大段重复代码块。' : 'No duplicated blocks detected.'));
      return;
    }
    put('dupFiles', {
      grid: { left: 200, right: 40, top: 10, bottom: 20 }, tooltip: tip({ formatter: p => `<b>${escapeHTML(rows[p.dataIndex].p)}</b><br/>~${rows[p.dataIndex].n} ${lang === 'pl' ? 'linii' : (lang === 'zh' ? '行' : 'lines')} (${nf(rows[p.dataIndex].pct, 1)}%)` }),
      xAxis: { type: 'value', axisLabel: { color: P.muted }, splitLine: { lineStyle: { color: P.line, opacity: .5 } } },
      yAxis: { type: 'category', inverse: true, data: rows.map(r => r.p), axisLabel: { color: P.text, fontSize: 11, width: 185, overflow: 'truncate' } },
      series: [{ type: 'bar', barMaxWidth: 18, data: rows.map(r => ({ value: r.n, itemStyle: { color: C.amber, borderRadius: [0, 5, 5, 0] } })), label: { show: true, position: 'right', color: P.text } }]
    }, p => xOpenFile(rows[p.dataIndex].p));
  }
  function xDeadRows() {
    const lang = getLang();
    const D = XS.dead || {};
    if (D.status !== 'ok') { if ($('deadRows')) $('deadRows').innerHTML = `<tr><td colspan="4">${statusText(D)}</td></tr>`; if ($('deadCount')) $('deadCount').textContent = ''; return; }
    const term = $('deadSearch') ? $('deadSearch').value.toLowerCase() : '', conf = $('deadConf') ? +$('deadConf').value : 60, prod = $('deadScope') ? $('deadScope').value === 'prod' : true;
    const d = ((EX.vulture || {}).items || []).filter(i => i.confidence >= conf && (!prod || PRODPY.has(i.category)) && `${i.name} ${i.file}`.toLowerCase().includes(term));
    if ($('deadRows')) {
      $('deadRows').innerHTML = d.slice(0, 80).map(i => `<tr><td class="numeric">${i.confidence}%</td><td>${escapeHTML(i.type)}</td><td><b>${escapeHTML(i.name)}</b></td><td>${fileCell(i.file)}:${i.line}</td></tr>`).join('') || `<tr><td colspan="4">${lang === 'pl' ? 'Brak wyników.' : (lang === 'zh' ? '暂无结果。' : 'No results.')}</td></tr>`;
    }
    if ($('deadCount')) {
      $('deadCount').textContent = lang === 'pl' ? `Pokazano ${Math.min(80, d.length)} z ${nf(d.length)}. Pełna lista w dead_code_*.csv.` :
        (lang === 'zh' ? `显示 ${Math.min(80, d.length)} / ${nf(d.length)} 条记录。完整清单见 dead_code_*.csv。` :
        `Showing ${Math.min(80, d.length)} of ${nf(d.length)}. Full dataset in dead_code_*.csv.`);
    }
  }
  function xDupRows() {
    const lang = getLang();
    const U = EX.duplication || {};
    if (U.status !== 'ok') { if ($('dupRows')) $('dupRows').innerHTML = `<tr><td colspan="3">${statusText(U)}</td></tr>`; return; }
    if ($('dupRows')) {
      $('dupRows').innerHTML = (U.blocks || []).slice(0, 40).map(b => `<tr><td class="numeric">${b.lines}</td><td>${fileCell(b.a)}:${b.a_from}–${b.a_to}</td><td>${fileCell(b.b)}:${b.b_from}–${b.b_to}</td></tr>`).join('') || `<tr><td colspan="3">${lang === 'pl' ? 'Brak zduplikowanych bloków.' : (lang === 'zh' ? '无重复代码块。' : 'No duplicated blocks.')}</td></tr>`;
    }
  }

  /* ───── graf zależności ───── */
  function xDeps() {
    const lang = getLang();
    const D = EX.deps || {}, P = pal();
    if (D.status !== 'ok') { note('depGraph', statusText(D)); if ($('depInfo')) $('depInfo').textContent = ''; return; }
    const g = D.graph || { nodes: [], edges: [] };
    if ($('depInfo')) {
      $('depInfo').textContent = lang === 'pl' ? `Moduły: ${nf(D.nodes_total)} (Python ${nf(D.python_modules)}, JS/TS ${nf(D.js_modules)}) · powiązania: ${nf(D.edges_total)} · cykle: ${nf(D.cycles_total)}.` :
        (lang === 'zh' ? `模块总数: ${nf(D.nodes_total)} (Python ${nf(D.python_modules)}, JS/TS ${nf(D.js_modules)}) · 依赖边数: ${nf(D.edges_total)} · 循环引用环: ${nf(D.cycles_total)}。` :
        `Modules: ${nf(D.nodes_total)} (Python ${nf(D.python_modules)}, JS/TS ${nf(D.js_modules)}) · dependencies: ${nf(D.edges_total)} · cycles: ${nf(D.cycles_total)}.`);
    }
    if (!g.nodes.length) {
      note('depGraph', lang === 'pl' ? 'Nie znaleziono wewnętrznych importów między modułami.' : (lang === 'zh' ? '未检测到模块间的内部调用依赖。' : 'No internal imports detected across modules.'));
      return;
    }
    const gc = {}; g.nodes.forEach(n => gc[n.group] = (gc[n.group] || 0) + 1);
    const groups = Object.entries(gc).sort((a, b) => b[1] - a[1]).map(x => x[0]);
    const pcol = [C.cyan, C.violet, C.green, C.amber, '#e07bb5', '#5fd0d8', '#9ac55a', '#f08a5d', '#7d93f0', '#c0a0e8'];
    const idx = n => Math.min(groups.indexOf(n.group), pcol.length - 1);
    const cyc = {}; (D.cycles || []).forEach((c, i) => c.forEach(m => cyc[m] = i));
    const nodes = g.nodes.map(n => { const deg = n.fan_in + n.fan_out; return { id: n.path, name: base(n.path), value: deg, category: idx(n), symbolSize: 12 + Math.sqrt(deg) * 5,
      itemStyle: { color: pcol[idx(n)], borderColor: n.cycle ? C.red : P.bg, borderWidth: n.cycle ? 3 : 1 }, label: { show: g.nodes.length <= 40 || deg >= 4 || n.cycle, color: P.text, fontSize: 10 }, path: n.path, fan_in: n.fan_in, fan_out: n.fan_out }; });
    const edges = g.edges.map(([a, b]) => ({ source: a, target: b, lineStyle: (a in cyc && b in cyc && cyc[a] === cyc[b]) ? { color: C.red, width: 2, opacity: .9 } : { color: P.muted, opacity: .35, width: 1 } }));
    put('depGraph', {
      tooltip: tip({ formatter: p => p.dataType === 'node' ? `<b>${escapeHTML(p.data.path)}</b><br/>${lang === 'pl' ? 'importowany przez' : (lang === 'zh' ? '被依赖数' : 'imported by')}: ${p.data.fan_in} · ${lang === 'pl' ? 'importuje' : (lang === 'zh' ? '对外依赖数' : 'imports')}: ${p.data.fan_out}` : `${escapeHTML(p.data.source)}<br/>→ ${escapeHTML(p.data.target)}` }),
      legend: { type: 'scroll', top: 0, textStyle: { color: P.muted }, data: groups.slice(0, 10) },
      series: [{ type: 'graph', layout: 'force', roam: true, draggable: true, top: 28, categories: groups.slice(0, 10).map(n => ({ name: n, itemStyle: { color: pcol[groups.indexOf(n)] } })),
                 data: nodes, links: edges, edgeSymbol: ['none', 'arrow'], edgeSymbolSize: 5, lineStyle: { curveness: .08 }, emphasis: { focus: 'adjacency' },
                 force: { repulsion: 150, gravity: .07, edgeLength: [35, 130], layoutAnimation: !printing && !reduceMotion } }]
    }, p => { if (p.dataType === 'node') xOpenFile(p.data.path); });
  }
  function xDepTables() {
    const lang = getLang();
    const D = EX.deps || {};
    const noData = lang === 'pl' ? 'Brak danych.' : (lang === 'zh' ? '暂无数据。' : 'No data.');
    const rows = (a, c) => (a || []).map(x => `<tr><td>${fileCell(x.path)}</td><td class="numeric">${x.value}</td></tr>`).join('') || `<tr><td colspan="2">${c}</td></tr>`;
    if ($('fanInRows')) $('fanInRows').innerHTML = rows(D.top_fan_in, noData);
    if ($('fanOutRows')) $('fanOutRows').innerHTML = rows(D.top_fan_out, noData);
    const cy = D.cycles || [];
    if ($('cycleList')) {
      $('cycleList').innerHTML = D.status !== 'ok' ? `<p class="muted small">${statusText(D)}</p>` :
        (cy.length ? cy.map(c => `<div class="cyc"><b>${c.length} ${lang === 'pl' ? 'modułów w cyklu' : (lang === 'zh' ? '个模块参与循环引用' : 'modules in cycle')}</b><br/>${c.slice(0, 8).map(fileCell).join(' ↔ ')}${c.length > 8 ? ' …' : ''}</div>`).join('') +
         `<p class="hint">${lang === 'pl' ? 'Cykle utrudniają testowanie i zmiany; to sygnał architektoniczny.' : (lang === 'zh' ? '循环引用增加模块耦合与测试难度；属于架构重构信号。' : 'Cycles complicate unit testing and modular refactoring.')}</p>` :
         `<p class="muted small">${lang === 'pl' ? 'Nie wykryto cykli importów.' : (lang === 'zh' ? '未检测到循环依赖环。' : 'No import cycles detected.')}</p>`);
    }
  }

  /* ───── aktywność Git ───── */
  function xGit() {
    const lang = getLang();
    const A = DATA.activity || {}, P = pal();
    const noHist = lang === 'pl' ? 'Brak historii Git.' : (lang === 'zh' ? '暂无 Git 历史。' : 'No Git history.');
    if (!A.daily || !A.daily.length) { note('calChart', noHist); note('hourChart', noHist); return; }
    const iso = d => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    const end = new Date(A.last + 'T12:00:00'), start = new Date(end); start.setDate(start.getDate() - 364);
    const from = iso(start), data = A.daily.filter(x => x[0] >= from);
    if ($('calInfo')) {
      $('calInfo').textContent = lang === 'pl' ? `Liczba commitów dziennie · okres ${from} – ${A.last} · dni z aktywnością w historii: ${nf(A.active_days)}.` :
        (lang === 'zh' ? `日提交活跃度 · 统计区间 ${from} – ${A.last} · 历史活跃天数: ${nf(A.active_days)} 天。` :
        `Daily commit density · window ${from} to ${A.last} · total active days: ${nf(A.active_days)}.`);
    }
    const monthNames = CAL_MONTHS[lang] || CAL_MONTHS.en;
    const dayNames = CAL_DAYS[lang] || CAL_DAYS.en;
    const wdList = WD_MAP[lang] || WD_MAP.en;
    put('calChart', {
      tooltip: tip({ formatter: p => `${escapeHTML(p.value[0])}: <b>${p.value[1]}</b> ${lang === 'pl' ? 'commit(ów)' : (lang === 'zh' ? '次提交' : 'commit(s)')}` }),
      visualMap: { type: 'piecewise', orient: 'horizontal', left: 'center', bottom: 0, itemWidth: 14, itemHeight: 14, textStyle: { color: P.muted },
                   pieces: [{ min: 1, max: 1, color: '#25757c', label: '1' }, { min: 2, max: 2, color: '#2fa0a6', label: '2' }, { min: 3, max: 4, color: '#4fd1a5', label: '3–4' }, { min: 5, color: '#c6f48f', label: '5+' }], outOfRange: { color: P.surface2 } },
      calendar: { top: 30, left: 36, right: 12, bottom: 38, cellSize: ['auto', 14], range: [from, A.last], itemStyle: { borderWidth: 3, borderColor: P.bg, color: P.surface2 }, splitLine: { show: false }, yearLabel: { show: false },
                  monthLabel: { color: P.muted, nameMap: monthNames }, dayLabel: { firstDay: 1, color: P.muted, nameMap: dayNames } },
      series: [{ type: 'heatmap', coordinateSystem: 'calendar', data }]
    });
    const grid = (A.grid || []).map(x => [x[1], x[0], x[2]]), mx = Math.max(1, ...grid.map(x => x[2]));
    put('hourChart', {
      grid: { left: 44, right: 20, top: 14, bottom: 50 }, tooltip: tip({ formatter: p => `${wdList[p.value[1]]}, ${p.value[0]}:00 — <b>${p.value[2]}</b> ${lang === 'pl' ? 'commit(ów)' : (lang === 'zh' ? '次提交' : 'commit(s)')}` }),
      xAxis: { type: 'category', data: Array.from({ length: 24 }, (_, i) => i), splitArea: { show: true }, axisLabel: { color: P.muted }, axisLine: { lineStyle: { color: P.line } } },
      yAxis: { type: 'category', data: wdList, inverse: true, axisLabel: { color: P.muted }, axisLine: { lineStyle: { color: P.line } } },
      visualMap: { min: 0, max: mx, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, itemHeight: 120, textStyle: { color: P.muted }, inRange: { color: [P.surface2, '#2fa0a6', '#c6f48f'] } },
      series: [{ type: 'heatmap', data: grid, itemStyle: { borderColor: P.bg, borderWidth: 2, borderRadius: 3 } }]
    });
  }

  /* ───── modal pliku ───── */
  function tbl(head, rows) {
    const lang = getLang();
    const emptyMsg = lang === 'pl' ? 'Brak pozycji.' : (lang === 'zh' ? '无记录。' : 'No entries.');
    return rows.length ? `<div class="tblWrap" style="max-height:260px"><table><thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>` : `<p class="muted small">${emptyMsg}</p>`;
  }
  function xOpenFile(path) {
    const lang = getLang();
    const k = kp(path), m = (DATA.matrix || []).find(r => kp(r.p) === k) || { p: path };
    if ($('fmTitle')) $('fmTitle').textContent = path;
    const st = (l, v) => `<div class="fmStat"><b>${v}</b><span>${escapeHTML(l)}</span></div>`;
    const catLabel = (DATA.cat_i18n && DATA.cat_i18n[lang] && DATA.cat_i18n[lang][m.c]) || m.c || '—';
    const statL = {
      en: ['Lines', 'Category', 'Max CC', 'MI', 'ESLint', 'Bandit (weight)', 'Dead code', 'Duplication', 'Commits', 'Triage index'],
      pl: ['Linie', 'Kategoria', 'CC maks.', 'MI', 'ESLint', 'Bandit (waga)', 'Martwy kod', 'Duplikacja', 'Commity', 'Indeks triage'],
      zh: ['代码行', '分类', 'CC 最大值', 'MI', 'ESLint', 'Bandit (权重)', '冗余代码', '重复率', '提交数', '审查风险指数']
    }[lang] || ['Lines', 'Category', 'Max CC', 'MI', 'ESLint', 'Bandit (weight)', 'Dead code', 'Duplication', 'Commits', 'Triage index'];
    let h = '<div class="fmStats">' + [
      st(statL[0], nf(m.l)), st(statL[1], escapeHTML(catLabel)), st(statL[2], nf(m.cc)), st(statL[3], nf(m.mi, 1)), st(statL[4], nf(m.es || 0)),
      st(statL[5], nf(m.sec || 0, 1)), st(statL[6], nf(m.dead || 0)), st(statL[7], nf(m.dup || 0, 1) + '%'), st(statL[8], nf(m.n || 0)), st(statL[9], nf(m.r || 0, 1))
    ].join('') + '</div>';

    const py = (DATA.functions || []).filter(f => kp(f.file) === k).sort((a, b) => b.cc - a.cc).slice(0, 12);
    if (py.length) {
      const hTitle = lang === 'pl' ? 'Funkcje Python wg CC' : (lang === 'zh' ? 'Python 函数 (按 CC 排序)' : 'Python Functions by CC');
      const hHeads = lang === 'pl' ? ['CC', 'Klasa', 'Funkcja', 'Linia'] : (lang === 'zh' ? ['CC', '评级', '函数名', '行号'] : ['CC', 'Rank', 'Function', 'Line']);
      h += `<h4>${hTitle}</h4>` + tbl(hHeads, py.map(f => `<tr><td class="numeric">${f.cc}</td><td>${escapeHTML(f.rank)}</td><td>${escapeHTML(f.name)}</td><td>${f.line}</td></tr>`));
    }
    const js = ((EX.lizard || {}).functions || []).filter(f => kp(f.file) === k).sort((a, b) => b.cc - a.cc).slice(0, 12);
    if (js.length) {
      const hTitle = lang === 'pl' ? 'Funkcje JS/TS wg CC (lizard)' : (lang === 'zh' ? 'JS/TS 函数 (按 CC 排序, lizard)' : 'JS/TS Functions by CC (lizard)');
      const hHeads = lang === 'pl' ? ['CC', 'NLOC', 'Param.', 'Funkcja', 'Linia'] : (lang === 'zh' ? ['CC', 'NLOC', '参数', '函数名', '行号'] : ['CC', 'NLOC', 'Params', 'Function', 'Line']);
      h += `<h4>${hTitle}</h4>` + tbl(hHeads, js.map(f => `<tr><td class="numeric">${f.cc}</td><td class="numeric">${f.nloc}</td><td class="numeric">${f.params}</td><td>${escapeHTML(f.name)}</td><td>${f.line}</td></tr>`));
    }
    const es = (DATA.issues || []).filter(i => kp(i.file) === k);
    if (es.length) {
      const hHeads = lang === 'pl' ? ['Linia', 'Reguła', 'Komunikat'] : (lang === 'zh' ? ['行号', '检查规则', '告警说明'] : ['Line', 'Rule', 'Message']);
      h += `<h4>ESLint (${es.length})</h4>` + tbl(hHeads, es.slice(0, 15).map(i => `<tr><td>${i.line || '?'}</td><td><b>${escapeHTML(i.rule)}</b></td><td class="small" style="white-space:normal">${escapeHTML(i.message).slice(0, 240)}</td></tr>`));
    }
    const bn = ((EX.bandit || {}).issues || []).filter(i => kp(i.file) === k);
    if (bn.length) {
      const hHeads = lang === 'pl' ? ['Waga', 'Test', 'Opis', 'Linia'] : (lang === 'zh' ? ['严重度', '测试项', '漏洞说明', '行号'] : ['Severity', 'Test', 'Description', 'Line']);
      h += `<h4>Bandit (${bn.length})</h4>` + tbl(hHeads, bn.slice(0, 15).map(i => `<tr><td><span class="badge ${sevCls(i.severity)}">${i.severity}</span></td><td>${escapeHTML(i.test_id)}</td><td class="small" style="white-space:normal">${escapeHTML(i.text)}</td><td>${i.line}</td></tr>`));
    }
    const vt = ((EX.vulture || {}).items || []).filter(i => kp(i.file) === k);
    if (vt.length) {
      const hTitle = lang === 'pl' ? `Kandydaci na martwy kod (${vt.length})` : (lang === 'zh' ? `冗余代码候选 (${vt.length})` : `Dead Code Candidates (${vt.length})`);
      const hHeads = lang === 'pl' ? ['Pewność', 'Typ', 'Nazwa', 'Linia'] : (lang === 'zh' ? ['置信度', '类型', '名称', '行号'] : ['Confidence', 'Type', 'Name', 'Line']);
      h += `<h4>${hTitle}</h4>` + tbl(hHeads, vt.slice(0, 15).map(i => `<tr><td class="numeric">${i.confidence}%</td><td>${escapeHTML(i.type)}</td><td>${escapeHTML(i.name)}</td><td>${i.line}</td></tr>`));
    }
    const du = ((EX.duplication || {}).blocks || []).filter(b => kp(b.a) === k || kp(b.b) === k);
    if (du.length) {
      const hTitle = lang === 'pl' ? 'Zduplikowane bloki' : (lang === 'zh' ? '重复代码块' : 'Duplicated Blocks');
      const hHeads = lang === 'pl' ? ['Linie', 'Fragment A', 'Fragment B'] : (lang === 'zh' ? ['行数', '代码片段 A', '代码片段 B'] : ['Lines', 'Fragment A', 'Fragment B']);
      h += `<h4>${hTitle}</h4>` + tbl(hHeads, du.slice(0, 10).map(b => `<tr><td class="numeric">${b.lines}</td><td>${escapeHTML(b.a)}:${b.a_from}–${b.a_to}</td><td>${escapeHTML(b.b)}:${b.b_from}–${b.b_to}</td></tr>`));
    }
    const dp = EX.deps || {};
    if (dp.files && dp.edges) {
      const i = dp.files.findIndex(f => kp(f) === k);
      if (i >= 0) {
        const out = dp.edges.filter(e => e[0] === i).map(e => dp.files[e[1]]), inn = dp.edges.filter(e => e[1] === i).map(e => dp.files[e[0]]);
        const dTitle = lang === 'pl' ? 'Zależności' : (lang === 'zh' ? '模块依赖拓扑' : 'Dependencies');
        const impOut = lang === 'pl' ? 'Importuje' : (lang === 'zh' ? '对外依赖' : 'Imports');
        const impIn = lang === 'pl' ? 'Importowany przez' : (lang === 'zh' ? '被依赖' : 'Imported by');
        h += `<h4>${dTitle}</h4><div class="small"><b>${impOut} (${out.length}):</b> ${out.slice(0, 14).map(fileCell).join(', ') || '—'}<br/><b>${impIn} (${inn.length}):</b> ${inn.slice(0, 14).map(fileCell).join(', ') || '—'}</div>`;
      }
    }
    if ($('fmBody')) $('fmBody').innerHTML = h;
    if ($('fileModal')) { $('fileModal').classList.add('open'); if ($('fmClose')) $('fmClose').focus(); }
  }
  function xClose() { if ($('fileModal')) $('fileModal').classList.remove('open'); }

  /* ───── start & re-render ───── */
  function renderCharts() { [xRadar, xTrend, xTree, xHot, xJsCharts, xSecCharts, xDeadCharts, xDupCharts, xDeps, xGit].forEach(safe); }
  function renderTables() { [xJsRows, xSecRows, xAudit, xDeadRows, xDupRows, xDepTables].forEach(safe); }

  window.renderExtraCharts = function (lang) {
    safe(xExec); safe(xKpi); renderTables(); renderCharts();
  };

  safe(xExec); safe(xKpi);
  const mt = DATA.meta || {};
  if ($('toolVersions')) {
    $('toolVersions').textContent = 'Radon ' + (mt.radon_version || '—') + ' · ESLint ' + (mt.eslint_version || '—') + ' · lizard ' + (mt.lizard_version || '—') + ' · vulture ' + (mt.vulture_version || '—') + ' · bandit ' + (mt.bandit_version || '—') + ' · pip-audit ' + (mt.pip_audit_version || '—') + ' · ECharts ' + (ECH ? ECH.version : 'n/a');
  }
  renderTables(); renderCharts();

  if ($('radarMode')) $('radarMode').addEventListener('change', () => safe(xRadar));
  if ($('trendMetric')) $('trendMetric').addEventListener('change', () => safe(xTrend));
  if ($('treeMetric')) $('treeMetric').addEventListener('change', () => safe(xTree));
  ['jsSearch', 'jsScope'].forEach(id => { if ($(id)) $(id).addEventListener('input', () => safe(xJsRows)); });
  ['secSearch', 'secSev', 'secScope'].forEach(id => { if ($(id)) $(id).addEventListener('input', () => safe(xSecRows)); });
  ['deadSearch', 'deadConf', 'deadScope'].forEach(id => { if ($(id)) $(id).addEventListener('input', () => safe(xDeadRows)); });
  if ($('fmClose')) $('fmClose').addEventListener('click', xClose);
  if ($('fileModal')) $('fileModal').addEventListener('click', e => { if (e.target === $('fileModal')) xClose(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') xClose(); });
  document.addEventListener('click', e => {
    const f = e.target.closest('[data-file]'); if (f) { xOpenFile(f.dataset.file); return; }
    const r = e.target.closest('#riskRows code'); if (r) xOpenFile(r.textContent);
  });
  if ($('theme')) $('theme').addEventListener('click', () => setTimeout(renderCharts, 40));
  if ($('printBtn')) $('printBtn').addEventListener('click', () => window.print());
  let rz = null;
  window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => Object.values(charts).forEach(c => c.resize()), 120); });
  window.addEventListener('beforeprint', () => {
    printing = true;
    document.querySelectorAll('.chart').forEach(el => { if (el.id === 'treeChart' || el.id === 'hotChart' || el.id === 'depGraph') el.style.height = '440px'; });
    Object.values(charts).forEach(c => c.resize({ width: Math.min(760, document.querySelector('.shell').clientWidth) }));
    renderCharts();
  });
  window.addEventListener('afterprint', () => {
    printing = false;
    document.querySelectorAll('.chart').forEach(el => el.style.height = '');
    Object.values(charts).forEach(c => c.resize({ width: 'auto' }));
    renderCharts();
  });
})();
