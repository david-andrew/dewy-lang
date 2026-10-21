"""A bare name arm matches every value; any name but `_` warns, saying what it shadows."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''let limit = 5
f = (n:int64):>string => match n {
    limit => "limit {limit}"
}
g = (n:int64|string):>string => match n {
    s:string => s
    int64 => "int"
}
h = (n:int64):>string => match n {
    other => "any {other}"
}
k = (n:int64):>string => match n {
    _ => "any"
}
printl(f(3) g(3) h(3) k(3))
'''


def test_bare_arm_warning(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True,
                             timeout=30, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    warnings = [line for line in checked.stderr.splitlines() if 'bare name' in line]
    assert len(warnings) == 3, checked.stderr
    assert ':3:' in warnings[0] and "shadowing the value 'limit'" in warnings[0]
    assert ':7:' in warnings[1] and "shadowing the type 'int64'" in warnings[1] and '`<int64>`' in warnings[1]
    assert ':10:' in warnings[2] and 'shadowing' not in warnings[2] and '`_` is the catch-all' in warnings[2]
