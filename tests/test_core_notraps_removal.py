"""Removing from an array is a partial operation: `xs.pop()` needs an element,
`xs.pop(i)` an index in bounds and `xs.truncate(k)` a nonnegative count."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROVED = '''$runtime_checks=false
drain=(@xs:array<int64>):>int64=>{
    let t:int64=0
    loop xs.length >? 0 {t+=xs.pop()}
    return t
}
take=(@xs:array<int64> i:int64):>int64=>if 0 <=? i <? xs.length xs.pop(i) else -1
main=():>void=>{
    let xs:array<int64>=[1 2 3 4]
    xs.push(5)
    let last=xs.pop()
    let k=take(@xs 1)
    xs.truncate(2)
    printl("{last} {k} {xs.length} {drain(@xs)}")
}
'''

REJECTED = {
    'pop_empty': ('let xs:array<int64>=[]\nprintl(xs.pop())\n', '3:8: error: pop() of an empty array'),
    'pop_unguarded': ('last=(@xs:array<int64>):>int64=>xs.pop()\nlet a:array<int64>=[1]\nprintl(last(@a))\n',
                      'cannot prove pop() has an element to remove: missing lower bound'),
    'pop_index': ('take=(@xs:array<int64> i:int64):>int64=>xs.pop(i)\nlet a:array<int64>=[1]\nprintl(take(@a 0))\n',
                  'cannot prove index is in bounds: missing lower and upper bounds'),
    'truncate_negative': ('cut=(@xs:array<int64> k:int64)=>xs.truncate(k)\nlet a:array<int64>=[1]\ncut(@a 0)\n',
                          "cannot prove truncate's count is nonnegative: missing lower bound"),
}


def run(compiler, tmp_path, source, *arguments):
    path = tmp_path / 'program.dewy'
    path.write_text(source)
    return subprocess.run([compiler, *arguments, path.name], text=True, capture_output=True, timeout=60, cwd=tmp_path)


def test_removal_proved(compiler, tmp_path):
    result = run(compiler, tmp_path, PROVED, 'run')
    assert result.returncode == 0 and result.stdout == '5 2 2 4\n', result.stdout + result.stderr


@pytest.mark.parametrize('name', sorted(REJECTED))
def test_removal_rejected(compiler, tmp_path, name):
    source, expected = REJECTED[name]
    result = run(compiler, tmp_path, '$runtime_checks=false\n' + source, 'check')
    assert result.returncode != 0 and expected in result.stderr, result.stderr


def test_removal_runtime_checks(compiler, tmp_path):
    source = '$runtime_checks\ntake=(@xs:array<int64> i:int64):>int64=>xs.pop(i)\nlet a:array<int64>=[1 2]\nprintl(take(@a 1))\nprintl(take(@a 3))\n'
    listed = run(compiler, tmp_path, source, 'check', '--obligations')
    assert 'program.dewy:2:41: runtime check: index is in bounds' in listed.stdout + listed.stderr, listed.stdout + listed.stderr
    result = run(compiler, tmp_path, source, 'run')
    assert result.stdout == '2\n' and result.returncode == 101 and 'out of bounds' in result.stderr, result.stderr
