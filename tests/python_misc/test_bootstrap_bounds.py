"""The native visitor applies proof rules in the program's evaluation order."""
import json
import subprocess
from pathlib import Path

from test_bootstrap_effects import emit_hir
from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.analyze import bounds
from dewy.semantic.errors import UserError
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
LOOP_FUNCTION_CASES = {
    'let f=():>int64=>{loop i in 0..1 {let inner=(value:int64):>int64=>{$assert value >? 0\nreturn value}\ninner(i);}\nreturn 0}': 'cannot prove assertion',
    'let f=():>int64=>{loop i in 0..1 {let inner=(value:int64):>int64=>{if value >? 0 {$assert value >? 0\nreturn value}\nreturn 0}\ninner(i);}\nreturn 0}': 'ok',
}

CASES = [
    'Store:type=const[key:addr]\nRemove:type=const[key:addr?]\nlet read=(node:Store|Remove):>addr=>{let key=node.key\nif key is? none return 0\nreturn key}',
    'Store:type=const[key:int64]\nRemove:type=const[key:addr?]\nlet read=(node:Store|Remove):>addr=>{let key=node.key\nif key is? none return 0\nreturn key}',
    # Optional record fields retain their numeric payload contract when a
    # branch selects them. An unconstrained alternative must still prevent
    # proving the entire result nonnegative.
    "Parts:type=const[key:addr value:addr?]\nlet word=():>addr=>0\nlet f=(parts:Parts name:string):>addr=>{let element=if name=?'keys' parts.key else if name=?'values' parts.value else word()\nif element is? none return 0\nreturn element}",
    "Parts:type=const[key:addr value:addr?]\nlet word=(raw:int64):>int64=>raw\nlet f=(parts:Parts name:string raw:int64):>addr=>{let element=if name=?'keys' parts.key else if name=?'values' parts.value else word(raw)\nif element is? none return 0\nreturn element}",
    'let narrow=():>bool=>true\nlet f=():>int64=>if narrow() 42 else 0',
    'Thing:type=[position:addr]\nlet read=(thing:Thing):>addr=>thing.position',
    'Thing:type=[position:int64]\nlet read=(thing:Thing):>addr=>thing.position',
    'Inner:type=[raw:int64]\nOuter:type=[part:Inner<raw not=? 0>]\nlet keep=(x:Outer):>Outer=>[part=x.part]',

    'Inner:type=[sign:int64]\nOuter:type=[part:Inner<sign =? 1>]\nlet keep=(x:Outer):>Outer=>[part=x.part]',
    'Inner:type=[sign:int64]\nOuter:type=[part:Inner]\nlet keep=(x:Outer):>Inner<sign =? 1>=>x.part',
    'Inner:type=[sign:int64]\nOuter:type=[part:Inner<sign =? 1>]\nlet bad=(x:Outer):>Inner<sign =? 2>=>x.part',

    'Box:type=[raw:int64]\nlet accept=(box:Box<raw not=? 0>):>int64=>box.raw\nlet f=(box:Box):>int64=>if box.raw not=? 0 accept(box) else 0',
    'Box:type=[raw:int64]\nlet accept=(box:Box<raw not=? 0>):>int64=>box.raw\nlet f=(box:Box):>int64=>{if box.raw not=? 0 {box.raw=0 return accept(box)} return 0}',

    # Contracts apply before branch guards are joined away, and scoped
    # result bindings retain their evidence until their obligation is checked.
    'let min=(a:int64 b:int64):>int64<v=>v <=? a and v <=? b>=>if a <? b a else b',
    'let max=(a:int64 b:int64):>int64<v=>v >=? a and v >=? b>=>if a >? b a else b',
    'let min=(a:int64 b:int64):>int64<v=>v <=? a and v <=? b>=>if a <? b {let answer=a answer} else {let answer=b answer}',
    'let wrong=(a:int64 b:int64):>int64<v=>v <=? a and v <=? b>=>if a <? b b else a',
    'let choose=(a:int64 b:int64 c:int64):>int64<v=>v <=? a and v <=? b and v <=? c>=>if a <? b {if a <? c a else c} else {if b <? c b else c}',

    'let n:int64=3\n$assert n >? 0',
    'let n:int64=3\nn=0\n$assert n >? 0',
    'let f=(x:int64):>int64=>{ $assert x >? 0\nreturn x }',
    'let f=(x:int64<x >? 0>):>int64=>{ $assert x >? 0\nreturn x }',
    'let f=(xs:array<int64> i:int64):>int64=>if i >=? 0 and i <? xs.length xs[i] else 0',
    'let f=(xs:array<int64> i:int64):>int64=>xs[i]',
    'let f=(s:string i:int64):>string=>if i >=? 0 and i <=? s.length s[i..] else ""',
    'let f=(s:string i:int64):>string=>s[i..]',
    'let f=(n:int64):>int64=>{ let i:int64=0\nloop i <? n { i += 1 }\nreturn i }',
    'let f=(xs:array<int64>):>int64=>{ let i:int64=0\nloop i <? xs.length { xs[i];\ni += 1 }\nreturn i }',
    'let f=(xs:array<int64>):>int64=>{ let i:int64=0\nloop i <=? xs.length { xs[i];\ni += 1 }\nreturn i }',
    'let f=(x:int64):>int64=>{ if x =? 0 return 0\nreturn 10 // x }',
    'let f=(x:int64):>int64=>10 // x',
    'let f=(x:int64):>uint8=>x',
    'let f=(x:int64):>uint8=>{ if x >=? 0 and x <=? 255 return x\nreturn 0 }',
    'let f=():>int64=>{ let n=if true 3 else 4\n$assert n >=? 3\nreturn n }',
    'let f=(xs:array<int64>):>int64=>{ loop i in 0.. and i <? xs.length { xs[i]; }\nreturn 0 }',
    'let f=(flag:bool):>int64=>{ let n=if flag 3 else 4\n$assert n >=? 3\nreturn n }',
    'let f=(xs:array<int64 length >? 0>):>int64=>{ if xs.length >? 0 {xs.pop;}\nreturn 0 }',
    'let f=(xs:array<int64 length >? 0>):>int64=>{ if xs.length >? 1 { xs.pop; }\nreturn 0 }',
    'let f=(xs:array<int64 length <=? 3>):>int64=>{ xs.push(1)\nreturn 0 }',
    'let f=(xs:array<int64 length <=? 3>):>int64=>{ if xs.length <? 3 {xs.push(1)}\nreturn 0 }',
    'let f=():>int64=>{ let xs:array<int64>=[]\nxs.push(42)\nreturn xs[0] }',
    'let f=(xs:array<int64> i:int64):>int64=>{ if i >=? 0 and i <? xs.length { let copy=xs\nxs.clear\nreturn copy[i] }\nreturn 0 }',
    'let f=(xs:array<int64> count:int64):>int64=>{ xs.truncate(count)\nreturn 0 }',
    'let f=(xs:array<int64> count:int64):>int64=>{ if count >=? 0 xs.truncate(count)\nreturn 0 }',
    'Box:type=[values:array<int64 length >? 0>]\nlet f=(box:Box):>int64=>{ box.values.clear\nreturn 0 }',
    'let f=(xs:array<int64>):>int64=>{ let i:int64=0\nloop i <? xs.length { if i >? 3 break\ni+=1\ncontinue }\nreturn i }',
    'let f=(xs:array<int64>):>int64=>{ let total:int64=0\nloop value in xs {total+=value}\nreturn total }',
    'let f=(flag:bool):>int64=>{ let n:int64=0\nn=if flag 3 else 4\n$assert n >=? 3\nreturn n }',
]


