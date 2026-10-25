"""An effectful RHS must reacquire a dictionary entry in a called function."""

import shutil
import subprocess

import pytest

from tests.support import Scripts, compiler, target_name  # noqa: F401


# Reduced from the 21-case dictionary matrix.  A direct main-body update is
# already covered by rhs_replace_count.dewy and passes; the called form fails.
SOURCE = '''
$runtime_checks
let d:dict<string int64>=["a"->0]
replace=():>int64=>{d=["a"->100]; return 0}
apply=():>int64=>{d["a"]+=replace(); return d["a"]}
main=()=>printl(apply())
'''


@pytest.mark.xfail(strict=True, reason='called dictionary update uses stale entry since 4fda96c0a')
def test_differential_dict_effect(compiler, tmp_path):
    source = tmp_path / 'dict.dewy'
    source.write_text(SOURCE)
    observed = {}
    for mode, flags in {'native': (), 'release': ('--release',), 'debug': ('-g',),
                        'wasm': ('--target', 'wasm32'),
                        'arm64': ('--target', target_name('linux-arm64'))}.items():
        if mode == 'wasm' and not shutil.which('node'):
            pytest.skip('Node is needed for web execution')
        if mode == 'arm64' and not shutil.which('qemu-aarch64'):
            pytest.skip('qemu-aarch64 is needed for arm64 execution')
        binary = tmp_path / mode
        built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, f'{mode}: {built.stdout}{built.stderr}'
        if mode == 'wasm':
            scripts = Scripts()
            scripts.feed(binary.with_suffix('.html').read_text())
            runner = tmp_path / 'wasm.cjs'
            runner.write_text('\n'.join(scripts.parts))
            command = [shutil.which('node'), runner]
        elif mode == 'arm64':
            command = [shutil.which('qemu-aarch64'), binary]
        else:
            command = [binary]
        ran = subprocess.run(command, capture_output=True, text=True, timeout=20)
        assert ran.returncode == 0, (mode, ran.stdout, ran.stderr)
        observed[mode] = ran.stdout
    assert observed == {mode: '100\n' for mode in observed}, observed
