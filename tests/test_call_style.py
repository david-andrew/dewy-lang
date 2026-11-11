"""A zero-argument call that returns nothing keeps `()`; one that gives a value drops it."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

DECLS = '''$runtime_checks

Counter:type=[value:int64 bump=()=>{value+=1} get=():>int64=>value]
tick=():>void=>printl"tick"
five=():>int64=>5
make=():>(():>int64)=>()=>7
twice=(x:int64):>int64=>x
value=(c:Counter):>int64=>7
'''


def warnings(compiler, tmp_path, body):
    entry = tmp_path / 'app.dewy'
    entry.write_text(DECLS + 'main=():>void=>{\n' + body + '\n}\n')
    result = subprocess.run([compiler, 'check', entry], capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    found = [line.split(': warning: ')[1] for line in result.stderr.splitlines() if ': warning: ' in line]
    return [w for w in found if w.startswith(('write `', 'drop the `()`'))]


@pytest.mark.parametrize('body,hint', [
    ('tick', 'write `tick()`: it is called for its side effect'),
    ('let c=Counter[1]\nc.bump', 'write `.bump()`: it is called for its side effect'),
    ('let a=five()', 'drop the `()`: `five` gives a value'),
    ('let c=Counter[1]\nlet a=c.get()', 'drop the `()`: `.get` gives a value'),
    ('let c=Counter[1]\nprintl"{c.get()}"', 'drop the `()`: `.get` gives a value'),
])
def test_hint(compiler, tmp_path, body, hint):
    assert warnings(compiler, tmp_path, body) == [hint]


@pytest.mark.parametrize('body', [
    'tick()',
    'let a=five',
    'let c=Counter[1]\nc.bump()\nlet a=c.get',
    'let g=make()\nlet a=g()',
    'let a=twice(five())',
    'let a=[five() 1]',
    'let a=five() + 1',
    'let xs=[1 2]\nxs.pop();',
    'let c=Counter[1]\nlet a=c.value()',
])
def test_quiet_where_it_is_right_or_unsafe(compiler, tmp_path, body):
    assert warnings(compiler, tmp_path, body) == []


def test_quiet_in_generic_code(compiler, tmp_path):
    body = 'let a=gen(1)\nprintl"{a}"'
    entry = tmp_path / 'app.dewy'
    entry.write_text(DECLS + 'gen=<T>(x:T):>int64=>{\n let a=five()\n return a\n}\nmain=():>void=>{\n' + body + '\n}\n')
    result = subprocess.run([compiler, 'check', entry], capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    assert 'drop the `()`' not in result.stderr


def test_compiler_sources_are_not_style_checked(compiler):
    from tests.support import ROOT
    result = subprocess.run([compiler, 'check', ROOT / 'compiler/main.jo'], capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert 'write `' not in result.stderr and 'drop the `()`' not in result.stderr
