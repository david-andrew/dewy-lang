"""Immediate literal fmt calls keep validation without loading closure/runtime code."""
import os
import shutil
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_fmt_literals_without_formats_module(compiler, tmp_path, release):
    library = tmp_path / 'lib'
    shutil.copytree(ROOT / 'lib', library)
    (library / 'prelude/formats.dewy').unlink()
    source = tmp_path / 'main.dewy'
    source.write_text('''$bulletproof
show=(x:int64):>string & allocates & no panics=>fmt'#06x'(x)
main=():>(void|OutOfMemory) & no panics=>{
printl(show(42) or_throw)
printl("{fmt'.2f'(1.25)} {fmt'^5'("ab")} {fmt','(2^70)}")
let a:int8=-7
let b:int16=-7
let c:int32=-7
let d:uint8=7
let e:uint16=7
let f:uint32=7
let g:uint64=18446744073709551615
let h:float32=1.25
printl("{fmt'd'(a)} {fmt'd'(b)} {fmt'd'(c)} {fmt'x'(d)} {fmt'x'(e)} {fmt'x'(f)} {fmt'x'(g)} {fmt'.2f'(h)}")
}
''')
    binary = tmp_path / 'program'
    env = dict(os.environ, DEWY_CORE_LIB=str(library))
    result = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run([binary], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ('0x002a\n1.25  ab   1,180,591,620,717,411,303,424\n'
                             '-7 -7 -7 7 7 7 ffffffffffffffff 1.25\n')


@pytest.mark.parametrize('declaration', [
    'fmt=(p:string)=>(x:int64):>string=>"module"',
    'from p"custom.dewy" import fmt',
    'from p"custom.dewy" import (custom as fmt)',
    'let fmt=(p:string)=>(x:int64):>string=>"module"',
])
def test_fmt_literal_respects_shadowing(compiler, tmp_path, declaration):
    (tmp_path / 'custom.dewy').write_text('''fmt=(p:string)=>(x:int64):>string=>"module"
custom=(p:string)=>(x:int64):>string=>"module"
''')
    source = tmp_path / 'main.dewy'
    source.write_text(declaration + '''
printl(fmt'q'(5))
local=():>string=>{
    let fmt=(p:string)=>(x:int64):>string=>"local"
    fmt'q'(5)
}
printl(local())
''')
    result = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == 'module\nlocal\n'