FIELD_EXPECTATIONS = dict(zip(CASES[:4], ['ok', 'cannot prove refinement', 'ok', 'cannot prove refinement']))
CASES.extend(LOOP_FUNCTION_CASES)
FIELD_EXPECTATIONS.update(LOOP_FUNCTION_CASES)
OBJECT_MUTATION_CASE = 'let n:int64=1\nchange=()=>{let box=[value={n=-1\n0}]}\npositive=()=>{$assert n >? 0}'
CASES.append(OBJECT_MUTATION_CASE)
FIELD_EXPECTATIONS[OBJECT_MUTATION_CASE] = 'cannot prove assertion'
LITERAL_RESULT_CASES = {
    'change=(@n:int64):>1=>{n=-1 return 1}\nmain=()=>{let n:int64=1\nchange(@n)\n$assert n >? 0}': 'cannot prove assertion',
    'change=(@n:int64):>1=>{n=-1 return 1}\nmain=()=>{let n:int64=1\nlet result=change(@n)\n$assert result =? 1\n$assert n >? 0}': 'cannot prove assertion',
    'change=(@n:int64):>1=>{n=-1 return 1}\nmain=()=>{let n:int64=1\nlet result=change(@n)\n$assert result =? 1}': 'ok',
}
CASES.extend(LITERAL_RESULT_CASES)
FIELD_EXPECTATIONS.update(LITERAL_RESULT_CASES)


