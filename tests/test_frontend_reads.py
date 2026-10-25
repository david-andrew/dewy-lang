"""Programs the direct parser once read only in part (the reference grammar re-read the rest): each
reads throughout."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DIRECT = [
    'tests/cases/numeric/matrix_slices.dewy',
    'tests/cases/numeric/matrix_stepped_read.dewy',
    'tests/cases/refinements/nonzero.dewy',
    'tests/cases/ffi/intrinsic.dewy',
    'tests/cases/partial/operator_global.dewy',
    'tests/cases/match/lookup_int_results.dewy',
    'tests/cases/directives/no_hidden_costs.dewy',
    'tests/ladder/99_dewy_frontend/design.dewy',
    'lib/new/dewy/platformer.dewy',
    'tests/cases/coalesce/precedence.dewy',
    'tests/cases/comprehension/bracket_call.dewy',
    'tests/cases/comprehension/match.dewy',
    'tests/cases/dogfood/09_logs.dewy',
    'tests/cases/generic/local_field_explicit.dewy',
    'tests/cases/generic/local_record.dewy',
    'tests/cases/loop/else_conditions.dewy',
    'tests/cases/loop/forever.dewy',
    'tests/cases/match/sequence_patterns.dewy',
    'tests/cases/match/unsigned_type_patterns.dewy',
    'tests/cases/named/parameter_kinds.dewy',
    'tests/cases/object/closure_member_capture.dewy',
    'tests/cases/object/generic.dewy',
    'tests/cases/object/recursive_closures.dewy',
    'tests/cases/overload/group_types.dewy',
    'tests/cases/refinements/length_uint64_max.dewy',
    'tests/cases/refinements/range_endpoints.dewy',
    'tests/cases/singleton/literal_overloads.dewy',
    'tests/cases/singleton/members_inline_union.dewy',
    'tests/cases/unpack/param_patterns.dewy',
    'tests/ladder/71_checked_proofs/design.dewy',
    'compiler/spelling.dewy',
    'tests/fixtures/programs/include_bytes.dewy',
]


@pytest.mark.parametrize('source', DIRECT)
def test_reads_directly(compiler, source):
    result = subprocess.run([compiler, 'check', source], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
