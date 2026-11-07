"""A shrink of a self-length array keeps what bounds every element; without such a bound it stays an error."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ACCEPTED = {
    'literal pop': ('let p:array<int64<(<? p.length)>> = [0 0]\nprintl(p.pop())\nprintl(p)\n', '0\n[0]\n'),
    'literal truncate': ('let p:array<int64<(<? p.length)>> = [0 0]\np.truncate(1)\nprintl(p)\n', '[0]\n'),
    'largest within the new length': ('let p:array<int64<(<? p.length)>> = [0 1 1]\np.truncate(2)\nprintl(p)\n', '[0 1]\n'),
    'written bound, pop': ('let p:array<int64<v => v <? p.length and v <? 1>> = [0 0]\nprintl(p.pop())\nprintl(p)\n', '0\n[0]\n'),
    'written bound, truncate': ('let p:array<int64<v => v <? p.length and v <? 1>> = [0 0]\np.truncate(1)\nprintl(p)\n', '[0]\n'),
    'written bound, a parameter': ('f=(@p:array<int64<v => v <? p.length and v <? 1>>)=>{\nif p.length >? 1 {p.truncate(1)}\nprintl(p)\n}\n'
                                   'let q:array<int64<v => v <? q.length and v <? 1>> = [0 0]\nf(@q)\n', '[0]\n'),
    'to nothing': ('let p:array<int64<(<? p.length)>> = [0 1]\np.truncate(0)\nprintl(p)\n', '[]\n'),
}
REJECTED = {
    'an element at the old end, pop': 'let p:array<int64<(<? p.length)>> = [0 1]\nprintl(p.pop())\n',
    'an element at the old end, truncate': 'let p:array<int64<(<? p.length)>> = [0 1]\np.truncate(1)\n',
    'written bound too high': 'let p:array<int64<v => v <? p.length and v <? 3>> = [0 2 1]\np.truncate(2)\n',
    'a store since the literal': 'let p:array<int64<(<? p.length)>> = [0 0 0]\np[2]=2\np.pop()\n',
    'a push since the literal': 'let p:array<int64<(<? p.length)>> = [0 0]\np.push(p.length)\np.pop()\n',
    'nothing known of a parameter': 'f=(@p:array<int64<(<? p.length)>>)=>{\nif p.length >? 1 {p.pop()}\n}\n'
                                    'let q:array<int64<(<? q.length)>> = [0 1]\nf(@q)\n',
}


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=120, check=False, cwd=tmp_path)


@pytest.mark.parametrize('name', ACCEPTED)
def test_accepted(compiler, tmp_path, name):
    source, output = ACCEPTED[name]
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == output


@pytest.mark.parametrize('name', REJECTED)
def test_rejected(compiler, tmp_path, name):
    ran = run(compiler, tmp_path, REJECTED[name])
    assert ran.returncode != 0
    assert 'stays a valid index' in ran.stderr
