"""Default loop inlining keeps record values and checked failure paths intact."""
import re
import shutil
import subprocess

import pytest

from tests.support import Scripts, compiler, target_name
from tools.compiler.bench import prepare_source


def function(ir, name):
    return next(body for body in re.split(r'^fn ', ir, flags=re.MULTILINE)
                if body.startswith(f'f_{name}_'))


@pytest.mark.core_quick
@pytest.mark.parametrize('debug', [False, True])
def test_default_game_inline(compiler, tmp_path, debug):
    source = prepare_source('game', tmp_path)
    binary = tmp_path / 'game'
    built = subprocess.run([compiler, 'build', source, '--ir',
                            *(['-g'] if debug else []), '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    simulate = function(built.stdout, 'simulate')
    assert bool(re.search(r'\bcall a=.*c=0 ', simulate)) == debug, simulate
    if not debug:
        assert not re.search(r'\bcopy .*imm=24\b', simulate), simulate
    ran = subprocess.run([binary, '1000'], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.split()[0] == '2096'


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_record_inline_checks_and_loop_scope(compiler, tmp_path, target):
    source = tmp_path / 'checked.dewy'
    source.write_text('''$no_assumed_bounds
Box:type=[value:int64]
read=(box:Box at:int64):>Box=>{
 let table:array<int64 length=2>=[20 22]
 let next=box
 next.value+=table[at]
 return next
}
probe=(at:int64):>int64=>{
 let original=Box[2]
 let box=original
 loop i in [0..2) {
  loop j in [0..1) {box=read(box at)}
  if i=?0 {box=read(box at)}
 }
 let final=read(box at)
 return final.value+original.value
}
main=(args:array<string>):>void=>{exit(probe(args.length-1))}
''')
    binary = tmp_path / 'checked'
    built = subprocess.run([compiler, 'build', source, '--ir', '--target', target_name(target),
                            '-o', binary], capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = function(built.stdout, 'probe')
    # Nested loops and conditional calls inline, but the call after the loop
    # stays out of line. Two expanded bounds checks and three exact stores
    # retain their own failure paths.
    assert len(re.findall(r'\bcall .* b=3 c=0 ', probe)) == 1, probe
    assert len(re.findall(r'\bcall .* c=1 ', probe)) == 2, probe
    assert len(re.findall(r' = checked_add ', probe)) == 3, probe
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web inlining checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'checked.cjs'
        runner.write_text('const dewyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [node, runner]
    for arguments, expected in [([], 84), (['one'], 92), (['one', 'two'], None)]:
        ran = subprocess.run([*command, *arguments], capture_output=True, text=True, timeout=10)
        if expected is not None:
            assert ran.returncode == expected, ran.stdout + ran.stderr
        else:
            assert ran.returncode not in (0, 84, 92), ran.stdout + ran.stderr
            assert 'out of bounds' in ran.stdout + ran.stderr
            assert 'checked.dewy' in ran.stdout + ran.stderr
