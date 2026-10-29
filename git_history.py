"""Offline, local, read-only Git inspection for CodeAudit.

Never fetch/pull/reset/checkout, never execute hooks, and never ask Git to write an index lock.
Git history is intentionally bounded; churn is not equivalent to present LOC.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import os
import subprocess

CODE_EXT = {'.py', '.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx', '.mts', '.cts',
            '.css', '.scss', '.sass', '.less', '.html', '.htm', '.ps1', '.bat', '.cmd',
            '.sh', '.sql', '.graphql', '.gql', '.vue', '.svelte'}
IGNORED = {'var', 'node_modules', 'dist', 'build', '.work', '.venv', 'venv',
           'env', '__pycache__', '.pytest_cache', 'coverage', 'vendor', 'htmlcov'}


def source_path(path, exclusions):
    normalized = path.replace('\\', '/').lstrip('./')
    parts = normalized.lower().split('/')
    if any(part in IGNORED for part in parts[:-1]):
        return False
    if normalized.casefold() in {str(x.get('path', '')).casefold() for x in exclusions}:
        return False
    return True


def git_output(root: Path, args, timeout=90, binary=False):
    env = dict(os.environ)
    env['GIT_OPTIONAL_LOCKS'] = '0'
    env['GIT_TERMINAL_PROMPT'] = '0'
    cmd = ['git', '-c', 'core.quotepath=false', '-C', str(root), *args]
    result = subprocess.run(cmd, capture_output=True, check=False, timeout=timeout,
                            env=env)
    if result.returncode != 0:
        stderr = result.stderr.decode('utf-8', errors='replace')[:320].strip()
        raise RuntimeError(f"git {' '.join(args[:3])} ({result.returncode}): {stderr}")
    return result.stdout if binary else result.stdout.decode('utf-8', errors='replace').strip()


def scan_git(root: Path, files: list[dict], exclusions: list[dict], max_commits: int = 800, disabled=False) -> dict:
    result = {
        'status': 'disabled' if disabled else 'not_repository',
        'repository_root': None, 'head': None, 'branch': None, 'head_date': None,
        'tracked_files': 0, 'tracked_source_files': 0, 'working_copy_source_files': len(files),
        'tracked_file_categories': {}, 'working_copy_untracked_files': None,
        'changed_tracked_files': None, 'git_objects': {}, 'git_metadata_files': None,
        'git_metadata_bytes': None,
        'commits_analyzed': 0, 'commits_limit': max_commits,
        'history_may_be_truncated': False, 'commits_total_reachable': None,
        'first_commit_date_in_window': None, 'latest_commit_date_in_window': None,
        'authors': [], 'timeline_monthly': [], 'timeline_weekly': [], 'commits': [], 'all_changed_files': [],
        'top_changed_files': [], 'recent_commits': [], 'line_additions': 0,
        'line_deletions': 0, 'net_line_changes': 0, 'source_commits': 0,
        'notes': [],
    }
    if disabled:
        return result
    try:
        root_of_git = Path(git_output(root, ['rev-parse', '--show-toplevel'])).resolve()
        if root_of_git != root.resolve():
            result['status'] = 'nested_project'
            result['notes'].append('Ścieżka projektu nie jest katalogiem głównym repozytorium; nie analizujemy nadrzędnego Git.')
            return result
        result['repository_root'] = str(root_of_git)
        result['head'] = git_output(root, ['rev-parse', 'HEAD'])
        result['branch'] = git_output(root, ['branch', '--show-current']) or '(detached HEAD)'
        result['head_date'] = git_output(root, ['log', '-1', '--format=%aI'])
        result['status'] = 'complete'
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result['notes'].append(str(exc))
        return result

    try:
        tracked = git_output(root, ['ls-files', '-z', '--cached'], binary=True).decode('utf-8', errors='replace').split('\0')
        tracked_set = {p.replace('\\', '/') for p in tracked if p}
        result['tracked_files'] = len(tracked_set)
        cats = Counter()
        for p in tracked_set:
            if source_path(p, exclusions):
                cats[Path(p).suffix.lower() or '(bez rozszerzenia)'] += 1
        result['tracked_file_categories'] = dict(cats.most_common(25))
        result['tracked_source_files'] = sum(cats.values())
        result['working_copy_untracked_files'] = sum(
            f['path'] not in tracked_set for f in files)
        changed = git_output(root, ['diff', '--name-only', '-z', 'HEAD'], binary=True).decode('utf-8', errors='replace').split('\0')
        result['changed_tracked_files'] = sum(bool(p) and source_path(p, exclusions) for p in changed)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result['notes'].append(f'Statystyki drzewa Git: {exc}')
        result['status'] = 'partial'

    try:
        objects = git_output(root, ['count-objects', '-v'], timeout=60)
        result['git_objects'] = dict(item.split(': ', 1) for item in objects.splitlines() if ': ' in item)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result['notes'].append(f'Obiekty Git: {exc}')
    # Physical .git file count is optional and can include Git's metadata; never inspect contents.
    gitfolder = root / '.git'
    try:
        if gitfolder.is_dir():
            count = size = 0
            for base, subdirs, filenames in os.walk(gitfolder, followlinks=False):
                subdirs[:] = [name for name in subdirs if not (Path(base) / name).is_symlink()]
                for name in filenames:
                    file = Path(base) / name
                    if file.is_symlink():
                        continue
                    try:
                        size += file.stat().st_size
                        count += 1
                    except OSError:
                        continue
            result['git_metadata_files'] = count
            result['git_metadata_bytes'] = size
        elif gitfolder.is_file():
            result['git_metadata_files'] = 1
            result['git_metadata_bytes'] = gitfolder.stat().st_size
            result['notes'].append('Worktree: .git to wskaźnik do katalogu metadanych, nie pełny katalog.')
    except OSError as exc:
        result['notes'].append(f'Metadane .git: {exc}')

    try:
        n = min(max(1, int(max_commits)), 5000)
        # Keep Git from silently quoting non-ASCII paths. Do not use --all: only current HEAD lineage.
        log = git_output(root, [
            'log', '--no-merges', '--no-renames', f'--max-count={n}',
            '--format=%x1e%H%x1f%aI%x1f%an%x1f%s', '--numstat', '--', '.',
            ':(exclude)var',
        ], timeout=240)
        months, weeks, authors, touched = defaultdict(Counter), defaultdict(Counter), Counter(), defaultdict(Counter)
        additions = removals = 0
        commit_by_hash = {}
        for block in log.split('\x1e'):
            if not block.strip():
                continue
            rows = block.strip('\r\n').splitlines()
            if not rows or '\x1f' not in rows[0]:
                continue
            header = rows[0].split('\x1f', 3)
            if len(header) != 4:
                continue
            sha, date, author, subject = header
            try:
                dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                week = f'{dt.isocalendar().year}-W{dt.isocalendar().week:02}'
                month = dt.strftime('%Y-%m')
            except ValueError:
                month = date[:7]
                week = date[:10]
            stat = {'sha':sha, 'date':date, 'author':author, 'subject':subject[:200],
                    'files':0, 'additions':0, 'deletions':0, 'source_files':0}
            for line in rows[1:]:
                bits = line.split('\t', 2)
                if len(bits) != 3:
                    continue
                a, d, path = bits
                if not source_path(path, exclusions):
                    continue
                if a == '-' or d == '-':
                    continue  # binary artifacts
                try:
                    na, nd = int(a), int(d)
                except ValueError:
                    continue
                stat['files'] += 1
                if Path(path).suffix.lower() in CODE_EXT:
                    stat['source_files'] += 1
                    stat['additions'] += na
                    stat['deletions'] += nd
                    touched[path]['commits'] += 1
                    touched[path]['added'] += na
                    touched[path]['deleted'] += nd
            months[month]['commits'] += 1
            weeks[week]['commits'] += 1
            authors[author] += 1
            if stat['source_files']:
                months[month]['source_commits'] += 1
                weeks[week]['source_commits'] += 1
                months[month]['additions'] += stat['additions']
                months[month]['deletions'] += stat['deletions']
                weeks[week]['additions'] += stat['additions']
                weeks[week]['deletions'] += stat['deletions']
                additions += stat['additions']
                removals += stat['deletions']
                result['source_commits'] += 1
            commit_by_hash[sha] = stat
        commits = list(commit_by_hash.values())
        result['commits_analyzed'] = len(commits)
        result['history_may_be_truncated'] = len(commits) >= n
        result['line_additions'], result['line_deletions'] = additions, removals
        result['net_line_changes'] = additions - removals
        result['first_commit_date_in_window'] = commits[-1]['date'] if commits else None
        result['latest_commit_date_in_window'] = commits[0]['date'] if commits else None
        result['authors'] = [{'name':name, 'commits':qty} for name,qty in authors.most_common(15)]
        result['timeline_monthly'] = [{'month':k, **v} for k,v in sorted(months.items())]
        result['timeline_weekly'] = [{'week':k, **v} for k,v in sorted(weeks.items())]
        result['commits'] = commits
        result['recent_commits'] = commits[:25]
        result['all_changed_files'] = [
            {'file':k, 'commits':v['commits'], 'additions':v['added'],
             'deletions':v['deleted'], 'churn':v['added'] + v['deleted']}
            for k,v in sorted(touched.items(), key=lambda x:-(x[1]['added']+x[1]['deleted']))
        ]
        result['top_changed_files'] = result['all_changed_files'][:80]
        result['notes'].append('Git log: tylko aktualna linia historii HEAD, bez merge commitów; limit ostatnich commitów.')
        result['notes'].append('Linie dodane/usunięte to churn z diffów, nie aktualny LOC; nie obejmuje lokalnych zmian bez commitu.')
        if result['history_may_be_truncated']:
            result['notes'].append('Historia ograniczona limitem; zwiększ --git-max-commits, aby objąć starsze commity.')
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result['status'] = 'partial'
        result['notes'].append(f'Historia Git: {exc}')
    return result
