"""Recursive cleanup calls follow finite owned storage, preserving hook order."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
NODE = '''let trace:int64=0
Node=type of [id:int64 next:Node|none
$__drop__
release=():>void=>{trace=trace*10+id}
]
'''
CASES = [
    (ROOT/'tests/fixtures/lifecycle_recursive_drop.dewy').read_text(),
    NODE+'''work=():>int64=>{let node=Node[1 Node[2 Node[3 none]]] return 42}
main=():>int64=>{let answer=work() return if trace=?123 answer else 0}''',
    NODE+'''work=():>int64=>{let nodes:array<Node>=[Node[1 Node[2 none]] Node[4 Node[5 none]]] return 42}
main=():>int64=>{let answer=work() return if trace=?4512 answer else 0}''',
    '''let trace:int64=0
Node=type of [id:int64 left:Node|none right:Node|none
$__drop__
release=():>void=>{trace=trace*10+id}
]
work=():>int64=>{let node=Node[1 Node[2 none none] Node[3 none none]] return 42}
main=():>int64=>{let answer=work() return if trace=?132 answer else 0}''',
    '''let drops:int64=0
Node=type of [next:Node|none
$__drop__
release=():>void=>{drops+=1}
]
make=(n:int64):>Node=>if n<=?0 Node[none] else Node[make(n-1)]
work=():>int64=>{let node=make(9) return 42}
main=():>int64=>{let answer=work() return if drops=?10 answer else 0}''',
]
ERRORS = [
    NODE+'work=():>int64 & no_effects=>{let node=Node[1 none] return 42}',
    NODE+'''work=():>int64=>{let node=Node[1 none] let other=node
node.id=2 other.id=3 return node.id+other.id}''',
]


@pytest.mark.parametrize('source', CASES)
def test_recursive_resource_cleanup(source, tmp_path):
    execute(tmp_path, 'recursive-drop', codegen(SrcFile(None,source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_recursive_drop_preserves_effects_and_move_only_rules(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source), debug_locations=False)


def test_native_recursive_resource_cleanup(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
