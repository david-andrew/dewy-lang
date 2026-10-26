"""Batched dogfood programs: the contained-paths walk follows only a checked loop's nodes.

A checked `for` keeps locals in its c and d fields. Walking them as nodes went wherever the
local's number pointed; in a batch large enough that the numbers met the loop's own node,
the walk looped until the stack overflowed. These programs alone never crashed.
"""
from tests.support import compiler  # noqa: F401 (fixture)
from tools import cases

BATCH = ['06_life', '07_stats', '09_logs', '10_scheduler', '11_markdown', '12_adventure',
         '15_projectile', '16_binary_format', '17_build_order', '18_roman_tests', '20_inventory',
         '21_numerics', '22_ledger', '23_templates', '24_wordcount_cli', '25_checkout', '26_lisp',
         '27_wordpool', '30_ode', '42_training_units', '43_log_workers', '45_spreadsheet',
         '46_snake', '48_triage', '49_gradebook']


def test_core_batch_loop_fields(compiler, tmp_path):
    batch = [cases.parse(cases.CASES / 'dogfood' / f'{name}.dewy') for name in BATCH]
    runner = cases.Runner(compiler, tmp_path, cases.clean_environment())
    command, _, _, failure = runner.build_batch(batch, 'native', select=False)
    assert failure is None and command is not None, failure
