# CodeAudit 2.2 — Inżynieria Jakości Kodu i Audyt Bezpieczeństwa

<p align="center">
  <a href="https://github.com/mystyc22/CodeAudit/blob/main/LICENSE"><img src="https://img.shields.io/badge/licencja-MIT-green.svg" alt="Licencja: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://nodejs.org/"><img src="https://img.shields.io/badge/node-18+-339933.svg?logo=node.js&logoColor=white" alt="Node 18+"></a>
  <img src="https://img.shields.io/badge/offline-100%25%20Zero--CDN-orange.svg" alt="100% Offline Zero-CDN">
  <img src="https://img.shields.io/badge/i18n-EN%20%7C%20PL%20%7C%20ZH-8A2BE2.svg" alt="Języki: EN | PL | ZH">
  <a href="https://github.com/mystyc22/CodeAudit/issues"><img src="https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat" alt="Współpraca mile widziana"></a>
</p>

<p align="center">
  <b><a href="README.md">🇺🇸 English</a></b> • <b><a href="README_PL.md">🇵🇱 Polski</a></b>
</p>

> **Niezależny pakiet statycznej analizy jakości oprogramowania, audytu bezpieczeństwa i historii Git dla projektów Python oraz JavaScript/TypeScript.**  
> Generuje rozbudowane raporty Markdown, zlokalizowane arkusze CSV z kodowaniem UTF-8 BOM pod program Excel oraz **interaktywny pulpit nawigacyjny HTML działający w 100% offline** w trzech językach: polskim, angielskim i uproszczonym chińskim.

---

## ⚡ Szybki start w 60 sekund

Uruchom pełny audyt w 3 prostych krokach:

```powershell
# 1. Zainstaluj analizatory Python
python -m pip install radon lizard vulture bandit pip-audit

# 2. Zainstaluj ESLint i pluginy (generuje folder node_modules)
cd C:\Tools\CodeAudit
npm install

# 3. Uruchom audyt na dowolnym badanym projekcie (tryb ściśle tylko do odczytu)
.\Run-CodeAudit.ps1 -ProjectPath "C:\sciezka\do\twojego-projektu"
```

*Raport otworzy się automatycznie w pliku `C:\Tools\CodeAudit\reports\<NazwaProjektu>_<znacznik_czasu>\report.html`!*

---

## 🌟 Dlaczego CodeAudit?

- 🛡️ **Ściśle tylko do odczytu (Read-Only)**: CodeAudit nigdy nie modyfikuje kodu źródłowego, nie uruchamia `eslint --fix`, nie przełącza gałęzi Git ani nie wykonuje zapytań sieciowych. Wszystkie raporty i metryki zapisywane są na zewnątrz analizowanego projektu.
- 🔌 **100% Offline (Zero-CDN)**: Interaktywny pulpit HTML osadza bibliotekę Apache ECharts lokalnie (`vendor/echarts.min.js`). Działa bez dostępu do Internetu, w odizolowanych sieciach firmowych (air-gapped).
- 🌐 **Natywna wielojęzyczność (PL / EN / ZH)**: Przełącznik języka w nagłówku pliku HTML jednym kliknięciem bez przeładowania + dedykowane raporty Markdown (`report_pl.md`, `report_en.md`, `report_zh.md`) oraz arkusze CSV z UTF-8 BOM.
- 📊 **Kompletny przekrój inżynieryjny**:
  - **Złożoność i utrzymywalność**: Złożoność cyklomatyczna CC (Radon dla Pythona, Lizard dla JS/TS), Indeks Utrzymywalności (MI) oraz pełny zestaw 12 metryk Halsteada.
  - **Linter i standardy**: ESLint 9 (flat config) z SonarJS, React i React Hooks.
  - **Bezpieczeństwo**: Statyczny skaner podatności Bandit (zamaskowane hasła) oraz wykrywanie podatności CVE zależności przez Pip-Audit.
  - **Dług techniczny**: Wykrywanie martwego kodu (Vulture), heurystyka zduplikowanych bloków (okno 8 linii) oraz graf importów z detekcją cykli.
  - **Historia Git**: Analiza churn (pliki najczęściej zmieniane), tempo prac (miesięczne/tygodniowe) i aktywność autorów.
- 🔄 **Automatyczne porównanie z bazą**: Automatycznie porównuje metryki z poprzednim pomiarem `metrics.json`.

---

## 1. Wymagania

- **Python 3.10+** oraz **Radon 6.x**:
  ```bash
  python -m pip install radon
  ```
- **Node.js (v18+)** oraz **Git** dostępny w ścieżce PATH:
  ```bash
  git --version
  ```
