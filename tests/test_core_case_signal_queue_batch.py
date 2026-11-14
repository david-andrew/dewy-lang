"""Signal imports must not let selection preflight fabricate MPMC positions."""
import pytest

from tests.support import compiler  # noqa: F401
from tools import cases


@pytest.mark.core_quick
@pytest.mark.parametrize('mode', ['native', 'native-release'])
@pytest.mark.parametrize('names', [
    ['reserve/or_throw', 'reserve/permits', 'reserve/select', 'signals_closing/helper'],
    ['queue_refined_slots/mpmc_refined_receive_ok', 'reserve/channel_select', 'reserve/or_throw',
     'reserve/permits', 'reserve/select', 'signals_unavailable/poll'],
], ids=['reserve-signals', 'coverage-queue-select'])
def test_reserve_batch_with_signal_imports(compiler, tmp_path, mode, names):
    chosen = [cases.parse(cases.CASES / f'{name}.dewy') for name in names]
    runner = cases.Runner(compiler, tmp_path, cases.clean_environment())
    source = tmp_path / 'batch.dewy'
    imports = [f'from p"{case.path.as_posix()}" import (main as case_{i})' for i, case in enumerate(chosen)]
    calls = [f'case_{i}();' for i in range(len(chosen))]
    source.write_text('\n'.join([*imports, 'main=()=>{', *calls, '}']) + '\n')
    output = tmp_path / 'batch'
    built = runner.build(source, output, mode)
    assert built.returncode == 0, built.stdout + built.stderr
    code, stdout, stderr = runner.execute(runner.command(output, mode))
    assert code == 0, (code, stdout, stderr)
    assert stdout == ''.join(case.expected for case in chosen), stderr