# Global writes cross call boundaries even without a place argument.
GLOBAL_CALL_CASES = {
    # The intrinsic spelling grants no effect promise to a user binding.
    'let xs:array<int64>=[]\nlet __add__=(a:int64 b:int64):>int64=>{xs.clear return a}\nlet main=():>int64=>{xs.push(42) let ignored=__add__(1 2) return xs[0]}': 'array index is not proven in bounds',

    'let xs:array<int64>=[]\nlet clear=():>bool=>{xs.clear return true}\nlet main=():>int64=>{xs.push(42) if xs.length >? 0 and clear() return xs[0] return 0}': 'array index is not proven in bounds',

    # read
    'let xs:array<int64>=[]\nlet read=():>int64=>xs.length\nlet main=():>int64=>{xs.push(42) read(); return xs[0]}': 'ok',
    # write
    'let xs:array<int64>=[]\nlet clear=():>void=>{xs.clear}\nlet main=():>int64=>{xs.push(42) clear() return xs[0]}': 'array index is not proven in bounds',
    # transitive
    'let xs:array<int64>=[]\nlet clear=():>void=>{xs.clear}\nlet call=():>void=>{clear()}\nlet main=():>int64=>{xs.push(42) call() return xs[0]}': 'array index is not proven in bounds',
    # entry
    'let xs:array<int64>=[42]\nlet clear=():>void=>{xs.clear}\nlet main=():>int64=>xs[0]': 'array index is not proven in bounds',
    # default
    'let xs:array<int64>=[]\nlet clear=():>int64=>{xs.clear return 0}\nlet call=(x:int64=clear()):>void=>{}\nlet main=():>int64=>{xs.push(42) call() return xs[0]}': 'array index is not proven in bounds',
    # callback
    'let xs:array<int64>=[]\nlet invoke=(f:<():>void>):>int64=>{xs.push(42) f() return xs[0]}': 'array index is not proven in bounds',
    # nested
    'let xs:array<int64>=[]\nlet read=():>int64=>{let unused=():>void=>{xs.clear} return 0}\nlet main=():>int64=>{xs.push(42) read(); return xs[0]}': 'ok',
    # sibling
    'let xs:array<int64>=[]\nlet ys:array<int64>=[]\nlet clear=():>void=>{ys.clear}\nlet main=():>int64=>{xs.push(42) clear() return xs[0]}': 'ok',
    # recursive
    'let xs:array<int64>=[]\nlet clear=(again:bool):>void=>{if again clear(false) else xs.clear}\nlet main=():>int64=>{xs.push(42) clear(true) return xs[0]}': 'array index is not proven in bounds',
}
CASES.extend(GLOBAL_CALL_CASES)
FIELD_EXPECTATIONS.update(GLOBAL_CALL_CASES)


