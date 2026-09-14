"""Intern hits must not rebuild recursive structural descriptions."""
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
BODY = '''
main=():>int64=>{
    let nodes=types.Table[]
    let base=types.primitive('int64' @nodes)
    loop depth in 0..23 {base=types.array_type(base none @nodes)}
    let fields=[types.ObjectField['value' base default=17]]
    let pos=[types.PosOrKwArg['x' base]]
    let props=[facts.Proposition[subject='self' op='>?' value=0]]
    let object=types.object_type(fields none true [] [] @nodes)
    let fn=types.function_type(pos [] none base [] @nodes)
    let refined=types.refined_type(base props @nodes)
    let array=types.array_type(base none @nodes)
    let count=nodes.entries.length
    let before:int64=_arena_allocated_bytes
    loop repeat in 0..999 {
        if types.object_type(fields none true [] [] @nodes) not=? object return 1
        if types.function_type(pos [] none base [] @nodes) not=? fn return 2
        if types.refined_type(base props @nodes) not=? refined return 3
        if types.array_type(base none @nodes) not=? array return 4
    }
    printl(_arena_allocated_bytes-before)
    return if nodes.entries.length =? count 42 else 5
}
'''


def test_type_factory_hits_avoid_shape_construction(tmp_path):
    source = tmp_path / 'factory-hits.dewy'
    source.write_text(f'import p"{ROOT / "dewy/bootstrap/semantic/ty.dewy"}" as types\n'
                      f'import p"{ROOT / "dewy/bootstrap/semantic/propositions.dewy"}" as facts\n' + BODY)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                             text=True, timeout=30, check=False)
        assert run.returncode == 42, (target, run.returncode, run.stdout, run.stderr)
        # The previous implementation allocated 35,808,000 bytes for these
        # 4,000 hits. Permit implementation variation without losing the gain.
        assert 0 <= int(run.stdout.strip()) < 7_000_000
