"""Shapes whose checking or layout cannot finish report a diagnostic instead of
exhausting the compiler (September 29 audit follow-up, items 3 and 8)."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import NotImplementedYet, UserError

GROWING = '''$no_prelude=true
let f=<T>(x:T):>int64=>f([x])
main=():>int64=>f(1)
'''
# A finite value whose record contains its own family: no inline layout.
RECURSIVE = '''$no_prelude=true
Root=type of [x:int64]
Child=type of Root & [parent:Root]
main=():>int64=>{let c=Child[1 Root[2]] return c.parent.x}
'''
# Recursion at the same or a smaller type argument still finishes.
FINITE = '''let g=<T>(x:T n:int64):>int64=>if n <=? 0 42 else g(x n-1)
main=():>int64=>g([1 2] 3)
'''


def test_growing_instantiation_is_reported():
    with pytest.raises(UserError, match='generic instantiation grows without bound'):
        codegen(SrcFile(None, GROWING))


def test_recursive_record_storage_is_reported():
    with pytest.raises(NotImplementedYet, match='recursive record storage needs an indirection'):
        codegen(SrcFile(None, RECURSIVE))


def test_finite_recursion_still_instantiates(tmp_path):
    from test_scalar_projection import execute
    execute(tmp_path, 'finite-generic', codegen(SrcFile(None, FINITE), debug_locations=False))


def test_native_nonterminating_shapes(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[FINITE], errors=[GROWING])
