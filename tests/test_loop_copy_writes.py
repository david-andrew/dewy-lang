"""`loop x in xs` holds a copy the body may change: a write nothing reads afterwards warns,
naming the place form; a write that is read, or may be, does not."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

DEAD = 'never read afterwards'
FORM = '`loop @{} in {}`'


def warnings(compiler, tmp_path, body):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text('Enemy:type = [hp:int]\nsee = (x:int) => printl(x)\nshow = (r:array<int>):>void => printl(r)\nbump = (@x:int):>void => { x += 1 }\nnext = (@x:int):>int => { x += 1; x }\nmain = () => {\n    let xs = [1 2]\n    let es = [Enemy[1]]\n    let rows = [[1] [2]]\n    let total = 0\n' + body + '\n    printl(total)\n    printl(xs)\n    printl(es)\n    printl(rows)\n}\n')
    run = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    return [line for line in run.stderr.splitlines() if 'warning:' in line and DEAD in line]


@pytest.mark.parametrize('body, name, source', [
    ('loop x in xs { x += 1 }', 'x', 'xs'),
    ('loop x in xs { x = 5 }', 'x', 'xs'),
    ('loop e in es { e.hp -= 1 }', 'e', 'es'),
    ('loop x in xs { see(x); x += 1 }', 'x', 'xs'),
    ('loop x in xs { x += 1; see(x); x += 1 }', 'x', 'xs'),
    ('loop y in xs { loop w in [1] { y += w } }', 'y', 'xs'),
    ('loop x in xs { if total >? 0 { x += 1 } }', 'x', 'xs'),
    ('loop r in rows { r.push(9) }', 'r', 'rows'),
    ('loop r in rows { total += r.pop }', 'r', 'rows'),
    ('loop x in xs { bump(@x) }', 'x', 'xs'),
])
def test_dead_store_warns(compiler, tmp_path, body, name, source):  # noqa: F811
    found = warnings(compiler, tmp_path, '    ' + body)
    assert len(found) == 1, found
    assert FORM.format(name, source) in found[0]


@pytest.mark.parametrize('body', [
    'loop x in xs { x += 1; total += x }',
    'loop r in rows { r.push(9); see(r.length) }',
    'loop r in rows { r.push(9); printl(r) }',
    'loop r in rows { r.push(9); show(r) }',
    'loop x in xs { bump(@x); see(x) }',
    'loop x in xs { see(next(@x)) }',
    'loop x in xs { x += 1; see(x) }',
    'loop e in es { e.hp -= 1; see(e.hp) }',
    'loop x in xs { loop w in [1 2] { total += x; x += w } }',
    'loop x in xs { if total >? 0 { x += 1 }; see(x) }',
    'loop x in xs { let g = ($capture @x):>int => { x += 1; x }; total += g() }',
    'loop @x in xs { x += 1 }',
    'loop _x in xs { _x += 1 }',
])
def test_read_writes_stay_quiet(compiler, tmp_path, body):  # noqa: F811
    assert warnings(compiler, tmp_path, '    ' + body) == []


def test_dictionary_write_names_the_key(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text('main = () => {\n    let d = ["a"->1]\n    loop [k v] in d { v += 1 }\n    printl(d)\n}\n')
    run = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    assert 'change the entry through its key' in run.stderr and 'never read afterwards' in run.stderr
