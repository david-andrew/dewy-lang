"""Scope self-hosting tests to changes since a landing base.

Each test depends on its recorded outputs, imported Python helpers, referenced
fixtures, and the compiler import closure of the modules it names. A driver
that loads the whole compiler depends on the entire compiler directory.
Toolchain and shared test-runner changes select all self-hosting tests.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TWIN_PREFIX = 'test_selfhost_'
# Inputs of every self-hosting test: the toolchain build and the test harness.
GLOBAL = ('lib/', 'bootstrap-seed/', 'tools/compiler/seed_archive.py', 'tools/compiler/build.py', 'tools/core.py', 'tools/headless.py',
          'tools/scratch.py', 'tools/filelock.py', 'tests/conftest.py', 'tests/support.py',
          'tests/driver_cache.py', 'tests/leaf_oracle.py', 'tests/leaf_record.py', 'tests/whole_oracle.py',
          'tools/compiler/pytest_parallel.py', 'VERSION', 'LICENSE', 'pyproject.toml')
# Directories whose mention by name is not a dependency on their contents (the repository root, the
# output cache, and trees whose members a test names one by one), and the harness every test imports.
NOT_WHOLE = ('', '.', 'tests', 'tests/cases', 'tests/fixtures', 'tests/fixtures/selfhost', 'bench', '__dewycache__')
HARNESS = ('tests/support.py', 'tests/conftest.py', 'tests/leaf_oracle.py')
IMPORT = re.compile(r'''(?m)^\s*(?:use|import)\s+['"]([\w./-]+\.(?:jo|dewy))['"]|\bp"([\w./-]+\.(?:jo|dewy))"''')
PATHLIKE = re.compile(r'[\w./-]+')
FILE_NAME = re.compile(r'([A-Za-z0-9_]+)\.(?:jo|dewy)\b')


def git(*arguments, root: Path = ROOT) -> str:
    done = subprocess.run(['git', *arguments], cwd=root, capture_output=True, text=True, check=False)
    if done.returncode:
        raise RuntimeError(f'git {" ".join(arguments)}: {done.stderr.strip()}')
    return done.stdout


def changed_files(base: str, root: Path = ROOT) -> tuple[str, set[str]]:
    """The merge base of `base` and HEAD, and every file that differs from it (tracked changes in the
    work tree, and untracked files)."""
    merge_base = git('merge-base', base, 'HEAD', root=root).strip()
    tracked = git('diff', '--name-only', '--no-renames', merge_base, root=root).split('\n')
    untracked = git('ls-files', '--others', '--exclude-standard', root=root).split('\n')
    return merge_base, {name for name in (*tracked, *untracked) if name}


def import_graph(root: Path = ROOT) -> dict[str, set[str]]:
    """compiler file name -> compiler files it imports."""
    files = {p.name: p for p in (root / 'compiler').iterdir() if p.suffix in ('.jo', '.dewy')}
    return {name: imported(path, files) for name, path in files.items()}


def imported(path: Path, files) -> set[str]:
    """The compiler files a Jo or Dewy file imports (compiler files sit in one directory: a path
    such as ../../../compiler/x.jo names x.jo)."""
    return {Path(m[1] or m[2]).name for m in IMPORT.finditer(path.read_text(errors='replace'))
            if Path(m[1] or m[2]).name in files}


def closure(graph: dict[str, set[str]], names) -> set[str]:
    seen, todo = set(), list(names)
    while todo:
        name = todo.pop()
        if name not in seen and name in graph:
            seen.add(name)
            todo += graph[name]
    return seen


def facts(path: Path, root: Path, stems: frozenset, graph: dict, memo: dict) -> tuple[set, set, list]:
    """What one Python file reads by itself: (repository paths, compiler files named, modules imported)."""
    if path in memo:
        return memo[path]
    paths, named, modules = set(), set(), []
    memo[path] = (paths, named, modules)
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, SyntaxError):
        paths.add('')  # (cannot place it: the empty prefix is an input of everything)
        return memo[path]
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
        names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                 else [node.module] + [f'{node.module}.{a.name}' for a in node.names]
                 if isinstance(node, ast.ImportFrom) and node.module and not node.level else [])
        for module in names:
            found = root.joinpath(*module.split('.')).with_suffix('.py')
            if module.split('.')[0] in ('tests', 'tools') and found.is_file() and found not in modules:
                modules.append(found)
        if (isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs
                and path.relative_to(root).as_posix() not in HARNESS):
            text = node.value
            for stem in FILE_NAME.findall(text) + ([text] if text in stems else []):
                named.update(n for n in (stem + '.jo', stem + '.dewy') if n in graph)
            if len(text) <= 200 and PATHLIKE.fullmatch(text) and not text.startswith(('/', '-')):
                for candidate in (text, f'tests/cases/{text}.dewy', f'tests/fixtures/{text}', f'tests/fixtures/selfhost/{text}',
                                  f'tests/{text}'):
                    candidate = os.path.normpath(candidate).replace(os.sep, '/')
                    if candidate.startswith('..') or candidate == '.':
                        continue
                    target = root / candidate
                    if target.is_dir():
                        if candidate.strip('/') not in NOT_WHOLE:
                            paths.add(candidate.rstrip('/') + '/')
                    elif target.is_file():
                        paths.add(candidate)
                        if target.suffix in ('.jo', '.dewy') and not candidate.startswith('compiler/'):
                            named.update(imported(target, graph))  # (a fixture program imports compiler modules)
    return memo[path]


def inputs(test: Path, graph: dict[str, set[str]], root: Path = ROOT, memo: dict | None = None) -> set[str]:
    """The repository-relative files and directories (directories end in '/') a self-hosting test reads."""
    memo = {} if memo is None else memo
    stems = memo.setdefault('stems', frozenset(p.stem for p in (root / 'compiler').iterdir()))
    reach = memo.setdefault('closures', {})
    found, named, seen, todo = set(), set(), set(), [test]
    # (its recorded leaf outputs, tests/leaf_oracle.py)
    found.add(f'tests/fixtures/leaf_outputs/{test.stem}.json')
    while todo:
        module = todo.pop()
        if module in seen:
            continue
        seen.add(module)
        found.add(module.relative_to(root).as_posix())
        paths, names, modules = facts(module, root, stems, graph, memo)
        found |= paths
        named |= names
        todo += modules
    if 'compiler/' in found:
        return found  # (the directory prefix covers every compiler file)
    for name in named:
        if name not in reach:
            reach[name] = closure(graph, [name])
        found |= {'compiler/' + other for other in reach[name]}
    return found


_inputs: dict = {}


def twin_files(root: Path = ROOT) -> list[Path]:
    return sorted((root / 'tests').glob(TWIN_PREFIX + '*.py'))


def scoped_out(changed: set[str], root: Path = ROOT) -> list[str]:
    """The self-hosting tests whose inputs are unchanged since the landing base."""
    if root not in _inputs:
        graph, memo = import_graph(root), {}
        _inputs[root] = {p: inputs(p, graph, root, memo) | set(GLOBAL) for p in twin_files(root)}
    return [p.relative_to(root).as_posix() for p, deps in _inputs[root].items()
            if not any(name == dep or (dep.endswith('/') and name.startswith(dep)) for name in changed for dep in deps)]
