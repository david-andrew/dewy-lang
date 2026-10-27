"""Unsigned count coordinates prove word shifts without changing wide results."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_dynamic_shift_representation(compiler, tmp_path, release):
    source = tmp_path / 'shifts.dewy'
    source.write_text('''$runtime_checks
bounded=(k:int64):>int=>{
 if k <? 0 or k >? 62 return 0
 let one:int64=1
 return one << k
}
wide=(k:int64):>int=>{
 let one:int64=1
 return one << k
}
unsigned=(k:uint64):>int=>{
 if k >? 62 return 0
 let one:int64=1
 return one << k
}
right=(x:int k:uint64):>int=>x >> k
main=(args:array<string>)=>{
 let k=int64(to_int(args[1]) ?? 0)
 printl(bounded(k) wide(k) unsigned(uint64(k)) right(1 << 130 uint64(k)))
}
''')
    for debug in (False, True):
        binary = tmp_path / ('debug' if debug else 'opt')
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else []), *(['-g'] if debug else [])],
                               capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        for k in (0, 1, 31, 62, 63, 64, 100, 130, 131):
            ran = subprocess.run([binary, str(k)], capture_output=True, text=True)
            small = 1 << k if k <= 62 else 0
            assert ran.returncode == 0, ran.stderr
            assert ran.stdout.strip() == f'{small} {1 << k} {small} {(1 << 130) >> k}'
