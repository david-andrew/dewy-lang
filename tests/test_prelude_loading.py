"""Demand-loaded declarations retain eager lookup, initialization and runtime roots."""
import os
import re
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
def scan_check(compiler, tmp_path_factory):
    binary = tmp_path_factory.mktemp('scan-check') / 'scan_check'
    run([compiler, 'build', ROOT / 'tools/compiler/scan_check.jo', '-o', binary])
    return binary


def test_declaration_index_matches_parser(scan_check):
    """Each library file's scanned names and units are what the parser finds in it."""
    run([scan_check, ROOT / 'lib'])


def test_prelude_known_names_listed():
    """Names the compiler reads from the prelude map directly are registered from the start."""
    listed = re.search(r'prelude_known = \[([^\]]*)\]', (ROOT / 'compiler/prelude.jo').read_text())
    known = set(re.findall(r'"([^"]+)"', listed.group(1)))
    used = set()
    for path in (ROOT / 'compiler').glob('*.jo'):
        if path.name == 'prelude.jo':
            continue
        text = path.read_text()
        used |= set(re.findall(r'prelude\.get\(intern\("([^"]+)"\)\)', text))
        used |= set(re.findall(r'rt_global\("([^"]+)"\)', text))
    assert used <= known, sorted(used - known)


def test_prelude_transitive_order(compiler, tmp_path):
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
    (library / 'game/01_demand.jo').write_text('''__demand_second = __demand_note("b")
demand_pick = (n: f64) -> int: 99
demand_result = () -> str:
    assert(__demand_first + __demand_second == 2)
    __demand_order
''')
    source = tmp_path / 'main.dewy'
    source.write_text('printl("{demand_result()} {demand_pick(2)}")\n')
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
