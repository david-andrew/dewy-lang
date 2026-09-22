"""Typed snapshots retain graph identities and reject incomplete data."""
import subprocess
import sys
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_snapshot_values(tmp_path):
    source = ROOT / 'tests/fixtures/native_cache_snapshot.dewy'
    output = tmp_path / 'snapshot.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=30)
        assert result.returncode == 42, (target, result.returncode, result.stdout, result.stderr)


def test_generated_snapshot_codec_is_current():
    result = subprocess.run([sys.executable, ROOT / 'tools/generate_native_cache.py', '--check'],
                            cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr


def test_effect_contracts_survive_native_snapshot(tmp_path):
    """A cached callable must retain permissions, exclusions and row binders."""
    body = (ROOT / 'tests/fixtures/native_cache_snapshot.dewy').read_text()
    body = body.replace('p"../../dewy/bootstrap/', f'p"{ROOT / "dewy/bootstrap"}/')
    body = body.replace('import p"', f'import p"{ROOT / "dewy/bootstrap/semantic/effect_rows.dewy"}" as rows\nimport p"', 1)
    body = body.replace('    let span=Span[0 1]', '''    let resources=rows.Row[[rows.Atom['reads' rows.Subject['resource' 'mint:17']]] ['binder:E']]
    let contract=rows.Contract[resources [rows.Atom['mutates' rows.Subject['parameter' 'slot:0' ['items']]]]]
    let parameters=[types.GenericParam['E' word 'effect' 'binder:E']]
    let callable=types.function_type([] [] none word parameters @session.types effects=contract)
    let pure=types.function_type([] [] none word [] @session.types effects=rows.Contract[rows.Row[]])
    let open=types.function_type([] [] none word [] @session.types)
    if callable =? pure or pure =? open return 25
    let span=Span[0 1]''')
    body = body.replace("    if types.primitive('int64' @copy.types) not=? word return 4", '''    if not copy.types.effect_contracts return 26
    let recovered=types.node_at(copy.types callable)
    if recovered isnt? types.FunctionType return 27
    if rows.identity(recovered.effects) not=? rows.identity(contract) return 28
    if recovered.type_params.length not=? 1 or recovered.type_params[0].kind not=? 'effect' or recovered.type_params[0].identity not=? 'binder:E' return 32
    if types.function_type([] [] none word parameters @copy.types effects=contract) not=? callable return 29
    let recovered_pure=types.node_at(copy.types pure)
    if recovered_pure isnt? types.FunctionType or not rows.implies(recovered_pure.effects rows.Contract[rows.Row[]]) return 30
    let recovered_open=types.node_at(copy.types open)
    if recovered_open isnt? types.FunctionType or rows.implies(recovered_open.effects rows.Contract[rows.Row[]]) return 31
    if types.primitive('int64' @copy.types) not=? word return 4''')
    body = body.replace('    record.value_type=word', """    record.kind='effect'
    record.effect_value=contract
    session.registry.generic_instances[binding]=bindings.GenericInstance[binding [] syntax ['binder:E' -> contract]]
    record.value_type=word""")
    body = body.replace("    if restored.prelude_bindings.get('answer') not=? binding return 6", """    let restored_binding=bindings.binding_at(copy.registry binding)
    if restored_binding.kind not=? 'effect' or restored_binding.effect_value is? none return 33
    if rows.identity(restored_binding.effect_value) not=? rows.identity(contract) return 34
    let instance=copy.registry.generic_instances.get(binding)
    if instance is? none return 35
    let argument=instance.effect_arguments.get('binder:E')
    if argument is? none or rows.identity(argument) not=? rows.identity(contract) return 36
    if restored.prelude_bindings.get('answer') not=? binding return 6""")
    source = tmp_path / 'effect-snapshot.dewy'
    source.write_text(body)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=30)
        assert result.returncode == 42, (target, result.returncode, result.stdout, result.stderr)
