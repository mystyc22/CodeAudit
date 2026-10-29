# CodeAudit 1.0 — Local Python + JavaScript/React Code Quality Audit

A standalone, read-only static analysis and auditing suite for Python and JavaScript/React codebases.

**CodeAudit operates directly on the filesystem.** It does not require Git, does not modify any source code, does not run tests, avoids `eslint --fix`, and produces all output files outside the scanned target project.

---

## Features

- **Read-only and non-intrusive**: Never writes to, modifies, or formats source files in the inspected codebase.
- **Git-independent**: Scans any local directory or backup snapshot, with or without a Git repository.
- **Python Quality Metrics (via Radon)**:
  - **RAW**: LOC, SLOC, LLOC, single/multi-line comments, blank lines.
  - **Cyclomatic Complexity (CC)**: Function and method-level complexity ranking (A–F) with closure detection.
  - **Maintainability Index (MI)**: Composite maintainability score per file.
  - **Halstead Complexity**: Complete 12-metric Halstead suite per file (volume, difficulty, effort, time, bugs, vocabulary).
- **JavaScript & React Linting (via ESLint 9 Flat Config)**:
  - Complexity checks (`max-depth`, `max-params`, `max-statements`).
  - Cognitive Complexity via `eslint-plugin-sonarjs`.
  - React rules & hooks checks via `eslint-plugin-react` and `eslint-plugin-react-hooks`.
- **Comprehensive Outputs**:
  - `report.md`: Markdown summary report with tables.
  - `metrics.json`: Structured machine-readable results.
  - `files.csv`: Per-file metrics (SLOC, LLOC, MI, CC max, Halstead volume/difficulty).
  - `functions.csv`: All detected Python functions and methods ranked by CC.
  - `issues.csv`: Complete listing of ESLint / SonarJS issues.
- **Lightweight Alternative Included**: Includes `project_metrics.py`, a zero-dependency script for fast file and line counts.

---

## Requirements

1. **Python 3.10+**
   ```bash
   python -m pip install radon
   ```
2. **Node.js (v18+)** *(Optional, for JavaScript/React linting)*
   ```bash
   cd CodeAudit
   npm install
   ```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/mystyc22/CodeAudit.git
cd CodeAudit
npm install
python -m pip install radon
```

---

## Usage

### 1. Full Audit (`audit.py`)

Run an audit on any target project folder:

```powershell
python audit.py "C:\path\to\your-project"
```

Or using the PowerShell helper:

```powershell
.\Run-CodeAudit.ps1 -ProjectPath "C:\path\to\your-project"
```

#### CLI Options

```powershell
# Custom output directory (must be outside the scanned project):
python audit.py "C:\path\to\your-project" --out "D:\Reports\MyProject_Audit"

# Python-only audit (skip ESLint):
python audit.py "C:\path\to\your-project" --no-eslint

# Include hidden directories:
python audit.py "C:\path\to\your-project" --include-hidden

# Adjust ESLint batch size (default: 40):
python audit.py "C:\path\to\your-project" --batch-size 25
```

### 2. Fast Tree & Line Metrics (`project_metrics.py`)

For a lightweight overview of file counts and lines of code without requiring Radon or ESLint:

```powershell
python project_metrics.py "C:\path\to\your-project"
```

---

## Output Reports

Each audit creates a dedicated directory inside `reports/` (e.g., `reports/ProjectName_20261029_010000/`) containing:

- **`report.md`**: Human-readable markdown audit summary with tables.
- **`metrics.json`**: Full hierarchical data dump for automation and CI/CD ingestion.
- **`files.csv`**: File-by-file metrics spreadsheet ready for Excel/data visualization.
- **`functions.csv`**: Python functions sorted by highest cyclomatic complexity.
- **`issues.csv`**: Lint issues with line numbers, severity, and rule names.

---

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

This project is licensed under the [MIT License](LICENSE).
