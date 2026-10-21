"""`end` in an index costs nothing over the length arithmetic it stands for."""
import re
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

SOURCE = '''
last = (xs:array<int64>) => xs[{index}]
tail = (xs:array<int64>) => xs[{slice}]
word = (text:string) => text[{index_text}]
printl(last([1 2 3]))
printl(tail([1 2 3]))
printl(word("abc"))
'''

FORMS = [dict(index='end', slice='end-1..end', index_text='end'),
         dict(index='xs.length - 1', slice='xs.length-1-1..xs.length-1', index_text='text.length - 1')]


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_end_matches_length_arithmetic(compiler, tmp_path, release):
    bodies = []
    for form in FORMS:
        source = tmp_path / 'end.dewy'
        source.write_text(SOURCE.format(**form))
        built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'program', '--ir',
                                *(['--release'] if release else [])],
                               text=True, capture_output=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        functions = re.findall(r'^fn f_(?:last|tail|word)_\d+ .*?\n(.*?)(?=^fn |\Z)', built.stdout, re.M | re.S)
        bodies.append([re.sub(r'imm=\d+', 'imm=_', body) for body in functions])
    assert bodies[0] == bodies[1], 'end changed the generated code'
