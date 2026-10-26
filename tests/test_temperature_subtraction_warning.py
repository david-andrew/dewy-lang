"""A lone point-minus-literal-only binding warns; evidence elsewhere settles its kind."""
import subprocess

from tests.support import compiler  # noqa: F401


SOURCE = '''from units import °C
reading=(c:int)=>c*°C
main=()=>{
    let t=reading(25)
    let rise=20°C
    printl(t-rise)
    EXTRA
}
'''


def check(compiler, tmp_path, extra):
    path = tmp_path / 'main.dewy'
    path.write_text(SOURCE.replace('EXTRA', extra))
    result = subprocess.run([compiler, 'check', path], capture_output=True, text=True,
                            timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stderr


def test_lone_subtraction_warns_with_two_explicit_fixes(compiler, tmp_path):  # noqa: F811
    warning = check(compiler, tmp_path, '')
    assert '`t - rise` leaves `rise` ambiguous' in warning, warning
    assert '`5K`' in warning and '`25°C - 5°C`' in warning, warning


def test_other_uses_settle_kind_without_subtraction_warning(compiler, tmp_path):  # noqa: F811
    assert 'leaves `rise` ambiguous' not in check(compiler, tmp_path, 'printl(t+rise)')
    assert 'leaves `rise` ambiguous' not in check(compiler, tmp_path, 'printl(rise<?t)')
