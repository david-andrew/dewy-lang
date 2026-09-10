"""Native source expressions enter HIR through the shared lexical/type arenas."""

import json
import subprocess
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.analyze.effects import _iter_children
from dewy.semantic.hir_display import type_to_dewy
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    'let identity=<T>(value:T):>T=>value\nidentity(7)',
    "let identity=<T>(value:T):>T=>value\nidentity('hi')",
    'let identity=<T>(value:T):>T=>value\nidentity(7); identity(8)',
    'let identity=<T>(value:T):>T=>value\nidentity(7); identity(true)',
    'let last=<T>(a:T b:T):>T=>b\nlast(1 2)',
    'let identity=<T of int>(value:T):>T=>value\nidentity(7)',
    'let identity=<T>(value:T):>T=>value\nlet f=(x:bool):>bool=>identity(x)\nf(true)',
    'let outer=<T>(x:T):>T=>inner(x)\nlet inner=<U>(x:U):>U=>x\nouter(4)',
    'let repeat=<T>(x:T n:int64):>T=>if n >? 0 repeat(x n-1) else x\nrepeat(7 2)',
    'let identity=<T>(value:T):>T=>value\nlet a=[1 2]\nidentity(a)',
    'let size=<T>(values:array<T>):>addr=>values.length\nsize([1 2])',
    'let identity=<T>(value:T):>T=>value\nlet f=(T:string):>int64=>identity(7)\nf("shadow")',
    'let seed:int64=9\nlet choose=<T>(x:T count:int64=seed):>T=>x\nchoose(7)',
    'let use=<T>(x:array<T>):>void=>{x.push(1)}\nlet a:array<addr>=[0]\nuse(a)',

    'set[1 2] | set[2 3]',
    'set[1 2] and set[2 3]',
    'set[1 2] - set[2]',
    'set[1 2] xor set[2 3]',
    "['a' -> 1] | ['b' -> 2]",
    "'a' + 'b'",
    "let text:string='a'\ntext+'b'",
    "'a' =? 'b'",
    "let f=(a:string b:string):>bool=>a not=? b\nf('a' 'b')",
    "let seed=['a' -> 1 'b' -> 2]\nseed.pop('a');\nconst d=seed\nlet read=():>int64=>d['b']\nread()",
    "let d=['a' -> 1 'b' -> 2]\nd.pop('a');\nlet k:string='b'\nif k in? d and d.values.length >? 0 {d[k];}",
    "let update=(@x:int64|string):>bool=>{x='done' return false}\nlet x:int64|string=1\nloop update(@x) {}\nx",

    "let d=['a' -> 1 'b' -> 2]\nloop [k v] in d {d[k];}",
    "let d=['a' -> 1]\nloop [k v] in d and v >? 0 {d[k];}",
    'let s=set[1 2]\nloop x in s {x;}',
    'let s=set[1 2]\nloop x in s {if x in? s {x;}}',
    "let d=['a' -> [x=1]]\nloop [k v] in d {let own=v own.x=2}",
    "let d=['a' -> 1 'b' -> 2 'c' -> 3]\nd.pop('a');\nloop [k v] in d {}\nd['b']",
    "let d=['a' -> 1 'b' -> 2 'c' -> 3]\nd.pop('a');\nlet values=d.values\nd['b']",
    "let d=['a' -> 1 'b' -> 2]\nloop [k v] in d and i in 0..3 {v+i;}",

    "let d=['a' -> 1 'b' -> 2]\nd['b']",
    "let d:dict<string int64>=[]\nd['a']=7\nd['a']",
    "let d=['a' -> 1]\nd.get('z')",
    "let d=['a' -> 1]\nd.get('z' 9)",
    "let d=['a' -> 1 'b' -> 2]\nd.pop('a');\nd['b']",
    "let d=['a' -> 1]\nd.pop('z' default=9)",
    "let d=['a' -> 1]\nd.clear\nd.length",
    "let d=['a' -> 1]\nlet k:string='b'\nif k in? d {d[k];}",
    "let d:dict<string int64>=[]\nlet k:string='a'\nif k in? d {d[k]=1} else {d[k]=2}\nd[k]",
    "let d=['a' -> 1]\nlet copy=d\ncopy['a']",
    "const d=['a' -> 1]\nlet f=():>int64=>d['a']\nf()",
    "let d=['a' -> 1]\nd.keys",
    "let d=['a' -> 1]\nd.values",
    'let s=set[1 2 2]\ns.length',
    'let s:set<int64>=set[]\ns.add(7)\ns.pop(7)',
    'let s=set[1 2]\ns.pop(3 default=none)',
    'let s=set[1 2]\ns.pop(3 default=9)',
    'let s=set[1 2]\ns.values',
    'let s=set[1 2]\n2 in? s',
    "let d:totaldict<'a'|'b' int64>=['a' -> 1 'b' -> 2]\nlet k:'a'|'b'='a'\nd[k]",
    "let f=(d:totaldict<'a'|'b' int64> k:'a'|'b'):>int64=>d[k]\nf(['a' -> 1 'b' -> 2] 'b')",
    "let p=[entries=['a' -> 1]]\np.entries['a']",
    "let p:[entries:dict<string int64>]=[entries=[]]\np.entries['a']=4\np.entries['a']",

    'let make=():>[x:int64] => [x=7]\nlet x=make().x\nx',
    'let make=():>[x:int64] => [x=7]\nlet p=[x=make().x]\np.x',
    'let make=():>[x:int64] => [x=7]\nP:type=[x:int64]\nP[x=make().x]',
    'let make=():>[x:int64] => [x=7]\nlet use=(x:int64):>int64=>x\nuse(x=make().x)',
    'let make=():>[x:int64] => [x=7]\nlet use=(x:int64=make().x):>int64=>x\nuse()',
    'let make=():>[values:array<int64>] => [values=[1 2]]\nloop x in make().values {x;}',
    'let make=():>[values:array<int64>] => [values=[1 2]]\nloop x in make().values and x >? 0 {x;}',
    'loop false {}',
    'loop true {break}',
    'let f=():>never => loop true {continue}\n@f',
    'let n:int64=0\nloop n <? 3 {n+=1}\nn',
    'loop i in 0..3 {i;}',
    'loop i in [2,4..10) {i;}',
    'loop i in (5,3..0] {i;}',
    'loop i in 0.. and i <? 3 {i;}',
    'loop x in [1 2] {x;}',
    'loop x in "hi" {x;}',
    'loop x in [1 2] and y in [3 4] {x+y;}',
    'let xs:array<int64>=[1]\nloop xs.length >? 0 {xs.pop;}\nxs',
    '1', "'hello'", 'true', 'none', '1 + 2', '3 >? 2',
    'let x:int64 = 1\nx + 2',
    'let x:int64=1\nx+=2\nx',
    'let p=[x=1]\np.x+=2\np.x', 'const x = 1\nx', '[1 2]',
    'let x:int64 = 1\nx = 2\nx', 'let xs:array<int64> = []\nxs',
    'Count:type = int64\nlet n:Count = 7\nn',
    'let f=(x:int64):>int64 => x + 1\nf(7)',
    'let f=(x:int64):>int64 => { return x }\nf(8)',
    'let first=():>int64 => later()\nlet later=():>int64 => 9\nfirst()',
    'let f=(x:int64|string):>int64 => if x is? int64 x else 0\nf(7)',
    'let f=(x:bool):>int64 => { if x return 1 return 2 }\nf(false)',
    'if true 1 else 2',
    'let xs:array<int64>=[1]\nxs.push(2)\nxs.length',
    'let xs=[1]\nxs.push(2)\nxs.length',
    'let xs:array<int64>=[1]\nxs.pop',
    'let xs:array<int64>=[1]\nxs.clear\nxs.length',
    'let xs:array<int64>=[1]\nxs.insert(2 0)\nxs.truncate(1)\nxs.length',
    'let xs:array<int64>=[1]\nxs.reserve(4)\nxs.length',
    'let xs:array<string>=["a" "b"]\nxs.join(",")',
    'let f=():>int64 => 7\nf',
    'let f=():>int64 => 7\nlet alias=@f\nalias()',
    'let set=(@x:int64):>void => {x=7}\nlet x:int64=1\nset(@x)\nx',
    'let set=(@x:int64):>void => {x=7}\nlet p=[x=1]\nset(@p.x)\np.x',
    'let set=(@x:int64 @y:int64):>void => {x=7 y=9}\nlet p=[x=1 y=2]\nset(@p.x @p.y)\np',
    'let f=(@x:int64|string):>bool => {x="changed" return true}\nlet g=(@x:int64|string):>bool => x is? int64 and f(@x)\nlet x:int64|string=1\ng(@x)',
    'let f=(x:int64|string):>bool => x is? int64 and x >? 0\nf(7)',
    'let f=(x:int64|string):>bool => x isnt? int64 or x >? 0\nf(7)',
    'let f=(x:bool y:bool):>bool => x nand y\nf(true false)',
    'let f=(x:bool y:bool):>bool => x nor y\nf(true false)',
    'let x:int64|string=1\n{ x="done" }\nx',
    'let xs=[1 2]\nxs.length',
    '"hello".length',
    '[x=1 y=2]',
    'let p=[x=1]\np.x=3\np.x',
    'let f=(x:int64=3):>int64 => x\nf()',
    'let x:int64=9\nlet f=(x:int64 y:int64=x+1):>int64 => y\nf(3)',
    'let p:[x:int64 y:string]=[x=2 y="hi"]\np',
    'let p=[x=1 y=2]\np.x',
    'Point:type=[x:int64 y:int64]\nPoint[1 2]',
    'Point:type=[x:int64 y:int64=3]\nlet p=Point[x=2]\np.y',
    'Point:type=const [x:int64=2 y:int64=x+1]\nPoint[]',
    'let seed:int64=4\nPoint:type=[x:int64=seed]\nlet f=(seed:string):>Point => Point[]\nf("shadow")',


]