- **Rozszerzone analizatory (Zalecane)**:
  ```bash
  python -m pip install lizard vulture bandit pip-audit
  ```
  *(Każda z tych bibliotek jest opcjonalna. W przypadku braku któregoś narzędzia odpowiednia sekcja raportu oznaczy się jako „niedostępna”, a audyt wykona się bez przeszkód).*
- **ESLint 9 i dodatki** (instalowane wewnątrz folderu `CodeAudit`):
  ```bash
  cd C:\Tools\CodeAudit
  npm install
  ```

---

## 2. Architektura i komponenty

- `audit.py`: Główny silnik inwentaryzacji plików, metryk Radon i przetwarzania ESLint.
- `i18n.py`: Modułowy silnik lokalizacyjny dla raportów Markdown, arkuszy CSV i pulpitu HTML.
- `audit_reporting.py`: Obliczanie wskaźnika utrzymywalności, porównanie z poprzednim audytem i lista modułów wrażliwych.
- `html_dashboard.py` / `dashboard_extra.py` / `dashboard_charts.js`: Samodzielny pulpit HTML offline z wykresami ECharts.
- `extra_analyzers.py`: Integracja analizatorów: Lizard, Vulture, Bandit, Pip-Audit, duplikacja i graf zależności.
- `audit_insights.py`: Wnioski zarządcze, radar zdrowia kodu, śledzenie trendu i macierz plików.
- `git_history.py`: Lokalne statystyki repozytorium Git, analiza churn i tempo rozwoju kodu.
- `Run-CodeAudit.ps1`: Skrypt uruchomieniowy dla systemu Windows PowerShell.
- `audit-settings.json`: Jawne reguły wyłączania plików z audytu.
- `project_metrics.py`: Lekki, bezdependencyjny skrypt zapasowy do szybkiego zliczania LOC i plików.

---

## 3. Uruchomienie

### PowerShell (zalecane na Windows)

```powershell
cd C:\Tools\CodeAudit
.\Run-CodeAudit.ps1 -ProjectPath "C:\sciezka\do\twojego-projektu"
```

Jeśli Windows blokuje uruchomienie skryptu:
```powershell
Unblock-File "C:\Tools\CodeAudit\Run-CodeAudit.ps1"
```

### Bezpośrednio przez Pythona

```powershell
python audit.py "C:\sciezka\do\twojego-projektu"
```

---

## 4. Parametry i przełączniki CLI

| Przełącznik PowerShell | Flaga CLI Python | Opis |
|---|---|---|
| `-ProjectPath <path>` | `<project>` (pozycyjny) | Ścieżka do badanego projektu (wymagana) |
| `-PipAudit` | `--pip-audit` | Audytuje zależności pod kątem luk CVE (**wymaga internetu**) |
| `-Requirements <pliki...>` | `--requirements <pliki...>` | Ścieżka do pliku z przypiętymi wersjami pakietów |
| `-Previous <path>` | `--previous <path>` | Wskazuje konkretny plik `metrics.json` do porównania |
| `-NoPrevious` | `--no-previous` | Pomija porównanie z poprzednim audytem |
| `-NoGit` | `--no-git` | Wyłącza analizę historii Git (dla dużych repozytoriów) |
| `-GitMaxCommits <int>` | `--git-max-commits <int>` | Maksymalna liczba skanowanych commitów (domyślnie: 800, max: 5000) |
| `-NoEslint` | `--no-eslint` | Pomija analizę statyczną ESLint dla plików JS/JSX |
| `-NoExtras` | `--no-extras` | Wyłącza rozszerzone analizatory 2.2 (szybki przebieg w stylu 2.1) |
| `-NoBandit` | `--no-bandit` | Wyłącza skaner bezpieczeństwa Bandit |
| `-NoVulture` | `--no-vulture` | Wyłącza wykrywanie martwego kodu Vulture |
| `-NoLizard` | `--no-lizard` | Wyłącza analizę złożoności Lizard dla JS/TS |
| `-NoDuplication` | `--no-duplication` | Wyłącza heurystyczne wykrywanie duplikacji kodu |
| `-NoDeps` | `--no-deps` | Wyłącza generowanie grafu zależności modułów |
| `-SkipVarInventory` | `--skip-var-inventory` | Pomija inwentaryzację rozmiaru folderu `var/` |
| *(Tylko CLI)* | `--out <path>` | Wskazuje własny katalog wyjściowy na raporty |

---

## 5. Audyt bezpieczeństwa zależności (`-PipAudit` i `-Requirements`)

