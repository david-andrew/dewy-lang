"""Exercise the complete recursive reader, including interpolation and rollback."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tools.compiler import parser_diff


@pytest.mark.core_quick
def test_recursive_reader_ships_dewy(compiler, tmp_path):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_reader.dewy\0' in binary
    assert b'/compiler/dewy_reader_seed.jo\0' not in binary
    source = tmp_path / 'nested.dewy'
    source.write_text('$runtime_checks\n'
                      'take=(xs:array<array<int64>>):>int64=>xs[0][0]\n'
                      'let text="{if true {\"{take([[7]])}\"} else \"bad\"}"\n'
                      'printl(text)\nprintl(take([[9]]))\n')
    program = tmp_path / 'nested'
    run = subprocess.run([compiler, 'build', source, '-o', program],
                         capture_output=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    run = subprocess.run([program], capture_output=True, timeout=30)
    assert (run.returncode, run.stdout, run.stderr) == (0, b'7\n9\n', b'')


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_recursive_reader_matches_frozen(compiler, tmp_path, release):
    pair = parser_diff.build_pair(compiler, tmp_path, release)
    sources = sorted((parser_diff.ROOT / 'tests/cases/frontend').glob('*.dewy'))
    sources += parser_diff.generated(tmp_path / 'generated', 4)
    failures = parser_diff.compare(pair, sources, tmp_path, release, workers=1)
    assert not failures, '\n'.join(f'{path}: {reason}' for path, reason in failures)
