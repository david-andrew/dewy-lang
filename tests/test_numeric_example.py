"""The documented linear-algebra example propagates failures through main."""
import subprocess

from tests.support import ROOT, compiler  # noqa: F401


def test_numeric_example(compiler, tmp_path):
    guide = (ROOT / 'docs/LANGUAGE.md').read_text()
    start = guide.index('let values:array<float64> = [3.0 1.0 1.0 2.0]')
    source = guide[guide.rfind('```dewy', 0, start) + len('```dewy'):guide.index('```', start)]
    path = tmp_path / 'numeric.dewy'
    path.write_text(source)
    ran = subprocess.run([compiler, 'run', path], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stderr


def test_numeric_example_function_error_boundary(compiler, tmp_path):
    path = tmp_path / 'failure.dewy'
    prefix = 'Oops:type = type of error\nfail = ():>int64|Oops => Oops\n'
    body = 'let value = fail() or_throw\nprintl(value)\n'
    path.write_text(prefix + body)
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True, timeout=30)
    assert checked.returncode == 1, checked.stderr
    assert 'or_throw requires an enclosing function' in checked.stderr
    path.write_text(prefix + 'main = () => {\n' + body + '}\n')
    ran = subprocess.run([compiler, 'run', path], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 1, ran.stderr
    assert ran.stderr.strip() == 'error: Oops', ran.stderr
    assert ran.stdout == ''
