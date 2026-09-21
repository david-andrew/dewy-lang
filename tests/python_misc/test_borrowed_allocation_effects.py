"""Allocation contracts consume the same forwarding proof as lowering."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/borrowed_allocation_effects.dewy'
ERRORS = [
    # Default expressions participate in the same call graph.
    'allocate=():>int64=>{let ys:array<int64>=[] ys.push(1) return ys.length}\n'
    'g=(xs:array<int64> n:int64=allocate()):>int64=>xs.length+n\n'
    'f=(xs:array<int64>):>int64 & no allocates=>g(xs)',
    # A callee writes a private by-value copy: caller reads remain independent.
    'g=(xs:array<int64>):>int64=>{if xs.length>?0 {xs[0]=9} return xs.length}\n'
    'f=(xs:array<int64>):>int64 & no allocates=>g(xs)',
    # Later argument evaluation changes the source before g runs.
    'g=(xs:array<int64> n:int64):>int64=>xs.length+n\n'
    'mutate=(@xs:array<int64>):>int64=>{xs.clear() return 0}\n'
    'f=(xs:array<int64>):>int64 & no allocates=>g(xs mutate(@xs))',
    # Unknown callbacks still have a value boundary even with a public row.
    'f=(xs:array<int64> g:(values:array<int64>):>int64 & no_effects):>int64 & no allocates=>g(xs)',
    'g=(xs:array<int64>):>array<int64>=>xs\n'
    'f=(xs:array<int64>):>array<int64> & no allocates=>g(xs)',
    # The view of nonlocal storage cannot establish an independent value.
    'let data:array<int64>=[42]\n'
    'g=(xs:array<int64>):>int64=>{data.clear() return xs.length}\n'
    'f=(xs:array<int64>):>int64 & no allocates=>g(xs)',
]


def test_forwarded_arrays_allocate_nothing(tmp_path):
    execute(tmp_path, 'borrowed-allocation-effects', codegen(SrcFile.from_path(FIXTURE)))


@pytest.mark.parametrize('source', ERRORS)
def test_unproved_forwarding_still_requires_allocation(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


def test_native_borrowed_allocation_effects(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[FIXTURE.read_text()], errors=ERRORS)
