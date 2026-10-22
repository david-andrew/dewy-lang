"""`$target` is the full target name, by the design's spelling, including in interpolation."""
import platform

import pytest

from tests.support import compiler  # noqa: F401 (fixture)
from tests.test_surface import run

PROGRAM = '''
if $target =? "aarch64-linux" {
    word=()=>"{$target.arch} {$target.os}"
} else {
    word=()=>"other {$target.arch} {$target.os}"
}
main=()=>printl"{$target} {word()}"
'''


@pytest.mark.parametrize('target, expected', [
    pytest.param('native', 'x86_64-linux other x86_64 linux', marks=pytest.mark.core_quick),
    ('wasm', 'wasm32 other wasm32 none'),
    ('linux-arm64', 'aarch64-linux aarch64 linux'),
])
def test_target_names(compiler, tmp_path, target, expected):
    if target == 'native' and (platform.machine() != 'x86_64' or platform.system() != 'Linux'):
        pytest.skip('the native expectation is for an x86-64 Linux host')
    ran = run(compiler, tmp_path, PROGRAM, target)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == expected + '\n'
