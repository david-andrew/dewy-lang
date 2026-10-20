"""Direct string decoding retains interpolation structure and source positions."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('literal', ['"plain"', 'r"raw {braces}"',
    '"line\\n\\u{1f642} {value+1}"', '"{value}{value*2}"',
    '"nested {str(value)}"', '"fallback {values[end-1]}"',
    '"""first\n{value}\nlast"""'])
def test_direct_string_identity(compiler, tmp_path, literal):
    source = tmp_path / 'strings.dewy'
    source.write_text('main=()=>{\nlet value=20\nlet values=[1 2 3]\n'
                      f'let text={literal}\nprintl(text)\nreturn 0\n}}\n')
    images, outputs = [], []
    for mode in ('old', 'compare'):
        output = tmp_path / mode
        result = subprocess.run([compiler, 'build', source, '-o', output],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        images.append(output.read_bytes())
        ran = subprocess.run([output], capture_output=True, timeout=10)
        assert ran.returncode == 0
        outputs.append(ran.stdout)
    assert images[0] == images[1]
    assert outputs[0] == outputs[1]


@pytest.mark.core_quick
@pytest.mark.parametrize('literal', ['"{1 +}"', '"\\u{d800}"', '"{1 2}"',
                                     '"{[1 2][end]}"'])
def test_string_diagnostics(compiler, tmp_path, literal):
    source = tmp_path / 'strings.dewy'
    source.write_text(f'main=()=>{{let text={literal}\nreturn 0}}\n')
    results = []
    for mode in ('old', 'direct', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1] == results[2]
