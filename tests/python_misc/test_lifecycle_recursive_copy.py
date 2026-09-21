"""Recursive copies and conditional owners retain independent lifetimes."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

NODE = '''let copies:int64=0 let drops:int64=0
Node=type of [id:int64 next:Node|none
$__drop__
release=():>void=>{drops+=1}
$__copy__
clone=():>Node=>{copies+=1 return Node[id if next is? Node next.copy() else none]}
]
'''
HANDLE = '''let copies:int64=0 let drops:int64=0
Handle=type of [id:int64
$__drop__
release=():>void=>{drops+=1}
$__copy__
clone=():>Handle=>{copies+=1 return Handle[id]}
]
'''
CASES = [
    NODE+'''work=():>int64=>{
 let node=Node[42 Node[1 none]] let other=node.copy()
 other.id=7 return node.id
}
main=():>int64=>{let answer=work() return if copies=?2 and drops=?4 answer else 0}''',
    HANDLE+'''Node:type=[handle:Handle next:Node|none]
work=():>int64=>{
 let node=Node[Handle[42] Node[Handle[1] none]] let other=node.copy()
 other.handle.id=7 return node.handle.id
}
main=():>int64=>{let answer=work() return if copies=?2 and drops=?4 answer else 0}''',
    HANDLE+'''work=(yes:bool):>int64=>{
 let selected=if yes {let local=Handle[42] local.copy()} else Handle[42]
 return selected.id
}
main=():>int64=>{let a=work(true) let b=work(false)
return if a=?42 and b=?42 and copies=?1 and drops=?3 42 else 0}''',
    HANDLE+'''work=(yes:bool):>int64=>{
 let selected=if yes {let local=Handle[42] local.copy() local.id=1} else Handle[42]
 return selected.id
}
main=():>int64=>{let a=work(true) let b=work(false)
return if a=?42 and b=?42 and copies=?1 and drops=?3 42 else 0}''',
]
ERRORS = [
    NODE+'work=():>int64 & no_effects=>{let node=Node[1 none] let other=node.copy() return other.id}',
    NODE.replace('copies+=1 return', 'id=7 copies+=1 return')+'main=():>int64=>42',
    HANDLE.replace('$__copy__\nclone=():>Handle=>{copies+=1 return Handle[id]}','')+'''work=(yes:bool):>int64=>{
let original=Handle[42] let selected=if yes original else Handle[42]
original.id=1 selected.id=2 return original.id+selected.id}''',
]

@pytest.mark.parametrize('source', CASES)
def test_recursive_or_conditional_copy(source, tmp_path):
    execute(tmp_path, 'recursive-copy', codegen(SrcFile(None,source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_recursive_copy_keeps_effect_and_receiver_checks(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source), debug_locations=False)


def test_native_recursive_or_conditional_copy(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
