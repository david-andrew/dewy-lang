"""The successful void alternative of a fallible main means exit status zero."""
import pytest
from tests.support import compiler
from tools import cases


@pytest.mark.core_quick
def test_void_success_marker():
    assert cases.parse_batch('@@dewy-case@@B0\nhello\n@@dewy-case@@E0:void\n@@dewy-case@@B1\n@@dewy-case@@E1:42\n') == (
        {0: ('hello\n', '0'), 1: ('', '42')}, 1, False)
    assert cases.parse_batch('@@dewy-case@@B0\n@@dewy-case@@E0:Canceled\n')[0] == {}


@pytest.mark.core_quick
@pytest.mark.parametrize('mode', ['native', 'native-release'])
def test_fallible_void_batch_keeps_all_results(compiler, tmp_path, monkeypatch, mode):
    names = ['reserve/or_throw', 'reserve/permits', 'reserve/select', 'signals_closing/helper']
    chosen = [cases.parse(cases.CASES / f'{name}.dewy') for name in names]
    runner = cases.Runner(compiler, tmp_path, cases.clean_environment())
    monkeypatch.setattr(runner, 'single', lambda *a: pytest.fail('successful fallible main must stay batched'))
    outcomes = runner.value_batch(chosen, mode)
    assert len(outcomes) == len(chosen)
    assert all(outcome.ok for outcome in outcomes), [outcome.message for outcome in outcomes]
