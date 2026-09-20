"""Word storage for abstract counters needs an invariant on every backedge."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError, NotImplementedYet
from tests.python_misc.test_scalar_projection import execute

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'


def test_nested_counter_facts_and_both_step_directions(tmp_path):
    execute(tmp_path, 'nested-counters', codegen(SrcFile.from_path(FIXTURES / 'nested_range_counters.dewy')))


@pytest.mark.parametrize('source', [
    'f=()=>{loop i in 0.. {}}',
    'f=(n:int64)=>{loop i in 0.. and i<=?n {}}',
    'f=()=>{loop i in 0,2.. and i<?int64.max {}}',
    'f=()=>{loop i in 0,-2.. and i>?int64.min {}}',
    'f=(skip:bool)=>{loop i in 0.. {if skip continue\nif i>=?3 break}}',
    '$prototype\nf=()=>{loop i in 0.. {}}',
    'f=()=>{loop i in 0.. {$assert i<=?int64.max}}',
])
def test_unknown_or_overflowing_backedge_is_not_a_word_loop(source):
    with pytest.raises((UserError, NotImplementedYet)):
        codegen(SrcFile(None, source))


def test_break_before_advance_can_bound_an_ordinary_body(tmp_path):
    execute(tmp_path, 'body-guard', codegen(SrcFile(None, '''main=():>int64=>{
 let n:int64=0
 loop i in 0.. {
  if i>=?6 break
  if i<?2 continue
  n+=i
 }
 return n+28
}''')))
