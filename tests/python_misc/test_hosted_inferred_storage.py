"""Inferred singleton facts still use ordinary runtime local storage."""
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_inferred_local_storage_preserves_runtime_reads(tmp_path):
    source = tmp_path / 'locals.dewy'
    source.write_text('''let counter:int64=0
let read=():>int64=>{let value=counter return value}
let narrowed=(value:int64):>int64=>{
    if value =? 42 {let copy=value return copy}
    return 1
}
let main=():>int64=>{
    counter=42
    let before=read()
    counter=1
    return narrowed(before)
}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=10)
        assert run.returncode == 42, (target, run)
