"""Immutable string snapshots have bounded costs and independent lifetimes."""
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.backend.udewy.lowering_strings import _StringLowering
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]


def program(width):
    return f'''
Box:type=[text:string]
make=(n:int64):>Box=>Box["{'a' * width}{{n}}"]
exercise=(box:Box):>int64=>{{
    let total:int64=0
    loop i in 0.. and i <? 100 {{let own=box total+=own.text.length}}
    return total
}}
main=():>int64=>{{
    let box=make(42)
    if exercise(box) not=? {(width + 2) * 100} return 1
    let live:int64=_arena_live_bytes
    let allocated:int64=_arena_allocated_bytes
    if exercise(box) not=? {(width + 2) * 100} return 2
    let used:int64=_arena_allocated_bytes-allocated
    let retained:int64=_arena_live_bytes-live
    printl("{{used}} {{retained}}")
    if retained not=? 0 return 3
    return 42
}}
'''


def test_owned_string_copy_cost_is_independent_of_buffer_length(tmp_path, monkeypatch):
    allocated = []
    for width in (16, 65536):
        source = SrcFile(None, program(width))
        shared = codegen(source, debug_locations=False)
        with monkeypatch.context() as patch:
            patch.setattr(_StringLowering, '_shared_string_clone_prefix', lambda *_: [])
            fallback = codegen(source, debug_locations=False)
        fast = execute(tmp_path, f'shared-{width}', shared)
        slow = execute(tmp_path, f'copied-{width}', fallback)
        for kept, copied in zip(fast, slow):
            used, retained = map(int, kept.stdout.split())
            copied_bytes, copied_retained = map(int, copied.stdout.split())
            assert retained == copied_retained == 0
            assert used < 16384
            assert used < copied_bytes
        allocated.append([int(result.stdout.split()[0]) for result in fast])
    assert allocated[0] == allocated[1]


def test_raw_string_exposure_preserves_other_snapshots(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/shared_string_raw.dewy')
    execute(tmp_path, 'raw-strings', codegen(source, debug_locations=False))
