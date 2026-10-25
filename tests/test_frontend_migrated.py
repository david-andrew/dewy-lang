"""Assertions, byte literals, membership, type settings and nominal types build directly as
the reference grammar and projection build them, and report the same mistakes."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROGRAM = '''Oops:type = type of error
Missing:type=type of Oops
wrap_add = (a:uint8<overflow='wrap'> b:uint8):>uint8<overflow="wrap"> => a + b
main=():>void=>{
    let pair:array<int64 length=2> = [20 22]
    let words = ["a" "b"]
    $runtime_assert pair[0] + pair[1] =? 42
    $runtime_assert(words.length =? 2, "two words")
    $assert 1 <? 2, "ordered"
    $assert(2 >? 1)
    let byte = b'a'
    let bytes = b"bc\\n"
    if "a" in? words and not ("z" in? words) printl("member {byte} {bytes.length}")
    let wide:int64<overflow='saturate'> = 5
    printl("{wrap_add(250 10)} {wide} {pair[1]}")
}
'''


def test_direct_migrated_identity(compiler, tmp_path):
    source = tmp_path / 'migrated.dewy'
    source.write_text(PROGRAM)
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
    assert outputs[0] == outputs[1] == b'member 97 3\n4 5 22\n'


@pytest.mark.core_quick
@pytest.mark.parametrize('body', ['let m="no" $assert 1 <? 2, m', '$assert 1 <? 2, "a{1}"',
                                  '$runtime_assert', '$assert(1 <? 2', 'let b=b\'ab\'',
                                  'let b=b"{1}"', 'let b=b\'\\q\'',
                                  'let x:uint8<overflow=\'wrapping\'> = 1',
                                  'let x:uint8<overflow=\'wrap\' overflow=\'wrap\'> = 1',
                                  'let x:array<int64 length=2 length=3> = [1 2]',
                                  'if 1 in [1 2] printl("in")'])
def test_migrated_diagnostics(compiler, tmp_path, body):
    source = tmp_path / 'migrated.dewy'
    source.write_text(f'E:type=type of error\nmain=():>void=>{{\n{body}\n}}\n')
    results = []
    for mode in ('old', 'direct', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1] == results[2]
