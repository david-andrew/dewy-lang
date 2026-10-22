"""String indexing and slicing are partial operations: grapheme positions must be proven in bounds.

`text[i]` needs 0 <=? i <? text.length and `text[a..b)` needs
0 <=? a <=? b <=? text.length, with `text.length` counting graphemes, as an
array index and slice need of an array's length.
"""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROVED = '''$runtime_checks=false
guarded=(text:string):>string=>{
    if text.length >? 0 return text[0]
    return ""
}
count_a=(text:string):>int64=>{
    let n=0
    loop i in [0..text.length) {if text[i] =? "a" n+=1}
    return n
}
last=(text:string):>string=>if text.length >? 2 text[end] else ""
literal=():>string=>"hello"[4]
head=(text:string):>string=>if text.length >=? 3 text[0..3) else text
tail=(text:string):>string=>if text.length >? 0 text[1..] else ""
inner=(text:string):>string=>if text.length >=? 4 text[1..2] else ""
clamped=(text:string k:int64):>string=>text[$clamp 0..k)
printl(guarded("abc") count_a("banana") last("xyz") literal() head("abcd") tail("hey") inner("wxyz") clamped("hi" 5))
'''

REJECTED = {
    'unguarded_index': ('first=(text:string):>string=>text[0]\nprintl(first("a"))\n',
                        '2:30: error: cannot prove index is in bounds: missing upper bound'),
    'literal_past_end': ('printl("hello"[5])\n', ':8: error: index is not in bounds'),
    'negative_index': ('at=(text:string i:int64):>string=>if i <? text.length text[i] else ""\nprintl(at("a" 0))\n',
                       'cannot prove index is in bounds: missing lower bound'),
    'unguarded_slice': ('head=(text:string k:int64):>string=>text[0..k)\nprintl(head("abc" 2))\n',
                        'cannot prove slice is in bounds: missing ordered bounds and upper bound'),
    'open_slice': ('rest=(text:string k:int64):>string=>if k >=? 0 text[k..] else ""\nprintl(rest("abc" 1))\n',
                   'cannot prove slice is in bounds: missing ordered bounds'),
}


def run(compiler, tmp_path, source, *arguments, env=None):
    path = tmp_path / 'program.dewy'
    path.write_text(source)
    return subprocess.run([compiler, *arguments, path.name], text=True, capture_output=True, timeout=60,
                          cwd=tmp_path, env=env)


def test_string_obligations_proved(compiler, tmp_path):
    result = run(compiler, tmp_path, PROVED, 'run')
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'a 3 z o abc ey xy hi\n'


@pytest.mark.parametrize('name', sorted(REJECTED))
def test_string_obligations_rejected(compiler, tmp_path, name):
    source, expected = REJECTED[name]
    result = run(compiler, tmp_path, '$runtime_checks=false\n' + source, 'check')
    assert result.returncode != 0 and expected in result.stderr, result.stderr


def test_string_obligations_runtime_checks(compiler, tmp_path):
    source = '$runtime_checks\npick=(text:string i:int64):>string=>text[i]\nprintl(pick("abc" 1))\nprintl(pick("abc" 3))\n'
    listed = run(compiler, tmp_path, source, 'check', '--obligations')
    assert 'program.dewy:2:37: runtime check: index is in bounds' in listed.stdout + listed.stderr
    result = run(compiler, tmp_path, source, 'run')
    assert result.stdout == 'b\n' and result.returncode == 101 and 'string index out of bounds' in result.stderr


def test_string_obligations_default_unchanged(compiler, tmp_path):
    """Until the default flips, an unproven string index keeps its runtime check."""
    env = {k: v for k, v in os.environ.items() if k != 'DEWY_INTERNAL_FACT_POLICY'}
    result = run(compiler, tmp_path, 'first=(text:string):>string=>text[0]\nprintl(first("a"))\n', 'run', env=env)
    assert result.returncode == 0 and result.stdout == 'a\n', result.stderr
