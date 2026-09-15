"""A restored native prelude must produce the same executable from fresh HIR."""
import os
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def check_prelude_cache(binary, work):
    work.mkdir()
    enabled_env = os.environ.copy()
    enabled_env.pop('DEWY_NO_PRELUDE_CACHE', None)
    (work / 'compiler.identity').write_bytes(b'compiler version one')
    dependency = work / 'dependency.dewy'
    dependency.write_text('const answer:int64=42\n')
    (work / 'prelude.dewy').write_text('import p"dependency.dewy" as dependency\nconst answer:int64=dependency.answer\n')
    (work / 'main.dewy').write_text('main=():>int64=>answer\n')

    def run(expected_hit, expected_exit=42, *, target='x86_64', disabled=False, first=None):
        env = os.environ.copy()
        env.pop('DEWY_NO_PRELUDE_CACHE', None)
        if isinstance(disabled, str):
            env['DEWY_NO_PRELUDE_CACHE'] = disabled
        elif disabled:
            env['DEWY_NO_PRELUDE_CACHE'] = '1'
        result = subprocess.run([binary, work, target, *([first] if first else [])],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == ('hit' if expected_hit else 'miss'), result.stdout
        source = work / 'program.udewy'
        assert entry_point(source, [], EntryPointOptions(compile_only=True, target=target)) == 0
        executed = subprocess.run([cache_artifact(source).resolve()], capture_output=True, timeout=10)
        assert executed.returncode == expected_exit, executed
        return source.read_bytes()

    cold = run(False)
    assert run(True) == cold
    assert run(True, disabled='') == cold
    assert run(False, disabled=True) == cold
    entries = list((work / 'cache').glob('*.bin'))
    assert len(entries) == 1
    entry = entries[0]
    good = entry.read_bytes()
    for damaged in (good[:-1], good + b'\0', bytes([good[0] ^ 1]) + good[1:],
                    good[:-1] + bytes([good[-1] ^ 1])):
        entry.write_bytes(damaged)
        assert run(False) == cold
        assert run(True) == cold
    # Equal size and timestamp still represent changed dependency contents.
    stamp = dependency.stat()
    dependency.write_text('const answer:int64=43\n')
    os.utime(dependency, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    changed = run(False, 43)
    assert run(True, 43) == changed
    (work / 'compiler.identity').write_bytes(b'compiler version two')
    assert run(False, 43) == changed
    assert len(list((work / 'cache').glob('*.bin'))) == 2
    run(False, 43, target='c')
    run(True, 43, target='c')
    assert len(list((work / 'cache').glob('*.bin'))) == 3
    bare = work / 'bare.dewy'
    bare.write_text('$no_prelude\nconst retained:int64=7\n')
    run(False, 43, first=bare)
    run(True, 43)
    rewritten = subprocess.run([binary, work, 'x86_64', '-', 'rewrite'], cwd=ROOT,
                               env=enabled_env, capture_output=True, text=True, timeout=60)
    assert rewritten.returncode == 1, rewritten.stdout + rewritten.stderr
    assert 'assertion refuted' in rewritten.stderr + rewritten.stdout
    # Neither this failed compilation nor a changed entry can poison the
    # shared prelude. Newly appended obligations remain independently checked.
    main = work / 'main.dewy'
    main.write_text('main=():>int64=>{$assert false return answer}\n')
    rejected = subprocess.run([binary, work, 'x86_64'], cwd=ROOT,
                              env=enabled_env, capture_output=True, text=True, timeout=60)
    assert rejected.returncode == 1, rejected.stdout + rejected.stderr
    assert 'assertion refuted' in rejected.stderr + rejected.stdout
    main.write_text('main=():>int64=>answer\n')
    assert run(True, 43) == changed
    # The generic declaration can be cached without checking its body; a
    # later entry instantiates that body and must still prove its assertions.
    prelude = work / 'prelude.dewy'
    prelude.write_text(prelude.read_text() + 'let guarded=<T>(value:T):>T=>{$assert false return value}\n')
    run(False, 43)
    main.write_text('main=():>int64=>guarded(answer)\n')
    generic = subprocess.run([binary, work, 'x86_64'], cwd=ROOT,
                             env=enabled_env, capture_output=True, text=True, timeout=60)
    assert generic.returncode == 1, generic.stdout + generic.stderr
    assert 'assertion refuted' in generic.stderr + generic.stdout
    assert not list((work / 'cache').glob('*.tmp-*'))


def test_native_prelude_cache_invalidation(tmp_path):
    source = ROOT / 'tests/fixtures/bootstrap_prelude_cache.dewy'
    output = tmp_path / 'cache-driver.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    check_prelude_cache(cache_artifact(output).resolve(), tmp_path / 'work')
