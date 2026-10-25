"""Step 2 of retiring the reference parser (docs/design/self_hosting.md): the direct parser reports
the mistakes of the golden error cases itself. DEWY_FRONTEND=strict stops at any statement the
reference grammar would re-read; every error case reports its mistake without such a stop."""
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

from tests.support import ROOT, compiler  # noqa: F401

CASES = sorted(str(p.relative_to(ROOT / 'tests' / 'cases').with_suffix(''))
               for p in (ROOT / 'tests' / 'cases').rglob('*.err'))


def test_reported_directly(compiler):
    env = dict(os.environ, DEWY_FRONTEND='strict')

    def stops(case):
        result = subprocess.run([compiler, 'check', f'tests/cases/{case}.dewy'], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=120)
        return case if 'DEWY_FRONTEND=strict' in result.stdout + result.stderr else None

    with ThreadPoolExecutor(2) as pool:
        stopped = [c for c in pool.map(stops, CASES) if c]
    assert stopped == []
