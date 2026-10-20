"""Demand-loaded declarations retain eager lookup, initialization and runtime roots."""
import os
import shutil
import subprocess
import sys

import pytest

from tests.support import ROOT, compiler  # noqa: F401


def run(command, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, timeout=60, **kwargs)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope='module')
def indexer(compiler, tmp_path_factory):
    binary = tmp_path_factory.mktemp('prelude-index') / 'index'
    run([compiler, 'build', ROOT / 'tools/compiler/prelude_index.jo', '-o', binary])
    return binary


def test_prelude_index_current(indexer):
    assert run([indexer, ROOT / 'lib']).stdout == (ROOT / 'lib/prelude.index').read_text()


@pytest.mark.parametrize('index', ['current', 'stale', 'missing'])
def test_prelude_transitive_order(compiler, indexer, tmp_path, index):
    library = tmp_path / 'lib'
    shutil.copytree(ROOT / 'lib', library)
    # Request the later module first, then the earlier one through a lazy body.
    # Both overloads must be available before choosing the better match.
    (library / 'game/00_demand.jo').write_text('''__demand_order = ""
__demand_first = __demand_note("a")
__demand_note = (s: str) -> int:
    __demand_order += s
    1
demand_pick = (n: int) -> int: 10 + n
''')
    later = library / 'game/01_demand.jo'
    later.write_text('''__demand_second = __demand_note("b")
demand_pick = (n: f64) -> int: 99
demand_result = () -> str:
    assert(__demand_first + __demand_second == 2)
    __demand_order
''')
    manifest = library / 'prelude.index'
    manifest.write_text(run([indexer, library]).stdout)
    if index == 'missing':
        manifest.unlink()
    if index == 'stale':
        later.write_text(later.read_text().replace('demand_result', 'changed_result'))
    source = tmp_path / 'main.dewy'
    result_name = 'changed_result' if index == 'stale' else 'demand_result'
    source.write_text('printl("{' + result_name + '()} {demand_pick(2)}")\n')
    binary = tmp_path / 'program'
    env = dict(os.environ, DEWY_CORE_LIB=str(library))
    run([compiler, 'build', source, '-o', binary], env=env)
    assert run([binary]).stdout == 'ab 12\n'


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux C library')
def test_prelude_implicit_exit_roots(compiler, tmp_path):
    source = tmp_path / 'exit.jo'
    source.write_text('''@lib("libc.so.6")
extern puts = (s: *u8) -> i32
finish = (): print("end")
main = ():
    __at_end(finish)
    puts(data(bytes("C buffered\\0")))
    print("Dewy buffered")
''')
    binary = tmp_path / 'exit'
    run([compiler, 'build', source, '-o', binary])
    assert sorted(run([binary]).stdout.splitlines()) == ['C buffered', 'Dewy buffered', 'end']