### Jak działa Pip-Audit
- `pip-audit` odpytuje publiczne bazy danych PyPI / OSV w celu wykrycia znanych luk CVE.
- **Wymaga dostępu do Internetu**: Jest to jedyna funkcja CodeAudit, która łączy się z siecią.
- **Wymaga przypiętych wersji**: Skaner musi znać dokładną wersję pakietu (np. `fastapi==0.115.0`). Wpisy ogólne (np. `fastapi>=0.100`) nie mogą zostać jednoznacznie ocenione.

### Jak wygenerować plik z przypiętymi wersjami (`pinned-requirements.txt`)

Jeśli badany projekt **nie ma przypiętych wersji** w pliku `requirements.txt` lub **w ogóle nie posiada takiego pliku** (np. używa poetry, `pyproject.toml` lub środowiska venv), możesz utworzyć zewnętrzny plik bez modyfikowania badanego projektu:

#### Scenariusz 1: Projekt posiada `requirements.txt`, ale BEZ numerów wersji
Wyciągnij nazwy pakietów, dopasuj je do aktualnie zainstalowanych wersji w Pythonie i zapisz poza projektem:

```powershell
# 1. Przejdź do folderu badanego projektu
cd "C:\sciezka\do\twojego-projektu"

# 2. Pobierz same nazwy pakietów (odrzucając znaki <, >, ==, itp.)
$names = Get-Content requirements.txt | ForEach-Object { ($_ -split '[<>=!~\[; ]')[0] } | Where-Object { $_ }

# 3. Zbuduj listę z zainstalowanymi wersjami z pip freeze i zapisz w CodeAudit
python -m pip freeze | Select-String -Pattern ("^(" + ($names -join '|') + ")==") | ForEach-Object { $_.Line } | Out-File -Encoding utf8 C:\Tools\CodeAudit\pinned-requirements.txt
```

#### Scenariusz 2: Projekt NIE POSIADA pliku `requirements.txt`
1. **Gdy projekt korzysta ze środowiska wirtualnego (`venv`)**:
   Aktywuj najpierw venv, a następnie wyeksportuj aktywne pakiety:
   ```powershell
   # W katalogu projektu (aktywuj środowisko):
   .\.venv\Scripts\Activate.ps1
   python -m pip freeze | Out-File -Encoding utf8 C:\Tools\CodeAudit\pinned-requirements.txt
   ```

2. **Gdy korzystasz ze środowiska globalnego**:
   Wyeksportuj wszystkie pakiety do pliku:
   ```powershell
   python -m pip freeze | Out-File -Encoding utf8 C:\Tools\CodeAudit\pinned-requirements.txt
   ```

### Uruchomienie audytu z plikiem zależności
Wskaż przełączniki `-PipAudit` i `-Requirements`:

```powershell
cd C:\Tools\CodeAudit
.\Run-CodeAudit.ps1 -ProjectPath "C:\sciezka\do\twojego-projektu" -PipAudit -Requirements C:\Tools\CodeAudit\pinned-requirements.txt
```

---

## 6. Raporty i eksporty wielojęzyczne (PL, EN, ZH)

CodeAudit generuje kompletne raporty audytowe równocześnie w **3 językach**: polskim, angielskim i uproszczonym chińskim.

### 6.1 Interaktywny Dashboard HTML offline (`report.html`)
- **Przełącznik 3 języków (PL / EN / ZH)**: Wygodne przyciski w górnym pasku nawigacyjnym pozwalają natychmiast zmienić język całego interfejsu bez przeładowywania strony.
- **100% Offline (Zero CDN)**: Biblioteka Apache ECharts jest osadzona lokalnie w pliku HTML (`vendor/echarts.min.js`), dzięki czemu pulpit działa w odciętych środowiskach bez dostępu do sieci.
- **Dynamiczna lokalizacja**: Przełączenie języka aktualizuje etykiety nawigacji, sekcje, karty KPI, nagłówki tabel, rekomendacje audytowe oraz wykresy ECharts.
- **Modułowa architektura i18n (`i18n.py`)**: Ułatwia dodawanie kolejnych języków poprzez rejestrację słowników tłumaczeń.

### 6.2 Raporty Markdown (`.md`)
Generowane w dedykowanych plikach językowych:
- `report.md`: Raport domyślny (język angielski).
- `report_pl.md`: Raport w języku polskim (*Raport jakości i długu technicznego*).
- `report_en.md`: Raport w języku angielskim (*Code Quality & Maintainability Audit*).
- `report_zh.md`: Raport w języku chińskim (*代码质量与可维护性技术审计报告*).

