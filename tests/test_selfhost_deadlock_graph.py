from tests.selfhost_expr_double import print_warnings
"""Demand closure and first-cycle reporting agree with frozen Jo."""
import re

from tests.selfhost_diagnostic_double import diagnostic_status
from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for
from tests.test_deadlock_warnings import NO_TASKS_CYCLE


def test_deadlock_graph_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    driver = '''use 'main.jo'
main = ():
    lower_test_cli()
    print("checked")
'''
    warning = tmp_path / 'cycle.dewy'
    warning.write_text(NO_TASKS_CYCLE)
    quiet = tmp_path / 'ordered.dewy'
    quiet.write_text(NO_TASKS_CYCLE.replace('    forward(q p)\n', '    forward(p q)\n'))
    cases = [(warning, 0, b'no task runs them at once yet'), (quiet, 0, b'checked\n')]
    for case in ('deadlock/order_cycle', 'deadlock/callback_given',
                 'deadlock/parallel_poll', 'deadlock/channel_cycle',
                 'deadlock/channel_join', 'deadlock/hidden_hash',
                 'no_deadlocks/order_no_tasks'):
        source = ROOT / 'tests/cases' / (case + '.dewy')
        cases.append((source, 41, source.with_suffix('.err').read_bytes().splitlines()[0]))
    for case in ('deadlock/mutex_basics', 'deadlock/channel_turns',
                 'deadlock/recursive_service', 'protocols/request_reply'):
        cases.append((ROOT / 'tests/cases' / (case + '.dewy'), 0, b'checked\n'))
    for source, status, expected in cases:
        modules = modules_for(source, tmp_path / 'unused', 'deadlock_graph')
        modules.arguments = ('check', str(source))
        modules.runtime_driver = lambda text: text
        diagnostic_status(modules)
        print_warnings(modules)
        result = compare_leaf(compiler, tmp_path, False, driver, status=status,
                              extra_stems=('deadlock_graph',), jo_doubles=modules)
        assert expected in result, (source, result)
