"""Check-time warnings made by pcheck workers (process-parallel checking) reach the parent's
output as a Dewy leaf agrees with frozen Jo: several modules, each warning in its own functions,
split over 2 and 4 workers give the bytes and messages of one process, in source order."""
import platform
import sys

import pytest

from tests.selfhost_process_double import compare_workers
from tests.support import compiler  # noqa: F401

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'amd64'),
    reason='partitioned checking is x86-64 Linux only')

MODULES = 4
PER_MODULE = 36
WARNING_EVERY = 12  # (functions 5, 17 and 29 of each module change a copy nothing reads)


def warns(i):
    return i % WARNING_EVERY == 5


def write_program(tmp_path):
    names = []
    for k in range(MODULES):
        functions = []
        for i in range(PER_MODULE):
            if warns(i):
                functions.append(f'w{k}_{i}=(xs:array<int64>):>int64=>{{\n    loop e in xs {{ e += {i} }}\n    return {i}\n}}')
            else:
                functions.append(f'f{k}_{i}=(x:int64):>int64=>x+{i}')
        (tmp_path / f'm{k}.dewy').write_text(('$runtime_checks\n\n') + ('\n'.join(functions)))
        names.append([f'w{k}_{i}' if warns(i) else f'f{k}_{i}' for i in range(PER_MODULE)])
    lines = [f'from p"m{k}.dewy" import ({" ".join(n)})' for k, n in enumerate(names)]
    lines += ['let sum:int64=0', 'let data:array<int64>=[1 2 3]']
    lines += [f'sum+={n}(data)' if n.startswith('w') else f'sum+={n}({i})' for ns in names for i, n in enumerate(ns)]
    (tmp_path / 'main.dewy').write_text('$runtime_checks\n\n' + '\n'.join(lines) + '\nprintl"{sum}"\n')
    return ['main.dewy']


def test_pcheck_worker_warnings_match_twin(compiler, tmp_path, monkeypatch):
    reports = compare_workers(compiler, tmp_path, monkeypatch, ('pcheck_drive',), write_program(tmp_path))
    assert f'pcheck: 4 workers checked {MODULES * PER_MODULE - 2} roots' in reports[0], reports[0]
    warnings = [line.split(':')[0] for line in reports[0].splitlines() if 'never read afterwards' in line]
    assert warnings == [f'./m{k}.dewy' for k in range(MODULES) for _ in range(3)], reports[0]
