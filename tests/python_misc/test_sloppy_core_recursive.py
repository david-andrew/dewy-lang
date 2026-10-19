"""Recursive values preserve Dewy's ordinary copy and callback semantics."""
import subprocess
import platform
import shutil

import pytest

from tests.python_misc.test_sloppy_core import compiler, run_value_batch

CASES = {
    'list-copies': '''Node:type=[value:int64 next:Node?]
sum=(node:Node?):>int64=>{
let cur=node let result=0
loop cur is?Node {result+=cur.value cur=cur.next}
return result}
main=()=>{
let a=Node[20 Node[22]] let b=a
if b.next is?none return 1
b.next.value=100
if a.next is?none return 2
if a.next.value not=?22 or b.next.value not=?100 return 3
if sum(a) not=?42 or sum(b) not=?120 return 4
let c=a c.next=c
if sum(c) not=?62 or sum(a) not=?42 return 5
return 42}''',
    'generic-tree': '''Tree:type=<T>[value:T left:Tree<T>? right:Tree<T>?]
sum=<T>(tree:Tree<T>?):>T=>{
if tree is?none return 0 as T
return tree.value+sum(tree.left)+sum(tree.right)}
main=()=>{
let root=Tree<int64>[20 Tree<int64>[10] Tree<int64>[12]]
let copy=root
if copy.left is?none return 1
copy.left.value=100
return if sum(root)=?42 and sum(copy)=?132 42 else 2}''',
    'mutual-recursion': '''A:type=[value:int64 b:B?]
B:type=[text:string a:A?]
main=()=>{
let source=A[20 B["before" A[22]]]
let copy=source
if copy.b is?none return 1
if copy.b.a is?none return 2
copy.b.a.value=99 copy.b.text="after"
if source.b is?none return 3
if source.b.a is?none return 4
return if source.b.text=?"before" and source.value+source.b.a.value=?42
and copy.b.a.value=?99 42 else 5}''',
    'recursive-union': '''Leaf:type=[value:int64]
Branch:type=[left:Leaf|Branch right:Leaf|Branch]
Tree:type=Leaf|Branch
evaluate=(tree:Tree):>int64=>{
if tree is?Leaf return tree.value
return evaluate(tree.left)+evaluate(tree.right)}
main=()=>{
let tree=Branch[Leaf[10] Branch[Leaf[20] Leaf[12]]]
let saved=tree tree.right=Leaf[100]
return if evaluate(saved)=?42 and evaluate(tree)=?110 42 else 1}''',
    'callback-private-state': '''Counter:type=():>int64
Link:type=[counter:Counter next:Link?]
make=()=>{let n=0 return ()=>{n+=1 return n}}
main=()=>{
let a=Link[make() Link[make()]] let b=a
if a.counter() not=?1 or b.counter() not=?1 return 1
if a.next is?none return 2
if b.next is?none return 3
if a.next.counter() not=?1 or b.next.counter() not=?1 return 4
let xs=[a] let ys=xs
if xs[0].counter() not=?2 or ys[0].counter() not=?2 return 5
return 42}''',
    'callback-explicit-sharing': '''Counter:type=():>int64
Link:type=[counter:Counter next:Link?]
main=()=>{
let n=0 let next=($capture @n)=>{n+=1 return n}
let a=Link[next Link[next]] let b=a
if a.counter() not=?1 or b.counter() not=?2 return 1
if a.next is?none return 2
if b.next is?none return 3
return if a.next.counter()=?3 and b.next.counter()=?4 and n=?4 42 else 4}''',
    'containers-and-equality': '''Node:type=[value:int64 next:Node?]
main=()=>{
let node=Node[20 Node[22]] let same=Node[20 Node[22]]
if node not=?same return 1
let rows=[node] let saved=rows
loop @row in rows {
if row.next is?none return 2
row.next.value=100}
if saved[0] not=?same or rows[0]=?same return 3
let map=[node->42] let copied=map
if copied[same] not=?42 return 4
return 42}''',
    'tree-walk-snapshot': '''Node:type=[value:int64 next:Node?]
let global=Node[20 Node[22]]
replace=()=>{global=Node[99] return 0}
sum=(node:Node?):>int64=>{
let cur=node let result=0
loop cur is?Node {result+=cur.value replace() cur=cur.next}
return result}
main=()=>{
let result=sum(global)
return if result=?42 and global.value=?99 42 else 1}''',
    'private-captured-tree': '''Node:type=[value:int64 next:Node?]
make=()=>{
let tree=Node[20 Node[21]]
return ()=>{
if tree.next is?none return 0
tree.next.value+=1 return tree.value+tree.next.value}}
main=()=>{let a=make() let b=a
return if a()=?42 and b()=?42 and a()=?43 and b()=?43 42 else 1}''',
    'deep-list-drop': '''Node:type=[value:int64 next:Node?]
make=(size:int64):>Node?=>{
let list:Node?=none
loop i in [0..size) {list=Node[i list]}
return list}
main=()=>{
let base=alloc_count()
{let list=make(100000) let saved=list list=none
if saved is?none return 1
if saved.value not=?99999 return 2}
return if alloc_count()=?base 42 else 3}''',
    'narrow-tree-branches': '''Node:type=[key:int64 left:Node? right:Node?]
find=(tree:Node? key:int64):>int64=>{
let cur=tree
loop true {
if cur is?none return 0
if key <? cur.key {cur=cur.left}
else if key >? cur.key {cur=cur.right}
else return cur.key
}}
main=()=>{let root=Node[20 Node[10] Node[30]]
return if find(root 10)=?10 and find(root 20)=?20 and find(root 30)=?30 and find(root 17)=?0 42 else 1}''',
    'narrow-expression-arms': '''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{
let x=input
if x is?none return 0
let value=if change {x=none 10} else x.value
return value}
main=()=>{return if f(Node[42] false)=?42 and f(Node[42] true)=?10 42 else 1}''',
    'narrow-match-arms': '''Node:type=[value:int64]
f=(input:Node? choice:int64):>int64=>{
let x=input
if x is?none return 0
return match choice {<0>=>{x=none 10} _=>x.value}}
main=()=>{return if f(Node[42] 1)=?42 and f(Node[42] 0)=?10 42 else 1}''',
    'narrow-union-sibling-arms': '''f=(input:int64|string change:bool):>int64=>{
let x=input
if x is?string return 0
if change {x="changed" return 10} else {return x}}
main=()=>{return if f(42 false)=?42 and f(42 true)=?10 42 else 1}''',
    'branch-join-versions': '''pick=(a:bool b:bool):>int64=>{
let value=7
if value=?7 {
if a {value=9}
else if b {value=11}
else {if value not=?7 return 0}
}
return value}
walk=(change:bool):>int64=>{
let value=1 let total=0
loop i in [0..4) {
if value>?0 {
if change {value=0} else {total+=value}
}
total+=value}
return total}
main=()=>{
if pick(false false)+pick(true false)+pick(false true)+pick(true true) not=?36 return 1
return if walk(true)=?0 and walk(false)=?8 42 else 2}''',

}


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_recursive_values(compiler, tmp_path, target, release):
    # Keep the edit loop small; the 100k-node drop also runs in the full suite.
    cases = {k: v for k, v in CASES.items() if k != 'deep-list-drop'}
    for name, (code, output) in run_value_batch(compiler, tmp_path, cases, release, target).items():
        assert code == '42', (name, cases[name], code, output)


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_recursive_deep_drop(compiler, tmp_path, target, release):
    cases = {'deep-list-drop': CASES['deep-list-drop']}
    for name, (code, output) in run_value_batch(compiler, tmp_path, cases, release, target).items():
        assert code == '42', (name, code, output)


