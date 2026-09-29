"""Inline call roots lend stable nested descriptors without retaining owners."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.backend.udewy import lower
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/nested_record_argument_loans.dewy').read_text()
CASES = [SOURCE,
    SOURCE.replace('Inner:type=[', 'Inner=type of ['),
    SOURCE.replace('items:array<int64>', 'items:dict<int64 int64>').replace('Inner[[20 22] 20]', 'Inner[[1 -> 20 2 -> 22] 20]'),
    SOURCE.replace('Pair:type=[inner:Inner', 'Wrapper:type=[inner:Inner]\nPair:type=[inner:Wrapper')
          .replace('pair.inner.items', 'pair.inner.inner.items').replace('pair.inner.offset', 'pair.inner.inner.offset')
          .replace('forward=(inner:Inner)', 'forward=(inner:Wrapper)').replace('work=(inner:Inner)', 'work=(inner:Wrapper)')
          .replace('work(Inner[[20 22] 20])', 'work(Wrapper[Inner[[20 22] 20]])'),
]
CASES.append(SOURCE.replace('Inner:type=[', 'Inner=type of [')
    .replace('Pair:type=', 'ExtendedInner=type of Inner & [extra:int64]\nPair:type=')
    .replace('pair.inner.items.length+pair.inner.offset+pair.offset',
             'if pair.inner is? ExtendedInner pair.inner.extra else 0')
    .replace('work(Inner[[20 22] 20])', 'work(ExtendedInner[[20 22] 20 42])'))
ERRORS = [
    SOURCE.replace('pair.inner.items.length+pair.inner.offset+pair.offset', '{pair.inner.items.clear return 42}'),
    SOURCE.replace('read=(pair:Pair)', 'read=(pair:Pair unused:int64)')
          .replace('read(Pair[inner 20])', 'read(Pair[inner 20] change(@inner))')
          .replace('forward=', 'change=(@inner:Inner):>int64=>{inner.items.clear return 0}\nforward='),
]
# The nominal family's possible inline layout counts against the frame bound,
# even when the current field value is displayed using its parent type.
FAMILY = SOURCE.replace('Inner:type=[', 'Inner=type of [')
FAMILY = FAMILY.replace('Pair:type=', 'WideInner=type of Inner & [' + ' '.join(f'f{i}:int64' for i in range(520)) + ']\nPair:type=')
ERRORS.append(FAMILY)

@pytest.mark.parametrize('source', CASES)
def test_nested_record_argument_loans(tmp_path, source):
    generated = codegen(SrcFile(None, source), debug_locations=False)
    notes = [note for note in lower.last_copy_notes if note.site == 'borrowed into a call root']
    assert notes and all(not note.runtime_sized and note.policy_exempt for note in notes)
    execute(tmp_path, 'nested-loan', generated)

@pytest.mark.parametrize('source', ERRORS)
def test_nested_record_loan_requires_stability_and_a_bounded_layout(source):
    with pytest.raises(ReportException, match='effect contract|unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_nested_record_argument_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
