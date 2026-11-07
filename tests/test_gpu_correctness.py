"""GPU contracts under the default panic policy, on drivers and CPU fallbacks."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import Scripts, compiler  # noqa: F401
from tools.headless import headless

CASES = Path(__file__).parent / 'cases'
GROUPS = ['gpu_integer_upload', 'gpu_ieee']


@pytest.mark.parametrize('group', GROUPS)
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_gpu_correctness(compiler, tmp_path, group, target, release):
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    headless(env)
    env.update(DEWY_THREADS='1', LP_NUM_THREADS='1', DEWY_VK_PIPELINE_CACHE='0')
    profiles = [{}, {'DEWY_VULKAN': '0', 'EGL_PLATFORM': 'surfaceless'},
                {'DEWY_NO_GPU': '1'}, {'DEWY_SOFTWARE': '1'}]
    if target == 'wasm':
        if not shutil.which('node'):
            pytest.skip('Node is needed for wasm CPU fallback')
        profiles = [{'DEWY_SOFTWARE': '1'}]
    for source in sorted((CASES / group).glob('*.dewy')):
        binary = tmp_path / source.stem
        flags = (['--release'] if release else []) + (['--target', 'wasm32'] if target == 'wasm' else [])
        built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                               env=env, capture_output=True, text=True, timeout=60)
        if source.with_suffix('.err').exists():
            assert built.returncode != 0, source.name
            assert source.with_suffix('.err').read_text().strip() in built.stderr, built.stderr
            continue
        assert built.returncode == 0, f'{source.name}\n{built.stdout}{built.stderr}'
        command = [binary]
        if target == 'wasm':
            scripts = Scripts()
            scripts.feed(binary.with_suffix('.html').read_text())
            runner = binary.with_suffix('.cjs')
            runner.write_text("const dewyFs = require('node:fs');\nconst dewyArgs = process.argv.slice(1);\n" + '\n'.join(scripts.parts))
            command = ['node', runner]
        expected = source.with_suffix('.out').read_text()
        for profile in profiles:
            ran = subprocess.run(command, env=dict(env, **profile), capture_output=True, text=True, timeout=20)
            assert ran.returncode == 0 and ran.stdout == expected, f'{source.name} {profile}\n{ran.stdout}{ran.stderr}'
