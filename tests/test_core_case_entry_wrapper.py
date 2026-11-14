"""Pure entry wrappers have the same result with or without a block."""
import pytest
from tests.support import compiler
from tools import cases


@pytest.mark.core_quick
@pytest.mark.parametrize('source, expected', [
    ('main=()=>exit(run())\n', 'run'),
    ('main=()=>{exit(run())}\n', 'run'),
    ('main = () => {\n    exit(run())\n}\n', 'run'),
    ('main=()=>{printl("before") exit(run())}\n', 'main'),
    ('main=()=>{defer printl("after") exit(run())}\n', 'main'),
    ('main=()=>{exit(run()) printl("after")}\n', 'main'),
])
def test_entry_wrapper(source, expected):
    assert cases.entry_name(source) == expected


@pytest.mark.core_quick
@pytest.mark.parametrize('mode', ['native', 'native-release'])
def test_multiline_entry_stays_batched(compiler, tmp_path, monkeypatch, mode):
    # A child task leaves the program using direct output; the next program's
    # pure exit wrapper must be called as a result, followed by another case.
    names = ['task_capture_cleanup/owner_task_ok', 'text/classification', 'time_integer_grid/multiples']
    chosen = [cases.parse(cases.CASES / f'{name}.dewy') for name in names]
    runner = cases.Runner(compiler, tmp_path, cases.clean_environment())
    monkeypatch.setattr(runner, 'single', lambda *a: pytest.fail('pure entry wrapper must stay batched'))
    outcomes = runner.value_batch(chosen, mode)
    assert len(outcomes) == len(chosen) and all(outcome.ok for outcome in outcomes), outcomes
