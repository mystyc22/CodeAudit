# CodeAudit

A single-file, zero-dependency Python script that recursively scans any project directory and produces a detailed Markdown report with file counts, sizes, and line counts — broken down by file type and top-level directory.

**CodeAudit does not require Git.** It reads the filesystem directly and never modifies any file.

---

## Features

- **Single file, no dependencies** — uses only the Python standard library (Python 3.10+).
- **Read-only** — never writes, deletes, or modifies anything in the scanned directory.
- **Git-independent** — works on any directory, whether or not it is a Git repository.
- **Smart filtering** — automatically skips common non-source directories (`node_modules`, `.venv`, `__pycache__`, `build`, `dist`, `.git`, etc.) and temporary files.
- **File classification** — categorises files into 14 groups: Python production, Python tests, frontend JS/TS, CSS/SCSS, HTML, shell scripts, documentation, config, assets, databases, and more.
- **Line counting** — counts physical lines and non-empty lines for all code and test files.
- **Test detection** — recognises test files by directory name (`tests/`, `__tests__/`) and naming conventions (`*.test.js`, `*.spec.ts`, `test_*.py`).
- **Markdown output** — prints a structured report you can paste directly into GitHub issues, PRs, or documentation.

## Requirements

- **Python 3.10** or newer.

## Installation

No installation needed. Just download `project_metrics.py`:

```bash
curl -O https://raw.githubusercontent.com/mystyc22/CodeAudit/main/project_metrics.py
```

Or clone the repository:

```bash
git clone https://github.com/mystyc22/CodeAudit.git
```

## Usage

### Option 1 — Run from inside the project directory

```bash
cd /path/to/your-project
python project_metrics.py
```

### Option 2 — Pass the project path as an argument

```bash
python project_metrics.py /path/to/your-project
```

### Windows

```powershell
python project_metrics.py C:\Users\me\Projects\my-app
```

### Save the report to a file

```bash
python project_metrics.py > metrics-report.md
```

## Output

The script prints a Markdown report to `stdout` with the following sections:

### Header — Summary statistics

```
# CodeAudit - project metrics (filesystem scan)

**Directory:** `/home/user/my-project`
**Method:** no Git; recursive walk, skipping dependencies/cache/build/var/.work.
**LOC:** physical lines, including blanks and comments.

**Files: 1 284 | Subdirectories: 187**
**Code + test lines: 94 320**
(non-empty: 78 540; excludes docs, databases, graphics, and config).
**Production/tools code: 71 200 | Tests: 23 120**
```

### Section A — Breakdown by file type

| Category | Files | Size (MB) | Physical lines | Non-empty |
|---|---:|---:|---:|---:|
| Python production (src/) | 312 | 1.85 | 28 400 | 24 100 |
| Python tests (tests/) | 198 | 1.12 | 18 320 | 15 200 |
| Frontend JS/TS - code | 140 | 0.94 | 12 800 | 10 600 |
| ... | ... | ... | ... | ... |

### Section B — Breakdown by top-level directory

| Directory | Files (recursive) | Size (MB) | Code + test lines |
|---|---:|---:|---:|
| `src` | 420 | 2.50 | 38 200 |
| `tests` | 260 | 1.40 | 22 800 |
| ... | ... | ... | ... |

## File Classification Rules

| Category | Extensions | Rule |
|---|---|---|
| Python production | `.py` | Files under `src/` |
| Python tests | `.py` | Files under `tests/` |
| Python other | `.py` | All other `.py` files |
| Frontend JS/TS code | `.js` `.jsx` `.mjs` `.cjs` `.ts` `.tsx` | Files under configured `FRONTEND_DIRS` (not tests) |
| Frontend JS/TS tests | `.js` `.jsx` `.mjs` `.cjs` `.ts` `.tsx` | Files matching test patterns (see below) |
| JS/TS other | `.js` `.jsx` `.mjs` `.cjs` `.ts` `.tsx` | All other JS/TS files |
| Styles | `.css` `.scss` `.sass` | — |
| HTML | `.html` `.htm` | — |
| Scripts | `.ps1` `.bat` `.cmd` `.sh` | — |
| Documentation | `.md` `.mdx` `.rst` | — |
| Config | `.json` `.yaml` `.yml` `.toml` `.ini` `.cfg` `.xml` | Also `.gitignore`, `.gitattributes`, `requirements.txt` |
| Assets | `.svg` `.png` `.jpg` `.jpeg` `.webp` `.avif` `.gif` `.ico` `.drawio` `.woff` `.woff2` `.ttf` `.gz` | — |
| Databases | `.db` `.sqlite` `.sqlite3` | — |
| Other | everything else | — |

### Test file detection (JS/TS)

A JavaScript/TypeScript file is classified as a test if:

- It is inside a `tests/` or `__tests__/` directory, **or**
- Its name ends with `.test`, `.spec`, or `.browser` (before the extension), **or**
- Its name starts with `test_` or `spec_`.

## Skipped directories

The following directories are always skipped:

`.git`, `node_modules`, `.venv`, `venv`, `.venv-semantic`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.tox`, `.nox`, `.next`, `.turbo`, `.parcel-cache`, `dist`, `build`, `coverage`, `htmlcov`, `.coverage_html`, `var`, `.work`, `.cache`, `.idea`, `.vscode-test`

Symbolic links (both files and directories) are also skipped.

## Customisation

### Frontend directories

If your project has frontend application directories, add them to the `FRONTEND_DIRS` set at the top of the script:

```python
FRONTEND_DIRS: set[str] = {"client-app", "web-ui", "frontend"}
```

This tells the classifier to treat JS/TS files under those directories as frontend code (or frontend tests if they match test naming patterns).

### Skip lists

Edit the sets at the top of the script to add or remove:

- `SKIP_DIRS` — directories to skip entirely
- `SKIP_NAMES` — specific filenames to skip
- `SKIP_SUFFIXES` — file extensions to skip

### Category labels

Modify the `LABELS` dictionary to change how categories are named in the report.

## How it works

1. Walks the directory tree using `os.walk()` (top-down, no symlink following).
2. Filters out skipped directories, filenames, and extensions.
3. Classifies each remaining file into one of 14 categories.
4. For code/test categories, opens the file and counts physical and non-empty lines.
5. Aggregates statistics by category and by top-level directory.
6. Prints a formatted Markdown report to stdout.

## Limitations

- **Physical lines only** — counts all lines including blanks and comments; does not compute logical SLOC.
- **Not language-aware** — classification is based on file extensions and path conventions, not code parsing.
- **UTF-8 assumed** — files are read as UTF-8 with error replacement; binary files in code categories may produce inflated line counts.
- **Python layout convention** — assumes `src/` for production code and `tests/` for test code. Projects with a different layout can adjust the `classify()` function.

## Contributing

Contributions are welcome! Feel free to open issues and pull requests.

## License

MIT License. See [LICENSE](LICENSE) for details.
