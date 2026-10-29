# CodeAudit 2.2 — Python, React, JavaScript, Security & Git History Audit

CodeAudit is an independent, non-intrusive static code quality and security analysis suite.

**CodeAudit is strictly read-only.** It never alters source code, does not execute `eslint --fix`, never runs `git fetch/pull/reset`, and avoids network calls by default. All reports and metrics are written outside the audited project into `CodeAudit/reports/` (or a custom `--out` destination).

---

## 1. Requirements

- **Python 3.10+** and **Radon 6.x**:
  ```bash
  python -m pip install radon
  ```
- **Node.js (v18+)** & npm with **Git** available in your PATH:
  ```bash
  git --version
  ```
- **Extended Analyzers in v2.2 (Recommended)**:
  ```bash
  python -m pip install lizard vulture bandit pip-audit
  ```
  *(All extra analyzers are optional. If a library is missing, that particular section gracefully marks as "unavailable", while the rest of the audit proceeds without interruption).*
- **ESLint 9 & Plugins** (installed inside `CodeAudit`):
  ```bash
  cd C:\Tools\CodeAudit
  npm install
  ```
  *(Or manually: `npm install --save-dev eslint@9 @eslint/js@9 eslint-plugin-sonarjs eslint-plugin-react eslint-plugin-react-hooks globals`).*

> **Offline Dashboard**: The Apache ECharts visualization library is bundled under `vendor/echarts.min.js` and embedded directly into `report.html`. The interactive dashboard works 100% offline without external CDN requests.

---

## 2. Project Architecture & Components

- `audit.py`: Core orchestrator managing inventory, Radon metrics, and ESLint batches.
- `audit_reporting.py`: Maintainability scoring, historical audit comparison, and sensitive-file identification.
- `html_dashboard.py` / `dashboard_extra.py` / `dashboard_charts.js`: Offline interactive dashboard with ECharts treemaps, heatmaps, and radars.
- `extra_analyzers.py`: Integrations for Lizard (JS/TS complexity), Vulture (dead code), Bandit (security), Pip-Audit (vulnerabilities), duplication detection, and module dependency graphs.
- `audit_insights.py`: Executive summaries, risk radar, audit trend tracking, and file matrices.
- `git_history.py`: Local repository statistics, churn hotspots, and weekly/monthly code change velocity.
- `Run-CodeAudit.ps1`: Convenient PowerShell wrapper script.
- `audit-settings.json`: Rules for excluding specific files or patterns from analysis.
- `project_metrics.py`: Zero-dependency, lightweight fallback script for fast file and LOC counting.

---

## 3. Quick Start

### Basic Usage (PowerShell)

Run an audit on any target project folder:

```powershell
cd C:\Tools\CodeAudit
.\Run-CodeAudit.ps1 -ProjectPath "C:\path\to\your-project"
```

If Windows blocks the downloaded PowerShell script:
```powershell
Unblock-File "C:\Tools\CodeAudit\Run-CodeAudit.ps1"
```

### Direct Python Invocation

```powershell
python audit.py "C:\path\to\your-project"
```

---

## 4. CLI Options & Parameters

Both `Run-CodeAudit.ps1` and `audit.py` accept the following configuration parameters:

| PowerShell Switch | Python CLI Flag | Description |
|---|---|---|
| `-ProjectPath <path>` | `<project>` (positional) | Path to target project (required) |
| `-PipAudit` | `--pip-audit` | Audits dependencies for known CVEs (**requires internet**) |
| `-Requirements <files...>` | `--requirements <files...>` | Path(s) to pinned requirements file(s) (can be outside the target project) |
| `-Previous <path>` | `--previous <path>` | Compares against a specific `metrics.json` file |
| `-NoPrevious` | `--no-previous` | Skips comparison with previous audit runs |
| `-NoGit` | `--no-git` | Skips Git history extraction (for non-git or large repos) |
| `-GitMaxCommits <int>` | `--git-max-commits <int>` | Maximum non-merge commits to scan (default: 800, max: 5000) |
| `-NoEslint` | `--no-eslint` | Skips ESLint static analysis on JS/JSX |
| `-NoExtras` | `--no-extras` | Skips all v2.2 extra analyzers (runs fast like v2.1) |
| `-NoBandit` | `--no-bandit` | Disables Bandit Python security scanning |
| `-NoVulture` | `--no-vulture` | Disables Vulture dead code detection |
| `-NoLizard` | `--no-lizard` | Disables Lizard JS/TS cyclomatic complexity |
| `-NoDuplication` | `--no-duplication` | Disables heuristic code duplication scan |
| `-NoDeps` | `--no-deps` | Disables import/dependency graph generator |
| `-SkipVarInventory` | `--skip-var-inventory` | Skips file count and size inventory of `var/` folder |
| *(CLI only)* | `--out <path>` | Custom output directory (must be outside scanned codebase) |