@pytest.mark.parametrize('source, message', [
    ('Bad:type=[next:Bad]\nmain=()=>0', 'no finite value'),
    ('Node:type=[value:int64 next:Node?]\nmain=()=>{const n=Node[1 Node[2]] if n.next is?none return 0 n.next.value=3 return 0}', 'cannot modify const'),
    ('Node:type=[value:int64 next:Node?]\nmain=()=>{let n:Node?=Node[1] loop n is?Node {n=none return n.value} return 0}', 'none'),
    ('A:type=[b:B]\nB:type=[a:A]\nmain=()=>0', 'no finite value'),
    ('struct Node:\n    next: Node?\nextern use_node = (n: *Node)\nmain = ():\n    n: Node\n    use_node(&n)\n', 'cannot cross the C ABI'),
    ('''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{
let x=input
if x is?none return 0
if change {x=none}
return x.value}
main=()=>{return f(Node[42] true)}''', 'none'),
    ('''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{
let x=input
if x is?none return 0
loop true {if change {x=none break} break}
return x.value}
main=()=>{return f(Node[42] true)}''', 'none'),
    ('''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{
let x=input
if x is?none return 0
{x=none}
if change {x=none} else {return x.value}
return 0}
main=()=>{return f(Node[42] false)}''', 'none'),
    ('''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{
let x=input
if x is?none return 0
if change {x=none} else {}
return x.value}
main=()=>{return f(Node[42] true)}''', 'none'),
    ('''Node:type=[value:int64]
f=(input:Node? choice:int64):>int64=>{
let x=input
if x is?none return 0
let ignored=match choice {<0>=>{x=none 10} _=>20}
return x.value}
main=()=>{return f(Node[42] 0)}''', 'none'),
])
def test_core_recursive_layout_diagnostics(compiler, tmp_path, source, message):
    path = tmp_path / ('bad.jo' if source.startswith('struct') else 'bad.dewy')
    path.write_text(source)
    result = subprocess.run([compiler, 'build', path, '-o', tmp_path / 'bad'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert message in result.stdout + result.stderr
    assert 'internal compiler error' not in result.stdout + result.stderr


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_narrow_iflet_siblings(compiler, tmp_path, release):
    source = tmp_path / 'siblings.jo'
    source.write_text('''struct Node:
    value: int
pick = (input: Node?, other: int?) -> int:
    x = input
    if x == none: return 0
    if let y = other:
        x = none
        return y
    else:
        return x.value
main = () -> int:
    assert(pick(Node(42), 10) == 10)
    pick(Node(42), none)
''')
    binary = tmp_path / 'siblings'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_recursive_box_size_classes(compiler, tmp_path, target, release):
    # Exercise compact boxes at size-class boundaries, the largest small class,
    # and large-block reuse. Mix ordinary allocations into the freed classes.
    cases = {}
    for length in (1, 2, 3, 5, 13, 29, 32764, 32765, 32766, 40000):
        cases[f'payload-{length}'] = f"""Node:type=[data:array<int64 length={length}> next:Node?]
main=()=>{{
let base=alloc_count()
loop i in [0..3) {{
    let a=Node[next=Node[]]
    let b=a
    if b.next is?none return 1
    b.next.data[0]=42
    if a.next is?none return 2
    if a.next.data[0] not=?0 or b.next.data[0] not=?42 return 3
}}
{{let rows:array<int64>=[] loop i in [0..100) {{rows.push(i)}}
if rows[99] not=?99 return 4}}
return if alloc_count()=?base 42 else 5
}}"""
    for name, (code, output) in run_value_batch(compiler, tmp_path, cases, release, target).items():
        assert code == '42', (name, code, output)


def test_core_recursive_debug_value(compiler, tmp_path):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or not shutil.which('gdb'):
        pytest.skip('native Linux x86-64 with GDB required')
    source = tmp_path / 'debug.dewy'
    source.write_text('''Node:type=[value:int64 next:Node?]
probe=()=>{
let node=Node[20 Node[22]]
printl(node.value)
return 0}
main=()=>probe()
''')
    binary = tmp_path / 'debug'
    built = subprocess.run([compiler, 'build', source, '-g', '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    printer = compiler.parent.parent / 'lib/debug/sloppy_gdb.py'
    ran = subprocess.run(['gdb', '--batch', '-nx', '-ex', f'source {printer}',
                          '-ex', f'break {source}:4', '-ex', 'run',
                          '-ex', 'printf "child=%ld\n", node.next->value.value.value',
                          '-ex', 'print node', str(binary)], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert 'child=22' in ran.stdout, ran.stdout + ran.stderr
    assert 'next = none' in ran.stdout, ran.stdout + ran.stderr


def test_core_recursive_watch_layout(compiler, tmp_path):
    from tests.python_misc.test_sloppy_core_watch import Watch, save
    source = tmp_path / 'recursive-game.dewy'
    program = '''Node:type=[value:int64 next:Node?]
let root=Node[0 Node[7]]
update=(dt:float64):>void=>{
root.value+=1
if root.next is?none return
if frame_number()%10 =?0 printl"tick={root.value} child={root.next.value}"
sleep(0.005)}
draw=():>void=>clear(BLACK)
'''
    save(source, program)
    watcher = Watch(compiler, source, game=True)
    try:
        before = int(watcher.expect(r'tick=(\d+) child=7').group(1))
        changed = program.replace('next:Node?]', 'next:Node? health:int64=100]')
        changed = changed.replace('child={root.next.value}',
                                  'child={root.next.value} health={root.health}/{root.next.health}')
        save(source, changed)
        watcher.expect(r'reloaded in \d+ ms:')
        after = int(watcher.expect(r'tick=(\d+) child=7 health=100/100').group(1))
        assert after > before, watcher.output
    finally:
        watcher.close()