ERROR_CASES = [
    'let identity=<T T>(value:T):>T=>value',
    'let identity=<T>(value)=>value\nidentity(7)',
    'let identity=<T>(value):>T=>value\nidentity(7)',
    'let identity=<T of int>(value:T):>T=>value\nidentity("hi")',
    'let broken=<T>(value:T):>T=>true\nbroken(7)',
    'let need=<T U>(value:T):>T=>value\nneed(7)',
    'let bad=<T>(x:array<T>):>void=>{x.push("bad")}\nlet a=[1 2]\nbad(a)',

    "set[1] | set['a']",
    "['a' -> 1] & ['b' -> 2]",
    "set[1] | ['a' -> 1]",
    "['a' -> 1] | ['b' -> 'wrong']",

    'let s=set[1 2]\nloop x in s {s.pop(x);}',
    "let d=['a' -> 1]\nloop [k v] in d {d['b']=2}",
    "let d=['a' -> [x=1]]\nloop [k v] in d {v.x=2}",
    "let d=['a' -> 1]\nloop [k k] in d {}",
    "let d=['a' -> 1]\nloop [k] in d {}",
    'let s=set[1 2]\nloop [k v] in s {}',

    "[1 'mixed']",
    "['a' -> 1 'b' -> 'mixed']",
    'set[]',
    "let d=['a' -> 1]\nd['b']",
    "let d=['a' -> 1]\nd.clear\nd['a']",
    "let d=['a' -> 1]\nlet k:string='a'\nif k in? d {k='b' d[k];}",
    "let d=['a' -> 1]\nlet k:string='a'\nd.pop(k default=0);\nd['a']",
    "let d=['a' -> 1]\nlet k:string='a'\nif k in? d {d.pop('a'); d[k];}",
    "let d=['a' -> 1]\nlet f=():>int64=>d['a']",
    "let d:totaldict<'a'|'b' int64>=['a' -> 1]",
    "let d:totaldict<'a'|'b' int64>=['a' -> 1 'b' -> 2]\nd.clear",
    "const d=['a' -> 1]\nd['a']=2",
    'const s=set[1]\ns.add(2)',
    'let s=set[1]\ns[1]',
    'let s=set[1]\ns.keys',
    'let s=set[1]\ns.pop(2)',
    "let d=['a' -> 1]\nlet k:string='b'\nif true {d[k]=2}\nd[k]",

    'break', 'continue',
    'loop true { let f=():>void => {break} }',
    'loop i in ..3 {}',
    'loop i in 1,1..3 {}',
    'loop x in [1] and x in [2] {}',
    'loop p in [[x=1]] {p.x=2}',

    'let xs:array<int64 length=1>=[1]\nxs.push(2)',
    'let xs:array<int64>=[]\nxs.pop',
    'let xs:array<int64>=[1]\nxs.insert(2 3)',
    'let xs:array<int64>=[1]\nxs.truncate(-1)',
    'const p=[x=1]\np.x=2',
    'let change=(@x:int64|string):>bool => {x="changed" return true}\nlet bad=(@x:int64|string):>int64 => {if x is? int64 and change(@x) return x+1 return 0}',

    'let f=(@x:int64):>void => {}\nlet x:int64=1\nf(x)',
    'let f=(x:int64):>void => {}\nlet x:int64=1\nf(@x)',
    'let f=(@x:int64):>void => {}\nconst x:int64=1\nf(@x)',
    'let f=(@x:int64 @y:int64):>void => {}\nlet x:int64=1\nf(@x @x)',
    'let f=(@p:[x:int64] @x:int64):>void => {}\nlet p=[x=1]\nf(@p @p.x)',
    'let x:int64=1\nlet escaped=@x',
    'let f=(@x:int64=1):>void => {}',
    'let x:int64=1\nx="wrong"',
    'const x=1\n{x=2}',
    'let f=():>int64 => "wrong"\nf()',
    'let f=(x:int64):>int64 => x\nf(x=1 x=2)',
    '[x=1 x=2]',
    'Point:type=[x:int64]\nPoint[y=1]',
    'Point:type=[x:int64]\nPoint[]',
    'Point:type=[x:int64]\nPoint[1 2]',
    'Point:type=[x:int64 y:int64]\nPoint[1 x=2]',
    'Point:type=const [x:int64]\nlet p=Point[1]\np.x=2',
]


