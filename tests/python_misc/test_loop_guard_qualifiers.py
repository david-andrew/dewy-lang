"""Loop guards select difference vocabulary, without assuming an iteration."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PAIR = (Path(__file__).resolve().parents[1] / 'fixtures/loop_guard_qualifiers.dewy').read_text()
CASES = [PAIR,
         PAIR.replace('lower<?upper', 'upper>?lower'),
         PAIR.replace('lower+=1 upper+=1',
                      'if lower%2=?0 {lower+=1 upper+=1 continue}\nlower+=1 upper+=1')]
# The useful ranged pair must not depend on fitting among the first exact
# entry values. These unrelated changing bindings exceed that seed budget.
CASES.append(PAIR.replace('let lower:int64=0',
    '\n'.join(f'let noise_{i}:int64=0' for i in range(70)) + '\nlet lower:int64=0').replace(
        'lower+=1 upper+=1',
        '\n'.join(f'noise_{i}+=2' for i in range(70)) + '\nlower+=1 upper+=1'))
ERRORS = [PAIR.replace('let lower:int64=0', 'let lower:int64=1'),
          PAIR.replace('upper+=1', 'upper+=2'),
          PAIR.replace('lower+=1 upper+=1', 'upper+=1 if upper%2=?0 continue\nlower+=1'),
          'change=(@upper:int64):>bool=>{upper=200 return true}\n' +
          PAIR.replace('lower<?upper', 'lower<?upper and change(@upper)')]


@pytest.mark.parametrize('source', CASES)
def test_guard_pair_is_inductive(tmp_path, source):
    execute(tmp_path, 'guard-qualifier', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_guard_is_not_assumed_at_entry_or_after_transfer(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_guard_qualifiers(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
