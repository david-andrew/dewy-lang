"""Public effect inference sees the checked module graph before pruning."""
from pathlib import Path

import pytest

from dewy.reporting import ReportException, SrcFile
from dewy.semantic.check import typecheck_and_resolve


def program(tmp_path, helper, caller):
    (tmp_path / 'helper.dewy').write_text(helper)
    source = tmp_path / 'main.dewy'
    source.write_text('from p"helper.dewy" import helper\n' + caller)
    return SrcFile.from_path(source)


@pytest.mark.parametrize('helper,caller', [
    ('helper=(x:int64):>int64=>x+1', 'f=(x:int64):>int64 & no_effects=>helper(x)'),
    ('helper=(@x:int64):>void=>{x=42}', 'f=(@x:int64):>void & mutates<x>=>helper(@x)'),
    ('helper=(@x:int64):>void=>{x=42}', 'f=():>int64 & no_effects=>{let n:int64=0 helper(@n) return n}'),
    ('read=(@x:int64):>int64=>x\nhelper=(@x:int64):>int64=>read(@x)',
     'f=(@r:[left:int64 right:int64]):>int64 & reads<r.left>=>helper(@r.left)'),
])
def test_imported_direct_helpers_keep_inferred_effects(tmp_path, helper, caller):
    typecheck_and_resolve(program(tmp_path, helper, caller))


@pytest.mark.parametrize('helper,caller', [
    ('helper=(x:int64):>int64=>{printl("observable") return x}', 'f=(x:int64):>int64 & no_effects=>helper(x)'),
    ('helper=(@x:int64):>void=>{x=42}', 'f=(@x:int64):>void & reads<x>=>helper(@x)'),
    ('helper=(xs:array<int64>):>array<int64>=>xs.copy()',
     'f=(xs:array<int64>):>array<int64> & no allocates=>helper(xs)'),
    ('helper=():>int64 & no_effects=>{printl("unused") return 42}', 'main=():>int64=>42'),
])
def test_imported_effects_are_not_hidden_by_module_or_reachability(tmp_path, helper, caller):
    with pytest.raises(ReportException, match='effect contract'):
        typecheck_and_resolve(program(tmp_path, helper, caller))


def test_transitive_imported_helpers(tmp_path):
    (tmp_path / 'leaf.dewy').write_text('leaf=(x:int64):>int64=>x+1')
    source = program(tmp_path, 'from p"leaf.dewy" import leaf\nhelper=(x:int64):>int64=>leaf(x)',
                     'f=(x:int64):>int64 & no_effects=>helper(x)')
    typecheck_and_resolve(source)
