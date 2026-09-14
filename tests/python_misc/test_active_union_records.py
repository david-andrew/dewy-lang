"""Active record handles retain union ownership and fixed-storage fallback."""
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_active_union_record_lifetimes(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/active_union_records.dewy')
    output = tmp_path / 'active-records.udewy'
    output.write_text(codegen(source, debug_locations=False))
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                text=True, timeout=15)
        assert result.returncode == 42, (target, result.returncode, result.stdout, result.stderr)


def test_union_with_fixed_record_arrays_keeps_prepared_storage(tmp_path):
    source = SrcFile(None, '''
Fixed:type=[values:array<int64 length=2>]
Dynamic:type=[values:array<int64>]
Choice:type=Fixed|Dynamic|int64
choose=(n:int64):>Choice=>if n=?0 Fixed[[20 22]] else Dynamic[[5 6]]
copy=(x:Choice):>Choice=>x
main=():>int64=>{
    let x=choose(0)
    let y=copy(x)
    if x isnt?Fixed or y isnt?Fixed return 1
    y.values[0]=99
    if x.values[0] not=?20 return 2
    y=choose(1)
    if y isnt?Dynamic return 3
    y=copy(x)
    if y isnt?Fixed return 4
    return y.values[0]+y.values[1]
}
''')
    output = tmp_path / 'fixed-union.udewy'
    output.write_text(codegen(source, debug_locations=False))
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                text=True, timeout=15)
        assert result.returncode == 42, (target, result.returncode, result.stdout, result.stderr)
