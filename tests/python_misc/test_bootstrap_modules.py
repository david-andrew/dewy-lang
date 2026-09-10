"""Native modules share imported declaration identities and namespace lookup."""

import json
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import ty
from dewy.semantic.hir_display import type_to_dewy
from dewy.semantic.modules import ModuleCompiler
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_module_graph_and_namespace_bindings(tmp_path):
    base = tmp_path / 'base.dewy'
    base.write_text('''$no_prelude
Number:type=type of [value:int64]
let answer:int64=41
let plus=(x:Number):>int64 => x.value+1
let identity=<T>(x:T):>T=>x
let answer_for=<T>(unused:T):>int64=>answer
''')
    entry = tmp_path / 'entry.dewy'
    entry.write_text('''$no_prelude
$supported_targets=["x86_64" "arm" "riscv" "c"]
$prototype=true
$prototype_warnings=false
if $target in? ["x86_64" "arm" "riscv" "c"] {
    from p"base.dewy" import (Number as N plus)
    let platform:int64=7
}
if $target =? "wasm32" {
    from p"missing-platform.dewy" import unavailable
}
import p"./base.dewy" as base
let n:base.Number=base.Number[value=base.answer]
let result:int64=plus(n)
let local=(base:[answer:int64]):>int64 => base.answer
let same=base.identity(7)
let same_again=base.identity(8)
let name=base.identity("text")
let shadow=(answer:string):>int64=>base.answer_for(answer)
let original=shadow("caller")
''')
    ty.reset_program_brands()
    hosted = ModuleCompiler(SrcFile.from_path(entry)).load(entry, entry=True)
    # Hosted exports include generated instance names. The native graph keeps
    # those in its hoisted declarations; compare the source-facing exports.
    # Compare exported declaration contracts. The hosted registry may keep a
    # singleton initializer (7) alongside its explicit mutable contract (int64);
    # native representation selection has not yet separated those descriptions.
    expected = [
        f'{name}:{type_to_dewy(binding.declaration.annotation if binding.declaration is not None and binding.declaration.annotation is not None else binding.type)}'
        for name, binding in hosted.exports.items() if binding.generic_instance is None
    ]
    missing = tmp_path / 'missing.dewy'
    missing.write_text('$no_prelude\nfrom p"base.dewy" import Missing\n')
    cycle_a, cycle_b = tmp_path / 'cycle_a.dewy', tmp_path / 'cycle_b.dewy'
    cycle_a.write_text('import p"cycle_b.dewy" as other\n')
    cycle_b.write_text('import p"cycle_a.dewy" as other\n')
    directive_errors = []
    for index, (text, title) in enumerate([
        ('$no_prelude=true\n$no_prelude=false', 'duplicate `$no_prelude` directive'),
        ('$no_prelude=7', '`$no_prelude` must be a boolean literal'),
        ('$prototype="yes"', '`$prototype` must be a boolean literal'),
        ('$supported_targets=["wasm32"]', 'module does not support target `x86_64`'),
        ('$supported_targets=[7]', '`$supported_targets` must list string target names'),
    ]):
        path = tmp_path / f'directive-error-{index}.dewy'
        path.write_text(text)
        directive_errors.append(f'''let invalid{index}=modules.load({json.dumps(str(path))} @engine)
    $runtime_assert invalid{index} is? Error and invalid{index}.title =? {json.dumps(title)}''')
    source = tmp_path / 'modules.dewy'
    source.write_text(f'''from reporting import Error
import p"{ROOT / 'dewy/bootstrap/semantic/modules.dewy'}" as modules
import p"{ROOT / 'dewy/bootstrap/semantic/bindings.dewy'}" as bindings
import p"{ROOT / 'dewy/bootstrap/semantic/type_display.dewy'}" as display
main = ():>int64 => {{
    let engine=modules.Engine[]
    let entry=modules.load({json.dumps(str(entry))} @engine)
    if entry is? Error {{ entry.fail return 1 }}
    $runtime_assert engine.modules.length =? 2
    $runtime_assert engine.session.registry.generic_instances.length =? 3
    $runtime_assert engine.session.hoisted.length =? 3
    let root=modules.module_at(entry engine)
    $runtime_assert root.no_prelude and root.options.prototype and not root.options.prototype_warnings
    loop [name binding_id] in root.exports {{
        let binding=bindings.binding_at(engine.session.registry binding_id)
        $runtime_assert binding.value_type isnt? none
        printl("{{name}}:{{display.type_to_dewy(binding.value_type engine.session.types)}}")
    }}
    let scope=bindings.scope_at(engine.session.scopes root.context.scope)
    let alias=scope.names.get('N')
    $runtime_assert alias isnt? none
    let base=modules.module_at(0 engine)
    $runtime_assert base.exports.get('Number') =? alias
    let failed=modules.load({json.dumps(str(missing))} @engine)
    $runtime_assert failed is? Error and failed.title =? 'module does not export this name'
    let cycle=modules.load({json.dumps(str(cycle_a))} @engine)
    $runtime_assert cycle is? Error and cycle.title =? 'cyclic module import'
    {chr(10).join(directive_errors)}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected
