# CodeAudit 2.2 — Python, React, JavaScript, bezpieczeństwo i lokalna historia Git

CodeAudit to niezależny analizator działający na Windows. **Nie modyfikuje kodu analizowanej aplikacji, nie uruchamia `eslint --fix`, nie wykonuje `git fetch/pull/reset` ani nie korzysta z sieci.** Tworzy raporty wyłącznie we własnym `C:\Tools\CodeAudit\reports\`.

## 1. Wymagania

- Python 3.10+ oraz Radon 6.x: `python -m pip install radon`
- Node.js i npm, Git w PATH: `git --version`
- **Nowe w 2.2 (zalecane):** `python -m pip install lizard vulture bandit pip-audit`. Każda z tych bibliotek jest opcjonalna — gdy jej brak, odpowiednia sekcja raportu pokazuje „niedostępne”, a audyt działa dalej.
- ESLint 9 oraz dodatki (już zainstalowane w `C:\Tools\CodeAudit`):

```powershell
cd C:\Tools\CodeAudit
npm install --save-dev eslint@9 @eslint/js@9 eslint-plugin-sonarjs eslint-plugin-react eslint-plugin-react-hooks globals
```

**Nie kopiuj `node_modules` z ZIP.** Własną instalację zachowaj. Biblioteka wykresów Apache ECharts jest dołączona w `vendor\echarts.min.js` i zostaje **osadzona w `report.html`**, więc raport nadal działa całkowicie offline (bez CDN). Nie trzeba robić `npm install echarts`.

## 2. Aktualizacja z CodeAudit 1.0

Wypakuj pliki ZIP bezpośrednio do `C:\Tools\CodeAudit` i potwierdź nadpisanie plików skryptów (nie usuwaj `package.json`, `package-lock.json` ani `node_modules`). Nowe pliki:

- `audit.py` — silnik inwentaryzacji, Radon i ESLint.
- `audit_reporting.py` — ocena, porównanie z poprzednim audytem i wykazy wrażliwych plików.
- `html_dashboard.py` — interaktywny raport offline; `dashboard_extra.py` i `dashboard_charts.js` — nowe sekcje i wykresy 2.2.
- `extra_analyzers.py` — lizard, vulture, bandit, pip-audit, duplikacja, graf zależności; `audit_insights.py` — radar, trend, streszczenie, macierz plików.
- `vendor\echarts.min.js` — biblioteka wykresów osadzana w raporcie.
- `git_history.py` — lokalne statystyki Git, historia przyrostów i ubytków kodu.
- `audit-settings.json` — lista plików wyłączonych z analizy.
- `eslint.config.mjs` — konfiguracja ESLint.
- `Run-CodeAudit.ps1` — wygodny skrypt PowerShell.

## 3. Uruchomienie

```powershell
cd C:\Tools\CodeAudit
.\Run-CodeAudit.ps1 -ProjectPath "C:\Users\osypo\Documents\Kenya_curier"
```

Jeśli Windows oznaczył pobrany skrypt jako plik z internetu i PowerShell odrzuca podpis, **po przeczytaniu i zweryfikowaniu zawartości skryptu** można użyć:

```powershell
Unblock-File "C:\Tools\CodeAudit\Run-CodeAudit.ps1"
```

Alternatywnie uruchom bezpośrednio Pythona:

```powershell
python C:\Tools\CodeAudit\audit.py "C:\Users\osypo\Documents\Kenya_curier"
```

Przebieg wykonuje: szybki skan plików źródłowych, osobną inwentaryzację `var`, Radon, ESLint, lokalne Git, a na końcu zapis raportów.

## 4. Opcje

```powershell
# Porównanie tylko ze wskazanym poprzednim pomiarem
.\Run-CodeAudit.ps1 -ProjectPath "C:\Users\osypo\Documents\Kenya_curier" -Previous "C:\Tools\CodeAudit\reports\Kenya_curier_20261028_015734\metrics.json"

# Pełniejsza historia Git (do 5000 nie-merge commitów)
.\Run-CodeAudit.ps1 -ProjectPath "C:\Users\osypo\Documents\Kenya_curier" -GitMaxCommits 2500

# Bez Git, jeśli repozytorium jest zbyt duże lub Git nie jest zainstalowany
.\Run-CodeAudit.ps1 -ProjectPath "C:\Users\osypo\Documents\Kenya_curier" -NoGit

# Pomiar bazowy bez porównania z poprzednim
.\Run-CodeAudit.ps1 -ProjectPath "C:\Users\osypo\Documents\Kenya_curier" -NoPrevious
```

Bez `-Previous` narzędzie automatycznie używa **jednego ostatniego `metrics.json`** z folderu `reports`, którego nazwa odpowiada nazwie projektu. Porównanie nigdy nie korzysta ze sztywno wpisanej tabeli historycznej. Poprzedni wynik z CodeAudit 1.0 jest przeliczany po odjęciu `var/` i archiwalnego `terminal_ui.py`, by porównanie zakresu było możliwie spójne.

Dodatkowe opcje Python: `python audit.py --help` (`--no-eslint`, `--no-git`, `--git-max-commits`, `--skip-var-inventory`, `--previous`, `--out`, a w 2.2 także `--pip-audit`, `--requirements`, `--no-extras`, `--no-lizard`, `--no-vulture`, `--no-bandit`, `--no-duplication`, `--no-deps`).

### Jak przygotować plik z przypiętymi wersjami (`pinned-requirements.txt`)

`pip-audit` wymaga dokładnie przypiętych wersji (np. `fastapi==0.115.0`), aby sprawdzić podatności w bazach CVE. Jeśli Twój projekt **nie ma numerów wersji** w `requirements.txt` lub **w ogóle nie posiada pliku requirements** (np. używa `pyproject.toml`, poetry lub instalacji ze środowiska venv), możesz utworzyć zewnętrzny plik bez modyfikowania projektu:

#### Scenariusz 1: W projekcie jest `requirements.txt`, ale BEZ numerów wersji
Wyciągnij nazwy pakietów z pliku projektu, dopasuj je do zainstalowanych wersji w Pythonie i zapisz poza projektem:

```powershell
# 1. Wejdź do katalogu projektu
cd "C:\path\to\your-project"

# 2. Pobierz same nazwy pakietów (odrzucając znaki <, >, ==, itp.)
$names = Get-Content requirements.txt | ForEach-Object { ($_ -split '[<>=!~\[; ]')[0] } | Where-Object { $_ }

# 3. Zbuduj listę z zainstalowanymi wersjami z pip freeze i zapisz w CodeAudit
python -m pip freeze | Select-String -Pattern ("^(" + ($names -join '|') + ")==") | ForEach-Object { $_.Line } | Out-File -Encoding utf8 C:\Tools\CodeAudit\pinned-requirements.txt
```

#### Scenariusz 2: W projekcie BRAK pliku `requirements.txt`
1. **Gdy projekt ma własne środowisko wirtualne (`venv`)**:
   Aktywuj najpierw venv, a następnie zrzuć pełną listę aktywnych zależności:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m pip freeze | Out-File -Encoding utf8 C:\Tools\CodeAudit\pinned-requirements.txt
   ```

2. **Gdy korzystasz z globalnego Pythona**:
   Zrzuć wszystkie zainstalowane pakiety do pliku:
   ```powershell
   python -m pip freeze | Out-File -Encoding utf8 C:\Tools\CodeAudit\pinned-requirements.txt
   ```
   *(Ta opcja obejmuje także zależności pośrednie, np. `starlette`, `urllib3`, dając pełny obraz bezpieczeństwa).*

#### Uruchomienie audytu z wygenerowanym plikiem:
```powershell
cd C:\Tools\CodeAudit
.\Run-CodeAudit.ps1 -ProjectPath "C:\path\to\your-project" -PipAudit -Requirements C:\Tools\CodeAudit\pinned-requirements.txt
```

## 5. Raporty i eksporty

Każde uruchomienie tworzy nowy katalog, np. `C:\Tools\CodeAudit\reports\Kenya_curier_20261028_031000\`:

| Plik | Zawartość |
|---|---|
| `report.html` | Interaktywny dashboard, animacje wykresów, filtrowane ryzyka i alerty, historia Git |
| `report.md` | Rozbudowany raport tekstowy, tabele Halsteada, MI, CC, ESLint, Git |
| `metrics.json` | Całe dane pomiaru do porównań między uruchomieniami |
| `files.csv` | Zestawienie każdego analizowanego pliku |
| `functions.csv` | CC i klasy A–F wszystkich funkcji i metod Python |
| `issues.csv` | Pełne zgłoszenia ESLint |
| `sensitive_files.csv` | Lista wrażliwych domenowo i złożonych plików; ręczny triage |
| `git_commits.csv` | Wszystkie przeanalizowane commity (limit domyślnie 800) |
| `git_monthly.csv` | Miesięczne statystyki Git |
| `git_weekly.csv` | Tygodniowe statystyki Git |
| `git_hotspots.csv` | Wszystkie zmieniane pliki kodu i churn w oknie historii |
| `js_functions.csv` | Złożoność (CC, NLOC, parametry) funkcji JS/TS — lizard |
| `security_bandit.csv` | Znaleziska bandit (wartości podejrzanych haseł są zastępowane `***`) |
| `security_dependencies.csv` | Podatności zależności — tylko przy `-PipAudit` |
| `dead_code.csv` | Kandydaci na martwy kod — vulture |
| `duplication.csv` | Największe zduplikowane bloki |
| `dependencies.csv` | Krawędzie grafu importów (kto importuje kogo) |
| `..\history_<projekt>.json` | Historia wyników do wykresu trendu (w folderze `reports`) |

## 6. Zakres i wyłączenia

- `var/` jest liczony **osobno** (liczba plików, zajęte miejsce, podkatalogi), ale nie jest analizowany przez Radon, ESLint ani wskaźnik jakości.
- `terminal_ui.py` (lub inne zdefiniowane pliki) można wyłączyć z audytu w `audit-settings.json`.
- Standardowe środowiska/buildy (`node_modules`, `.venv`, `.git`, `.work`, `dist`, `build`, `__pycache__`) również nie liczą się jako bieżący kod.
- Nie usuwaj katalogu `var`! Wyłączenie dotyczy jedynie audytu.

Dodatkowe pliki można wykluczyć, dopisując regułę z polem `pattern` (może zawierać `*`) i `reason` do `audit-settings.json`.

## 7. Historia Git

Moduł działa tylko wtedy, kiedy wskazany katalog jest **korzeniem lokalnego repozytorium Git**. Analizuje wyłącznie dostępne lokalnie commity bieżącej gałęzi HEAD, bez merge commitów. Domyślnie ostatnich 800 commitów spełniających warunki ścieżki. Zbiera m.in. SHA, autora, temat, datę, liczbę commitów, śledzone pliki, lokalne zmiany, `git count-objects`, rozmiar folderu `.git`, plus/minus linii dla kodu w poszczególnych miesiącach i tygodniach, pliki o największym churn. `var/` i wyłączone TUI nie są uwzględniane w historii kodu. Jeśli folder nie jest repozytorium albo Git nie jest dostępny, audyt kodu działa dalej, a raport wyświetla brak historii Git.

**Churn nie jest obecnym LOC.** Przyrosty liczone z kolejnych commitów nie uwzględniają niezacommitowanych zmian, zmian w merge commitach, binarnych artefaktów ani pełnego historycznego stanu repozytorium. Przy limicie 800 historia może być ucięta.

## 8. Ocena jakości: interpretacja

- `CodeAudit Maintainability Score` to **własny, jawny wskaźnik pomocniczy** (CC Python + MI Python + priorytetowe zgłoszenia ESLint). Nie jest certyfikatem bezpieczeństwa, poprawności finansowej, test coverage ani wynikiem Clean Architecture.
- Ranking „wrażliwe pliki” jest listą do przeglądu na podstawie nazw domenowych, CC, MI, zgłoszeń ESLint, wielkości plików i Git churn. **Sam ranking nie oznacza podatności ani błędu.**
- Radon mierzy SLOC/LLOC i Halstead tylko dla Pythona. ESLint dla JS/JSX/MJS/CJS nie liczy Halsteada; TS/TSX wymaga osobnego parsera.
- Liczba plików testowych / liczba plików produkcyjnych **nie jest** pokryciem testami.
- Równolegle pracujący agent może edytować pliki podczas skanowania; analiza nie stanowi atomowej migawki.
- Szczegółowe wyniki i indeks triage pozwalają podjąć decyzję o przeglądzie. **Nie uruchamiaj automatycznej refaktoryzacji na podstawie samych metryk** w obszarach transakcyjnych/logistycznych.

## 9. Nowości w 2.2

**Dashboard:** streszczenie zarządcze i lista „od czego zacząć”, treemap projektu (kolor wg ryzyka, CC, MI, ESLint, bandit, martwego kodu, duplikacji lub liczby commitów), wykres hotspotów (zmiany × złożoność), radar zdrowia kodu, trend między audytami, graf zależności z cyklami, kalendarz aktywności Git, mapa godzin pracy, okno ze szczegółami pliku (kliknij plik), przycisk **PDF** (druk w jasnej palecie) i przełącznik motywu.

**Nowe pomiary:**

| Narzędzie | Co mierzy | Uwagi |
|---|---|---|
| lizard | CC funkcji JS/JSX/TS/TSX | uzupełnia Radon (tylko Python); `.mts/.cts` nie są obsługiwane |
| vulture | kandydaci na martwy kod Python | wywołania dynamiczne i frameworki dają fałszywe alarmy |
| bandit | bezpieczeństwo kodu Python | działa lokalnie; zgłoszenia w testach nie wchodzą do oceny |
| pip-audit | znane podatności z `requirements*.txt` | **wymaga internetu**, tylko z `-PipAudit`; wymaga przypiętych wersji (`pakiet==1.2.3`); `pyproject.toml` nie jest analizowany |
| duplikacja | powielone bloki (okno 8 znaczących linii) | własna heurystyka, nie zastępuje dedykowanych narzędzi |
| zależności | graf importów, cykle, fan-in/fan-out | własny parser; aliasy ścieżek JS (np. `@/`) nie są rozwiązywane |

**Wskaźnik główny nie zmienił się** (CC Python + MI + ESLint), żeby dało się porównywać audyty z 2.1. Nowe miary widać na radarze, w KPI i w sekcjach; wzory osi radaru są w dashboardzie, w sekcji „Metodologia rozszerzeń”.

**Prywatność raportu:** wartości w komunikatach bandit o twardo zapisanych hasłach (B105–B107) są zastępowane `***`. Komunikaty ESLint (SonarJS) są kopiowane bez zmian — przed udostępnieniem raportu osobom trzecim sprawdź `issues.csv`.

## 10. Możliwe rozszerzenia w przyszłości

Pokrycie testami (`coverage.py` / `pytest-cov`, import gotowego `coverage.xml`), `npm audit` dla zależności JS, dedykowane `jscpd` do duplikacji oraz profilowanie wydajności pozostają osobnymi czynnościami i nie są częścią CodeAudit.
