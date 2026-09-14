"""Native scalar getter variants retain return cleanup and input ownership."""
import subprocess
from pathlib import Path

from tests.python_misc.test_bootstrap_lowering import ARENA, build_native_lowering_driver
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def check_native_projection(binary, tmp_path):
    text = (ROOT / 'tests/fixtures/native_scalar_projection.dewy').read_text()
    # This driver enters below fact validation/runtime-report installation.
    # Use plain indices and a divergent guard for the valid-input cost gate:
    # a raw syscall would conservatively disable argument borrowing. The
    # separate effects/guard gates below retain the raw failure path.
    text = text.replace('    printl("{allocations} {copies} {retained}")',
                        '    if allocations not=? 0 or copies not=? 0 return 4')
    text = text.replace('$runtime_assert id <? nodes.length',
                        'loop id >=? nodes.length {}')
    text = text.replace('id:addr', 'id:int64')
    effects = (ROOT / 'tests/fixtures/scalar_projection_effects.dewy').read_text()
    effects = effects.replace('addr', 'int64').replace('$runtime_assert id <? nodes.length',
                                                     'if id >=? nodes.length {__syscall1__(60 101);}')
    effects = effects.replace('$runtime_assert nodes.length >? 0',
                              'if nodes.length =? 0 {__syscall1__(60 101);}')
    guard = '''
Node=type of [value:int64]
node_at=(nodes:array<Node> id:int64):>Node=>{
    if id >=? nodes.length {__syscall1__(60 101);}
    return nodes[id]
}
main=():>int64=>{let nodes:array<Node>=[] return node_at(nodes 0).value}
'''
    for name, body, expected in [('scalar-projection', text, 42), ('effects', effects, 42), ('guard', guard, 101)]:
        source = tmp_path / f'{name}.dewy'
        source.write_text(ARENA + body)
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=45, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        output = source.with_suffix('.udewy')
        output.write_text(result.stdout)
        for target in ['x86_64', 'c']:
            assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
            run = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True,
                                 timeout=15, check=False)
            assert run.returncode == expected, (name, run.returncode, run.stdout, run.stderr)


def test_native_scalar_projection(tmp_path):
    check_native_projection(build_native_lowering_driver(tmp_path), tmp_path)


def test_shared_read_is_not_projected_out_of_the_prefix(tmp_path):
    source = tmp_path / 'shared-read.dewy'
    source.write_text(f'''
from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/backend/udewy/lower.dewy'}" as lower
main=():>int64=>{{
    let nodes:array<hir.AST>=[]
    let loc=Span[0 0]
    let read=hir.append_node(@nodes hir.ExpressedIdentifier[loc 0 'record' 0])
    let returned=hir.append_node(@nodes hir.Return[loc 0 read])
    let unique=hir.append_node(@nodes hir.Block[loc 0 [returned] true])
    let prefix=hir.append_node(@nodes hir.Suppress[loc 0 read])
    let shared=hir.append_node(@nodes hir.Block[loc 0 [prefix returned] true])
    if lower.getter_read(unique nodes) not=? read return 1
    if lower.getter_read(shared nodes) isnt? none return 2
    return 42
}}
''')
    target = source.with_suffix('.udewy')
    target.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert entry_point(target, [], EntryPointOptions(compile_only=True)) == 0
    assert subprocess.run([cache_artifact(target).resolve()], timeout=15, check=False).returncode == 42
