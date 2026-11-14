"""A batch deadlock is a failure even when its members would pass alone."""
import pytest

from tools import cases


@pytest.mark.core_quick
@pytest.mark.parametrize('stdout', ['', '@@dewy-case@@B0\n',
                                   '@@dewy-case@@B0\n@@dewy-case@@E0:0\n'])
def test_batch_timeout_never_retries_alone(tmp_path, monkeypatch, stdout):
    case = cases.Case('waiting', tmp_path / 'waiting.dewy')
    runner = cases.Runner(tmp_path / 'compiler', tmp_path)
    monkeypatch.setattr(runner, 'build_batch', lambda *a, **kw: (['program'], [case], [], None))
    monkeypatch.setattr(runner, 'execute', lambda *a, **kw: ('timeout', stdout, ''))
    for name in ('single', 'split', 'isolate'):
        monkeypatch.setattr(runner, name, lambda *a, **kw: pytest.fail('a timeout must not be hidden by retrying'))
    outcomes = runner.value_batch([case], 'native')
    assert len(outcomes) == 1 and not outcomes[0].ok
    assert outcomes[0].stdout is None
    assert 'batch timed out' in outcomes[0].message
