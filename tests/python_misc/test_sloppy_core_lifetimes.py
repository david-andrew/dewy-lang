"""Abandoned expressions release owned temporaries without changing value semantics."""
import shutil
import subprocess

import pytest

from tests.python_misc.test_sloppy_core import compiler, run_value_batch, Scripts

MAKE = 'make=(n:int64):>string=>"value={n}"\n'
EXIT = '{if stop return 42; make(2)}'


def return_case(statement, declarations=''):
    return MAKE + declarations + '''
probe=(stop:bool):>int64=>{
''' + statement + '''
return 0}
main=()=>{
probe(false)
let before=alloc_count()
loop i in [0..20) {
    if probe(false) not=?0 or probe(true) not=?42 return 1
    if alloc_count() not=?before return 2
}
return 42}
'''


CASES = {
    'array': return_case('let xs=[make(1) ' + EXIT + ']'),
    'scalar-array': return_case('let xs=[1 {if stop return 42; 2}]'),
    'nested-arrays': return_case('let xs=[[make(0)] [make(1) ' + EXIT + ']]'),
    'closure-array': return_case('let xs=[counter() {if stop return 42; counter()}]',
                                 'counter=()=>{let n=0 return ()=>{n+=1; n}}\n'),
    'fixed-array': return_case('let xs:array<string length=2>=[make(1) ' + EXIT + ']'),
    'record': return_case('let row=Row[make(1) ' + EXIT + ']',
                          'Row:type=[left:string right:string]\n'),
    'named-record': return_case('let row=Row[right=make(1) left=' + EXIT + ']',
                                'Row:type=[left:string right:string]\n'),
    'dictionary': return_case('let map=[make(0)->make(1) make(3)->' + EXIT + ']'),
    'arguments': return_case('let n=consume(make(1) ' + EXIT + ')',
                             'consume=(a:string b:string):>int64=>a.length+b.length\n'),
    'conditional-arguments': return_case('let n=consume(if stop make(1) else "" ' + EXIT + ')',
                                         'consume=(a:string b:string):>int64=>a.length+b.length\n'),
    'interpolation': return_case('let text="first={make(1)} second={' + EXIT + '}"'),
    'repeated-array': return_case('let xs=fill(make(1) {if stop return 42; 2})'),
    'returned-owned-value': MAKE + '''
probe=():>string=>{let xs=[make(1) {return make(42); make(2)}] return "unreachable"}
main=()=>{let before=alloc_count()
loop i in [0..20) {{let result=probe() if result not=?"value=42" return 1}
if alloc_count() not=?before return 2}
return 42}
''',
    'continue': MAKE + '''
probe=()=>{let count=0
loop i in [0..6) {
    let xs=[make(i) {if i%2=?0 continue; make(i+1)}]
    count+=1
}
return count}
main=()=>{let before=alloc_count()
if probe() not=?3 return 1
return if alloc_count()=?before 42 else 2}
''',
    'break': MAKE + '''
probe=()=>{let count=0
loop i in [0..6) {
    let xs=[make(i) {if i=?3 break; make(i+1)}]
    count+=1
}
return count}
main=()=>{let before=alloc_count()
if probe() not=?3 return 1
return if alloc_count()=?before 42 else 2}
''',
    'preserve-outer-construction': MAKE + '''
probe=()=>{
let xs=[make(1) {loop i in [0..3) {if i=?0 continue; break}; make(2)}]
return xs}
main=()=>{let before=alloc_count()
{let result=probe() if result not=?["value=1" "value=2"] return 1}
return if alloc_count()=?before 42 else 2}
''',
    'preserve-outer-argument': MAKE + '''
consume=(a:string b:string):>int64=>a.length+b.length
probe=()=>consume(make(1) {loop i in [0..3) {if i=?0 continue; break}; make(2)})
main=()=>{let before=alloc_count()
if probe() not=?14 return 1
return if alloc_count()=?before 42 else 2}
''',
    'abandoned-copy-back': MAKE + '''
let rows:array<string>=[]
Action:type=():>void
mutate=(@text:string n:int64 callback:Action):>void=>{callback() text+="!"}
nothing=():>void=>{}
probe=()=>{mutate(@rows[0] {return 42; 1} nothing) return 0}
main=()=>{let before=alloc_count()
loop i in [0..20) {
    rows=[make(i)]
    if probe() not=?42 return 1
    rows=[]
    if alloc_count() not=?before return 2
}
return 42}
''',
    'labeled-break': MAKE + '''
probe=()=>{let count=0
$outer loop i in [0..3) {
    let xs=[make(i) {loop j in [0..3) {if j=?1 break $outer}; make(i+1)}]
    count+=1
}
return count}
main=()=>{let before=alloc_count()
if probe() not=?0 return 1
return if alloc_count()=?before 42 else 2}
''',
    'labeled-continue': MAKE + '''
probe=()=>{let count=0
$outer loop i in [0..3) {
    let xs=[make(i) {loop j in [0..3) {if j=?1 continue $outer}; make(i+1)}]
    count+=1
}
return count}
main=()=>{let before=alloc_count()
if probe() not=?0 return 1
return if alloc_count()=?before 42 else 2}
''',
}


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_abandoned_expressions(compiler, tmp_path, target, release):
    results = run_value_batch(compiler, tmp_path, CASES, release, target)
    for name, (code, output) in results.items():
        assert code == '42', (name, CASES[name], code, output)


@pytest.mark.core_quick
@pytest.mark.parametrize('target,flags', [
    ('native', []), ('native', ['--release']), ('native', ['-g']),
    ('wasm', []), ('wasm', ['--release']),
])
def test_core_abandoned_implementation_values(compiler, tmp_path, target, flags):
    # Tuple/variant constructors and general partial application are also used
    # by implementation libraries. Keep their source frontend in this check.
    declarations = ['make = (n: int) -> str: "value={n}"',
                    'consume = (a: str, b: str, c: int) -> int: len(a) + len(b) + c',
                    'enum Choice: empty, pair(a: str, b: str)']
    value = '(if stop:\n        return 42\n    else:\n        make(2)\n    )'
    expressions = ['(make(1), ' + value + ')', 'Choice.pair(make(1), ' + value + ')',
                   'consume(make(1), ' + value + ', _)']
    for i, expression in enumerate(expressions):
        declarations.append(f'probe{i} = (stop: bool) -> int:\n    value = {expression}\n    0')
    checks = ''.join(f'        if probe{i}(false) != 0 or probe{i}(true) != 42: return 1\n'
                     for i in range(len(expressions)))
    declarations.append('main = () -> int:\n    before = alloc_count()\n    loop i in [0..20):\n'
                        + checks + '        if alloc_count() != before: return 2\n    42')
    source = tmp_path / 'construction.jo'
    source.write_text('\n'.join(declarations) + '\n')
    binary = tmp_path / 'construction'
    built = subprocess.run([compiler, 'build', source, '-o', binary, '--target', target, *flags],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web cleanup checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'construction.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
