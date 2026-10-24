"""A numeric or array value named like a function, used as a coefficient (`let sin=0.5`
then `sin(x)^2`), warns that it hides the function."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''main = () => {
    let x = 2.0
    let sin = 0.5
    printl(sin(x)^2)
    let a = 3
    printl(a(x))
}
'''


def test_shadowed_function_coefficient_warns(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    warnings = [line for line in checked.stderr.splitlines() if 'warning:' in line]
    assert len(warnings) == 1, checked.stderr
    assert ':4:12:' in warnings[0] and 'which hides the function `sin`' in warnings[0], warnings
