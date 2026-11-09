"""`exit(n)` takes a code from 0 to 255, the range every system reports alike (Linux keeps only
the low 8 bits, so `exit(256)` would report success): `exit` takes a `uint8`, so a constant
outside the range is a compile error, a computed code needs a proof, and an in-range constant
proves for free."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, verb='run'):
    (tmp_path / 'main.dewy').write_text(source)
    return subprocess.run([compiler, verb, 'main.dewy'], text=True, capture_output=True, timeout=120, cwd=tmp_path)


@pytest.mark.parametrize('code', [0, 1, 42, 255])
def test_in_range_constant_exits_with_it(compiler, tmp_path, code):
    result = run(compiler, tmp_path, f'main = () => exit({code})\n')
    assert result.returncode == code, result.stderr


@pytest.mark.parametrize('code', ['256', '1000', '(-1)'])
def test_out_of_range_constant_is_a_compile_error(compiler, tmp_path, code):
    result = run(compiler, tmp_path, f'main = () => exit({code})\n', 'check')
    assert result.returncode != 0
    assert 'expects uint8' in result.stderr, result.stderr


def test_computed_code_needs_a_proof(compiler, tmp_path):
    result = run(compiler, tmp_path, 'main = () => exit(args().length * 100)\n', 'check')
    assert result.returncode != 0
    assert 'fits uint8' in result.stderr, result.stderr


@pytest.mark.parametrize('code', ['min(args().length * 100 255)', 'args().length * 100 & 255'])
def test_clamped_or_masked_code_proves_and_runs(compiler, tmp_path, code):
    result = run(compiler, tmp_path, f'main = () => exit({code})\n')
    assert result.returncode == 100, result.stderr


def test_runtime_checks_turns_the_obligation_into_a_check(compiler, tmp_path):
    result = run(compiler, tmp_path, 'main = () => exit(args().length * 300)\n\n$runtime_checks\n')
    assert result.returncode == 101, result.stderr
