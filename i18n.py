"""CodeAudit — Internationalization (i18n) Engine.

Supports generating Markdown reports, CSV datasets, and interactive dashboard UI
in multiple languages (English, Polish, Simplified Chinese). Designed to easily
extend with additional languages by registering new translation tables.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from collections import Counter, defaultdict

LANGUAGES = ["en", "pl", "zh"]
DEFAULT_LANG = "en"

LANG_META = {
    "en": {"name": "English", "native": "English", "flag": "EN"},
    "pl": {"name": "Polish", "native": "Polski", "flag": "PL"},
    "zh": {"name": "Chinese", "native": "中文", "flag": "ZH"},
}

# ─────────────────────────────────────────────────────────────────────────────
# CSV Headers Definitions & Value Transformers
# ─────────────────────────────────────────────────────────────────────────────

CSV_COLUMNS = {
    "issues": {
        "en": ["file", "line", "column", "end_line", "end_column", "severity", "rule", "message", "fatal"],
        "pl": ["plik", "linia", "kolumna", "linia_koncowa", "kolumna_koncowa", "waznosc", "regula", "komunikat", "krytyczny"],
        "zh": ["文件", "行", "列", "结束行", "结束列", "严重级别", "规则", "消息", "致命错误"],
    },
    "functions": {
        "en": ["file", "category", "name", "kind", "line", "end_line", "cc", "rank"],
        "pl": ["plik", "kategoria", "nazwa", "rodzaj", "linia", "linia_koncowa", "cc", "klasa"],
        "zh": ["文件", "类别", "名称", "类型", "行", "结束行", "圈复杂度_cc", "等级"],
    },
    "files": {
        "en": ["path", "category", "folder", "bytes", "physical_lines", "nonempty_lines", "py_sloc", "py_lloc", "py_cc_max", "py_mi", "halstead_volume", "halstead_difficulty"],
        "pl": ["sciezka", "kategoria", "katalog", "bajty", "linie_fizyczne", "linie_niepuste", "py_sloc", "py_lloc", "py_cc_maks", "py_mi", "halstead_objetosc", "halstead_trudnosc"],
        "zh": ["路径", "类别", "目录", "字节数", "物理行数", "非空行数", "py_sloc", "py_lloc", "py_cc最大值", "py_mi", "halstead体积", "halstead难度"],
    },
    "js_functions": {
        "en": ["file", "category", "name", "line", "end_line", "cc", "nloc", "params", "tokens"],
        "pl": ["plik", "kategoria", "nazwa", "linia", "linia_koncowa", "cc", "nloc", "parametry", "tokeny"],
        "zh": ["文件", "类别", "名称", "行", "结束行", "圈复杂度_cc", "代码行_nloc", "参数个数", "标记数_tokens"],
    },
    "security_bandit": {
        "en": ["file", "category", "line", "severity", "confidence", "test_id", "test_name", "cwe", "text"],
        "pl": ["plik", "kategoria", "linia", "waga", "pewnosc", "identyfikator_testu", "nazwa_testu", "cwe", "opis"],
        "zh": ["文件", "类别", "行", "严重程度", "置信度", "测试编号", "测试名称", "cwe编号", "说明"],
    },
    "security_dependencies": {
        "en": ["requirements", "package", "version", "id", "aliases", "fix_versions", "description"],
        "pl": ["plik_zaleznosci", "pakiet", "wersja", "identyfikator", "aliasy", "wersje_naprawcze", "opis"],
        "zh": ["依赖文件", "软件包", "当前版本", "漏洞编号", "别名", "修复版本", "漏洞描述"],
    },
    "dead_code": {
        "en": ["file", "category", "line", "type", "name", "confidence"],
        "pl": ["plik", "kategoria", "linia", "typ", "nazwa", "pewnosc"],
        "zh": ["文件", "类别", "行", "类型", "名称", "置信度"],
    },
    "duplication": {
        "en": ["file_a", "a_from", "a_to", "file_b", "b_from", "b_to", "lines"],
        "pl": ["plik_a", "a_od", "a_do", "plik_b", "b_od", "b_do", "linie"],
        "zh": ["文件a", "a起始行", "a结束行", "文件b", "b起始行", "b结束行", "重复行数"],
    },
    "dependencies": {
        "en": ["from", "to"],
        "pl": ["modul_zrodlowy", "modul_docelowy"],
        "zh": ["调用模块", "被调用模块"],
    },
    "sensitive_files": {
        "en": ["file", "priority", "risk_index", "domains", "reasons", "cc_max", "mi", "lines", "eslint_total", "eslint_priority", "is_sensitive"],
        "pl": ["plik", "priorytet", "indeks_ryzyka", "domeny", "powody", "cc_maks", "mi", "linie", "eslint_wszystkie", "eslint_priorytetowe", "czy_wrazliwy"],
        "zh": ["文件", "优先级", "风险指数", "业务领域", "审查原因", "cc最大值", "mi", "行数", "eslint问题总数", "eslint优先问题", "是否敏感"],
    },
    "git_commits": {
        "en": ["sha", "date", "author", "subject", "files", "source_files", "additions", "deletions"],
        "pl": ["sha", "data", "autor", "temat", "pliki", "pliki_zrodlowe", "dodane_linie", "usuniete_linie"],
        "zh": ["提交哈希_sha", "日期", "作者", "提交说明", "变更文件数", "源码文件数", "新增行数", "删除行数"],
    },
    "git_monthly": {
        "en": ["month", "commits", "source_commits", "additions", "deletions"],
        "pl": ["miesiac", "commity", "commity_kodu", "dodane_linie", "usuniete_linie"],
        "zh": ["月份", "提交总数", "源码提交数", "新增行数", "删除行数"],
    },
    "git_weekly": {
        "en": ["week", "commits", "source_commits", "additions", "deletions"],
        "pl": ["tydzien", "commity", "commity_kodu", "dodane_linie", "usuniete_linie"],
        "zh": ["周次", "提交总数", "源码提交数", "新增行数", "删除行数"],
    },
    "git_hotspots": {
        "en": ["file", "commits", "additions", "deletions", "churn"],
        "pl": ["plik", "commity", "dodane_linie", "usuniete_linie", "churn_lacznie"],
        "zh": ["文件", "提交次数", "新增行数", "删除行数", "代码变动总量_churn"],
    },
}

VALUE_TRANSFORMERS = {
    "pl": {
        "severity": {"error": "błąd", "warning": "ostrzeżenie", "HIGH": "WYSOKA", "MEDIUM": "ŚREDNIA", "LOW": "NISKA"},
        "kind": {"function": "funkcja", "method": "metoda"},
        "fatal": {True: "tak", False: "nie"},
        "is_sensitive": {True: "tak", False: "nie", 1: "tak", 0: "nie"},
    },
    "zh": {
        "severity": {"error": "错误", "warning": "警告", "HIGH": "高危", "MEDIUM": "中危", "LOW": "低危"},
        "kind": {"function": "函数", "method": "方法"},
        "fatal": {True: "是", False: "否"},
        "is_sensitive": {True: "是", False: "否", 1: "是", 0: "否"},
    },
}

CATEGORY_NAMES = {
    "en": {
        "py_prod": "Python — Production", "py_tests": "Python — Tests",
        "py_other": "Python — Tools/Other", "js_prod": "JS/JSX — Frontend",
        "js_tests": "JS/JSX — Tests", "js_other": "JS/JSX — Other",
        "ts_prod": "TypeScript — Production", "ts_tests": "TypeScript — Tests",
        "styles": "CSS / SCSS", "html": "HTML", "scripts": "Shell / Batch / PowerShell",
        "other_code": "Other Code / SQL", "docs": "Documentation",
        "config": "Configuration", "assets": "Assets / Graphics",
        "databases": "Databases", "other": "Other Files",
    },
    "pl": {
        "py_prod": "Python — produkcja", "py_tests": "Python — testy",
        "py_other": "Python — narzędzia", "js_prod": "JS/JSX — frontend",
        "js_tests": "JS/JSX — testy", "js_other": "JS/JSX — pozostałe",
        "ts_prod": "TypeScript — produkcja", "ts_tests": "TypeScript — testy",
        "styles": "CSS / SCSS", "html": "HTML", "scripts": "Skrypty systemowe",
        "other_code": "Inny kod / SQL", "docs": "Dokumentacja",
        "config": "Konfiguracja", "assets": "Zasoby / grafika",
        "databases": "Bazy danych", "other": "Pozostałe",
    },
    "zh": {
        "py_prod": "Python — 生产代码", "py_tests": "Python — 测试代码",
        "py_other": "Python — 工具/其他", "js_prod": "JS/JSX — 前端代码",
        "js_tests": "JS/JSX — 测试代码", "js_other": "JS/JSX — 其他",
        "ts_prod": "TypeScript — 生产代码", "ts_tests": "TypeScript — 测试代码",
        "styles": "CSS / SCSS 样式", "html": "HTML 页面", "scripts": "Shell / 批处理 / PowerShell",
        "other_code": "其他代码 / SQL", "docs": "文档 Markdown / RST",
        "config": "配置文件 JSON / YAML / TOML", "assets": "资源文件 / 图像",
        "databases": "数据库 SQLite / DB", "other": "其他文件",
    },
}

DOMAIN_TRANSLATIONS = {
    "en": {
        "FINANSE / LEDGER": "Finance / Ledger",
        "TOŻSAMOŚĆ / BEZPIECZEŃSTWO": "Identity / Security",
        "PRZESYŁKI / TRASY": "Shipments / Routing",
        "HUB / TRANSAKCJE": "Hub / Transactions",
    },
    "pl": {
        "FINANSE / LEDGER": "Finanse / Ledger",
        "TOŻSAMOŚĆ / BEZPIECZEŃSTWO": "Tożsamość / Bezpieczeństwo",
        "PRZESYŁKI / TRASY": "Przesyłki / Trasy",
        "HUB / TRANSAKCJE": "Hub / Transakcje",
    },
    "zh": {
        "FINANSE / LEDGER": "财务 / 账本",
        "TOŻSAMOŚĆ / BEZPIECZEŃSTWO": "身份 / 安全认证",
        "PRZESYŁKI / TRASY": "物流 / 路由调度",
        "HUB / TRANSAKCJE": "集散枢纽 / 交易处理",
    },
}

REASON_TRANSLATIONS = {
    "en": {
        "wysokie CC": "high CC",
        "niski MI": "low MI",
        "alerty ESLint": "ESLint alerts",
        "wysoki churn": "high churn",
        "duży plik": "large file",
        "złożoność": "complexity",
    },
    "pl": {
        "wysokie CC": "wysokie CC",
        "niski MI": "niski MI",
        "alerty ESLint": "alerty ESLint",
        "wysoki churn": "wysoki churn",
        "duży plik": "duży plik",
        "złożoność": "złożoność",
    },
    "zh": {
        "wysokie CC": "高圈复杂度",
        "niski MI": "低可维护性",
        "alerty ESLint": "ESLint告警",
        "wysoki churn": "高变动率",
        "duży plik": "大文件",
        "złożoność": "复杂度",
    },
}


def translate_domains(domains: list[str], lang: str) -> list[str]:
    mapping = DOMAIN_TRANSLATIONS.get(lang, {})
    return [mapping.get(d, d) for d in domains]


def translate_reasons(reasons: list[str], lang: str) -> list[str]:
    mapping = REASON_TRANSLATIONS.get(lang, {})
    return [mapping.get(r, r) for r in reasons]


def write_multilang_csv(out_dir: Path, base_name: str, raw_fields: list[str], rows: list[dict]):
    """Writes <base_name>.csv (standard English) and localized <base_name>_{lang}.csv files."""
    spec = CSV_COLUMNS.get(base_name, {})
    for lang in LANGUAGES:
        target_fields = spec.get(lang, raw_fields)
        out_file = out_dir / (f"{base_name}.csv" if lang == DEFAULT_LANG else f"{base_name}_{lang}.csv")
        # Also always write base_name_en.csv explicitly so all 3 languages have named versions
        alt_file = out_dir / f"{base_name}_{lang}.csv" if lang == DEFAULT_LANG else None

        xform = VALUE_TRANSFORMERS.get(lang, {})
        with out_file.open("w", encoding="utf-8-sig", newline="") as h:
            writer = csv.writer(h)
            writer.writerow(target_fields)
            for row in rows:
                row_vals = []
                for k in raw_fields:
                    val = row.get(k, "")
                    if k in xform and val in xform[k]:
                        val = xform[k][val]
                    elif k in {"domains", "reasons"} and isinstance(val, str):
                        # Translate semicolons separated domain/reason lists
                        parts = [p.strip() for p in val.split(";") if p.strip()]
                        if k == "domains":
                            parts = translate_domains(parts, lang)
                        else:
                            parts = translate_reasons(parts, lang)
                        val = "; ".join(parts)
                    row_vals.append(val)
                writer.writerow(row_vals)

        if alt_file and alt_file != out_file:
            alt_file.write_bytes(out_file.read_bytes())


# ─────────────────────────────────────────────────────────────────────────────
# Executive Summary Builder in 3 Languages
# ─────────────────────────────────────────────────────────────────────────────

def build_multilang_executive_summary(data: dict, scope: dict, quality: dict, risks: list, previous: dict, xs: dict) -> dict:
    """Builds headline, facts, and suggested actions in EN, PL, and ZH."""
    results = {}
    score, grade = quality.get("score"), quality.get("grade")
    pq = (previous or {}).get("quality") if previous else None
    delta = round(score - pq["score"], 1) if (pq and pq.get("score") is not None and score is not None) else None

    cr = scope.get("cc_ranks", {})
    hard = cr.get("D", 0) + cr.get("E", 0) + cr.get("F", 0)
    lz = xs.get("lizard", {})
    sc = xs.get("security", {})
    pa = xs.get("pip_audit", {})
    dd = xs.get("dead", {})
    du = xs.get("duplication", {})
    dp = xs.get("deps", {})
    top_risks = [r for r in risks if r.get("priority") in {"P1", "P2"}][:3] or risks[:3]

    def fmt_num(v):
        return f"{v:,}".replace(",", "\u00a0")

    # 1. English
    en_head = f"Maintainability Index: {score}/100 (Grade {grade})." if score is not None else "Maintainability index unavailable."
    if delta is not None:
        en_head += f" Delta from previous audit: {'+' if delta > 0 else ''}{delta} pts."
    en_facts = [
        {"level": "info", "text": f"Scope — Physical code lines: {fmt_num(scope['physical_lines'])}; Code files: {fmt_num(scope['code_files'])}; Python prod files: {fmt_num(scope['python_prod'])}; Python functions: {fmt_num(scope['cc_count'])}."}
    ]
    if scope.get("cc_count"):
        en_facts.append({"level": "warn" if hard else "ok", "text": f"Python — Functions with CC > 20 (Rank D–F): {hard}; Ratio of Rank A/B: {scope['cc_AB_percent']:.0f}%."})
    if lz.get("status") == "ok" and lz.get("functions"):
        en_facts.append({"level": "warn" if lz.get("over15") else "ok", "text": f"Frontend (Lizard) — JS/TS functions with CC > 15: {lz.get('over15')} of {lz.get('functions')}; Maximum CC: {lz.get('max')}."})
    if sc.get("status") in {"ok", "partial"}:
        lvl = "warn" if sc.get("high") else ("info" if sc.get("medium") else "ok")
        en_facts.append({"level": lvl, "text": f"Bandit (excluding tests) — HIGH: {sc.get('high')}, MEDIUM: {sc.get('medium')}, LOW: {sc.get('low')}. Triage signals requiring review."})
    pa_skipped = pa.get("skipped")
    en_skip_str = f"; unpinned skipped: {pa_skipped}" if pa_skipped else ""
    pl_skip_str = f"; pominięto bez przypiętej wersji: {pa_skipped}" if pa_skipped else ""
    zh_skip_str = f"; 未指定版本跳过: {pa_skipped}" if pa_skipped else ""

    if pa.get("status") == "ok":
        en_facts.append({"level": "warn" if pa.get("vulnerabilities") else "ok", "text": f"Pip-Audit — Known CVEs: {pa.get('vulnerabilities')} (affected packages: {pa.get('vulnerable_packages')} of {pa.get('packages')} checked{en_skip_str})."})
    elif pa.get("status") == "disabled":
        en_facts.append({"level": "info", "text": "Dependency CVE scan disabled (requires internet via --pip-audit)."})
    if dd.get("status") == "ok":
        en_facts.append({"level": "info", "text": f"Vulture — Dead code candidates: {dd.get('count')} (confidence ≥ 80%: {dd.get('high_confidence')}). Manual review required."})
    if du.get("status") == "ok" and du.get("percent") is not None:
        en_facts.append({"level": "warn" if du.get("percent", 0) >= 10 else "ok", "text": f"Code duplication (heuristic) — ~{du.get('percent')}% of significant production code lines."})
    if dp.get("status") == "ok":
        en_facts.append({"level": "warn" if dp.get("cycles") else "ok", "text": f"Dependencies — Modules: {dp.get('modules')}, Edges: {dp.get('edges')}, Import cycles: {dp.get('cycles')}."})

    en_actions = []
    if sc.get("high"):
        en_actions.append(f"Investigate high-severity Bandit security findings (count: {sc.get('high')}) in the Security section.")
    if pa.get("vulnerabilities"):
        en_actions.append("Upgrade packages flagged by Pip-Audit with known CVE vulnerabilities.")
    if du.get("percent", 0) >= 10:
        en_actions.append("Review largest duplicate code blocks for common modular abstraction.")
    if dp.get("cycles"):
        en_actions.append("Refactor circular import dependencies that degrade testability and clean architecture.")
    if scope.get("eslint_errors"):
        en_actions.append(f"Fix ESLint errors ({scope['eslint_errors']} issues) in the frontend codebase.")
    if top_risks:
        en_actions.insert(0, f"Prioritize manual review on: {', '.join(r['file'] for r in top_risks)} (highest triage index).")
    if not en_actions:
        en_actions.append("No critical issues detected — maintain regular audits and monitor historical trends.")
    results["en"] = {"headline": en_head, "facts": en_facts, "actions": en_actions[:5]}

    # 2. Polish
    pl_head = f"Indeks utrzymywalności: {score}/100 (klasa {grade})." if score is not None else "Indeks utrzymywalności niedostępny (brak danych)."
    if delta is not None:
        pl_head += f" Zmiana względem poprzedniego audytu: {'+' if delta > 0 else ''}{delta} pkt."
    pl_facts = [
        {"level": "info", "text": f"Zakres — linie kodu: {fmt_num(scope['physical_lines'])}; pliki kodu: {fmt_num(scope['code_files'])}; pliki Python produkcja: {fmt_num(scope['python_prod'])}; funkcje Python: {fmt_num(scope['cc_count'])}."}
    ]
    if scope.get("cc_count"):
        pl_facts.append({"level": "warn" if hard else "ok", "text": f"Python — funkcje o CC > 20 (klasy D–F): {hard}; udział klas A/B: {scope['cc_AB_percent']:.0f}%."})
    if lz.get("status") == "ok" and lz.get("functions"):
        pl_facts.append({"level": "warn" if lz.get("over15") else "ok", "text": f"Frontend (lizard) — funkcje JS/TS o CC > 15: {lz.get('over15')} z {lz.get('functions')}; najwyższe CC: {lz.get('max')}."})
    if sc.get("status") in {"ok", "partial"}:
        lvl = "warn" if sc.get("high") else ("info" if sc.get("medium") else "ok")
        pl_facts.append({"level": lvl, "text": f"Bandit (bez testów) — HIGH: {sc.get('high')}, MEDIUM: {sc.get('medium')}, LOW: {sc.get('low')}. Sygnały do weryfikacji ręcznej."})
    if pa.get("status") == "ok":
        pl_facts.append({"level": "warn" if pa.get("vulnerabilities") else "ok", "text": f"pip-audit — znane podatności: {pa.get('vulnerabilities')} (pakiety dotknięte: {pa.get('vulnerable_packages')} z {pa.get('packages')} sprawdzonych{pl_skip_str})."})
    elif pa.get("status") == "disabled":
        pl_facts.append({"level": "info", "text": "Zależności nie były sprawdzane pod kątem podatności (pip-audit wyłączony — wymaga internetu)."})
    if dd.get("status") == "ok":
        pl_facts.append({"level": "info", "text": f"Vulture — kandydaci na martwy kod: {dd.get('count')} (pewność ≥ 80%: {dd.get('high_confidence')}). Wymagają weryfikacji."})
    if du.get("status") == "ok" and du.get("percent") is not None:
        pl_facts.append({"level": "warn" if du.get("percent", 0) >= 10 else "ok", "text": f"Duplikacja (heurystyka) — około {du.get('percent')}% znaczących linii kodu produkcyjnego."})
    if dp.get("status") == "ok":
        pl_facts.append({"level": "warn" if dp.get("cycles") else "ok", "text": f"Zależności — moduły: {dp.get('modules')}, powiązania: {dp.get('edges')}, cykle importów: {dp.get('cycles')}."})

    pl_actions = []
    if sc.get("high"):
        pl_actions.append(f"Zweryfikuj znaleziska bandit o wysokiej wadze (liczba: {sc.get('high')}) w sekcji „Bezpieczeństwo”.")
    if pa.get("vulnerabilities"):
        pl_actions.append("Rozważ aktualizację pakietów wskazanych przez pip-audit ze znanymi lukami CVE.")
    if du.get("percent", 0) >= 10:
        pl_actions.append("Przejrzyj największe zduplikowane bloki pod kątem wspólnej abstrakcji modułowej.")
    if dp.get("cycles"):
        pl_actions.append("Uporządkuj cykliczne importy modułów utrudniające testowanie i architekturę.")
    if scope.get("eslint_errors"):
        pl_actions.append(f"Napraw błędy ESLint (liczba: {scope['eslint_errors']}) w warstwie frontendu.")
    if top_risks:
        pl_actions.insert(0, f"Zacznij przegląd od: {', '.join(r['file'] for r in top_risks)} (najwyższy indeks triage).")
    if not pl_actions:
        pl_actions.append("Brak pilnych sygnałów ostrzegawczych — utrzymuj regularne audyty i obserwuj trend.")
    results["pl"] = {"headline": pl_head, "facts": pl_facts, "actions": pl_actions[:5]}

    # 3. Chinese
    zh_head = f"代码可维护性综合评分: {score}/100 (评级: {grade}级)。" if score is not None else "可维护性指数暂不可用（数据不足）。"
    if delta is not None:
        zh_head += f" 较上次审计变动: {'+' if delta > 0 else ''}{delta} 分。"
    zh_facts = [
        {"level": "info", "text": f"审计范围 — 代码物理行数: {fmt_num(scope['physical_lines'])}; 代码文件数: {fmt_num(scope['code_files'])}; Python生产文件: {fmt_num(scope['python_prod'])}; Python函数数: {fmt_num(scope['cc_count'])}。"}
    ]
    if scope.get("cc_count"):
        zh_facts.append({"level": "warn" if hard else "ok", "text": f"Python — CC > 20 的高复杂度函数 (D–F级): {hard} 个; A/B级优质函数占比: {scope['cc_AB_percent']:.0f}%。"})
    if lz.get("status") == "ok" and lz.get("functions"):
        zh_facts.append({"level": "warn" if lz.get("over15") else "ok", "text": f"前端 (Lizard) — JS/TS 函数 CC > 15 数量: {lz.get('over15')} / {lz.get('functions')}; 最高圈复杂度: {lz.get('max')}。"})
    if sc.get("status") in {"ok", "partial"}:
        lvl = "warn" if sc.get("high") else ("info" if sc.get("medium") else "ok")
        zh_facts.append({"level": lvl, "text": f"Bandit (排除测试代码) — 高危: {sc.get('high')}, 中危: {sc.get('medium')}, 低危: {sc.get('low')}。此结果为静态分析提示，需人工核对。"})
    if pa.get("status") == "ok":
        zh_facts.append({"level": "warn" if pa.get("vulnerabilities") else "ok", "text": f"Pip-Audit — 已知CVE漏洞: {pa.get('vulnerabilities')} (受影响依赖包: {pa.get('vulnerable_packages')} / 已检查 {pa.get('packages')}{zh_skip_str})。"})
    elif pa.get("status") == "disabled":
        zh_facts.append({"level": "info", "text": "第三方依赖CVE漏洞扫描未启用（需使用 --pip-audit 连接网络）。"})
    if dd.get("status") == "ok":
        zh_facts.append({"level": "info", "text": f"Vulture — 疑似冗余/死代码: {dd.get('count')} (置信度 ≥ 80%: {dd.get('high_confidence')})。动态调用代码需人工复核。"})
    if du.get("status") == "ok" and du.get("percent") is not None:
        zh_facts.append({"level": "warn" if du.get("percent", 0) >= 10 else "ok", "text": f"代码重复度 (启发式) — 生产环境有效代码行约 {du.get('percent')}% 存在重复。"})
    if dp.get("status") == "ok":
        zh_facts.append({"level": "warn" if dp.get("cycles") else "ok", "text": f"依赖架构 — 模块数: {dp.get('modules')}, 关联数: {dp.get('edges')}, 循环依赖环: {dp.get('cycles')}。"})

    zh_actions = []
    if sc.get("high"):
        zh_actions.append(f"优先排查 Bandit 高危安全告警 (共 {sc.get('high')} 项)，确认是否存在真实注入或凭证泄露。")
    if pa.get("vulnerabilities"):
        zh_actions.append("升级 Pip-Audit 发现的含已知 CVE 漏洞的第三方依赖包。")
    if du.get("percent", 0) >= 10:
        zh_actions.append("审查篇幅最大的重复代码块，考虑提取公共函数或重构组件。")
    if dp.get("cycles"):
        zh_actions.append("重构模块循环依赖关系，提升单元测试覆盖度与架构整洁度。")
    if scope.get("eslint_errors"):
        zh_actions.append(f"修复前端 ESLint 严重级别错误 ({scope['eslint_errors']} 处)。")
    if top_risks:
        zh_actions.insert(0, f"建议优先人工审查模块: {', '.join(r['file'] for r in top_risks)} (审查风险指数最高)。")
    if not zh_actions:
        zh_actions.append("未发现紧急隐患 — 建议保持定期代码审计并跟踪历史趋势指标。")
    results["zh"] = {"headline": zh_head, "facts": zh_facts, "actions": zh_actions[:5]}

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Markdown Report Generator (EN, PL, ZH)
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_val(v, places=0):
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        if not math.isfinite(v):
            return "—"
        return f"{v:,.{places}f}".replace(",", " ")
    return str(v)


def _safe_md(s):
    return str(s).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _make_table(headers, rows):
    hdr = "| " + " | ".join(map(_safe_md, headers)) + " |"
    sep = "|" + "|".join(["---"] * len(headers)) + "|"
    lines = [hdr, sep]
    for row in rows:
        lines.append("| " + " | ".join(_safe_md(cell) for cell in row) + " |")
    return "\n".join(lines)


def render_markdown_report(data: dict, lang: str = "en") -> str:
    """Renders the comprehensive 15-section Markdown report in the chosen language."""
    meta = data["metadata"]
    summary = data["summary"]
    scope = data["source_scope"]
    quality = data["quality_assessment"]
    risks = data["review_candidates"]
    previous = data.get("previous_audit")
    comparison = data.get("comparison_previous_only", [])
    var = data["var_inventory"]
    excluded = data["excluded_files"]
    git = data.get("git_history") or {}
    xs = data.get("extras_summary") or {}
    ex = data.get("extras") or {}
    exec_i18n = data.get("executive_summary_i18n", {})
    es = exec_i18n.get(lang) or data.get("executive_summary") or {}

    # Gather data for tables
    py_files = [f for f in data["files"] if f.get("ext") == ".py"]
    rad = [f for f in py_files if f.get("radon") and f["radon"].get("raw")]
    hfiles = [f for f in py_files if f.get("radon") and f["radon"].get("halstead")]
    fn = [f for f in data.get("cc_functions", []) if f.get("category") == "py_prod"]
    fn_counts = Counter(f.get("rank", "") for f in fn)
    rawkeys = ["loc", "sloc", "lloc", "comments", "single_comments", "multi", "blank"]
    rawtot = {key: sum(f["radon"]["raw"].get(key, 0) for f in rad) for key in rawkeys}

    cats = data.get("categories", {})
    issues = data.get("eslint_issues", [])
    rules = Counter(x.get("rule", "(none)") for x in issues)
    issue_files = Counter(x.get("file", "") for x in issues)
    mi_vals = [f["radon"]["mi"] for f in py_files if f.get("radon") and f["radon"].get("mi") is not None]
    mi_rank = Counter((f.get("radon") or {}).get("mi_rank") for f in py_files)
    hkeys = ["h1", "h2", "N1", "N2", "vocabulary", "length", "calculated_length", "volume", "difficulty", "effort", "time", "bugs"]

    h_means = {k: _fmt_val(sum(float(f["radon"]["halstead"].get(k, 0)) for f in hfiles) / len(hfiles) if hfiles else 0, 2) for k in hkeys}
    h_meds = {k: _fmt_val(sorted(float(f["radon"]["halstead"].get(k, 0)) for f in hfiles)[len(hfiles)//2] if hfiles else 0, 2) for k in hkeys}
    h_maxs = {k: _fmt_val(max((float(f["radon"]["halstead"].get(k, 0)) for f in hfiles), default=0), 2) for k in hkeys}

    # Language text dictionary
    T = {
        "en": {
            "title": "# CodeAudit 2.2 — Technical Code Quality & Maintainability Audit",
            "project": "Project", "date": "Date (UTC)", "engines": "Analysis Engines",
            "analysis_desc": "Read-only static analysis · All outputs written outside target project · Non-intrusive · No fix / no network modifications",
            "disclaimer": "**Disclaimer:** Static code analysis findings do not prove business logic correctness, absolute security, runtime test coverage, or Clean Architecture compliance.",
            "sec1": "## 1. Executive Assessment & Summary",
            "maint_index": f"**CodeAudit Maintainability Score: {_fmt_val(quality['score'], 1)}/100 — Grade {quality['grade'] or '—'}.**",
            "maint_desc": "Transparent engineering health index. Does not constitute formal certification or Clean Architecture compliance rating.",
            "kpi_headers": ["Metric", "Value"],
            "kpi_rows": [
                ("Audited Files in Scope", _fmt_val(scope['files'])),
                ("Physical Code/Test Lines", _fmt_val(scope['physical_lines'])),
                ("Python Production Files", _fmt_val(scope['python_prod'])),
                ("Python Test Files", _fmt_val(scope['python_tests'])),
                ("Test / Prod File Ratio", _fmt_val(scope['ratio'], 3)),
                ("Python Production Functions", _fmt_val(scope['cc_count'])),
                ("Average CC (Python Prod)", _fmt_val(scope['cc_avg'], 2)),
                ("CC Rank A/B Ratio", f"{_fmt_val(scope['cc_AB_percent'], 1)}%"),
                ("Median MI (Python Prod)", _fmt_val(scope['mi_median'], 2)),
                ("ESLint Issues (Source)", _fmt_val(scope['eslint_total'])),
                ("Sensitive Modules for Review", _fmt_val(sum(r['is_sensitive'] for r in risks))),
                ("var/ Directory Inventory", f"{_fmt_val(var['files'])} files / {_fmt_val(var['bytes']/(1024**3), 2)} GiB"),
                ("Explicitly Excluded Files", _fmt_val(len(excluded))),
            ],
            "sec2": "## 2. Comparison with Previous Audit",
            "prev_note": "Comparison normalized to current exclusions. No hardcoded historical tables.",
            "prev_none": "No prior `metrics.json` discovered for this project path. This run establishes the baseline.",
            "comp_headers": ["Metric", "Previous", "Current", "Delta"],
            "sec3": "## 3. Scope Separation: Source, var/, and Excluded Files",
            "scope_desc": "`var/` is cataloged strictly as runtime/cache artifacts and excluded from code metrics and linting.",
            "scope_headers": ["Scope", "Files", "Bytes", "Notes"],
            "sec4": "## 4. File Structure & Categories",
            "sec5": "## 5. Radon RAW — Python Metrics",
            "sec6": "## 6. Cyclomatic Complexity — Python Production Code",
            "sec7": "## 7. Maintainability Index — Python Files",
            "sec8": "## 8. Halstead Complexity — Complete 12-Metric Suite",
            "hal_note": "Evaluated per file. `time` and `bugs` represent mathematical models, not literal working hours or exact defect counts.",
            "sec9": "## 9. ESLint / SonarJS / React Hooks — Source Analysis",
            "sec10": "## 10. Sensitive Modules & Review Priorities",
            "sens_note": "Triage ranking combines CC, MI, ESLint alerts, commit churn, and domain criticality. A high triage score indicates recommended manual review, not a proven vulnerability.",
            "sec11": "## 11. Scoring Methodology & Architecture Assessment",
            "sec12": "## 12. Measurement Integrity & Limitations",
            "sec13": "## 13. Output Files & Artifacts",
            "sec14": "## 14. Git Repository History & Code Evolution",
            "sec15": "## 15. CodeAudit 2.2 Extended Analyzers",
        },
        "pl": {
            "title": "# CodeAudit 2.2 — audyt techniczny i utrzymywalności projektu",
            "project": "Projekt", "date": "Data (UTC)", "engines": "Silniki analizy",
            "analysis_desc": "Analiza statyczna, tylko odczyt · Wyniki zapisane poza projektem · Bez modyfikacji kodu · Brak sieci",
            "disclaimer": "**Zastrzeżenie:** to pomiar statyczny. Wskaźniki CC, MI, Halstead i ESLint nie dowodzą bezpieczeństwa, poprawności biznesowej, pokrycia testami ani zgodności z Clean Architecture.",
            "sec1": "## 1. Ocena i podsumowanie zarządcze",
            "maint_index": f"**Indeks pomocniczy utrzymywalności CodeAudit: {_fmt_val(quality['score'], 1)}/100 — klasa {quality['grade'] or '—'}.**",
            "maint_desc": "Jawny wskaźnik trendu inżynierskiego. Nie stanowi certyfikatu bezpieczeństwa ani oficjalnej oceny Clean Architecture.",
            "kpi_headers": ["Metryka", "Wynik"],
            "kpi_rows": [
                ("Pliki w głównym audycie", _fmt_val(scope['files'])),
                ("Linie kodu/testów (fizyczne)", _fmt_val(scope['physical_lines'])),
                ("Pliki Python produkcja", _fmt_val(scope['python_prod'])),
                ("Pliki Python testy", _fmt_val(scope['python_tests'])),
                ("Test / Prod — udział plików", _fmt_val(scope['ratio'], 3)),
                ("Funkcje Python produkcja", _fmt_val(scope['cc_count'])),
                ("Średnia CC Python produkcja", _fmt_val(scope['cc_avg'], 2)),
                ("Odsetek CC A/B", f"{_fmt_val(scope['cc_AB_percent'], 1)}%"),
                ("Mediana MI Python produkcja", _fmt_val(scope['mi_median'], 2)),
                ("Problemy ESLint (źródła)", _fmt_val(scope['eslint_total'])),
                ("Wrażliwe moduły do przeglądu", _fmt_val(sum(r['is_sensitive'] for r in risks))),
                ("Katalog var (inwentaryzacja)", f"{_fmt_val(var['files'])} plików / {_fmt_val(var['bytes']/(1024**3), 2)} GiB"),
                ("Pliki jawnie wyłączone", _fmt_val(len(excluded))),
            ],
            "sec2": "## 2. Porównanie WYŁĄCZNIE z poprzednim audytem",
            "prev_note": "Porównanie oparte na identycznych filtrach var/ i wykluczeń. Brak sztywnej tabeli historycznej.",
            "prev_none": "Nie znaleziono wcześniejszego `metrics.json` dla tej samej ścieżki projektu. Raport stanowi pomiar bazowy.",
            "comp_headers": ["Metryka", "Poprzednio", "Teraz", "Zmiana"],
            "sec3": "## 3. Rozdzielenie źródeł, var i plików wyłączonych",
            "scope_desc": "`var/` jest traktowany jako artefakty/runtime i nie wchodzi do metryk kodu ani problemów lintera.",
            "scope_headers": ["Zakres", "Pliki", "Bajty", "Uwagi"],
            "sec4": "## 4. Struktura i rozmiary źródeł",
            "sec5": "## 5. Radon RAW — Python",
            "sec6": "## 6. Cyclomatic Complexity — kod produkcyjny Python",
            "sec7": "## 7. Maintainability Index — pliki Python",
            "sec8": "## 8. Halstead — wszystkie 12 metryk",
            "hal_note": "Miary liczone per plik. Wartości `time` i `bugs` to modele matematyczne, nie realny czas ani liczba usterek.",
            "sec9": "## 9. ESLint / SonarJS / React Hooks — źródła",
            "sec10": "## 10. WRAŻLIWE moduły i plan przeglądu",
            "sens_note": "Ranking triage łączy CC, MI, alerty ESLint, churn Git oraz domeny. Wskazuje moduły do przeglądu, nie błędy.",
            "sec11": "## 11. Metodologia oceny i wizualizacji",
            "sec12": "## 12. Integralność pomiaru i ograniczenia",
            "sec13": "## 13. Pliki wynikowe",
            "sec14": "## 14. Historia kodu i struktura repozytorium Git",
            "sec15": "## 15. Rozszerzenia CodeAudit 2.2",
        },
        "zh": {
            "title": "# CodeAudit 2.2 — 代码质量与可维护性技术审计报告",
            "project": "项目路径", "date": "审计时间 (UTC)", "engines": "分析引擎",
            "analysis_desc": "只读静态分析 · 所有报告写入目标项目外部 · 无代码修改 · 无网络外连 (除--pip-audit)",
            "disclaimer": "**声明:** 静态代码分析结果不代表业务逻辑的绝对正确性、安全漏洞的绝对免疫、动态测试覆盖率或Clean Architecture规范达标证明。",
            "sec1": "## 1. 管理评估与概要",
            "maint_index": f"**CodeAudit 可维护性综合评分: {_fmt_val(quality['score'], 1)}/100 — 等级: {quality['grade'] or '—'}级。**",
            "maint_desc": "透明的代码工程健康指数。不构成官方安全认证或 Clean Architecture 严格架构背书。",
            "kpi_headers": ["度量指标", "当前值"],
            "kpi_rows": [
                ("主审计范围文件总数", _fmt_val(scope['files'])),
                ("代码及测试物理行数", _fmt_val(scope['physical_lines'])),
                ("Python 生产文件数", _fmt_val(scope['python_prod'])),
                ("Python 测试文件数", _fmt_val(scope['python_tests'])),
                ("测试/生产文件比例", _fmt_val(scope['ratio'], 3)),
                ("Python 生产函数总数", _fmt_val(scope['cc_count'])),
                ("Python 生产平均圈复杂度(CC)", _fmt_val(scope['cc_avg'], 2)),
                ("圈复杂度 A/B级优质占比", f"{_fmt_val(scope['cc_AB_percent'], 1)}%"),
                ("Python 生产可维护性(MI)中位数", _fmt_val(scope['mi_median'], 2)),
                ("ESLint 问题总数 (源码)", _fmt_val(scope['eslint_total'])),
                ("待重点审查的敏感核心模块", _fmt_val(sum(r['is_sensitive'] for r in risks))),
                ("var/ 目录清单 (独立归档)", f"{_fmt_val(var['files'])} 个文件 / {_fmt_val(var['bytes']/(1024**3), 2)} GiB"),
                ("显式排除审计的文件数", _fmt_val(len(excluded))),
            ],
            "sec2": "## 2. 与上一次审计对比",
            "prev_note": "对比采用相同的var/及排除过滤规则标准化处理，不使用硬编码的历史数据表。",
            "prev_none": "未在 reports 目录发现此项目的早期 `metrics.json` 记录。当前报告作为初始基准度量。",
            "comp_headers": ["指标名称", "上期值", "本期值", "变动 (Delta)"],
            "sec3": "## 3. 范围划分：源码、var/ 与排除文件",
            "scope_desc": "`var/` 目录被视作运行时缓存与生成物，仅做文件清单统计，不计入代码质量与代码行数。",
            "scope_headers": ["范围范围", "文件数", "字节数", "说明"],
            "sec4": "## 4. 文件结构与分类规模",
            "sec5": "## 5. Radon RAW — Python基础度量",
            "sec6": "## 6. 圈复杂度 (Cyclomatic Complexity) — Python生产代码",
            "sec7": "## 7. 可维护性指数 (Maintainability Index) — Python文件",
            "sec8": "## 8. 霍尔斯特德复杂度 (Halstead Complexity) — 完整12项指标",
            "hal_note": "指标按单个文件计算。`time` 与 `bugs` 属于数学经验模型，非实际工时预测或确定缺陷数。",
            "sec9": "## 9. ESLint / SonarJS / React Hooks — 源码静态检查",
            "sec10": "## 10. 敏感模块与审查优先级 (Triage Ranking)",
            "sens_note": "审查优先级综合了圈复杂度(CC)、可维护性(MI)、ESLint告警、Git变动率(Churn)及业务领域词。旨在提供人工审查指引，不代表已确定存在漏洞。",
            "sec11": "## 11. 评分方法与架构评估说明",
            "sec12": "## 12. 审计完整性与局限性说明",
            "sec13": "## 13. 输出报告与文件清单",
            "sec14": "## 14. Git仓库历史与代码演进",
            "sec15": "## 15. CodeAudit 2.2 扩展分析器",
        },
    }
    t = T.get(lang, T["en"])
    cat_names = CATEGORY_NAMES.get(lang, CATEGORY_NAMES["en"])

    doc = [
        t["title"], "",
        f"**{t['project']}:** `{_safe_md(meta['project'])}`  ",
        f"**{t['date']}:** {meta['generated_at_utc']}  ",
        f"**{t['engines']}:** Radon {meta['radon_version']} · ESLint {meta.get('eslint_version') or 'N/A'}  ",
        f"**{t['analysis_desc']}**", "",
        f"> {t['disclaimer']}", "",
        t["sec1"], "",
        t["maint_index"], "",
        t["maint_desc"], "",
        _make_table(t["kpi_headers"], t["kpi_rows"]), "",
        t["sec2"], "",
    ]

    # Section 2: Comparison
    if previous:
        p_src = previous.get("source", "")
        p_date = previous.get("generated_at", "—")
        doc.extend([
            f"**Previous Audit:** `{_safe_md(p_src)}` · {p_date}", "",
            f"_{t['prev_note']}_", "",
            _make_table(t["comp_headers"], [
                [
                    row["metric"],
                    _fmt_val(row["previous"], row.get("places", 0)),
                    _fmt_val(row["current"], row.get("places", 0)),
                    (('+' if (row.get("delta") or 0) > 0 else '') + _fmt_val(row.get("delta"), row.get("places", 0))) if row.get("delta") is not None else "—"
                ] for row in comparison
            ]), ""
        ])
    else:
        doc.extend([t["prev_none"], ""])

    # Section 3: Scope
    doc.extend([
        t["sec3"], "",
        t["scope_desc"], "",
        _make_table(t["scope_headers"], [
            [
                "Source code & tests" if lang == "en" else ("Kod źródłowy i testy" if lang == "pl" else "源码与测试代码"),
                _fmt_val(scope["files"]), _fmt_val(scope["bytes"]),
                "Radon + ESLint" if lang == "en" else ("Radon + ESLint" if lang == "pl" else "Radon + ESLint分析")
            ],
            [
                "var/ runtime directory" if lang == "en" else ("Katalog var/ (runtime)" if lang == "pl" else "var/ 运行缓存目录"),
                _fmt_val(var["files"]), _fmt_val(var["bytes"]),
                "Inventory only" if lang == "en" else ("Tylko statystyki" if lang == "pl" else "仅统计文件规模")
            ],
            [
                "Excluded files" if lang == "en" else ("Pliki wyłączone" if lang == "pl" else "显式排除文件"),
                _fmt_val(len(excluded)), _fmt_val(sum(e.get("bytes", 0) for e in excluded)),
                "audit-settings.json"
            ],
        ]), ""
    ])

    # Section 4: File categories
    cat_headers = ["Category", "Files", "Physical Lines", "MiB"] if lang == "en" else (["Kategoria", "Pliki", "Linie fizyczne", "MiB"] if lang == "pl" else ["分类名称", "文件数", "物理代码行", "大小 (MiB)"])
    doc.extend([
        t["sec4"], "",
        _make_table(cat_headers, [
            [
                cat_names.get(k, k),
                _fmt_val(v.get("files", 0)),
                _fmt_val(v.get("physical_lines", 0)),
                _fmt_val(v.get("bytes", 0) / (1024 * 1024), 2)
            ] for k, v in sorted(cats.items(), key=lambda kv: -kv[1].get("files", 0))
        ]), ""
    ])

    # Section 5: Radon RAW
    raw_headers = ["Metric", "Total"] if lang == "en" else (["Miara", "Łącznie"] if lang == "pl" else ["度量指标", "总量合计"])
    doc.extend([
        t["sec5"], "",
        _make_table(raw_headers, [[k.upper(), _fmt_val(rawtot[k])] for k in rawkeys]), ""
    ])

    # Section 6: Cyclomatic Complexity
    cc_headers = ["Rank", "Function Count", "Share"] if lang == "en" else (["Ocena", "Liczba funkcji", "Udział"] if lang == "pl" else ["等级评定", "函数数量", "占比"])
    top_cc_headers = ["File", "Function", "Line", "CC", "Rank"] if lang == "en" else (["Plik", "Funkcja", "Linia", "CC", "Klasa"] if lang == "pl" else ["文件路径", "函数/方法名", "起始行", "圈复杂度CC", "等级"])
    doc.extend([
        t["sec6"], "",
        _make_table(cc_headers, [
            [g, _fmt_val(fn_counts[g]), f"{_fmt_val(100 * fn_counts[g] / len(fn) if fn else 0, 2)}%"]
            for g in "ABCDEF"
        ]), "",
        _make_table(top_cc_headers, [
            [f"`{_safe_md(v['file'])}`", f"`{_safe_md(v['name'])}`", v['line'], v['cc'], v['rank']]
            for v in sorted(fn, key=lambda x: -x['cc'])[:30]
        ]), ""
    ])

    # Section 7: Maintainability Index
    mi_headers = ["Metric", "Value"] if lang == "en" else (["Miara", "Wartość"] if lang == "pl" else ["度量指标", "数值"])
    doc.extend([
        t["sec7"], "",
        _make_table(mi_headers, [
            ["Analyzed Python Files" if lang == "en" else ("Pliki z MI" if lang == "pl" else "已分析文件数"), _fmt_val(len(mi_vals))],
            ["Mean MI" if lang == "en" else ("Średnia MI" if lang == "pl" else "平均可维护性(MI)"), _fmt_val(sum(mi_vals)/len(mi_vals) if mi_vals else 0, 2)],
            ["Median MI" if lang == "en" else ("Mediana MI" if lang == "pl" else "可维护性中位数"), _fmt_val(sorted(mi_vals)[len(mi_vals)//2] if mi_vals else 0, 2)],
            *[[f"{'Rank' if lang == 'en' else ('Klasa' if lang == 'pl' else '等级')} {g}", _fmt_val(mi_rank[g])] for g in "ABC"]
        ]), ""
    ])

    # Section 8: Halstead
    hal_headers = ["Metric", "Mean / File", "Median", "Max"] if lang == "en" else (["Metryka", "Średnia / plik", "Mediana", "Maksimum"] if lang == "pl" else ["度量指标", "单文件均值", "中位数", "最大值"])
    doc.extend([
        t["sec8"], "",
        t["hal_note"], "",
        _make_table(hal_headers, [
            [k, h_means[k], h_meds[k], h_maxs[k]] for k in hkeys
        ]), ""
    ])

    # Section 9: ESLint
    es_headers = ["Rule", "Issues"] if lang == "en" else (["Reguła", "Liczba"] if lang == "pl" else ["规则标识", "触发次数"])
    doc.extend([
        t["sec9"], "",
        _make_table(es_headers, [[f"`{_safe_md(k)}`", _fmt_val(v)] for k, v in rules.most_common(25)]), ""
    ])

    # Section 10: Sensitive Modules
    sens_headers = ["Priority", "File", "Domains", "Reasons", "Triage Index"] if lang == "en" else (["Priorytet", "Plik", "Domeny", "Powody", "Indeks triage"] if lang == "pl" else ["优先级", "文件路径", "所属业务领域", "审查原因", "风险指数"])
    doc.extend([
        t["sec10"], "",
        t["sens_note"], "",
        _make_table(sens_headers, [
            [
                r.get("priority", "—"),
                f"`{_safe_md(r.get('file', ''))}`",
                ", ".join(translate_domains(r.get("domains", []), lang)) or ("General" if lang == "en" else ("Ogólna" if lang == "pl" else "通用")),
                ", ".join(translate_reasons(r.get("reasons", []), lang)),
                _fmt_val(r.get("risk_index", 0), 1)
            ] for r in risks[:40]
        ]), ""
    ])

    # Section 11: Methodology
    doc.extend([
        t["sec11"], "",
        f"**{quality.get('formula', '')}**", ""
    ])

    # Section 12: Measurement integrity
    doc.extend([
        t["sec12"], "",
        f"- {'Recorded scan diagnostics' if lang == 'en' else ('Zgłoszone błędy skanowania' if lang == 'pl' else '扫描诊断告警数')}: **{len(data.get('diagnostics', []))}**.", ""
    ])

    # Section 13: Result files
    res_intro = "Available in target reports directory:" if lang == "en" else ("Pliki w katalogu wyjściowym:" if lang == "pl" else "审计报告目录中的输出文件:")
    doc.extend([
        t["sec13"], "",
        res_intro, "",
        "- `report.html` (Interactive multilingual dashboard)",
        "- `report_en.md`, `report_pl.md`, `report_zh.md` (Markdown reports)",
        "- `metrics.json` (Structured JSON dump)",
        "- `files_en.csv`, `files_pl.csv`, `files_zh.csv` (File metrics)",
        "- `functions_en.csv`, `functions_pl.csv`, `functions_zh.csv` (Function complexity)",
        "- `issues_en.csv`, `issues_pl.csv`, `issues_zh.csv` (Linting issues)",
        "- `sensitive_files_en.csv`, `sensitive_files_pl.csv`, `sensitive_files_zh.csv` (Triage rankings)",
        "- `git_commits_*.csv`, `git_hotspots_*.csv`, `git_monthly_*.csv`, `git_weekly_*.csv`", ""
    ])

    # Section 14: Git History
    git_headers = ["Git Metric", "Value"] if lang == "en" else (["Metryka Git", "Wynik"] if lang == "pl" else ["Git 度量指标", "数值"])
    doc.extend([
        t["sec14"], "",
        _make_table(git_headers, [
            ["Status" if lang == "en" else ("Status" if lang == "pl" else "分析状态"), git.get("status", "none")],
            ["Branch" if lang == "en" else ("Gałąź" if lang == "pl" else "当前分支"), git.get("branch") or "—"],
            ["HEAD SHA" if lang == "en" else ("HEAD" if lang == "pl" else "HEAD哈希"), (git.get("head") or "—")[:16]],
            ["Tracked Files" if lang == "en" else ("Śledzone pliki" if lang == "pl" else "Git跟踪文件总数"), _fmt_val(git.get("tracked_files"))],
            ["Commits in Window" if lang == "en" else ("Commity w oknie" if lang == "pl" else "分析窗口提交数"), _fmt_val(git.get("commits_analyzed"))],
            ["Line Additions (+)" if lang == "en" else ("Dodane linie (+)" if lang == "pl" else "累计新增代码行(+)"), _fmt_val(git.get("line_additions"))],
            ["Line Deletions (-)" if lang == "en" else ("Usunięte linie (-)" if lang == "pl" else "累计删除代码行(-)"), _fmt_val(git.get("line_deletions"))],
        ]), ""
    ])

    # Section 15: CodeAudit 2.2 Extensions
    doc.extend([
        t["sec15"], "",
        f"### 15.1 {'Executive Summary' if lang == 'en' else ('Streszczenie zarządcze' if lang == 'pl' else '管理层概要与行动建议')}", "",
        f"**{es.get('headline', '')}**", ""
    ])
    for f in es.get("facts", []):
        doc.append(f"- {f.get('text', '')}")
    doc.append("")
    doc.append(f"**{'Suggested Actions:' if lang == 'en' else ('Sugerowane działania:' if lang == 'pl' else '建议跟进行动:')}**")
    for idx, act in enumerate(es.get("actions", []), 1):
        doc.append(f"{idx}. {act}")
    doc.append("")

    # 15.2 Radar
    radar_headers = ["Axis", "Score (0-100)", "Method"] if lang == "en" else (["Oś", "Wartość", "Sposób obliczenia"] if lang == "pl" else ["雷达指标轴", "评分 (0-100)", "计算公式"])
    radar_axes = data.get("radar", [])
    doc.extend([
        f"### 15.2 {'Code Health Radar' if lang == 'en' else ('Radar zdrowia kodu' if lang == 'pl' else '代码健康雷达图')}", "",
        _make_table(radar_headers, [
            [
                RADAR_AXES_NAMES.get(lang, {}).get(a.get("key"), a.get("name")),
                _fmt_val(a.get("value"), 1),
                a.get("formula", "")
            ] for a in radar_axes
        ]), ""
    ])

    # 15.3 Lizard
    lz = xs.get("lizard", {})
    doc.extend([
        f"### 15.3 {'JS/TS Complexity (Lizard)' if lang == 'en' else ('Złożoność JS/TS (lizard)' if lang == 'pl' else 'JS/TS 圈复杂度 (Lizard)')}", "",
        f"{'Functions' if lang == 'en' else ('Funkcji' if lang == 'pl' else '函数总数')}: {lz.get('functions', 0)} · CC > 15: {lz.get('over15', 0)} · Max CC: {lz.get('max', 0)}.", ""
    ])

    # 15.4 Bandit Security
    sc = xs.get("security", {})
    doc.extend([
        f"### 15.4 {'Security Analysis (Bandit)' if lang == 'en' else ('Bezpieczeństwo (bandit)' if lang == 'pl' else '代码安全性分析 (Bandit)')}", "",
        f"HIGH: {sc.get('high', 0)} · MEDIUM: {sc.get('medium', 0)} · LOW: {sc.get('low', 0)}.", ""
    ])

    # 15.5 Pip-Audit
    pa = xs.get("pip_audit", {})
    doc.extend([
        f"### 15.5 {'Dependency CVE Vulnerabilities (Pip-Audit)' if lang == 'en' else ('Podatności zależności (pip-audit)' if lang == 'pl' else '第三方依赖已知漏洞 (Pip-Audit)')}", "",
        f"{'Known CVEs' if lang == 'en' else ('Znane podatności' if lang == 'pl' else '已知CVE漏洞数')}: {pa.get('vulnerabilities', 0)} ({'Checked packages' if lang == 'en' else ('Sprawdzonych pakietów' if lang == 'pl' else '已检查软件包')}: {pa.get('packages', 0)}).", ""
    ])

    # 15.6 Vulture
    dd = xs.get("dead", {})
    doc.extend([
        f"### 15.6 {'Dead Code Candidates (Vulture)' if lang == 'en' else ('Kandydaci na martwy kod (vulture)' if lang == 'pl' else '冗余/死代码候选 (Vulture)')}", "",
        f"{'Candidates' if lang == 'en' else ('Kandydatów' if lang == 'pl' else '候选代码块数')}: {dd.get('count', 0)} (Confidence ≥ 80%: {dd.get('high_confidence', 0)}).", ""
    ])

    # 15.7 Duplication
    du = ex.get("duplication", {})
    doc.extend([
        f"### 15.7 {'Code Duplication' if lang == 'en' else ('Duplikacja kodu' if lang == 'pl' else '代码重复度 (启发式)')}", "",
        f"{'Duplicated lines ratio' if lang == 'en' else ('Zduplikowane linie' if lang == 'pl' else '重复代码行占比')}: {du.get('percent', 0)}% ({du.get('duplicated_lines', 0)} / {du.get('significant_lines', 0)}).", ""
    ])

    # 15.8 Dependencies
    dp = ex.get("deps", {})
    doc.extend([
        f"### 15.8 {'Module Dependencies & Architecture Cycles' if lang == 'en' else ('Zależności między modułami' if lang == 'pl' else '模块依赖拓扑与循环引用')}", "",
        f"{'Modules' if lang == 'en' else ('Moduły' if lang == 'pl' else '模块总数')}: {dp.get('nodes_total', 0)} · {'Edges' if lang == 'en' else ('Powiązania' if lang == 'pl' else '依赖关联边数')}: {dp.get('edges_total', 0)} · {'Cycles' if lang == 'en' else ('Cykle' if lang == 'pl' else '循环依赖环数')}: {dp.get('cycles_total', 0)}.", ""
    ])

    return "\n".join(doc) + "\n"


def write_all_markdown_reports(out_dir: Path, data: dict):
    """Generates report_en.md, report_pl.md, report_zh.md, and default report.md."""
    for lang in LANGUAGES:
        content = render_markdown_report(data, lang)
        (out_dir / f"report_{lang}.md").write_text(content, encoding="utf-8")
        if lang == DEFAULT_LANG:
            (out_dir / "report.md").write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Radar Axis Names Translations
# ─────────────────────────────────────────────────────────────────────────────

RADAR_AXES_NAMES = {
    "en": {
        "maintainability": "Maintainability (MI)",
        "complexity": "Low Complexity (CC)",
        "react_hooks": "React Hooks & Rules",
        "js_clean": "Clean Frontend JS/TS",
        "security": "Security (Bandit)",
        "dead_code": "No Dead Code",
        "duplication": "Low Duplication",
        "architecture": "Architecture (No Cycles)",
    },
    "pl": {
        "maintainability": "Utrzymywalność (MI)",
        "complexity": "Niska złożoność (CC)",
        "react_hooks": "React Hooks i reguły",
        "js_clean": "Czysty frontend JS/TS",
        "security": "Bezpieczeństwo (bandit)",
        "dead_code": "Brak martwego kodu",
        "duplication": "Niska duplikacja",
        "architecture": "Architektura (brak cykli)",
    },
    "zh": {
        "maintainability": "代码可维护性 (MI)",
        "complexity": "低复杂度 (CC)",
        "react_hooks": "React Hooks 规范性",
        "js_clean": "前端 JS/TS 纯洁度",
        "security": "代码安全性 (Bandit)",
        "dead_code": "精简度 (无冗余代码)",
        "duplication": "低重复率 (DRY)",
        "architecture": "架构结构 (无依赖环)",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# HTML Dashboard UI Translations
# ─────────────────────────────────────────────────────────────────────────────

DASHBOARD_I18N = {
    "en": {
        "nav_overview": "Summary",
        "nav_quality": "Quality",
        "nav_map": "Code Map",
        "nav_compare": "Compare",
        "nav_sensitive": "Review",
        "nav_frontend": "Frontend",
        "nav_security": "Security",
        "nav_debt": "Debt",
        "nav_deps": "Dependencies",
        "nav_git": "Git",
        "nav_scope": "Scope",
        "btn_theme": "☼ Theme",
        "btn_print": "⎙ PDF",
        "hero_eyebrow": "ENGINEERING INTELLIGENCE / STATIC ANALYSIS",
        "hero_title": "Codebase Health. <em>Without guesswork.</em>",
        "hero_desc": "Professional report on software quality, technical debt, and architecture. Radon × Halstead × ESLint × SonarJS × Git. Distinct runtime inventory and explicit exclusions.",
        "badge_offline": "● OFFLINE · ZERO CDN",
        "kpi_lines": "Physical code lines",
        "kpi_lines_sub": "Source and tests only",
        "kpi_files": "Files in scope",
        "kpi_files_sub": "Excluding var/ and ignored files",
        "kpi_funcs": "Python prod functions",
        "kpi_funcs_sub": "Cyclomatic complexity",
        "kpi_eslint": "ESLint alerts",
        "kpi_eslint_sub": "{errors} errors / {warnings} warnings",
        "sec_quality_title": "Maintainability Assessment",
        "sec_quality_sub": "Transparent CodeAudit trend index — not a security certification or Clean Architecture score",
        "gauge_signal": "Maintenance signal",
        "grade_label": "Grade {grade}",
        "cc_dist_title": "Cyclomatic Complexity Distribution",
        "cc_dist_sub": "Python functions in production code · Rank A/B represents low complexity",
        "sec_compare_title": "Comparison with Previous Audit",
        "sec_compare_sub": "Normalized against previous metrics.json — no hardcoded tables",
        "compare_th_metric": "Metric",
        "compare_th_prev": "Previous",
        "compare_th_curr": "Current",
        "compare_th_delta": "Delta",
        "sec_sensitive_title": "Sensitive & High-Complexity Modules",
        "sec_sensitive_sub": "Triage ranking for manual code review based on CC, MI, React Hooks, and domain keywords",
        "callout_sensitive": "<b>Interpretation:</b> An elevated triage index is not proof of vulnerability. Modules handling finance, authorization, settlements, and shipments are flagged for periodic review due to business impact.",
        "search_sens_ph": "Search file or domain…",
        "opt_all_priorities": "All priorities",
        "opt_all": "All",
        "opt_sens_only": "Sensitive domains only",
        "sens_th_pri": "Priority",
        "sens_th_file": "File",
        "sens_th_dom": "Domain / Signals",
        "sens_th_idx": "Index",
        "sec_eslint_title": "ESLint · SonarJS · React",
        "sec_eslint_sub": "Searchable source code issues; full data in issues.csv",
        "eslint_top_rules": "Most Frequent Rules",
        "eslint_registry": "Issue Registry",
        "search_issue_ph": "Path, rule, message…",
        "opt_all_issues": "All",
        "opt_errors": "Errors",
        "opt_warnings": "Warnings",
        "opt_all_rules": "All rules",
        "opt_priority_rules": "Priority only",
        "issue_th_level": "Level",
        "issue_th_loc": "File : Line",
        "issue_th_msg": "Rule / Message",
        "sec_struct_title": "File Architecture",
        "sec_struct_sub": "Breakdown across layers, tests, and assets; metrics from filesystem",
        "top_file_groups": "Largest File Groups",
        "top_folders": "Largest Directories",
        "folder_th_name": "Directory",
        "folder_th_files": "Files",
        "folder_th_lines": "Code lines",
        "sec_git_title": "Git History · Code Evolution",
        "sec_git_sub": "Commits, velocity, code additions and deletions — local Git metadata only",
        "git_project_history": "Project History",
        "git_kpi_commits": "Commits in scanned window",
        "git_kpi_tracked": "Tracked files in Git",
        "git_kpi_tracked_sub": "Includes binary files outside source audit",
        "git_kpi_added": "Lines added (diffs)",
        "git_kpi_added_sub": "In history window",
        "git_kpi_removed": "Lines removed (diffs)",
        "git_kpi_removed_sub": "Churn ≠ current LOC",
        "git_velocity": "Development Velocity",
        "opt_months": "Monthly",
        "opt_weeks": "Weekly",
        "git_legend_add": "Added lines",
        "git_legend_del": "Removed lines",
        "git_note_footer": "Chart represents commit diff activity, not cumulative LOC. Does not include uncommitted changes.",
        "git_top_changed": "Most Frequently Modified Files (Hotspots)",
        "git_recent_commits": "Recent Commits",
        "git_author_activity": "Activity by Author (from Git metadata)",
        "sec_scope_title": "Scope & Exclusions",
        "sec_scope_sub": "Source audit strictly separated from runtime and build artifacts",
        "var_title": "var/ Directory — Runtime Inventory",
        "excluded_title": "Excluded Files",
        "excluded_sub": "Excluded from LOC, Radon, ESLint, and quality score via audit-settings.json.",
        "sec_method_title": "Methodology & Limitations",
        "callout_method": "Static analysis does not guarantee runtime correctness. Unit tests, test coverage, dependency vulnerability audits, profiling, and security reviews remain separate activities. Halstead 'Bugs' and 'Time' are mathematical models, not literal hours or defect predictions.",
        "footer_text": "CodeAudit 2.2 · Radon + ESLint + SonarJS + Git · Generated locally · Zero telemetry, zero external scripts, zero network calls.",
        "exec_title": "EXECUTIVE SUMMARY",
        "actions_title": "RECOMMENDED ACTIONS",
        "exec_hint": "Summary is generated automatically from the metrics below. Findings are triage signals, not absolute verdicts.",
        "kpi_sec": "Security · Bandit (excl. tests)",
        "kpi_dead": "Dead code · Vulture candidates",
        "kpi_dup": "Code duplication (heuristic)",
        "kpi_deps": "Dependencies · Import cycles",
        "radar_title": "Code Health Radar",
        "radar_sub": "Axes 0–100, higher is better. Independent of main score to allow historical comparability.",
        "trend_title": "Multi-Audit Trend",
        "trend_sub": "Data aggregated across historical metrics.json files in reports directory",
        "map_title": "Codebase Map",
        "map_sub": "Visual distribution of complexity, defects, and churn — click any file for details",
        "treemap_title": "Project Treemap",
        "treemap_sub": "Area = line count, Color = selected metric (green → red). Click directories to zoom.",
        "hotspot_title": "Hotspots: Churn × Complexity",
        "hotspot_sub": "Top-right quadrant shows files that are both highly complex and frequently modified — prime candidates for refactoring.",
        "frontend_title": "Frontend · JS/TS Complexity",
        "frontend_sub": "Lizard evaluates cyclomatic complexity of JavaScript and TypeScript functions",
        "security_title": "Security Analysis",
        "security_sub": "Bandit (Python code, local) and Pip-Audit (dependency CVEs, requires internet). Verification signals, not proofs.",
        "debt_title": "Dead Code & Duplication",
        "debt_sub": "Unused code candidates (Vulture) and duplicated blocks (heuristic 8-line sliding window)",
        "deps_title": "Module Dependency Graph",
        "deps_sub": "Import relationships across Python and JS/TS. Red nodes belong to import cycles. Drag to pan, scroll to zoom.",
        "modal_title": "FILE DETAILS",
        "modal_close": "Close ✕",
    },
    "pl": {
        "nav_overview": "Podsumowanie",
        "nav_quality": "Jakość",
        "nav_map": "Mapa kodu",
        "nav_compare": "Porównanie",
        "nav_sensitive": "Przegląd",
        "nav_frontend": "Frontend",
        "nav_security": "Bezpieczeństwo",
        "nav_debt": "Dług",
        "nav_deps": "Zależności",
        "nav_git": "Git",
        "nav_scope": "Zakres",
        "btn_theme": "☼ Motyw",
        "btn_print": "⎙ PDF",
        "hero_eyebrow": "ENGINEERING INTELLIGENCE / STATIC ANALYSIS",
        "hero_title": "Stan kodu. <em>Bez domysłów.</em>",
        "hero_desc": "Profesjonalny raport jakości, struktury i długu technicznego. Radon × Halstead × ESLint × SonarJS × Git. Osobna inwentaryzacja plików generowanych i jawne wyłączenia z audytu.",
        "badge_offline": "● OFFLINE · ZERO CDN",
        "kpi_lines": "Fizyczne linie kodu",
        "kpi_lines_sub": "Tylko źródła i testy",
        "kpi_files": "Pliki w audycie",
        "kpi_files_sub": "Bez var i plików wyłączonych",
        "kpi_funcs": "Funkcje Python prod",
        "kpi_funcs_sub": "Złożoność cyklomatyczna",
        "kpi_eslint": "Alerty ESLint",
        "kpi_eslint_sub": "{errors} błędów / {warnings} ostrzeżeń",
        "sec_quality_title": "Ocena utrzymywalności",
        "sec_quality_sub": "Jawny indeks trendu CodeAudit — nie ocena bezpieczeństwa ani Clean Architecture",
        "gauge_signal": "Maintenance signal",
        "grade_label": "Klasa {grade}",
        "cc_dist_title": "Rozkład Cyclomatic Complexity",
        "cc_dist_sub": "Funkcje Python w kodzie produkcyjnym · A/B oznacza niższą złożoność",
        "sec_compare_title": "Porównanie z poprzednim audytem",
        "sec_compare_sub": "Znormalizowane względem poprzedniego metrics.json — bez tabeli wpisanej na stałe",
        "compare_th_metric": "Metryka",
        "compare_th_prev": "Poprzednio",
        "compare_th_curr": "Obecnie",
        "compare_th_delta": "Zmiana",
        "sec_sensitive_title": "Wrażliwe i złożone moduły",
        "sec_sensitive_sub": "Lista priorytetów ręcznego code review na podstawie CC, MI, Hooks i wrażliwości domenowej",
        "callout_sensitive": "<b>Interpretacja:</b> podwyższony indeks triage nie jest podatnością. Moduły finansowe, autoryzacja, rozliczenia i przesyłki są dodatkowo flagowane do okresowego przeglądu ze względu na ich znaczenie biznesowe.",
        "search_sens_ph": "Szukaj pliku / domeny…",
        "opt_all_priorities": "Wszystkie priorytety",
        "opt_all": "Wszystkie",
        "opt_sens_only": "Tylko domenowo wrażliwe",
        "sens_th_pri": "Priorytet",
        "sens_th_file": "Plik",
        "sens_th_dom": "Domena / sygnały",
        "sens_th_idx": "Indeks",
        "sec_eslint_title": "ESLint · SonarJS · React",
        "sec_eslint_sub": "Wyszukiwalne zgłoszenia z plików źródłowych; pełne dane także w issues.csv",
        "eslint_top_rules": "Najczęściej zgłaszane reguły",
        "eslint_registry": "Rejestr zgłoszeń",
        "search_issue_ph": "Ścieżka, reguła, treść…",
        "opt_all_issues": "Wszystkie",
        "opt_errors": "Błędy",
        "opt_warnings": "Ostrzeżenia",
        "opt_all_rules": "Wszystkie reguły",
        "opt_priority_rules": "Priorytetowe",
        "issue_th_level": "Poziom",
        "issue_th_loc": "Plik : linia",
        "issue_th_msg": "Reguła / komunikat",
        "sec_struct_title": "Architektura plików",
        "sec_struct_sub": "Podział na warstwy, testy i zasoby; metryki z fizycznego systemu plików",
        "top_file_groups": "Największe grupy plików",
        "top_folders": "Największe katalogi",
        "folder_th_name": "Katalog",
        "folder_th_files": "Pliki",
        "folder_th_lines": "Linie kodu",
        "sec_git_title": "Historia Git · ewolucja kodu",
        "sec_git_sub": "Commity, tempo prac, przyrosty i usunięcia kodu, aktywność repozytorium — wyłącznie lokalne dane Git",
        "git_project_history": "Historia projektu",
        "git_kpi_commits": "Commity w analizowanym zakresie",
        "git_kpi_tracked": "Pliki śledzone przez Git",
        "git_kpi_tracked_sub": "Obejmuje również pliki poza audytem źródłowym",
        "git_kpi_added": "Dodane linie kodu (diffy)",
        "git_kpi_added_sub": "W oknie historii Git",
        "git_kpi_removed": "Usunięte linie kodu (diffy)",
        "git_kpi_removed_sub": "Churn ≠ obecne LOC",
        "git_velocity": "Tempo rozwoju kodu",
        "opt_months": "Miesiące",
        "opt_weeks": "Tygodnie",
        "git_legend_add": "Dodane linie",
        "git_legend_del": "Usunięte linie",
        "git_note_footer": "Wykres przedstawia zmiany w commitach, a nie przyrost obecnej liczby LOC. Nie uwzględnia zmian niezatwierdzonych.",
        "git_top_changed": "Najczęściej zmieniane pliki źródłowe",
        "git_recent_commits": "Ostatnie commity",
        "git_author_activity": "Aktywność według autora — na podstawie metadanych commitów",
        "sec_scope_title": "Zakres i wyłączenia",
        "sec_scope_sub": "Audyt źródłowy oddzielony od artefaktów środowiskowych",
        "var_title": "Katalog var/ — osobna inwentaryzacja",
        "excluded_title": "Pliki wyłączone z audytu",
        "excluded_sub": "Nie wchodzą do LOC, Radon, ESLint ani oceny jakości. Obowiązuje jawna lista w audit-settings.json.",
        "sec_method_title": "Metodologia i ograniczenia",
        "callout_method": "Analiza statyczna nie dowodzi, że kod działa poprawnie. Testy, pomiar pokrycia, analiza zależności, profilowanie i przegląd bezpieczeństwa pozostają osobnymi czynnościami. Halstead „Bugs” i „Time” to wskaźniki modelowe, nie prognozy realnych błędów i godzin.",
        "footer_text": "CodeAudit 2.2 · Radon + ESLint + SonarJS + Git · Wygenerowane lokalnie · Bez telemetrii, zewnętrznych skryptów i połączeń sieciowych.",
        "exec_title": "STRESZCZENIE ZARZĄDCZE",
        "actions_title": "OD CZEGO ZACZĄĆ",
        "exec_hint": "Streszczenie jest generowane automatycznie z liczb poniżej. Wyniki to sygnały do przeglądu, nie wyroki.",
        "kpi_sec": "Bezpieczeństwo · bandit (bez testów)",
        "kpi_dead": "Martwy kod · kandydaci vulture",
        "kpi_dup": "Duplikacja kodu (heurystyka)",
        "kpi_deps": "Zależności · cykle importów",
        "radar_title": "Radar zdrowia kodu",
        "radar_sub": "Osie 0–100, wyżej = lepiej. Niezależny od indeksu głównego, by zachować porównywalność audytów.",
        "trend_title": "Trend między audytami",
        "trend_sub": "Dane zagregowane z kolejnych plików metrics.json w folderze reports",
        "map_title": "Mapa kodu",
        "map_sub": "Gdzie w projekcie koncentrują się złożoność, błędy i zmiany — kliknij plik, aby zobaczyć szczegóły",
        "treemap_title": "Treemap projektu",
        "treemap_sub": "Powierzchnia = liczba linii, kolor = wybrana miara (zielony → czerwony). Kliknij katalog, aby przybliżyć.",
        "hotspot_title": "Hotspoty: zmiany × złożoność",
        "hotspot_sub": "Prawy górny róg to pliki jednocześnie złożone i często zmieniane — dobre kandydaty do refaktoryzacji.",
        "frontend_title": "Frontend · złożoność JS/TS",
        "frontend_sub": "Lizard liczy złożoność cyklomatyczną funkcji JavaScript i TypeScript",
        "security_title": "Bezpieczeństwo",
        "security_sub": "Bandit (kod Python, lokalnie) i pip-audit (podatności zależności, wymaga internetu). Sygnały do weryfikacji.",
        "debt_title": "Martwy kod i duplikacja",
        "debt_sub": "Kandydaci na kod nieużywany (vulture) oraz powielone fragmenty (heurystyka okna 8 linii)",
        "deps_title": "Zależności między modułami",
        "deps_sub": "Graf importów Python i JS/TS. Czerwone węzły leżą w cyklach. Przeciągaj węzły, przewijaj, aby przybliżyć.",
        "modal_title": "SZCZEGÓŁY PLIKU",
        "modal_close": "Zamknij ✕",
    },
    "zh": {
        "nav_overview": "概要",
        "nav_quality": "质量",
        "nav_map": "代码全景",
        "nav_compare": "版本对比",
        "nav_sensitive": "重点审查",
        "nav_frontend": "前端度量",
        "nav_security": "安全漏洞",
        "nav_debt": "技术债务",
        "nav_deps": "依赖拓扑",
        "nav_git": "Git演进",
        "nav_scope": "范围说明",
        "btn_theme": "☼ 主题",
        "btn_print": "⎙ 打印/PDF",
        "hero_eyebrow": "ENGINEERING INTELLIGENCE / STATIC ANALYSIS",
        "hero_title": "代码全景透视 <em>真实量化</em>",
        "hero_desc": "专业级软件架构质量、技术债务与安全度量报告。Radon × Halstead × ESLint × SonarJS × Git。运行时文件独立清单与显式排除规则。",
        "badge_offline": "● 离线运行 · 零 CDN 依赖",
        "kpi_lines": "物理代码行数",
        "kpi_lines_sub": "仅限源码与测试代码",
        "kpi_files": "审计范围文件数",
        "kpi_files_sub": "排除 var/ 与忽略文件",
        "kpi_funcs": "Python 生产函数数",
        "kpi_funcs_sub": "圈复杂度评估",
        "kpi_eslint": "ESLint 告警数",
        "kpi_eslint_sub": "{errors} 错误 / {warnings} 警告",
        "sec_quality_title": "代码可维护性评估",
        "sec_quality_sub": "透明的代码工程健康指数 — 非安全认证或Clean Architecture达标结论",
        "gauge_signal": "可维护性健康度",
        "grade_label": "评级: {grade} 级",
        "cc_dist_title": "圈复杂度 (CC) 等级分布",
        "cc_dist_sub": "Python 生产函数 · A/B 级代表较低复杂度与良好可读性",
        "sec_compare_title": "与上一次审计对比",
        "sec_compare_sub": "基于上一版 metrics.json 标准化比对 — 不含硬编码数据",
        "compare_th_metric": "度量指标",
        "compare_th_prev": "上期值",
        "compare_th_curr": "本期值",
        "compare_th_delta": "增减变动",
        "sec_sensitive_title": "高复杂度与敏感核心模块",
        "sec_sensitive_sub": "基于 CC、MI、React Hooks 及业务领域权重的重点人工审查优先级清单",
        "callout_sensitive": "<b>报告说明:</b> 较高的审查风险指数并不代表代码存在缺陷或漏洞。财务账本、权限认证、支付及调度等核心业务模块由于对系统影响巨大，会被优先标记以供定期审查。",
        "search_sens_ph": "搜索文件或业务领域…",
        "opt_all_priorities": "所有优先级",
        "opt_all": "全部",
        "opt_sens_only": "仅限核心敏感领域",
        "sens_th_pri": "优先级",
        "sens_th_file": "文件路径",
        "sens_th_dom": "业务领域 / 信号",
        "sens_th_idx": "风险指数",
        "sec_eslint_title": "ESLint · SonarJS · React",
        "sec_eslint_sub": "源码静态检查详细问题；完整明细请参阅 issues.csv",
        "eslint_top_rules": "最高频触发规则",
        "eslint_registry": "代码问题列表",
        "search_issue_ph": "按文件路径、规则或内容搜索…",
        "opt_all_issues": "全部严重度",
        "opt_errors": "仅错误 (Errors)",
        "opt_warnings": "仅警告 (Warnings)",
        "opt_all_rules": "所有检查规则",
        "opt_priority_rules": "高危优先规则",
        "issue_th_level": "级别",
        "issue_th_loc": "文件 : 行号",
        "issue_th_msg": "规则标识 / 问题说明",
        "sec_struct_title": "文件结构与分类",
        "sec_struct_sub": "架构分层、测试与资产分布；基于物理文件系统度量",
        "top_file_groups": "文件类型规模分布",
        "top_folders": "代码规模最大目录",
        "folder_th_name": "目录名",
        "folder_th_files": "文件总数",
        "folder_th_lines": "代码行数",
        "sec_git_title": "Git 历史演进与活动",
        "sec_git_sub": "提交趋势、开发节奏、新增与删除行、代码热点 — 基于本地 Git 元数据",
        "git_project_history": "代码仓库演进",
        "git_kpi_commits": "分析窗口提交数",
        "git_kpi_tracked": "Git 跟踪文件数",
        "git_kpi_tracked_sub": "包含源码审计之外的二进制文件",
        "git_kpi_added": "累计新增代码行",
        "git_kpi_added_sub": "历史窗口统计",
        "git_kpi_removed": "累计删除代码行",
        "git_kpi_removed_sub": "变动量 (Churn) ≠ 当前行数",
        "git_velocity": "代码开发速度与节奏",
        "opt_months": "按月份统计",
        "opt_weeks": "按周次统计",
        "git_legend_add": "新增代码行",
        "git_legend_del": "删除代码行",
        "git_note_footer": "图表展示历次提交的增删代码行，不反映未提交的本地临时修改。",
        "git_top_changed": "最高频变动文件 (Git Hotspots)",
        "git_recent_commits": "近期提交记录",
        "git_author_activity": "开发者提交活跃度 (基于提交者元数据)",
        "sec_scope_title": "范围与排除规则",
        "sec_scope_sub": "源码审计严格独立于环境缓存及构建产物",
        "var_title": "var/ 目录 — 独立运行时清单",
        "excluded_title": "显式排除的文件",
        "excluded_sub": "依据 audit-settings.json 排除，不计入代码行数、Radon、ESLint与质量分。",
        "sec_method_title": "方法论与局限性声明",
        "callout_method": "静态代码分析不等于软件动态执行的正确性证明。自动化测试、测试覆盖率、依赖包漏洞、性能画像及安全渗透测试仍属于独立工作。Halstead 缺陷与时间仅为数学经验模型。",
        "footer_text": "CodeAudit 2.2 · Radon + ESLint + SonarJS + Git · 本地计算生成 · 零遥测，零外部脚本，零网络外连。",
        "exec_title": "管理层概要",
        "actions_title": "建议跟进行动",
        "exec_hint": "概要由各项静态度量自动汇总生成。所有发现属于待核查信号，非绝对判定。",
        "kpi_sec": "安全审计 · Bandit (排除测试)",
        "kpi_dead": "冗余代码 · Vulture 候选",
        "kpi_dup": "代码重复度 (启发式)",
        "kpi_deps": "依赖拓扑 · 循环引用环",
        "radar_title": "代码健康雷达图",
        "radar_sub": "指标轴 0–100 分，分高者优。独立于主评分，保障跨审计版本可比性。",
        "trend_title": "跨版本历史趋势",
        "trend_sub": "汇总自 reports 目录下的历史 metrics.json 数据",
        "map_title": "代码全景图谱",
        "map_sub": "直观展现代码复杂度、漏洞与变动热点的空间分布 — 点击文件查看详情",
        "treemap_title": "项目矩形树图 (Treemap)",
        "treemap_sub": "面积 = 代码行数，颜色 = 所选指标 (绿 → 红)。点击目录可下钻放大。",
        "hotspot_title": "热点分析：代码变动 × 圈复杂度",
        "hotspot_sub": "右上角象限文件兼具高复杂度与高频修改特征 — 属于优先重构候选对象。",
        "frontend_title": "前端 · JS/TS 圈复杂度",
        "frontend_sub": "Lizard 分析器度量 JavaScript 和 TypeScript 函数圈复杂度",
        "security_title": "安全性分析",
        "security_sub": "Bandit (Python源码，本地离线) 与 Pip-Audit (第三方依赖漏洞，需联网)。",
        "debt_title": "冗余代码与重复度",
        "debt_sub": "疑似未引用代码候选 (Vulture) 与大段重复代码块 (8行滑动窗口)",
        "deps_title": "模块依赖拓扑关系图",
        "deps_sub": "Python 与 JS/TS 模块导入图谱。红色节点代表存在循环依赖。支持拖拽缩放。",
        "modal_title": "文件详细分析",
        "modal_close": "关闭 ✕",
    },
}

