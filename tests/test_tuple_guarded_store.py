"""A store through a runtime index reaches only the position a dominating guard holds it to;
the guard is a hint the bounds proof must confirm, so a guard no longer true rejects the store."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ACCEPTED = {
    'equal': ('f=(i:int64)=>{let t:[int64 string]=[10 "x"]\nif i =? 0 {t[i]=42}\nprintl(t)}\nf(0)\nf(1)\n',
              '[42 "x"]\n[10 "x"]\n'),
    'later position': ('f=(i:int64)=>{let t:[string int64]=["x" 10]\nif i =? 1 {t[i]=42}\nprintl(t)}\nf(0)\nf(1)\n',
                       '["x" 10]\n["x" 42]\n'),
    'literal first, compound': ('f=(i:int64)=>{let t:[string int64 string]=["x" 10 "y"]\nif 1 =? i {t[i]+=5}\nprintl(t)}\nf(1)\n',
                                '["x" 15 "y"]\n'),
    'early return': ('f=(i:int64)=>{let t:[int64 string]=[10 "x"]\nif i not=? 0 {return}\nt[i]=42\nprintl(t)}\nf(0)\nf(1)\n',
                     '[42 "x"]\n'),
    'conjunction': ('f=(i:int64 go:bool)=>{let t:[int64 string]=[10 "x"]\nif go and i =? 0 {t[i]=42}\nprintl(t)}\nf(0 true)\n',
                    '[42 "x"]\n'),
    'each position its own type': ('f=(i:int64)=>{let t:[int64 string]=[10 "x"]\nif i =? 1 {t[i]="y"}\nif i =? 0 {t[i]=7}\nprintl(t)}\nf(1)\nf(0)\n',
                                   '[10 "y"]\n[7 "x"]\n'),
}
REJECTED = {
    'two positions': ('f=(i:int64)=>{let t:[int64 string]=[10 "x"]\nif i <? 2 {t[i]=42}\nprintl(t)}\nf(0)\n', 'position 1'),
    'after the guard': ('f=(i:int64)=>{let t:[int64 string]=[10 "x"]\nif i =? 0 {let k=1}\nt[i]=42\nprintl(t)}\nf(0)\n', 'position 1'),
    'in the else': ('f=(i:int64)=>{let t:[int64 string]=[10 "x"]\nif i =? 1 {printl"x"} else {t[i]=42}\nprintl(t)}\nf(0)\n', 'position 1'),
    'the wrong type there': ('f=(i:int64)=>{let t:[int64 string]=[10 "x"]\nif i =? 1 {t[i]=42}\nprintl(t)}\nf(1)\n', 'position 1'),
    'reassigned': ('f=(i0:int64)=>{let i=i0\nlet t:[int64 string]=[10 "x"]\nif i =? 0 {i=1; t[i]=42}\nprintl(t)}\nf(0)\n', 'bounds'),
    'reassigned in a loop': ('f=(i0:int64)=>{let i=i0\nlet t:[int64 string]=[10 "x"]\nif i =? 0 {\nlet n=0\nloop n <? 2 {t[i]=42; i=1; n=n+1}\n}\nprintl(t)}\nf(0)\n', 'bounds'),
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
    source, message = REJECTED[name]
    ran = run(compiler, tmp_path, source)
    assert ran.returncode != 0
    assert message in ran.stderr
