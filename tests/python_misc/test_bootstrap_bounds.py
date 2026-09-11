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
CASES = [
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
    let type_nodes:array<types.Type>=[]
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