---

## 5. Dependency Vulnerability Auditing (`-PipAudit` & `-Requirements`)

### How Pip-Audit Works
- `pip-audit` queries PyPI / OSV vulnerability databases to find security issues in your dependencies.
- **Requires internet access**: Because it consults online CVE databases, this is the only feature of CodeAudit that connects to the internet.
- **Requires pinned versions**: Vulnerability scanners must know the exact version in use (e.g. `fastapi==0.115.0`). Lines without exact pins (e.g. `fastapi` or `fastapi>=0.100`) cannot be reliably evaluated.

### How to Generate a Pinned Requirements File for Your Project

`pip-audit` requires pinned versions (e.g. `fastapi==0.115.0`) to check vulnerabilities. If your target project **has unpinned versions** (e.g. just `fastapi` or `fastapi>=0.100`), or **does not have a `requirements.txt` file at all** (e.g. poetry, pyproject.toml, or ad-hoc setup), you can easily generate an external pinned file without touching or modifying the target project:

#### Scenario 1: Project has `requirements.txt` but WITHOUT exact versions
Extract only the package names defined in the project, match them against the exact versions currently installed in Python, and save outside the project:

```powershell
# 1. Navigate to target project folder
cd "C:\path\to\your-project"

# 2. Extract package names (stripping >, <, ==, etc.)
$names = Get-Content requirements.txt | ForEach-Object { ($_ -split '[<>=!~\[; ]')[0] } | Where-Object { $_ }

# 3. Match against currently installed pip packages and write to CodeAudit folder
python -m pip freeze | Select-String -Pattern ("^(" + ($names -join '|') + ")==") | ForEach-Object { $_.Line } | Out-File -Encoding utf8 C:\Tools\CodeAudit\pinned-requirements.txt
```

#### Scenario 2: Project DOES NOT have any `requirements.txt` file
If the project has no requirements file (or uses `pyproject.toml` / virtualenv):

1. **If using a virtual environment (`venv`) for the project**:
   Activate the project's virtualenv first, then export all active dependencies:
   ```powershell
   # In the project directory (activate venv first):
   .\.venv\Scripts\Activate.ps1
   python -m pip freeze | Out-File -Encoding utf8 C:\Tools\CodeAudit\pinned-requirements.txt
   ```

2. **If using global Python environment**:
   Export all installed packages directly to `pinned-requirements.txt`:
   ```powershell
   python -m pip freeze | Out-File -Encoding utf8 C:\Tools\CodeAudit\pinned-requirements.txt
   ```
   *(This also captures all transitive dependencies like `starlette`, `urllib3`, etc., giving the most comprehensive security scan).*

### Running the Audit with Pinned Dependencies
Pass `-PipAudit` and `-Requirements` pointing to your generated file:

```powershell
cd C:\Tools\CodeAudit
.\Run-CodeAudit.ps1 -ProjectPath "C:\path\to\your-project" -PipAudit -Requirements C:\Tools\CodeAudit\pinned-requirements.txt
```

Or directly via Python CLI:
```powershell
python audit.py "C:\path\to\your-project" --pip-audit --requirements C:\Tools\CodeAudit\pinned-requirements.txt
```

---

## 6. Output Reports & Artifacts (Multilingual: EN, PL, ZH)

CodeAudit generates comprehensive, publication-ready reports in **3 languages** (English, Polish, and Simplified Chinese) simultaneously:

### 6.1 Interactive Offline HTML Dashboard (`report.html`)
- **Interactive Language Switcher**: Toggle effortlessly between **English (EN)**, **Polish (PL)**, and **Simplified Chinese (ZH)** with a single click in the top navbar.
- **100% Offline & Zero-CDN**: Embedded with Apache ECharts (`vendor/echarts.min.js`), requiring no internet connection or external CDN requests.
- **Dynamic Content Updates**: Switching languages instantly translates navigation, section titles, KPI cards, table headers, risk descriptions, and data charts without page reloads.
- **Extensible i18n Architecture**: Designed around a modular translation engine (`i18n.py`) allowing additional languages to be added easily.

