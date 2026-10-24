"""A bare zero-argument function before a member call is called: the member applies to its result."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''target_names = () => ['a' 'b' 'c']
shout = () => 'abc'
main = () => {
    printl(target_names.length)
    printl(target_names.join(', '))
    printl(target_names.contains('b'))
    printl(shout.upper())
    let pick = () => [3 1 2]
    printl(pick.sorted().length)
}
'''


def test_bare_function_receiver_is_called(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    run = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout.split('\n')[:5] == ['3', 'a, b, c', 'true', 'ABC', '3'], run.stdout
