"""Record formatters are shared, recursive, and ordinary typed functions."""
import os
import subprocess

from test_bootstrap_structural_text import build_program_driver, check_structural_text
from test_bootstrap_lowering import ROOT
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


CASES = [
    '''Point:type=[x:int64 name:string]
let main=():>int64=>if (Point[42 "aa"] as string)=?'[x=42 name="aa"]' 42 else 0''',
    '''Point=type of [x:int64]
Empty=type of []
let main=():>int64=>if "{Point[7]} {Empty[]}"=?'Point[x=7] Empty' 42 else 0''',
    '''Node:type=[value:int64 next:Node|none]
let main=():>int64=>{let node=Node[1 Node[2 none]] return if "{node}"=?'[value=1 next=[value=2 next=none]]' 42 else 0}''',
    '''Point:type=[x:int64]
let main=():>int64=>{let xs:array<Point>=[Point[1] Point[2]] let ys:dict<string Point>=["aa" -> Point[3]] return if "{xs} {ys}"=?'[[x=1] [x=2]] ["aa" -> [x=3]]' 42 else 0}''',
    '''Box:type=[values:array<int64>]
let main=():>int64=>if "{Box[[1 2]]}"=?'[values=[1 2]]' 42 else 0''',
    '''Inner:type=[x:int64 __as__=():>string=>"inner:{x}"]
Outer:type=[item:Inner]
let main=():>int64=>if "{Outer[Inner[42]]}"=?'[item=inner:42]' 42 else 0''',
    '''Point:type=[x:int64]
let calls:int64=0
let next=():>Point=>{calls+=1 return Point[calls]}
let main=():>int64=>{let text="{next()}:{next()}" return if text=?'[x=1]:[x=2]' and calls=?2 42 else 0}''',
    '''Fn:type=(x:int64):>int64
Box:type=[f:Fn|none]
let main=():>int64=>if "{Box[none]}"=?'[f=none]' 42 else 0''',
    '''Root=$abstract type of [x:int64]
let Child=type of Root & [y:int64]
let show=(value:Root):>string=>value as string
let main=():>int64=>if show(Child[1 2])=?'Child[x=1 y=2]' 42 else 0''',
    '''Root=type of [x:int64 __as__=():>string=>"root"]
let Child=type of Root & [__as__=():>string=>"child"]
let show=(value:Root):>string=>"{value}"
let main=():>int64=>if show(Child[1])=?"child" and show(Root[2])=?"root" 42 else 0''',
    '''Shape:type=[x:int64]
let Child=type of Shape
let calls:int64=0
let next=():>Shape=>{calls+=1 return Child[calls]}
let main=():>int64=>{let text=next() as string return if text=?'Child[x=1]' and calls=?1 42 else 0}''',
]
ERRORS = [
    'Child=type of [x:int64]',
    'Node:type=[x:int64]\nNode=type of [y:int64]',
    'Box:type=[values:array<array<int64>>]\nlet main=():>int64=>{let text=Box[[[1]]] as string return 0}',
]


def check_cached_object_helpers(binary, tmp_path):
    extra = tmp_path / 'records.dewy'
    extra.write_text('Point:type=[x:int64]\nlet format=(point:Point):>string=>point as string\n')
    source = tmp_path / 'cached-record.dewy'
    source.write_text('let main=():>int64=>if (Point[42] as string)=?"[x=42]" 42 else 0\n')
    outputs = []
    for hit in (False, True):
        env = os.environ.copy()
        env.pop('DEWY_NO_PRELUDE_CACHE', None)
        env['DEWY_TEST_PRELUDE_CACHE'] = 'hit' if hit else 'miss'
        result = subprocess.run([binary, source, ROOT / 'library', tmp_path / 'record-cache', extra],
                                env=env, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stderr + result.stdout
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
    output = tmp_path / 'cached-record.udewy'
    output.write_text(outputs[1])
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    assert subprocess.run([cache_artifact(output).resolve()], timeout=10).returncode == 42


def test_native_object_text(tmp_path):
    binary = build_program_driver(tmp_path)
    check_structural_text(binary, tmp_path, cases=CASES, errors=ERRORS)
    check_cached_object_helpers(binary, tmp_path)
