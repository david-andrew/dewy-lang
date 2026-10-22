"""Direct module functions retain signatures and synthesized parameter locals."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_direct_module_function(compiler, tmp_path, release):
    source = tmp_path / 'functions.dewy'
    source.write_text('''increment=(@value:int64):>void=>{value+=1}
add=(value:int64 extra:int64=1):>int64=>value+extra
length=(values:array<int64>):>int64=>values.length
main=():>void=>exit(entry()) entry=()=>{
    let value:int64=40
    increment(@value)
    return add(value)
}
''')
    images = []
    for mode in ('old', 'compare'):
        output = tmp_path / mode
        result = subprocess.run([compiler, 'build', source,
                                 *(['--release'] if release else []), '-o', output],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        images.append(output.read_bytes())
        assert subprocess.run([output], timeout=10).returncode == 42
    assert images[0] == images[1]


@pytest.mark.parametrize('depth', [0, 250, 252, 253, 254, 255, 256])
def test_function_nesting_diagnostics(compiler, tmp_path, depth):
    source = tmp_path / 'nested.dewy'
    source.write_text('main=()=>{return ' + '(' * depth + '1' + ')' * depth + '}\n')
    results = []
    for mode in ('old', 'direct', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1] == results[2]
