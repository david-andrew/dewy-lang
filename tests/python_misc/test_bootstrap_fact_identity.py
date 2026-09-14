"""Identity proof operations preserve value snapshots and capped provenance."""
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.analyze import bounds
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
BODY = '''

measure=(state:facts.State context:facts.Context):>int64=>{
    let before:int64=_arena_allocated_bytes
    loop repeat in 0..99 {
        let branch=facts.join([state] context)
        facts.put(@branch facts.value(facts.Term[1]) ranges.exact(1))
        if branch.values.length not=? state.values.length return -1
    }
    return _arena_allocated_bytes-before
}
main=():>int64=>{
    let state=facts.State[]
    loop id in 0..63 {facts.put(@state facts.value(facts.Term[id]) ranges.exact(id))}
    let context=facts.Context[cap=1024]
    let bytes=measure(state context)
    printl(bytes)
    let fork=facts.join([state] context)
    let saved=fork
    let key=facts.value(facts.Term[1])
    facts.put(@fork key ranges.Interval[1 1 true])
    let changed=facts.lookup(fork key)
    let original=facts.lookup(saved key)
    if changed is? none or original is? none return 1
    if not changed.capped or original.capped return 2
    facts.put(@fork key ranges.Interval[2 3])
    let replaced=facts.lookup(fork key)
    if replaced is? none or not ranges.same_bounds(replaced ranges.Interval[2 3]) return 3
    let retained=facts.lookup(state key)
    if retained is? none or not ranges.same_bounds(retained ranges.exact(1)) return 4
    if facts.join([] context).values.length not=? 0 return 5
    return if bytes >=? 0 42 else 6
}
'''


def test_hosted_single_path_join_is_an_independent_mapping():
    validator = object.__new__(bounds._BoundsValidator)
    original = {1: bounds.Interval(0, 3, capped=True)}
    joined = validator._join_states([original])
    assert joined == original and joined is not original
    joined[1] = bounds.Interval.exact(42)
    assert original[1] == bounds.Interval(0, 3, capped=True)
    assert validator._join_states([]) == {}


def test_native_identity_operations_avoid_detaching_snapshots(tmp_path):
    source = tmp_path / 'fact-identity.dewy'
    source.write_text(f'import p"{ROOT / "dewy/bootstrap/semantic/analyze/fact_state.dewy"}" as facts\n'
                      f'import p"{ROOT / "dewy/bootstrap/semantic/analyze/intervals.dewy"}" as ranges\n' + BODY)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                             text=True, timeout=30, check=False)
        assert run.returncode == 42, (target, run.returncode, run.stdout, run.stderr)
        # The previous implementation rebuilt and detached 64-entry states,
        # allocating 14,899,240 bytes for these 100 identity operations.
        assert 0 <= int(run.stdout.strip()) < 1_000_000
