"""Mutually exclusive consumers are separate last uses, not sequential reads."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile,ReportException
from test_scalar_projection import execute

BASE='''$explicit_copies
Box:type=[items:array<int64>]
make=():>array<int64>=>[42]
work=(flag:bool):>int64=>{
 let items=make()
 let rows:array<Box>=[]
 if flag {rows.push(Box[items])}
 else {rows.push(Box[items])}
 return if rows.length>?0 and rows[0].items.length>?0 rows[0].items[0] else 1
}
main=():>int64=>{
 loop i in [0..100) {if work(true) not=?42 or work(false) not=?42 return 1}
 let before:int64=_arena_live_bytes
 loop i in [0..100) {if work(true) not=?42 or work(false) not=?42 return 2}
 return if _arena_live_bytes=?before 42 else 3
}'''
CASES=[BASE,
 BASE.replace('if flag {rows.push(Box[items])}', 'if flag {if flag {rows.push(Box[items])} else {rows.push(Box[items])}}'),
 BASE.replace('let items=make()', 'let value:array<int64>|none=make()\n if value is? none return 1').replace('Box[items]', 'Box[value]'),
 BASE.replace('let items=make()', 'let items=make()\n const saved=@items').replace('else {rows.push(Box[items])}', 'else {if saved.length>?0 return saved[0]}'),
]
ERRORS=[BASE.replace(' return if rows.length', ' items.clear()\n return if rows.length'),
 BASE.replace(' if flag {rows.push(Box[items])}', ' const saved=@items\n if flag {rows.push(Box[items])}').replace(' return if rows.length', ' $runtime_assert saved.length>?0\n return if rows.length'),
 BASE.replace(' else {rows.push(Box[items])}', ' if not flag {rows.push(Box[items])}'),
 BASE.replace(' if flag {rows.push(Box[items])}\n else {rows.push(Box[items])}', ' loop i in [0..2) {if flag {rows.push(Box[items])} else {rows.push(Box[items])}}'),
]

@pytest.mark.parametrize('source',CASES)
def test_branch_last_use(tmp_path,source):
 execute(tmp_path,'branch-move',codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source',ERRORS)
def test_branch_move_keeps_compatible_reads(source):
 with pytest.raises(ReportException,match='unproven copy|read-only view'):
  codegen(SrcFile(None,source),debug_locations=False)


def test_native_branch_last_uses(tmp_path):
 from test_bootstrap_structural_text import build_program_driver,check_structural_text
 check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)


def branch_chain(count):
    choices='\n else '.join(f'if choice=?{i} {{rows.push(Box[items])}}' for i in range(count-1))
    choices+='\n else {rows.push(Box[items])}'
    return BASE.replace('flag:bool','choice:int64').replace(
        'if flag {rows.push(Box[items])}\n else {rows.push(Box[items])}',choices).replace('work(true)','work(0)').replace('work(false)',f'work({count-1})')


def test_branch_search_budget_is_conservative():
    # 100 mutually exclusive transfers exceed 4096 pairwise queries. Every
    # missed transfer must retain its copy, rather than assuming liveness.
    with pytest.raises(ReportException,match='unproven copy'):
        codegen(SrcFile(None,branch_chain(100)),debug_locations=False)

CASES.append(branch_chain(16))
ERRORS.append(branch_chain(100))
