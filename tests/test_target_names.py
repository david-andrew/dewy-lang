"""`$target` names each backend by the design's spelling, including in interpolation."""
import platform

import pytest

from tests.support import compiler  # noqa: F401 (fixture)
from tests.test_surface import run

PROGRAM = '''
if $target =? "arm" {
    word=()=>"arm arm"
} else {
    word=()=>"other {$target}"
}
main=()=>printl"{$target} {word()}"
'''


@pytest.mark.parametrize('target, expected', [
    pytest.param('native', 'x86_64 other x86_64', marks=pytest.mark.core_quick),
    ('wasm', 'wasm32 other wasm32'),
    ('linux-arm64', 'arm arm arm'),
])
def test_target_names(compiler, tmp_path, target, expected):
    if target == 'native' and platform.machine() != 'x86_64':
        pytest.skip('the native expectation is for an x86-64 host')
    ran = run(compiler, tmp_path, PROGRAM, target)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == expected + '\n'
