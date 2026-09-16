"""Structured fact identity survives collisions, dense removal, and snapshots."""
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
BODY = '''
measure=(state:facts.State):>int64=>{
    let before:int64=_arena_allocated_bytes
    loop i in 0.. and i <? 1000 {
        let one=facts.lookup(state facts.value(facts.Term[1]))
        let two=facts.lookup(state facts.order(facts.Term[1] facts.Term[2 'length']))
        let three=facts.lookup(state facts.index(1 2))
        let four=facts.lookup(state facts.nonzero(1))
        let five=facts.lookup(state facts.remainder(facts.Term[1] facts.Term[2 'length'] 3))
        if one is? none or two is? none or three is? none or four is? none or five is? none return -1
    }
    return _arena_allocated_bytes-before
}
main=():>int64=>{
    # Force every kind into one bucket, including distinct projections and
    # binding ids beyond the old packed representation. Hash equality alone
    # must never grant a proof or remove another fact.
    let keys:array<facts.Fact>=[
        facts.Value[0 facts.Term[1]] facts.Value[0 facts.Term[1 'length']]
        facts.Index[0 1 2] facts.Nonzero[0 1]
        facts.Order[0 facts.Term[1] facts.Term[2 'length']]
        facts.Remainder[0 facts.Term[1] facts.Term[2 'length'] 3]
        facts.Value[0 facts.Term[2097152]]
        facts.Order[0 facts.Term[2097152] facts.Term[1]]
    ]
    let state=facts.State[]
    loop i in 0.. and i <? keys.length {facts.put(@state keys[i] ranges.exact(i))}
    let saved=state
    facts.put(@state keys[2] ranges.exact(99))
    facts.remove(@state keys[0])
    facts.remove(@state keys[4])
    facts.remove(@state keys[4])
    loop i in 0.. and i <? keys.length {
        let original=facts.lookup(saved keys[i])
        if original is? none or not ranges.same_bounds(original ranges.exact(i)) return 1
        let changed=facts.lookup(state keys[i])
        if i =? 0 or i =? 4 {if changed isnt? none return 2}
        else {
            let expected:int64=if i =? 2 99 else i
            if changed is? none or not ranges.same_bounds(changed ranges.exact(expected)) return 3
        }
    }
    # Reinsert into the same bucket after moving dense entries, then empty
    # it completely. No stale position may survive either operation.
    facts.put(@state keys[0] ranges.exact(42))
    loop key in keys {facts.remove(@state key)}
    if state.values.length not=? 0 or state.heads.length not=? 0 or state.next.length not=? 0 return 4
    state=facts.State[]
    facts.put(@state facts.value(facts.Term[1]) ranges.exact(42))
    facts.put(@state facts.order(facts.Term[1] facts.Term[2 'length']) ranges.exact(42))
    facts.put(@state facts.index(1 2) ranges.exact(42))
    facts.put(@state facts.nonzero(1) ranges.exact(42))
    facts.put(@state facts.remainder(facts.Term[1] facts.Term[2 'length'] 3) ranges.exact(42))
    let bytes=measure(state)
    printl(bytes)
    return if bytes >=? 0 42 else 5
}
'''


def test_structured_fact_index(tmp_path):
    source = tmp_path / 'fact-index.dewy'
    source.write_text(f'''import p"{ROOT / 'dewy/bootstrap/semantic/analyze/fact_state.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as ranges
''' + BODY)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                             text=True, timeout=30, check=False)
        assert run.returncode == 42, (target, run.returncode, run.stdout, run.stderr)
        # The string-key implementation allocated 5,424,000 bytes for these
        # 5,000 lookups. Keep this a cost gate on the actual generated code.
        assert 0 <= int(run.stdout.strip()) < 2_712_000