def loop_summary(node):
    parts = []
    if isinstance(node, hir.LoopArm):
        parts.append(f'loop:{type_to_dewy(node.type)};')
    if isinstance(node, hir.SetAlgebra):
        parts.append(f'algebra:{node.op};')
    if isinstance(node, hir.StringEqual):
        parts.append(f'string_equal:{str(node.negated).lower()};')
    if isinstance(node, hir.StringConcat):
        parts.append('concat;')
    if isinstance(node, hir.DictLookup):
        slot = 'none' if node.static_position is None else str(node.static_position)
        parts.append(f'lookup:{type_to_dewy(node.type)}:{str(node.proven).lower()}:{str(node.position is not None).lower()}:{slot};')
    if isinstance(node, hir.DictRemove):
        parts.append(f'remove:{type_to_dewy(node.type)}:{str(node.default is not None).lower()}:{str(node.lenient).lower()};')
    if isinstance(node, hir.DictStore):
        parts.append(f'store:{"set" if node.values is None else "dict"};')
    if isinstance(node, hir.DictView):
        parts.append(f'view:{node.name};')
    if isinstance(node, hir.IteratorExpression):
        last = 'none' if node.last is None else str(node.last)
        count = 'none' if node.count is None else str(node.count)
        parts.append(f'iter:{type_to_dewy(node.target.type)}:{node.first}:{node.step}:{last}:{count}:{str(node.guarded).lower()};')
    if isinstance(node, (hir.Break, hir.Continue)):
        parts.append(f'{type(node).__name__.lower()}:{node.loop_levels};')
    for child in _iter_children(node):
        parts.append(loop_summary(child))
    return ''.join(parts)


