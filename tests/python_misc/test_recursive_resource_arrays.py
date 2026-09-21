"""Recursive array edges terminate at empty arrays and own their descendants."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

TREE = '''let trace:int64=0
Node=type of [id:int64 children:array<Node>
$__drop__ release=():>void=>{trace=trace*10+id}]
'''
CASES = [
    (Path(__file__).resolve().parents[1] / 'fixtures/recursive_resource_arrays.dewy').read_text(),
    TREE+'''make=():>Node=>Node[1 [Node[2 []] Node[3 []]]]
work=():>void=>{let tree=make() tree.children.push(Node[4 []]) tree.children.clear()}
main=():>int64=>{let before:int64=_arena_live_bytes work()
return if trace=?4321 and before=?_arena_live_bytes 42 else 1}''',
    TREE+'''work=():>void=>{let tree=Node[1 [Node[2 []]]]
let taken=tree.children.pop() taken.children.push(Node[3 []])}
main=():>int64=>{let before:int64=_arena_live_bytes work()
return if trace=?231 and before=?_arena_live_bytes 42 else 1}''',
    '''Node:type=[id:int64 children:array<Node>]
work=():>int64=>{let tree=Node[42 [Node[1 []]]]
let saved=tree.copy()
if saved.children.length>?0 {saved.children[0].id=7}
if tree.children.length>?0 return tree.id+tree.children[0].id-1
return 1}
main=():>int64=>{let before:int64=_arena_live_bytes let answer=work()
return if before=?_arena_live_bytes answer else 1}''',
    '''let copies:int64=0 let drops:int64=0
Node=type of [id:int64 children:array<Node>
$__drop__ release=():>void=>{drops+=1}
$__copy__ clone=():>Node=>{copies+=1 return Node[id children.copy()]}]
work=():>int64=>{let tree=Node[42 [Node[1 []] Node[2 []]]]
let saved=tree.copy() saved.id=7 return tree.id}
main=():>int64=>{let before:int64=_arena_live_bytes let answer=work()
return if copies=?3 and drops=?6 and before=?_arena_live_bytes answer else 1}''',
]
CASES += [
    """let drops:int64=0
Node=type of [children:array<Node> $__drop__ release=():>void=>{drops+=1}]
make=(n:int64):>Node=>if n<=?0 Node[[]] else Node[[make(n-1)]]
work=():>void=>{let tree=make(9)}
main=():>int64=>{let before:int64=_arena_live_bytes work()
return if drops=?10 and before=?_arena_live_bytes 42 else 1}""",
    """Node:type=[id:int64 children:array<Node>]
change=(items:array<Node>):>void=>{if items.length>?0 {items[0].id=7}}
main=():>int64=>{let tree=Node[1 [Node[42 []]]] change(tree.children)
if tree.children.length>?0 return tree.children[0].id
return 1}""",
]

CASES.append(TREE.replace('children:array<Node>', 'children:array<array<Node>>')+
    """work=():>void=>{let tree=Node[1 [[Node[2 []]] [Node[3 []]]]]}
main=():>int64=>{let before:int64=_arena_live_bytes work()
return if trace=?132 and before=?_arena_live_bytes 42 else 1}""")
ERRORS = [
    'let Base=type of [value:int64] let Child=type of Base & [extra:int64]\n'
    'change=(items:array<Base>):>void=>{}\n'
    'main=():>int64=>{let items:array<Child>=[Child[40 2]] change(items) return 42}',
    'Node:type=[children:array<Node length=1>]\nmain=():>int64=>42',
    TREE+'work=():>int64=>{let tree=Node[42 []] let saved=tree.copy() return saved.id}',
    TREE+'work=():>int64 & no_effects=>{let tree=Node[42 []] return tree.id}',
]


@pytest.mark.parametrize('source', CASES)
def test_recursive_array_owners(tmp_path, source):
    execute(tmp_path, 'recursive-array', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_recursive_array_constraints(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_recursive_array_owners(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
