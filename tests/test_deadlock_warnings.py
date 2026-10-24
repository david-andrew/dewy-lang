"""Undecided deadlock cases are warnings, never errors (compiler/deadlock.jo); programs without
locks or polling get none."""
import subprocess

from tests.support import compiler  # noqa: F401


def warnings(compiler, tmp_path, program):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(program)
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    return [line for line in checked.stderr.splitlines() if 'warning:' in line]


ELEMENTS = 'touch = (m:Mutex<int64>):>void => {\n    let v = @(m.lock())\n    v += 1\n}\nmain = () => {\n    let accounts = [mutex<int64>(1) mutex<int64>(2)]\n    let first = accounts[0]\n    let a = @(first.lock())\n    touch(accounts[1])\n    a += 1\n}\n'

FUNCTION_VALUE = 'main = () => {\n    let m = mutex<int64>(0)\n    let handlers = [() => printl"hi"]\n    let held = @(m.lock())\n    let h = handlers[0]\n    h()\n    held += 1\n}\n'

NO_TASKS_CYCLE = 'forward = (a:Mutex<int64> b:Mutex<int64>):>void => {\n    let x = @(a.lock())\n    let y = @(b.lock())\n    x += y\n}\nmain = () => {\n    let p = mutex<int64>(1)\n    let q = mutex<int64>(2)\n    forward(p q)\n    forward(q p)\n}\n'

POLLING = 'main = () => {\n    let ready = atomic(1)\n    parallel i in [0..4) {\n        loop ready.load() =? 0 { }\n    }\n    ready.store(0)\n}\n'


def test_elements_of_one_array_taken_nested_warn(compiler, tmp_path):  # noqa: F811
    found = warnings(compiler, tmp_path, ELEMENTS)
    assert len(found) == 1 and ':9:5:' in found[0] and "may wait for 'accounts[]'" in found[0] and 'lock_all(x y)' in found[0], found


def test_function_value_called_under_a_lock_warns(compiler, tmp_path):  # noqa: F811
    found = warnings(compiler, tmp_path, FUNCTION_VALUE)
    assert len(found) == 1 and ':6:5:' in found[0] and "while holding 'm' (since line 4)" in found[0], found


def test_cycle_without_tasks_warns(compiler, tmp_path):  # noqa: F811
    found = warnings(compiler, tmp_path, NO_TASKS_CYCLE)
    assert len(found) == 1 and 'lock order cycle' in found[0] and '(no task runs them at once yet)' in found[0], found


def test_polling_an_atomic_set_elsewhere_warns(compiler, tmp_path):  # noqa: F811
    found = warnings(compiler, tmp_path, POLLING)
    assert len(found) == 1 and ':4:9:' in found[0] and "polls 'ready'" in found[0], found


def test_ordered_locks_are_quiet(compiler, tmp_path):  # noqa: F811
    program = NO_TASKS_CYCLE.replace('    forward(q p)\n', '    forward(p q)\n')
    assert warnings(compiler, tmp_path, program) == []
