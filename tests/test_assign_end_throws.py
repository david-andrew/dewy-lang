"""A function whose body ends in an assignment expresses nothing, yet its `or_throw`
still adds the failures to its inferred result: `void | E`."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''let total = 0
risky = (x:int64):>int64 | Overflow => {
    if x >? 10 { return Overflow() }
    x * 2
}
add_up = (x:int64) => {
    let y = risky(x) or_throw
    total = total + y
}
bump = (x:int64) => {
    total += risky(x) or_throw
}
main = () => {
    add_up(3) or_throw
    bump(1) or_throw
    printl(total)
    printl(add_up(30) is? Overflow)
    printl(total)
    bump(40) or_throw
    printl('not reached')
}
'''


def test_assignment_end_infers_thrown_kinds(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text((SOURCE) + "\n$runtime_checks\n")
    run = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 1, run.stdout + run.stderr
    assert run.stdout.split('\n')[:3] == ['8', 'true', '8'], run.stdout
    assert 'Overflow' in run.stderr and 'not reached' not in run.stdout, run.stdout + run.stderr