### 6.3 Zestawienia CSV w 3 językach (`.csv`)
Wszystkie pliki CSV generowane są w wersjach językowych z przetłumaczonymi nagłówkami kolumn i wartościami kategorycznymi (wagi alertów, rodzaje funkcji, priorytety). Zapisywane w formacie **UTF-8 z BOM (`utf-8-sig`)**, co gwarantuje natychmiastowe otwarcie w programie Microsoft Excel:

| Zestaw danych | Warianty językowe | Opis |
|---|---|---|
| `files.csv` | `files_pl.csv`, `files_en.csv`, `files_zh.csv` | Zestawienie każdego analizowanego pliku z metrykami CC, MI i Halstead |
| `functions.csv` | `functions_pl.csv`, `functions_en.csv`, `functions_zh.csv` | CC i klasy A–F wszystkich funkcji i metod Python |
| `js_functions.csv` | `js_functions_pl.csv`, `_en.csv`, `_zh.csv` | Złożoność (CC, NLOC, parametry) funkcji JS/TS — Lizard |
| `issues.csv` | `issues_pl.csv`, `issues_en.csv`, `issues_zh.csv` | Pełne zgłoszenia ESLint / SonarJS / React Hooks |
| `security_bandit.csv` | `security_bandit_pl.csv`, `_en.csv`, `_zh.csv` | Znaleziska Bandit (podejrzane hasła zamaskowane jako `***`) |
| `security_dependencies.csv` | `security_dependencies_pl.csv`, `_en.csv`, `_zh.csv` | Podatności CVE zależności — Pip-Audit |
| `dead_code.csv` | `dead_code_pl.csv`, `dead_code_en.csv`, `dead_code_zh.csv` | Kandydaci na martwy kod — Vulture |
| `duplication.csv` | `duplication_pl.csv`, `duplication_en.csv`, `duplication_zh.csv` | Największe zduplikowane bloki kodu |
| `dependencies.csv` | `dependencies_pl.csv`, `_en.csv`, `_zh.csv` | Krawędzie grafu importów między modułami |
| `sensitive_files.csv` | `sensitive_files_pl.csv`, `_en.csv`, `_zh.csv` | Lista modułów krytycznych domenowo do ręcznego review |
| `git_commits.csv` | `git_commits_pl.csv`, `git_commits_en.csv`, `git_commits_zh.csv` | Historia commitów w oknie analizy |
| `git_hotspots.csv` | `git_hotspots_pl.csv`, `git_hotspots_en.csv`, `git_hotspots_zh.csv` | Najczęściej zmieniane pliki kodu i churn |
| `git_monthly.csv` / `weekly.csv` | `git_monthly_*.csv`, `git_weekly_*.csv` | Miesięczne i tygodniowe statystyki przyrostu i usuwania kodu |
| `metrics.json` | — | Pełny zrzut metryk do automatycznych porównań między audytami |

---

## 7. Zakres i wyłączenia (`audit-settings.json`)

- Folder `var/` jest liczony **osobno** (liczba plików, zajęte miejsce, podkatalogi), ale nie jest analizowany przez Radon, ESLint ani wskaźnik jakości.
- Standardowe środowiska i buildy (`node_modules`, `.venv`, `.git`, `.work`, `dist`, `build`, `__pycache__`) są ignorowane domyślnie.
- Dodatkowe pliki lub foldery można wykluczyć w `audit-settings.json`:

```json
{
  "excluded_files": [
    {
      "pattern": "src/legacy/*.py",
      "reason": "Archiwalny podsystem zaplanowany do usunięcia"
    }
  ]
}
```

---

## 8. Wytyczne interpretacyjne i ograniczenia

- **Indeks utrzymywalności (Maintainability Score)**: Własny, jawny wskaźnik pomocniczy (CC Python + MI Python + priorytetowe alerty ESLint). Nie jest certyfikatem bezpieczeństwa ani Clean Architecture.
- **Ranking wrażliwych plików**: Lista rekomendacji ręcznego przeglądu — sama obecność w rankingu nie dowodzi błędu w kodzie.
- **Bandit i Vulture**: Statyczne heurystyki mogą generować fałszywe alarmy na dynamicznych wzorcach frameworków.
- **Git Churn**: Mierzy tempo zmian w commitach, a nie aktualną liczbę linii kodu (LOC).

---

## Współpraca

Propozycje ulepszeń, zgłoszenia problemów (Issues) oraz Pull Requesty są mile widziane!

## Licencja

Projekt udostępniany jest na warunkach otwartoźródłowej licencji [MIT License](LICENSE).