def test_native_bounds_visitor_matches_hosted(tmp_path):
    functions, expected = [], []
    for index, body in enumerate(CASES):
        srcfile = SrcFile(None, body)
        root, context = check._typecheck_module(srcfile)
        registry = context.binding_registry
        validator = bounds._BoundsValidator(registry, srcfile, root)
        validator.unfit = {}
        try:
            validator.validate(root)
            expected.append(f'{index}|unfit' if validator.unfit else f'{index}|ok')
        except UserError as error:
            expected.append(f'{index}|{error.report.title}')
        if body in FIELD_EXPECTATIONS:
            # Other proof suites reuse this driver with their own CASES.
            assert expected[-1] == f'{index}|{FIELD_EXPECTATIONS[body]}'
        type_lines = []
        build = type_builder(type_lines)
        hir_lines, root_id, names = emit_hir(root, type_value=build, with_names=True)
        binding_lines = []
        for binding in registry.by_id.values():
            type_ = 'none' if binding.type is None else build(binding.type)
            storage = 'none' if binding.store_type is None else build(binding.store_type)
            binding_lines.append(f'    registry.by_id[{binding.id}]=bindings.Binding[{binding.id} {json.dumps(binding.name)} {json.dumps(binding.kind)} span value_type={type_} store_type={storage} declaration={names.get(id(binding.declaration), "none")}]')
        functions.append(f'''case_{index}=():>void=>{{
    let span=Span[0 0]
    let srcfile=SrcFile['fixture' '']
    let nodes:array<hir.AST>=[]
    let type_nodes:types.Table=types.Table[]
    let registry=bindings.Registry[]
{chr(10).join(type_lines + hir_lines + binding_lines)}
    registry.next_id={registry.next_id}
    let word=types.primitive('int64' @type_nodes)
    let env=values.Environment[nodes type_nodes registry {validator.max_length}]
    let data=predicates.Data[env relations.Context[facts.Context[{validator.max_length}]] intervals.Snapshot[] registry]
    let checker=bounds.Checker[data srcfile word source_files=[srcfile]]
    bounds.configure(@checker)
    bounds.validate({root_id} @checker)
    let problem=checker.problem
    if problem isnt? none {{printl("{index}|{{problem.title}}")}}
    else {{printl("{index}|{{if checker.unfit.length >? 0 'unfit' else 'ok'}}")}}
}}
''')
    imports = '\n'.join(f'import p"{ROOT / "dewy/bootstrap/semantic" / path}" as {alias}' for alias, path in [
        ('hir', 'hir.dewy'), ('types', 'ty.dewy'), ('bindings', 'bindings.dewy'), ('props', 'propositions.dewy'),
        ('values', 'analyze/value_bounds.dewy'), ('predicates', 'analyze/predicate_facts.dewy'),
        ('facts', 'analyze/fact_state.dewy'), ('ranges', 'analyze/intervals.dewy'),
        ('intervals', 'analyze/expression_intervals.dewy'), ('relations', 'analyze/relations.dewy'),
        ('bounds', 'analyze/bounds.dewy'),
    ])
    # type_builder emits propositions under the established `facts` alias;
    # use `flow` for the abstract state in these generated fixtures.
    functions = [f.replace('facts.Context', 'flow.Context') for f in functions]
    imports = imports.replace('fact_state.dewy" as facts', 'fact_state.dewy" as flow').replace('propositions.dewy" as props', 'propositions.dewy" as facts')
    source = tmp_path / 'bounds.dewy'
    source.write_text('from reporting import Span, SrcFile\n' + imports + '\n' + '\n'.join(functions) + '\nmain=():>int64=>{\n' + '\n'.join(f'case_{i}()' for i in range(len(CASES))) + '\nreturn 0\n}\n')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == expected
