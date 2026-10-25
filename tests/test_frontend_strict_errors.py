"""Step 2 of retiring the reference parser (docs/design/self_hosting.md): the direct parser reports
the mistakes of the golden error cases itself. DEWY_FRONTEND=strict stops at any statement the
reference grammar would re-read; every error case reports its mistake without such a stop, except
those still PENDING."""
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

from tests.support import ROOT, compiler  # noqa: F401

# (still reported through the reference grammar)
PENDING = {
    'arena/reject_return', 'callable/parenthesized_type_removed', 'closure/capture_old_list',
    'comprehension/mixed', 'lambda/bare_parameter_annotated', 'match/arm_assignment_braces',
    'match/else_arm', 'missing/asset', 'new_axis/range_endpoint', 'object/local_type',
    'string/interpolation_format_spec', 'surface/habit_colon_if', 'surface/habit_def',
    'surface/habit_eqeq', 'surface/habit_for_in', 'surface/habit_loop_comma',
    'surface/habit_param_comma', 'surface/python_slice_bounds', 'surface/range_bound_as',
    'syntax/deep_expression',
}

CASES = sorted(str(p.relative_to(ROOT / 'tests' / 'cases').with_suffix(''))
               for p in (ROOT / 'tests' / 'cases').rglob('*.err'))


def test_reported_directly(compiler):
    env = dict(os.environ, DEWY_FRONTEND='strict')

    def stops(case):
        result = subprocess.run([compiler, 'check', f'tests/cases/{case}.dewy'], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=120)
        return case if 'DEWY_FRONTEND=strict' in result.stdout + result.stderr else None

    with ThreadPoolExecutor(2) as pool:
        stopped = [c for c in pool.map(stops, [c for c in CASES if c not in PENDING]) if c]
    assert stopped == []
    assert PENDING <= set(CASES)
