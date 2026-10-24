"""Never-called warnings: a public type's methods are its members, not dead code."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''Span:type = [
    start:int64
    stop:int64
    width = ():>int64 => stop - start
    spare = ():>int64 => start * 2
]
_Inner:type = [
    v:int64
    used = ():>int64 => v
    stale = ():>int64 => v * 2
]
helper = (x:int64):>int64 => x
main = () => {
    printl(Span(1 4).width)
    printl(_Inner(1).used)
}
'''


def test_unused_methods(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text((SOURCE) + "\n$runtime_checks\n")
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True,
                             timeout=30, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "'helper' is never called" in checked.stderr
    assert "'stale' is never called" in checked.stderr and '`value.stale`' in checked.stderr
    assert "'spare'" not in checked.stderr and "'width'" not in checked.stderr
    assert "'used'" not in checked.stderr
