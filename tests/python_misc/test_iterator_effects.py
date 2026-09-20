"""Allocation contracts consume checked counter storage proofs."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute


@pytest.mark.parametrize('source', [
    'f=():>int64 & no_effects=>{let n:int64=0 loop i in [0..4) {n+=1} return n}',
    'f=():>int64 & no_effects=>{let n:int64=0 loop i in 0.. and i <? 4 {n+=1} return n}',
    'f=(limit:int64):>int64 & no allocates=>{let n:int64=0 loop i in 0.. and i <? limit {n+=1} return n}',
    'f=():>int64 & no_effects=>{let n:int64=0 loop i in [0..4) and j in [0..2) {n+=1} return n}',
    'f=(@n:int64):>void & reads<n> & mutates<n> & no allocates=>{loop i in [0..4) {n+=1}}',
    'g=(x:int64):>int64 & no_effects=>x\nf=():>int64 & no_effects=>{let n:int64=0 loop i in [0..4) {n=g(i)} return n}',
])
def test_proven_word_iteration_is_effect_free(source):
    codegen(SrcFile(None, source))


@pytest.mark.parametrize('source', [
    'f=():>int64 & no allocates=>{let n:int64=0 loop i in 0.. {n+=1} return n}',
    'f=():>int64 & no allocates=>{loop i in 0.. {if i>=?0 continue break} return 42}',
    'f=():>int64 & no allocates=>{loop i in [0..18446744073709551616) {break} return 42}',
    'f=():>int64 & no allocates=>{loop i in [0..4) {let xs=[i]} return 42}',
    'f=(@n:int64):>void & no_effects=>{loop i in [0..4) {n+=1}}',
    'f=():>int64 & no_effects=>{loop i in [0..4) {printl(i)} return 42}',
])
def test_iteration_does_not_hide_storage_or_body_effects(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


def test_iterator_effect_contracts_execute_without_allocation(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'fixtures/iterator_effects.dewy'
    execute(tmp_path, 'iterator_effects', codegen(SrcFile.from_path(path), debug_locations=False))
