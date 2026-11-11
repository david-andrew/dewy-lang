"""Channel identity, capacity and cancellation queries match frozen Jo."""
import re

from tests.selfhost_diagnostic_double import diagnostic_status
from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for
from tests.test_channel_warnings import PING, PIPELINE


def compare_channels(compiler, tmp_path, monkeypatch, leaf):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    driver = '''use 'main.jo'
main = ():
    lower_test_cli()
    print("checked")
'''
    uncertain = tmp_path / 'uncertain.dewy'
    uncertain.write_text(('$runtime_checks\n\n') + (PING))
    pipeline = tmp_path / 'pipeline.dewy'
    pipeline.write_text(('$runtime_checks\n\n') + (PIPELINE))
    cases = [(uncertain, 0, b'may wait to send'), (pipeline, 0, b'checked\n')]
    for case in ('deadlock/channel_cycle', 'deadlock/channel_self',
                 'deadlock/channel_join', 'deadlock/channel_unfilled',
                 'deadlock/channel_lock_held', 'deadlock/reserve_held', 'queues/spsc_cycle',
                 'queues/spsc_try_cycle', 'queue_cancel_wait/mpmc_no_cancel'):
        source = ROOT / 'tests/cases' / (case + '.dewy')
        cases.append((source, 41, source.with_suffix('.err').read_bytes().splitlines()[0]))
    for case in ('deadlock/channel_turns', 'deadlock/reserve_dropped', 'channels/close', 'channels/cancel_blocked',
                 'queues/spsc_turns', 'queues/spsc_tasks', 'queues/spawn_forward_end'):
        cases.append((ROOT / 'tests/cases' / (case + '.dewy'), 0, b'checked\n'))
    for case in ('channel_cancel_diag_ok', 'mpmc_failure_diag', 'cancel_helper', 'failure_helper'):
        cases.append((ROOT / 'tests/cases/queue_cancel_wait' / (case + '.dewy'),
                      0, b'group cancellation may end the wait'))
    # Runtime inputs share a single pair of compiler binaries for this leaf.
    for source, status, expected in cases:
        modules = modules_for(source, tmp_path / 'unused', leaf)
        modules.arguments = ('check', str(source))
        modules.runtime_driver = lambda text: text
        diagnostic_status(modules)
        for name, body in [('warn', 'print(msg)')]:
            modules['util.jo'], count = re.subn(
                rf'(?m)^{name} = \([^\n]*\):\n(?:[ \t].*\n|\n)*',
                f'{name} = (p: int, msg: str): {body}\n\n',
                modules['util.jo'], count=1)
            assert count == 1
        result = compare_leaf(compiler, tmp_path, False, driver, status=status,
                              extra_stems=(leaf,), jo_doubles=modules)
        assert expected in result, (source, result)


def test_deadlock_channels_twins(compiler, tmp_path, monkeypatch):
    compare_channels(compiler, tmp_path, monkeypatch, 'deadlock_channels')
