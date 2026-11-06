"""Demanded lock walks, task joins and callback substitution match frozen Jo."""
import re
import subprocess

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


def test_deadlock_walk_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    driver = '''use 'main.jo'
main = ():
    lower_test_cli()
    print(read_file(args()[4]) ?? "")
'''
    # One compiler pair; program paths, modes and output paths are runtime inputs.
    for case, message in [
        ('deadlock/mutex_basics', None),
        ('deadlock/lock_all_transfers', None),
        ('deadlock/mutex_tasks', None),
        ('deadlock/self_copied_handle', b'already holds'),
        ('deadlock/callback_given', b'already holds'),
        ('deadlock/callback_under_lock', b'already holds'),
        ('deadlock/hidden_hash', b'already holds'),
        ('deadlock/join_held', b'while waiting for'),
        ('deadlock/parallel_held', b'already holds'),
        ('deadlock/order_cycle', b'lock order cycle'),
        ('no_deadlocks/function_value', b'function value'),
    ]:
        source = ROOT / 'tests/cases' / (case + '.dewy')
        for release in ((False, True) if message is None else (False,)):
            output = tmp_path / 'program'
            modules = modules_for(source, output, 'deadlock_walk',
                                  flags=('--release',) if release else ())
            modules['util.jo'], count = re.subn(
                r'(?m)^fatal = \(p0: int, msg0: str\):\n(?:[ \t].*\n|\n)*',
                'fatal = (p0: int, msg0: str):\n    print(msg0)\n    exit(41)\n\n',
                modules['util.jo'], count=1)
            assert count == 1
            result = compare_leaf(compiler, tmp_path, False, driver,
                                  status=41 if message else 0,
                                  extra_stems=('deadlock_walk',), jo_doubles=modules)
            if message:
                assert message in result, (case, result)
            else:
                assert result == output.read_bytes() + b'\n', (case, release)
                ran = subprocess.run([output], capture_output=True, timeout=30)
                assert ran.returncode == 0, (case, release, ran.stderr)
                assert ran.stdout == source.with_suffix('.out').read_bytes(), (case, release)
