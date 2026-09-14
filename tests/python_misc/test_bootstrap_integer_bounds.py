"""Fixed integer limits are arena independent and built once per process."""
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
BODY = '''

measure=(ids:array<addr> nodes:types.Table):>int64=>{
    let before:int64=_arena_allocated_bytes
    loop repeat in 0..249 {
        loop id in ids {
            let bounds=views.fixed_integer_bounds(id nodes)
            if bounds is? none or bounds.maximum <? 1 return -1
        }
    }
    return _arena_allocated_bytes-before
}
main=():>int64=>{
    let nodes=types.Table[]
    let names=['int8' 'uint8' 'int16' 'uint16' 'int32' 'uint32' 'int64' 'uint64']
    let ids:array<addr>=[]
    loop name in names {
        let id=types.primitive(name @nodes)
        ids.push(id)
        let bounds=views.fixed_integer_bounds(id nodes)
        if bounds is? none return 1
        if not subtyping.integer_fits(bounds.minimum name) or not subtyping.integer_fits(bounds.maximum name) return 3
        if subtyping.integer_fits(bounds.minimum-1 name) or subtyping.integer_fits(bounds.maximum+1 name) return 4
        printl("{name}:{_bigint_as_string(bounds.minimum)}:{_bigint_as_string(bounds.maximum)}")
    }
    let other=types.Table[]
    let large=types.primitive('uint64' @other)
    let unknown=types.primitive('bool' @nodes)
    if views.fixed_integer_bounds(unknown nodes) isnt? none return 5
    let wide=views.fixed_integer_bounds(large other)
    if wide is? none or wide.maximum not=? 18446744073709551615 return 6
    if not subtyping.integer_fits(-1 'int') or subtyping.integer_fits(-1 'uint') return 7
    let bytes=measure(ids nodes)
    printl(bytes)
    return if bytes >=? 0 42 else 2
}
'''


def test_fixed_integer_bounds_and_fit_endpoints(tmp_path):
    source = tmp_path / 'integer-bounds.dewy'
    source.write_text(f'import p"{ROOT / "dewy/bootstrap/semantic/ty.dewy"}" as types\n'
                      f'import p"{ROOT / "dewy/bootstrap/semantic/type_queries.dewy"}" as views\n'
                      f'import p"{ROOT / "dewy/bootstrap/semantic/subtyping.dewy"}" as subtyping\n' + BODY)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    expected = []
    for bits in (8, 16, 32, 64):
        expected.extend([f'int{bits}:{-(1 << (bits-1))}:{(1 << (bits-1))-1}',
                         f'uint{bits}:0:{(1 << bits)-1}'])
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                             text=True, timeout=30, check=False)
        assert run.returncode == 42, (target, run.returncode, run.stdout, run.stderr)
        rows = run.stdout.splitlines()
        assert rows[:-1] == expected
        # Rebuilding BigInt powers for these 2,000 queries cost 19,760,000 bytes.
        assert 0 <= int(rows[-1]) < 5_000_000
