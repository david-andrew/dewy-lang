"""Logical storage effects stay distinct from reads, mutation and unknown calls."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from dewy.semantic import effect_rows as rows
from tests.python_misc.test_scalar_projection import execute


@pytest.mark.parametrize('source', [
    'f=(xs:array<int64>):>array<int64> & allocates=>xs.copy()',
    'f=(xs:array<int64>):>int64 & no allocates=>xs.length',
    'f=(xs:array<int64>):>int64 & no_effects=>{const view=@xs return view.length}',
    'f=(x:int64):>int64 & no allocates=>{let saved=x return saved}',
    'f=(xs:array<int64>):>int64 & allocates=>{let saved=xs return saved.length}',
    'f=(xs:array<int64>):>array<int64> & allocates=>[xs... 42]',
    'f=(@x:int64):>int64 & reads<x> & no allocates=>x',
    'f=(@x:array<int64>):>array<int64> & reads<x> & allocates=>x.copy()',
    'f=(@x:array<int64> y:array<int64>):>void & mutates<x> & allocates=>{x=y}',
    'f=(callback:():>int64 & allocates):>int64 & allocates=>callback()',
    'f=(callback:():>int64 & no allocates):>int64 & no allocates=>callback()',
    'g=(xs:array<int64>):>array<int64>=>xs.copy()\nf=(xs:array<int64>):>array<int64> & allocates=>g(xs)',
    'g=():>int64=>{let xs=[42] return xs[0]}\nf=(x:int64=g()):>int64 & allocates=>x',
    'g=():>int64=>{let xs=[42] return xs[0]}\nf=(x:int64):>int64 & allocates=>if x>?0 f(x-1) else g()',
    'g=():>int64=>{let xs=[42] return xs[0]}\nf=(x:int64=g()):>int64 & no allocates=>x',
    'g=():>int64=>{let xs=[42] return xs[0]}\nf=(x:int64):>int64 & no allocates=>if x>?0 f(x-1) else g()',
])
def test_known_storage_and_allocation_exclusions(source):
    codegen(SrcFile(None, source))


@pytest.mark.parametrize('source', [
    'f=(xs:array<int64>):>array<int64> & no allocates=>xs.copy()',
    'f=(xs:array<int64>):>int64 & no allocates=>{let saved=xs return saved.length}',
    'f=(xs:array<int64>):>int64 & no_effects=>{let saved=xs.copy() return saved.length}',
    'f=(xs:array<int64>):>array<int64> & no allocates=>xs',
    'f=(@xs:array<int64>):>array<int64> & allocates=>xs.copy()',
    'f=(@x:array<int64> y:array<int64>):>void & allocates=>{x=y}',
    'f=(@x:int64):>int64 & allocates=>x',
    'f=(callback:(@x:int64):>void & mutates<x>):>int64 & no allocates=>{let n:int64=0 callback(@n) return n}',
    'g=(callback:(@x:int64):>void & mutates<x> @n:int64):>void=>callback(@n)\nf=(callback:(@x:int64):>void & mutates<x>):>int64 & no allocates=>{let n:int64=0 g(@callback @n) return n}',
    'f=(callback:():>int64):>int64 & allocates=>callback()',
    'f=(callback:():>int64 & allocates):>int64 & no allocates=>callback()',
    'f=(xs:array<int64>):>array<int64> & allocates & no allocates=>xs.copy()',
    'f=():>int64 & allocates=>{printl("observable") return 42}',
])
def test_permission_does_not_hide_other_effects_or_copy_boundaries(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


@pytest.mark.parametrize('annotation', ['allocates<>', 'no allocates<>', 'allocates<Resource>', 'no allocates<Resource>'])
def test_allocation_family_does_not_invent_allocator_resources(annotation):
    with pytest.raises(ReportException, match='allocation effect does not take resources'):
        codegen(SrcFile(None, f'Resource=type of any\nf=():>int64 & {annotation}=>42'))


def test_allocation_rows_use_normal_permission_subtyping():
    allocation = rows.Atom('allocates')
    permitted = rows.Contract(rows.Row((allocation,)))
    excluded = rows.Contract(excluded=(allocation,))
    assert rows.implies(rows.Contract(rows.Row()), permitted)
    assert rows.implies(rows.Contract(rows.Row()), excluded)
    assert not rows.implies(permitted, excluded)
    assert not rows.implies(None, excluded)
    assert rows.display(permitted, {}) == ' & allocates'
    assert rows.display(excluded, {}) == ' & no allocates'


@pytest.mark.parametrize('name', ['allocation_effects', 'scalar_place_storage'])
def test_allocation_contracts_execute(tmp_path, name):
    fixture = Path(__file__).resolve().parents[1] / f'fixtures/{name}.dewy'
    execute(tmp_path, name, codegen(SrcFile.from_path(fixture)))