### 6.2 Markdown Reports (`.md`)
Generated in dedicated language files alongside the default report:
- `report.md`: Default report (English).
- `report_en.md`: English report.
- `report_pl.md`: Polish report (*Raport z audytu kodu*).
- `report_zh.md`: Simplified Chinese report (*代码质量与可维护性技术审计报告*).

### 6.3 Localized CSV Datasets (`.csv`)
All CSV files are produced in 3 localized variants with translated column headers and translated categorical values (severity, kinds, triage status), encoded in **UTF-8 with BOM (`utf-8-sig`)** for seamless loading into Microsoft Excel and spreadsheet tools:

| Base Dataset | Localized Variants | Description |
|---|---|---|
| `files.csv` | `files_en.csv`, `files_pl.csv`, `files_zh.csv` | Metrics per individual analyzed file |
| `functions.csv` | `functions_en.csv`, `functions_pl.csv`, `functions_zh.csv` | Python functions and methods ranked by Cyclomatic Complexity |
| `js_functions.csv` | `js_functions_en.csv`, `js_functions_pl.csv`, `js_functions_zh.csv` | JavaScript/TypeScript functions with CC and NLOC metrics (Lizard) |
| `issues.csv` | `issues_en.csv`, `issues_pl.csv`, `issues_zh.csv` | Full listing of ESLint / SonarJS / React Hooks issues |
| `security_bandit.csv` | `security_bandit_en.csv`, `security_bandit_pl.csv`, `security_bandit_zh.csv` | Static security findings from Bandit (passwords masked with `***`) |
| `security_dependencies.csv` | `security_dependencies_en.csv`, `_pl.csv`, `_zh.csv` | Known dependency vulnerabilities from Pip-Audit |
| `dead_code.csv` | `dead_code_en.csv`, `dead_code_pl.csv`, `dead_code_zh.csv` | Dead code candidates identified by Vulture |
| `duplication.csv` | `duplication_en.csv`, `duplication_pl.csv`, `duplication_zh.csv` | Largest duplicate code blocks detected |
| `dependencies.csv` | `dependencies_en.csv`, `dependencies_pl.csv`, `dependencies_zh.csv` | Graph edges representing file import relationships |
| `sensitive_files.csv` | `sensitive_files_en.csv`, `_pl.csv`, `_zh.csv` | Triage list of high-risk / domain-critical files for manual review |
| `git_commits.csv` | `git_commits_en.csv`, `git_commits_pl.csv`, `git_commits_zh.csv` | History of scanned non-merge commits |
| `git_hotspots.csv` | `git_hotspots_en.csv`, `git_hotspots_pl.csv`, `git_hotspots_zh.csv` | Code files ranked by churn and modification frequency |
| `git_monthly.csv` / `weekly.csv` | `git_monthly_*.csv`, `git_weekly_*.csv` | Code addition/deletion velocity aggregated over time |
| `metrics.json` | — | Complete machine-readable metrics dump used for multi-run delta comparisons |

---

## 7. Customizing Exclusions (`audit-settings.json`)

To exclude specific archival files, generated mocks, or vendor code from triggering alerts, add rules to `audit-settings.json`:

```json
{
  "excluded_files": [
    {
      "pattern": "src/legacy/*.py",
      "reason": "Archived subsystem scheduled for deprecation"
    }
  ]
}
```

Standard directories (`node_modules`, `.venv`, `.git`, `.work`, `dist`, `build`, `__pycache__`) are ignored by default.

---

## 8. Interpretive Guidelines & Limitations

- **Maintainability Score**: A composite, transparent index (Python CC + Python MI + high-priority ESLint findings). It is an engineering health heuristic, not an official security certification or test coverage measurement.
- **Sensitive Files Ranking**: A triage recommendation indicating where manual review may be most beneficial. It does not prove the existence of bugs.
- **Bandit & Vulture**: Heuristic static analyzers may output false positives on dynamic framework patterns or test fixtures.
- **Git Churn**: Measures commit activity velocity, which differs from active lines of code (LOC).

---

## Contributing

Contributions, feedback, and issue reports are welcome! Please open an issue or pull request on GitHub.

## License

This project is licensed under the [MIT License](LICENSE).

