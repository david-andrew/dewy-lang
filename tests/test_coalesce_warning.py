"""`x ?? 0 + 1` is `x ?? (0 + 1)`: a literal fallback followed by arithmetic warns."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''main = () => {
    let counts = ["a"->1]
    let x:int64? = none
    counts["a"] = counts.get("a") ?? 0 + 1
    printl(x ?? 2 * 3 + 1)
    printl((x ?? 0) + 1)
    printl(x ?? (0 + 1))
    printl(x ?? 1 =? 1)
}
'''


def test_coalesce_arithmetic_warning(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text((SOURCE) + "\n$runtime_checks\n")
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True,
                             timeout=30, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    warnings = [line for line in checked.stderr.splitlines() if 'warning:' in line]
    assert len(warnings) == 2, checked.stderr
    assert ':4:' in warnings[0] and 'includes `0 + 1`, not just `0`' in warnings[0]
    assert '`(value ?? 0) + 1`' in warnings[0] and '`value ?? (0 + 1)`' in warnings[0]
    assert ':5:' in warnings[1] and '`(x ?? 2) * 3`' in warnings[1]
