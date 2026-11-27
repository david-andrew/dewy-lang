"""A number times an offset unit (`20*°C`) is a point, so a binding of it never warns as
ambiguous; the juxtaposed literal `20°C` still does when one subtraction is all it has."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''from units import °C
let start = VALUE
let later = start + 15°C
printl"{later - start}"
'''


def check(compiler, tmp_path, value):  # noqa: F811
    path = tmp_path / 'main.dewy'
    path.write_text(SOURCE.replace('VALUE', value))
    result = subprocess.run([compiler, 'check', path], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stderr


def test_product_is_a_point(compiler, tmp_path):  # noqa: F811
    assert 'ambiguous' not in check(compiler, tmp_path, '20*°C')
    assert 'ambiguous' not in check(compiler, tmp_path, '2.5*°C')


def test_literal_still_warns(compiler, tmp_path):  # noqa: F811
    assert '`later - start` leaves `start` ambiguous' in check(compiler, tmp_path, '20°C')
