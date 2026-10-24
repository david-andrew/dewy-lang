"""Dictionary key presence: `d[k]`, `d[k] += 1` and `d.pop(k)` need k in d,
proven from a guard (`k in? d`) or an earlier store, else a compile error
without runtime checks; `d.get(k)` and `d.pop(k default=v)` cannot fail."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROVEN = '''$runtime_checks=false
count=(words:array<string>):>dict<string int64>=>{
    let counts:dict<string int64>=[]
    loop word in words {if word in? counts {counts[word]+=1} else {counts[word]=1}}
    return counts
}
main=():>void=>{
    let c=count(["a" "b" "a"])
    let d:dict<string int64>=[]
    d["x"]=4
    d["y"]=5
    printl(d["x"])
    let y=d["x"]+d["y"]
    if "a" in? c {printl(c["a"]) c.pop("a");}
    let k="b"
    if k in? c {printl(c.pop(k))}
    printl"{y} {c.pop("q" default=0)} {c.get("q")}"
}
'''

REJECTED = {
    'missing': 'main=():>void=>{\n    let d:dict<string int64>=["a"->1]\n    printl(d["b"])\n}\n',
    'popped': 'main=():>void=>{\n    let d:dict<string int64>=["a"->1]\n    if "a" in? d {d.pop("a"); printl(d["a"])}\n}\n',
    'other_key': 'f=(d:dict<string int64> a:string b:string):>int64=>{\n    if a in? d return d[b]\n    return 0\n}\nmain=():>void=>printl(f(["a"->1] "a" "b"))\n',
    # (a fact about one iteration's key does not reach the next)
    'loop_order': 'f=(ws:array<string> d:dict<string int64>):>int64=>{\n    let t=0\n    loop w in ws {\n        t+=d[w]\n        if not (w in? d) return 0\n    }\n    return t\n}\nmain=():>void=>printl(f(["a" "b"] ["a"->1]))\n',
    'removed': 'f=(d:dict<string int64> k:string):>void=>{\n    if k in? d {d.remove(k); printl(d[k])}\n}\nmain=():>void=>f(["a"->1] "a")\n',
}


def run(compiler, tmp_path, source, *arguments):
    path = tmp_path / 'program.dewy'
    path.write_text(source)
    return subprocess.run([compiler, *arguments, path.name], text=True, capture_output=True, timeout=60, cwd=tmp_path)


def test_key_presence_proven(compiler, tmp_path):
    result = run(compiler, tmp_path, PROVEN, 'run')
    assert result.returncode == 0 and result.stdout == '4\n2\n1\n9 0 none\n', result.stdout + result.stderr


@pytest.mark.parametrize('name', sorted(REJECTED))
def test_key_presence_rejected(compiler, tmp_path, name):
    result = run(compiler, tmp_path, '$runtime_checks=false\n' + REJECTED[name], 'check')
    assert result.returncode != 0 and 'cannot prove the key is in the dictionary' in result.stderr, result.stderr


def test_key_presence_runtime_check(compiler, tmp_path):
    result = run(compiler, tmp_path, '$runtime_checks\n' + REJECTED['missing'], 'run')
    assert result.returncode == 101 and 'no entry for this key' in result.stderr, result.stdout + result.stderr
