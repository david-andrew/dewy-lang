"""Formatting bytes as text warns: `bytes as string | none` decodes them."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''main = () => {
    let b = bytes("hi")
    printl(string(b))
    printl(b as string)
    printl((b as string | none) ?? "")
    printl(string(42))
}
'''


def test_bytes_text_warning(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True,
                             timeout=30, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    warnings = [line for line in checked.stderr.splitlines() if 'warning:' in line]
    assert [w.split(':')[1] for w in warnings] == ['3', '4'], checked.stderr
    assert all('`bytes as string | none` decodes UTF-8 text' in w for w in warnings)
