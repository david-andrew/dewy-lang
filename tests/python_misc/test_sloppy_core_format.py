"""Dewy formatting through the CLI and editor, including spacing-sensitive code."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.python_misc.test_sloppy_core import Scripts
from tests.python_misc.test_sloppy_core_editor import Client


@pytest.fixture(scope='module')
def compiler():
    path = os.environ.get('DEWY_CORE_COMPILER')
    if not path:
        pytest.skip('set DEWY_CORE_COMPILER for formatter checks')
    return Path(path).resolve(strict=True)


def command(compiler, *args, **options):
    return subprocess.run([compiler, *args], capture_output=True, text=True,
                          timeout=30, check=False, **options)


def test_core_format_layout(compiler, tmp_path):
    path = tmp_path / 'main.dewy'
    path.write_text('\tmain=()=>{\nlet x:int64=20\n if x>?0{\n return x+22   # keep 🙂\n }\nreturn 0\n}')
    expected = 'main = () => {\n    let x: int64 = 20\n    if x>?0{\n        return x+22   # keep 🙂\n    }\n    return 0\n}\n'
    before = path.read_bytes()
    check = command(compiler, 'fmt', '--check', path)
    assert check.returncode == 1 and str(path) in check.stdout
    assert path.read_bytes() == before
    formatted = command(compiler, 'fmt', path)
    assert formatted.returncode == 0, formatted.stderr
    assert path.read_text() == expected
    assert command(compiler, 'fmt', '--check', path).returncode == 0
    stdin = command(compiler, 'fmt', '-', input=expected)
    assert stdin.returncode == 0 and stdin.stdout == expected, stdin.stderr


@pytest.mark.parametrize('text', ['main=()=>{', 'main=()=>[42}', 'main=()=>"missing',
                                 'main=()=>"{1', 'main=()=>42`'])
def test_core_format_invalid(compiler, tmp_path, text):
    path = tmp_path / 'bad.dewy'
    path.write_text(text)
    formatted = command(compiler, 'fmt', path)
    assert formatted.returncode != 0 and formatted.stderr
    assert path.read_text() == text


def test_core_format_implementation_language(compiler, tmp_path):
    path = tmp_path / 'main.jo'
    path.write_text('main=()->int:\n  return 20+22')
    formatted = command(compiler, 'fmt', path)
    assert formatted.returncode == 0, formatted.stderr
    assert path.read_text() == 'main = () -> int:\n    return 20 + 22\n'
    assert command(compiler, 'check', path).returncode == 0


PROGRAMS = {
    'closure-captures': '''main=()=>{
let n=0 let xs=[10]
let next=($capture @n step:int64
$capture xs extra:int64)=>{n+=step xs[0]+=extra; n+xs[0]}
let other=next printl(next(1 2)) printl(other(3 4)) printl(n) return 0
}''',
    'mutable-loop': """main=()=>{
let values=[20 22] let saved=values
loop @value in values {value+=1}
printl(values) printl(saved)
return 0
}""",
    'broadcast': '''square=(x:float64)=>x*x
main=()=>{
let xs=[1.0 4.0 9.0]
xs .+=1.0 xs .*=2.0
xs[1..end] .+=0.5 xs[[true false true]] .*=2.0
printl(square.(sqrt.(xs) .+ 1.0))
printl(reshape([1 2 3 4] 2 2) .* [10 20])
printl([1 2 3] .not<=? 2)
printl(.-(xs .+ 1.0)) printl(.+xs) printl(.- .-xs)
return 0
}''',
    'matrix-slices': '''main=()=>{
let m=reshape([1 2 3 4 5 6] 2 3)
let part:NDArray<int64>=m[[0..end] [1..end]]
m[[..] end]=[20 22]
m[[..] end] .+=10
printl(part.data) printl(m.data) printl(m[0 [0..end+1)].data)
let rows=[1,0..0]
printl(m[rows [2,0..0]].data)
m[rows (0..2]] .+= [1 2]
printl(m[[..] [end,end-1..]].data)
return 0
}''',
    'unpack-leaf-types': 'main=()=>{const [x:int64 y:float64]=[20 22] printl(x+y) return 0}',
    'record-spread': 'main=()=>{let base=[x=20 y=1] let next=[base... y=22] printl(next.x+next.y) return 0}',
    'generic-value': 'identity=<T>(x:T):>T=>x\nmain=()=>{let f=identity<int64> printl(f(42)) return 0}',
    'generic-return-adjacency': 'pair=():>array<array<int64>>=>[[20 22]]\nmain=()=>{printl(pair()[0]) return 0}',
    'spread': 'main=()=>{let xs=[20 22] printl([0 xs... 1 (xs)...]) return 0}',
    'sequence': 'Series:type=[count:int64]\nlen=(s:Series)=>s.count\n__index__=(s:Series i:int64)=>i\nmain=()=>{printl([loop x in Series[3] x]) return 0}',
    'slice-update': 'main=()=>{let xs=[1 2 3 4] xs[1..2]=[20 22] printl(xs) return 0}',
    'range-index': 'main=()=>{let xs=[10 20 30 40 50] printl(xs[0,2..]) xs[4,2..]=[1 2 3] printl(xs[(0..4]]) return 0}',
    'coalesce': 'read=():>int64?=>none\nmain=()=>{printl"{read()??20+22}" return 0}',
    'compound': 'main=()=>{let x=-17 x//=3 x%=4 x^=2 let y=3/2 y/=3 printl"{x} {y}" return 0}',
    'loop-else': '''main=()=>{
loop x in [0..0) {printl(x)}
else loop c in "" {printl(c)}
else {printl("empty")}
return 0
}''',
    'labels': '''main=()=>{
let total=0
$outer
loop i in [0..4) {
loop c in "ab" {
total+=1
if i =? 0 {continue $outer}
if i =? 2 {break $outer}
}
}
printl(total)
return 0
}''',
    'adjacency': '''identity=<T>(x:T):>T=>x
main=()=>{
let x=5
let values=[1 -2 3]
let optional:array<array<int64>?>=[]
let points=[0,2..8)
let exclusive=(0,2..8]
printl(identity<int64>(2x+2(x+1)))
printl(values) printl([loop point in points point]) printl(optional.length)
printl([loop point in exclusive point])
return 0
}''',
    'strings': '''main=()=>{
let raw=r"""first  
\t{raw # untouched}  
  last"""
let quoted="""first  
{"nested"}  
  last"""
printl(raw) printl(quoted) printl(0x"cafe")
return 0
}''',
    'crlf': 'main=()=>{\r\nlet text=r"""a  \r\n\tb\r\nc"""\r\nprintl(text)\r\nreturn 0\r\n}',
}


@pytest.mark.parametrize('name', PROGRAMS)
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_format_execution(compiler, tmp_path, name, target):
    path = tmp_path / 'main.dewy'
    path.write_bytes(PROGRAMS[name].encode())

    def execute(label):
        output = tmp_path / label
        flags = ['--target', 'wasm'] if target == 'wasm' else []
        built = command(compiler, 'build', path, '-o', output, *flags)
        assert built.returncode == 0, built.stdout + built.stderr
        args = [output]
        if target == 'wasm':
            node = shutil.which('node')
            if not node:
                pytest.skip('Node is needed for web formatting checks')
            scripts = Scripts()
            scripts.feed(output.with_suffix('.html').read_text())
            runner = output.with_suffix('.cjs')
            runner.write_text('\n'.join(scripts.parts))
            args = [node, runner]
        ran = subprocess.run(args, capture_output=True, timeout=10, check=False)
        assert ran.returncode == 0, ran.stderr
        return ran.stdout

    before = execute('before')
    formatted = command(compiler, 'fmt', path)
    assert formatted.returncode == 0, formatted.stderr
    assert execute('after') == before
    check = command(compiler, 'fmt', '--check', path)
    assert check.returncode == 0, check.stdout + check.stderr
    if name == 'crlf':
        assert path.read_bytes().endswith(b'}\r\n')


def test_core_format_examples(compiler, tmp_path):
    examples = Path(__file__).resolve().parents[2] / 'examples/sloppy_core'
    directory = tmp_path / 'examples'
    shutil.copytree(examples, directory)
    formatted = command(compiler, 'fmt', directory)
    assert formatted.returncode == 0, formatted.stdout + formatted.stderr
    checked = command(compiler, 'fmt', '--check', directory)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    for name in ['tour', 'dunes']:
        checked = command(compiler, 'check', directory / f'{name}.dewy')
        assert checked.returncode == 0, checked.stdout + checked.stderr


def test_core_format_unsaved_recovery(compiler, tmp_path):
    path = tmp_path / 'main.dewy'
    path.write_text('main=()=>0')
    client = Client(compiler, tmp_path)
    request = {'textDocument': {'uri': path.as_uri()}, 'options': {'tabSize': 4, 'insertSpaces': True}}
    try:
        client.set_text(path.as_uri(), 'main=()=>"missing', 1)
        assert client.request('textDocument/formatting', request) == []
        client.set_text(path.as_uri(), 'main=()=>{\nreturn 42\n}', 2)
        edits = client.request('textDocument/formatting', request)
        assert edits and edits[0]['newText'] == 'main = () => {\n    return 42\n}\n', edits
        client.set_text(path.as_uri(), 'main=()=>"🙂"', 3)
        edits = client.request('textDocument/formatting', request)
        assert edits[0]['range']['end'] == {'line': 0, 'character': 13}, edits
        assert path.read_text() == 'main=()=>0', 'Editor formatting must use the unsaved buffer'
    finally:
        client.close()
