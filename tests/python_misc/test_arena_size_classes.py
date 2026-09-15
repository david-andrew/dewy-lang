"""Arena size selection retains exact power-of-two boundaries and reuse."""
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_arena_class_boundaries_and_reused_block_clearing(tmp_path):
    sizes = {0, -1, *range(1, 300)}
    for power in range(3, 51):
        sizes.update([2**power - 1, 2**power, 2**power + 1])
    checks = []
    for size in sorted(sizes):
        cls = max(0, (max(size, 1) - 1).bit_length() - 3)
        checks.append(f'if _arena_class({size}) not=? {cls} return 1')
    for cls in [-1, *range(65)]:
        width = 8 if cls < 0 else (8 << cls) % 2**64
        if width >= 2**63:
            width -= 2**64
        checks.append(f'if _arena_width({cls}) not=? {width} return 2')
    source = tmp_path / 'classes.dewy'
    source.write_text('''main=():>int64=>{
''' + '\n'.join(checks) + '''
    let before:int64=_arena_live_bytes
    let block=_arena_alloc(72)
    __store_i64__(123 block)
    __store_i64__(456 block+120)
    _arena_release(block 72)
    let reused=_arena_alloc(100)
    if reused not=? block return 3
    if __load_i64__(reused) not=? 0 or __load_i64__(reused+120) not=? 0 return 4
    _arena_release(reused 100)
    if _arena_live_bytes not=? before return 5
    return 42
}
''')
    output = tmp_path / 'classes.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                             text=True, timeout=10, check=False)
        assert run.returncode == 42, (target, run.stderr)
