"""Timing observes the compiler process and writes only to stderr."""
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_phase_clock(tmp_path):
    source = tmp_path / 'clock.dewy'
    source.write_text(f'''import p"{ROOT / 'dewy/bootstrap/timing.dewy'}" as timing
main=():>int64=>{{
    let disabled=timing.start(false)
    if disabled isnt? none return 1
    timing.finish('disabled' disabled)
    let started=timing.start(true)
    if started is? none return 2
    let storage=_arena_alloc(1000)
    _arena_note_copy(257)
    _arena_release(storage 1000)
    timing.finish('kernel' started)
    printl('ordinary output')
    return 42
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                             text=True, timeout=10, check=False)
        assert run.returncode == 42, (target, run.returncode, run.stderr)
        assert run.stdout == 'ordinary output\n'
        timing, storage = run.stderr.splitlines()
        fields = timing.split()
        assert len(fields) == 5 and fields[:3] == ['dewy', 'timing', 'kernel']
        assert fields[3].isdigit() and fields[4] == 'ns'
        fields = storage.split()
        assert fields[:3] == ['dewy', 'storage', 'kernel']
        counters = dict(field.split('=') for field in fields[3:])
        assert set(counters) == {'allocated', 'copied', 'live', 'peak'}
        counters = {key: int(value) for key, value in counters.items()}
        assert counters['allocated'] >= 1024
        assert counters['copied'] >= 257
        assert 0 <= counters['live'] <= counters['peak']
