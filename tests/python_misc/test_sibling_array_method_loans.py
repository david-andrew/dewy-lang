"""Modeled array operations do not make unrelated sibling storage opaque."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from dewy.semantic.analyze import storage_borrows
from test_place_projection_argument_loans import SOURCE as SCALAR_SOURCE
from test_scalar_projection import execute

SOURCE = (SCALAR_SOURCE.replace('counter:int64', 'counter:array<int64>')
          .replace('box.counter+=1', 'box.counter.clear')
          .replace('box.counter=?1000', 'box.counter.length=?0')
          .replace('Box[[20 22] 0]', 'Box[[20 22] [1]]')
          # The builtin retains its conservative allocation permission. This
          # kernel measures the actual unique-owner case; the new proof only
          # removes snapshots of the unrelated `items` field.
          .replace('& no allocates', '& allocates'))
CASES = [SOURCE,
         SOURCE.replace('box.counter.clear', 'box.counter.truncate(0)'),
         SOURCE.replace('box.counter.clear', 'box.counter.reserve(0)')
               .replace('box.counter.length=?0', 'box.counter.length=?1'),
         SOURCE.replace('return read(Pair[box.items 40])',
                        'const items=box.items\n    return read(Pair[items 40])')]
ERRORS = [SOURCE.replace('read=(pair:Pair)', 'read=(pair:Pair unused:int64)')
                .replace('forward=', 'change=(@box:Box):>int64=>{box.items.clear return 0}\nforward=')
                .replace('& mutates<box.counter>', '& mutates<box>')
                .replace('read(Pair[box.items 40])', 'read(Pair[box.items 40] change(@box))')]


@pytest.mark.parametrize('source', CASES)
def test_sibling_array_method_loan(tmp_path, source):
    execute(tmp_path, 'sibling-array-method', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_overlapping_array_method_keeps_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_modeled_method_proof_controls_acceptance(monkeypatch):
    monkeypatch.setattr(storage_borrows, 'ARRAY_METHODS', frozenset())
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, SOURCE), debug_locations=False)


def test_method_loan_does_not_remove_allocation_permission():
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, SOURCE.replace('& allocates', '& no allocates')),
                debug_locations=False)


def test_native_sibling_array_method_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES,
                          errors=[*ERRORS, SOURCE.replace('& allocates', '& no allocates')])
