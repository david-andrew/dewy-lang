"""The online starter's value-only model and input quantization need no opt-in."""
from pathlib import Path
import shutil
import subprocess

import pytest

from tests.support import compiler, Scripts


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_online_template_numeric(compiler, tmp_path, target, release):
    source = (Path(__file__).resolve().parents[1] / 'lib/new/dewy/online.dewy').read_text()
    model = source.split('const SPEED:', 1)[1].split('# Connection and presentation state', 1)[0]
    quantize = next(line for line in source.splitlines() if line.startswith('pad_axis ='))
    program = 'const SPEED:' + model + '\n' + quantize + r'''
main=()=>{
    loop v in [-1.0 -0.75 -0.5 -0.49 0.0 0.49 0.5 0.75 1.0] printl(pad_axis(v))
    # Widening the seed calculation preserves the old game's first 40 seeds.
    let same=true
    loop i in [0..40) {
        let n=int64(i)
        if hash(int(n)*2) not=?hash(n*2) or hash(int(n)*2+1) not=?hash(n*2+1) same=false
    }
    printl(same)
    let before=Game[coin=vec2(400 360)]
    let after=tick(before [Pad[x=1] Pad[]])
    printl(before.players[0].score)
    printl(after.players[0].score)
    printl(after.taken)
    printl(after.players[0].pos=?vec2(406 360))
    printl(after.coin=?vec2(float32(100+int64(hash(int64(2))%1080)) float32(100+int64(hash(int64(3))%520))))
}
'''
    path = tmp_path / 'model.dewy'
    path.write_text(program)
    binary = tmp_path / 'model'
    flags = (['--release'] if release else []) + (['--target', 'wasm32'] if target == 'wasm' else [])
    built = subprocess.run([compiler, 'build', path, '-o', binary, *flags], capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is required for Wasm execution')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'model.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['-1', '-1', '0', '0', '0', '0', '0', '1', '1', 'true', '0', '1', '1', 'true', 'true']