def test_native_source_values(tmp_path):
    expected = []
    for text in CASES:
        ty.reset_program_brands()
        module, context = check._typecheck_module(SrcFile(None, text))
        expected.append(type_to_dewy(module.type) + "|" + loop_summary(module) + "|instances:" + ",".join(type_to_dewy(item.expr.type) for item in context.generic_instances))
    for text in ERROR_CASES:
        ty.reset_program_brands()
        with pytest.raises((check.UserError, check.TypeCheckError, check.NotImplementedYet)):
            check._typecheck_module(SrcFile(None, text))
    cases = ' '.join(json.dumps(text).replace('{', r'\{') for text in CASES)
    errors = ' '.join(json.dumps(text).replace('{', r'\{') for text in ERROR_CASES)
    source = tmp_path / 'check.dewy'
    source.write_text(f'''from reporting import SrcFile, Error
import p"{ROOT / 'dewy/bootstrap/parser/p0.dewy'}" as parser
import p"{ROOT / 'dewy/bootstrap/semantic/context.dewy'}" as contexts
import p"{ROOT / 'dewy/bootstrap/semantic/check.dewy'}" as checking
import p"{ROOT / 'dewy/bootstrap/semantic/type_display.dewy'}" as display
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
loop_summary = (id:addr session:contexts.Session):>string => {{
    let node=checking.node_at(id session)
    let parts:array<string>=[]
    if node is? hir.LoopArm {{ parts.push("loop:{{display.type_to_dewy(node.value_type session.types)}};") }}
    if node is? hir.SetAlgebra {{ parts.push("algebra:{{node.op}};") }}
    if node is? hir.StringEqual {{ parts.push("string_equal:{{node.negated}};") }}
    if node is? hir.StringConcat {{ parts.push('concat;') }}
    if node is? hir.DictLookup {{
        let slot = if node.static_position is? none 'none' else "{{node.static_position}}"
        parts.push("lookup:{{display.type_to_dewy(node.value_type session.types)}}:{{node.proven}}:{{node.position isnt? none}}:{{slot}};")
    }}
    if node is? hir.DictRemove {{ parts.push("remove:{{display.type_to_dewy(node.value_type session.types)}}:{{node.default isnt? none}}:{{node.lenient}};") }}
    if node is? hir.DictStore {{ parts.push(if node.values is? none 'store:set;' else 'store:dict;') }}
    if node is? hir.DictView {{ parts.push("view:{{node.name}};") }}
    if node is? hir.IteratorExpression {{
        let target=checking.node_at(node.target session)
        let last=if node.last is? none 'none' else "{{node.last}}"
        let count=if node.count is? none 'none' else "{{node.count}}"
        parts.push("iter:{{display.type_to_dewy(target.value_type session.types)}}:{{node.first}}:{{node.step}}:{{last}}:{{count}}:{{node.guarded}};")
    }}
    if node is? hir.Break {{ parts.push("break:{{node.loop_levels}};") }}
    if node is? hir.Continue {{ parts.push("continue:{{node.loop_levels}};") }}
    loop child in hir.children(node) {{ parts.push(loop_summary(child session)) }}
    return parts.join
}}
main = ():>int64 => {{
    let cases:array<string> = [{cases}]
    let failures:int64 = 0
    loop text in cases {{
        let source = SrcFile['fixture' text]
        let parsed = parser.parse(source)
        if parsed is? Error {{ parsed.fail return 1 }}
        let session = contexts.Session[]
        let lexical = contexts.begin(source parsed.nodes @session)
        let environment = checking.begin(lexical @session)
        let module = checking.module(parsed.root environment @session)
        if module is? Error {{ module.fail failures += 1 continue }}
        let node = checking.node_at(module session)
        let instances:array<string>=[]
        loop item in session.hoisted {{
            let declared=checking.node_at(item session)
            $runtime_assert declared is? hir.Declare
            instances.push(display.type_to_dewy(checking.node_at(declared.expr session).value_type session.types))
        }}
        printl("{{display.type_to_dewy(node.value_type session.types)}}|{{loop_summary(module session)}}|instances:{{instances.join(',')}}")
    }}
    let invalid:array<string> = [{errors}]
    loop text in invalid {{
        let source = SrcFile['fixture' text]
        let parsed = parser.parse(source)
        if parsed is? Error {{ parsed.fail return 1 }}
        let session = contexts.Session[]
        let lexical = contexts.begin(source parsed.nodes @session)
        let environment = checking.begin(lexical @session)
        let result = checking.module(parsed.root environment @session)
        $runtime_assert result is? Error
        $runtime_assert result.title not=? 'native checker implementation pending'
        $runtime_assert result.pointers.length >? 0 and result.pointers[0].message.length >? 0
        printl('rejected')
    }}
    return if failures =? 0 0 else 1
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=90, check=False)
    (tmp_path / 'native-output.txt').write_text(result.stdout)
    (tmp_path / 'expected-output.txt').write_text('\n'.join(expected + ['rejected'] * len(ERROR_CASES)) + '\n')
    assert result.returncode == 0, result.stderr
    assert list(zip(CASES + ERROR_CASES, result.stdout.splitlines(), strict=True)) == list(zip(CASES + ERROR_CASES, expected + ['rejected'] * len(ERROR_CASES), strict=True))
