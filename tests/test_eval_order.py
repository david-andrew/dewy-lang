"""Earlier arguments keep their evaluated values across later writes."""
from pathlib import Path

import pytest

from tests.test_core import compiler, run_value_batch


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_argument_snapshots(compiler, tmp_path, release, target):
    fixtures = Path(__file__).parent / 'fixtures' / 'eval_order'
    cases = {path.stem: path.read_text() for path in sorted(fixtures.glob('*.dewy'))}
    outcomes = run_value_batch(compiler, tmp_path, cases, release, target)
    for name, (code, diagnostic) in outcomes.items():
        assert code == '42', f'{name}: {code}\n{diagnostic}'
