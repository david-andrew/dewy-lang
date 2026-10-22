"""Recursive values preserve Dewy's ordinary copy and callback semantics."""
import subprocess
import platform
import shutil

import pytest

from tests.support import compiler, run_value_batch

CASES = {
    'list-copies': '''Node:type=[value:int64 next:Node?=none]
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
    'generic-tree': '''Tree:type=<T>[value:T left:Tree<T>?=none right:Tree<T>?=none]
sum=<T>(tree:Tree<T>?):>T=>{
if tree is?none return 0 as T
return tree.value+sum(tree.left)+sum(tree.right)}
main=()=>{
let root=Tree<int64>[20 Tree<int64>[10] Tree<int64>[12]]
let copy=root
if copy.left is?none return 1
copy.left.value=100
return if sum(root)=?42 and sum(copy)=?132 42 else 2}''',
    'mutual-recursion': '''A:type=[value:int64 b:B?=none]
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
    'callback-private-state': '''Counter:type=():>int
Link:type=[counter:Counter next:Link?=none]
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
    'callback-explicit-sharing': '''Counter:type=():>int
Link:type=[counter:Counter next:Link?=none]
main=()=>{
let n=0 let next=($capture @n)=>{n+=1 return n}
let a=Link[@next Link[@next]] let b=a
if a.counter() not=?1 or b.counter() not=?2 return 1
if a.next is?none return 2
if b.next is?none return 3
return if a.next.counter()=?3 and b.next.counter()=?4 and n=?4 42 else 4}''',
    'containers-and-equality': '''Node:type=[value:int64 next:Node?=none]
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
    'tree-walk-snapshot': '''Node:type=[value:int64 next:Node?=none]
let global=Node[20 Node[22]]
replace=()=>{global=Node[99] return 0}
sum=(node:Node?):>int64=>{
let cur=node let result=0
loop cur is?Node {result+=cur.value replace() cur=cur.next}
return result}
main=()=>{
let result=sum(global)
return if result=?42 and global.value=?99 42 else 1}''',
    'private-captured-tree': '''Node:type=[value:int64 next:Node?=none]
make=()=>{
let tree=Node[20 Node[21]]
return ()=>{
if tree.next is?none return 0
tree.next.value+=1 return tree.value+tree.next.value}}
main=()=>{let a=make() let b=@a
return if a()=?42 and b()=?42 and a()=?43 and b()=?43 42 else 1}''',
    'deep-list-drop': '''Node:type=[value:int64 next:Node?=none]
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
    'narrow-tree-branches': '''Node:type=[key:int64 left:Node?=none right:Node?=none]
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

    'guard-local-field-write': '''Node:type=[value:int64]
f=(input:Node?):>int64=>{let x=input
if x is?none {return 0} else {x.value+=1}
return x.value}
main=()=>f(Node[41])''',
    'guard-field-same-type': '''Node:type=[value:int64]
Box:type=[child:Node?]
f=(input:Box):>int64=>{let x=input
if x.child is?none {return 0} else {x.child=Node[42]}
return x.child.value}
main=()=>f(Box[Node[1]])''',
    'guard-field-siblings': '''Node:type=[value:int64]
Box:type=[child:Node?]
f=(input:Box change:bool):>int64=>{let x=input
if x.child is?none return 0
if change {x.child=none return 1} else {return x.child.value}}
main=()=>{return if f(Box[Node[42]] false)=?42 and f(Box[Node[42]] true)=?1 42 else 2}''',
    'guard-unrelated-field': '''Node:type=[value:int64]
Box:type=[child:Node? other:int64]
f=(input:Box):>int64=>{let x=input
if x.child is?none {return 0} else {x.other=9}
return x.child.value}
main=()=>f(Box[Node[42] 0])''',
    'guard-field-preserved-block': '''Node:type=[value:int64]
Box:type=[child:Node?]
f=(input:Box):>int64=>{let x=input
if x.child is?none return 0
{x.child=Node[42]}
return x.child.value}
main=()=>f(Box[Node[1]])''',
    'guard-shadowed-local': '''Node:type=[value:int64]
f=(input:Node?):>int64=>{let x=input
if x is?none {return 0} else {let x:Node?=none}
return x.value}
main=()=>f(Node[42])''',

    'returning-local': '''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{let x=input
if x is?none return 0
if change {x=none return 1}
return x.value}
main=()=>{return if f(Node[42] false)=?42 and f(Node[42] true)=?1 42 else 2}''',
    'returning-field': '''Node:type=[value:int64]
Box:type=[child:Node?]
f=(input:Box change:bool):>int64=>{let x=input
if x.child is?none return 0
if change {x.child=none return 1}
return x.child.value}
main=()=>{return if f(Box[Node[42]] false)=?42 and f(Box[Node[42]] true)=?1 42 else 2}''',
    'returning-else': '''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{let x=input
if x is?none return 0
if change {} else {x=none return 1}
return x.value}
main=()=>{return if f(Node[42] true)=?42 and f(Node[42] false)=?1 42 else 2}''',
    'returning-expression': '''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{let x=input
if x is?none return 0
let extra=if change {x=none return 1} else 0
return x.value+extra}
main=()=>{return if f(Node[42] false)=?42 and f(Node[42] true)=?1 42 else 2}''',
    'returning-match': '''Node:type=[value:int64]
f=(input:Node? choice:int64):>int64=>{let x=input
if x is?none return 0
let extra=match choice {<0>=>{x=none return 1} _=>0}
return x.value+extra}
main=()=>{return if f(Node[42] 1)=?42 and f(Node[42] 0)=?1 42 else 2}''',
    'returning-union': '''A:type=[value:int64]
B:type=[text:string]
f=(input:A|B change:bool):>int64=>{let x=input
if x is?B return 0
if change {x=B["changed"] return 1}
return x.value}
main=()=>{return if f(A[42] false)=?42 and f(A[42] true)=?1 42 else 2}''',
    'returning-lazy-callee': '''Node:type=[value:int64]
helper=()=>{loop true {break} return 0}
f=(input:Node? change:bool):>int64=>{let x=input
if x is?none return 0
if change {x=none helper() return 1}
return x.value}
main=()=>{return if f(Node[42] false)=?42 and f(Node[42] true)=?1 42 else 2}''',
    'returning-nested-closure': '''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{let x=input
if x is?none return 0
if change {x=none let helper=()=>{loop true {break} return 0} helper() return 1}
return x.value}
main=()=>{return if f(Node[42] false)=?42 and f(Node[42] true)=?1 42 else 2}''',
    'returning-contained-break': '''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{let x=input
if x is?none return 0
if change {x=none loop true {break} return 1}
return x.value}
main=()=>{return if f(Node[42] false)=?42 and f(Node[42] true)=?1 42 else 2}''',
    'returning-contained-continue': '''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{let x=input
if x is?none return 0
if change {x=none loop i in [0..3) {if i <? 2 continue} return 1}
return x.value}
main=()=>{return if f(Node[42] false)=?42 and f(Node[42] true)=?1 42 else 2}''',

    'coalesce-narrowed-local': '''Node:type=[value:int64]
let calls:int64=0
fallback=()=>{calls+=1 return Node[1]}
f=(input:Node?):>int64=>{let x=input
if x is?none return 0
let answer=x??fallback()
return answer.value}
main=()=>{return if f(Node[42])=?42 and calls=?0 42 else 1}''',
    'coalesce-assigned-field': '''Node:type=[value:int64]
Box:type=[child:Node?]
let calls:int64=0
fallback=()=>{calls+=1 return Node[1]}
main=()=>{let x=Box[none] x.child=Node[42]
let answer=x.child??fallback()
return if answer.value=?42 and x.child.value=?42 and calls=?0 42 else 1}''',
    'coalesce-narrowed-optional-fallback': '''Node:type=[value:int64]
let calls:int64=0
fallback=():>Node?=>{calls+=1 return none}
f=(input:Node?):>int64=>{let x=input
if x is?none return 0
let answer:Node?=x??fallback()
if answer is?none return 1
return answer.value}
main=()=>{return if f(Node[42])=?42 and calls=?0 42 else 1}''',

    'returning-private-capture': '''Node:type=[value:int64]
make=()=>{let x:Node?=Node[42]
return (clear:bool)=>{
if x is?none return 0
if clear {x=none return 1}
return x.value}}
main=()=>{let a=make() let b=@a
if a(false) not=?42 or b(false) not=?42 return 2
if a(true) not=?1 or a(false) not=?0 return 3
return if b(false)=?42 and b(true)=?1 and b(false)=?0 42 else 4}''',
    'returning-shared-capture': '''Node:type=[value:int64]
main=()=>{let x:Node?=Node[42]
let a=($capture @x clear:bool)=>{
if x is?none return 0
if clear {x=none return 1}
return x.value}
let b=@a
if a(false) not=?42 or b(false) not=?42 return 2
return if b(true)=?1 and a(false)=?0 and x is?none 42 else 3}''',

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
    ('Bad:type=[next:Bad]\nmain=():>void=>exit(entry()) entry=()=>0', 'no finite value'),
    ('Node:type=[value:int64 next:Node?=none]\nmain=():>void=>exit(entry()) entry=()=>{const n=Node[1 Node[2]] if n.next is?none return 0 n.next.value=3 return 0}', 'cannot modify const'),
    ('Node:type=[value:int64 next:Node?=none]\nmain=():>void=>exit(entry()) entry=()=>{let n:Node?=Node[1] loop n is?Node {n=none return n.value} return 0}', 'none'),
    ('A:type=[b:B]\nB:type=[a:A]\nmain=():>void=>exit(entry()) entry=()=>0', 'no finite value'),
    ('struct Node:\n    next: Node?\nextern use_node = (n: *Node)\nmain = ():\n    n: Node\n    use_node(&n)\n', 'cannot cross the C ABI'),
    ('''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{
let x=input
if x is?none return 0
if change {x=none}
return x.value}
main=():>void=>exit(entry()) entry=()=>{return f(Node[42] true)}''', 'none'),
    ('''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{
let x=input
if x is?none return 0
loop true {if change {x=none break} break}
return x.value}
main=():>void=>exit(entry()) entry=()=>{return f(Node[42] true)}''', 'none'),
    ('''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{
let x=input
if x is?none return 0
{x=none}
if change {x=none} else {return x.value}
return 0}
main=():>void=>exit(entry()) entry=()=>{return f(Node[42] false)}''', 'none'),
    ('''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{
let x=input
if x is?none return 0
if change {x=none} else {}
return x.value}
main=():>void=>exit(entry()) entry=()=>{return f(Node[42] true)}''', 'none'),
    ('''Node:type=[value:int64]
f=(input:Node? choice:int64):>int64=>{
let x=input
if x is?none return 0
let ignored=match choice {<0>=>{x=none 10} _=>20}
return x.value}
main=():>void=>exit(entry()) entry=()=>{return f(Node[42] 0)}''', 'none'),
    # local-else
    ('''Node:type=[value:int64]
f=(input:Node?):>int64=>{let x=input
if x is?none {return 0} else {x=none}
return x.value}
main=():>void=>exit(entry()) entry=()=>f(Node[42])''', 'check it with `is?none`'),
    # local-then
    ('''Node:type=[value:int64]
f=(input:Node?):>int64=>{let x=input
if x is?Node {x=none} else {return 0}
return x.value}
main=():>void=>exit(entry()) entry=()=>f(Node[42])''', 'may be none'),
    # field-else
    ('''Node:type=[value:int64]
Box:type=[child:Node?]
f=(input:Box):>int64=>{let x=input
if x.child is?none {return 0} else {x.child=none}
return x.child.value}
main=():>void=>exit(entry()) entry=()=>f(Box[Node[42]])''', 'may be none'),
    # field-block
    ('''Node:type=[value:int64]
Box:type=[child:Node?]
f=(input:Box):>int64=>{let x=input
if x.child is?none return 0
{x.child=none}
return x.child.value}
main=():>void=>exit(entry()) entry=()=>f(Box[Node[42]])''', 'may be none'),
    # parent-block
    ('''Node:type=[value:int64]
Box:type=[child:Node?]
f=(input:Box):>int64=>{let x=input
if x.child is?none return 0
{x=Box[none]}
return x.child.value}
main=():>void=>exit(entry()) entry=()=>f(Box[Node[42]])''', 'may be none'),
    # field-join
    ('''Node:type=[value:int64]
Box:type=[child:Node?]
f=(input:Box change:bool):>int64=>{let x=input
if x.child is?none return 0
if change {x.child=none} else {}
return x.child.value}
main=():>void=>exit(entry()) entry=()=>f(Box[Node[42]] true)''', 'may be none'),
    # nested-parent-block
    ('''Node:type=[value:int64 next:Node?=none]
Box:type=[child:Node?]
f=(input:Box):>int64=>{let x=input
if x.child is?none return 0
if x.child.next is?none return 0
{x.child=Node[42]}
return x.child.next.value}
main=():>void=>exit(entry()) entry=()=>f(Box[Node[1 Node[42]]])''', 'may be none'),
    # local-union
    ('''A:type=[value:int64]
B:type=[text:string]
f=(input:A|B):>int64=>{let x=input
if x is?B {return 0} else {x=B["changed"]}
return x.value}
main=():>void=>exit(entry()) entry=()=>f(A[42])''', 'has no field'),
    # branch-local-escape
    ('''Node:type=[value:int64]
f=(input:Node?):>int64=>{let x=input
if x is?none {return 0} else {let hidden=42}
return hidden}
main=():>void=>exit(entry()) entry=()=>f(Node[42])''', "unknown name 'hidden'"),

    # returning-labeled-break
    ('''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{let x=input
if x is?none return 0
$outer loop true {
if change {loop true {x=none break $outer} return 1}
break}
return x.value}
main=():>void=>exit(entry()) entry=()=>f(Node[42] true)''', 'may be none'),
    # returning-labeled-continue
    ('''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{let x=input
if x is?none return 0
$outer loop i in [0..2) {
if change {loop true {x=none continue $outer} return 1}}
return x.value}
main=():>void=>exit(entry()) entry=()=>f(Node[42] true)''', 'may be none'),
    # returning-prior-invalid
    ('''Node:type=[value:int64]
f=(input:Node? change:bool):>int64=>{let x=input
if x is?none return 0
{x=none}
if change {return 1}
return x.value}
main=():>void=>exit(entry()) entry=()=>f(Node[42] false)''', 'may be none'),

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
finish = (input: Node?, other: int?) -> int:
    x = input
    if x == none: return 0
    if let y = other:
        x = none
        return y
    return x.value
struct Box:
    value: int?
optional_ops = () -> int:
    b = Box()
    b.value = 42
    if let v = b.value: assert(v == 42)
    total = 0
    loop let v = b.value:
        total += v
        b.value = none
    total
main = () -> int:
    assert(optional_ops() == 42)
    assert(pick(Node(42), 10) == 10)
    assert(finish(Node(42), 10) == 10)
    assert(finish(Node(42), none) == 42)
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
        cases[f'payload-{length}'] = f"""Node:type=[data:array<int64 length={length}>=[] next:Node?=none]
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
    source.write_text('''Node:type=[value:int64 next:Node?=none]
probe=()=>{
let node=Node[20 Node[22]]
printl(node.value)
return 0}
main=():>void=>exit(entry()) entry=()=>probe()
''')
    binary = tmp_path / 'debug'
    built = subprocess.run([compiler, 'build', source, '-g', '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    printer = compiler.parent.parent / 'lib/debug/dewy_gdb.py'
    ran = subprocess.run(['gdb', '--batch', '-nx', '-ex', f'source {printer}',
                          '-ex', f'break {source}:4', '-ex', 'run',
                          '-ex', 'printf "child=%ld\n", node.next->value.value.value',
                          '-ex', 'print node', str(binary)], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert 'child=22' in ran.stdout, ran.stdout + ran.stderr
    assert 'next=[value=22 next=none]' in ran.stdout, ran.stdout + ran.stderr


def test_core_recursive_watch_layout(compiler, tmp_path):
    from tests.test_core_watch import Watch, save
    source = tmp_path / 'recursive-game.dewy'
    program = '''Node:type=[value:int64 next:Node?=none]
let root=Node[0 Node[7]]
update=(dt:float64):>void=>{
root.value+=1
if root.next is?none return
if frame_number()%10 =?0 printl"tick={root.value} child={root.next.value}"
sleep(5ms)}
draw=():>void=>clear(BLACK)
'''
    save(source, program)
    watcher = Watch(compiler, source, game=True)
    try:
        before = int(watcher.expect(r'tick=(\d+) child=7').group(1))
        changed = program.replace('next:Node?=none]', 'next:Node?=none health:int64=100]')
        changed = changed.replace('child={root.next.value}',
                                  'child={root.next.value} health={root.health}/{root.next.health}')
        save(source, changed)
        watcher.expect(r'reloaded in \d+ ms:')
        after = int(watcher.expect(r'tick=(\d+) child=7 health=100/100').group(1))
        assert after > before, watcher.output
    finally:
        watcher.close()


@pytest.mark.parametrize('kind', ['optional', 'union'])
def test_core_field_assignment_narrowing_is_order_independent(compiler, tmp_path, kind):
    if kind == 'optional':
        prefix = '''Node:type=[value:int64]
Box:type=[child:Node?]
prime=(b:Box)=>{if b.child is?none return 0 return b.child.value}
'''
        initial, value = 'none', 'Node[42]'
    else:
        prefix = '''A:type=[value:int64]
B:type=[text:string]
Box:type=[child:A|B]
prime=(b:Box)=>{if b.child is?B return 0 return b.child.value}
'''
        initial, value = 'B["before"]', 'A[42]'
    # Each build is a fresh compiler process. A combined value batch could
    # conceal the bug by checking another function's field guard first.
    for order in ('none', 'before', 'after'):
        source = prefix + 'main=():>void=>exit(entry()) entry=()=>{let x=Box[' + initial + ']\n'
        if order == 'before':
            source += 'prime(x)\n'
        source += 'x.child=' + value + '\n'
        if order == 'after':
            source += 'prime(x)\n'
        source += 'return x.child.value}\n'
        path = tmp_path / f'{kind}_{order}.dewy'
        path.write_text(source)
        binary = tmp_path / f'{kind}_{order}'
        built = subprocess.run([compiler, 'build', path, '-o', binary],
                               capture_output=True, text=True, timeout=30)
        assert built.returncode == 0, (order, built.stdout, built.stderr)
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 42, (order, ran.stdout, ran.stderr)
