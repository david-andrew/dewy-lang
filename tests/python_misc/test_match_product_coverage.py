"""Coordinate coverage must not erase the correlation between match patterns."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import UserError
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

PREFIX = 'let choose=(x:int64|string y:int64|string):>int64=>match (x y) {'
DIAGONAL = '(a:int64 b:int64)=>0 (a:string b:string)=>1'


def test_diagonal_patterns_leave_mixed_pairs_uncovered():
    with pytest.raises(UserError, match='match is not exhaustive'):
        check._typecheck_module(SrcFile(None, PREFIX + DIAGONAL + '}'))


def test_mixed_pair_reaches_fallback(tmp_path):
    source = tmp_path / 'products.dewy'
    source.write_text(PREFIX + DIAGONAL + ' (_ _)=>42}\n'
                      'let main=():>int64=>{printl(choose(1 "a")) printl(choose("a" 1)) return 0}\n')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == '42\n42\n'


def test_crossed_arm_adds_a_new_product():
    check._typecheck_module(SrcFile(None, PREFIX + DIAGONAL + ' (a:int64 b:string)=>2 (_ _)=>3}'))


def test_a_previous_arm_can_still_cover_the_entire_product():
    with pytest.raises(UserError, match='unreachable match arm'):
        check._typecheck_module(SrcFile(None, PREFIX + ' (a:int64 _)=>0 (b:int64 s:string)=>1 (_ _)=>2}'))


def test_duplicate_product_is_unreachable():
    with pytest.raises(UserError, match='unreachable match arm'):
        check._typecheck_module(SrcFile(None, PREFIX + ' (a:int64 s:string)=>0 (b:int64 t:string)=>1 (_ _)=>2}'))
