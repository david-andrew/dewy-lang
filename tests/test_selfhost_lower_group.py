"""Recursive lowering and its frozen twin emit identical programs and diagnostics."""
import json
import re
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf


PROGRAM = r'''$runtime_checks
fib=(n:int64):>int64=>if n <? 2 {n} else {fib(n-1)+fib(n-2)}
inside=(x:int64):>bool=>x >=? -9223372036854775808 and x <=? 9223372036854775807
choose=(x:int64):>int64=>match x {
    <-9223372036854775808> => 1
    <0> => 2
    <9223372036854775807> => 3
    _ => 4
}
main=()=>{
    let xs:array<int64>=[1 2 3]
    xs.insert(4 1)
    xs[1]=fib(6)
    let total:int64=0
    loop x in xs {total+=x}
    let scale=(x:int64):>int64=>x+total
    printl(scale(2))
    let optional:int64?=none
    printl(optional ?? -7)
    let wide:int=18446744073709551615
    printl(uint64<overflow='wrap'>(wide))
    let pair=[left=xs[0] right=xs[1]]
    printl(pair.left+pair.right)
    printl(xs[1..3))
    printl(inside(-1))
    printl(choose(0))
}
'''


@pytest.fixture(autouse=True)
def lowering_library(monkeypatch):
    # The differential compilers live beside their copied modules, away from lib.
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))


def modules_for(source, output):
    # Keep the real service graph: this group owns the recursive dispatcher, so
    # stubbing each outward edge would hide the execution we need to compare.
    # Switch only this group. Other twins are import shims to the live services;
    # otherwise the helper's Jo imports and Dewy's direct imports create two
    # copies of checker state. Double-quoted service imports stay fixed while
    # compare_leaf switches the single-quoted lower_group import.
    modules = {p.name: p.read_text() for p in (ROOT / 'compiler').iterdir()
               if p.suffix in ('.jo', '.dewy')}
    for name in list(modules):
        if name.endswith('.jo') and name != 'lower_group.jo':
            leaf = name[:-3] + '.dewy'
            if leaf in modules:
                modules[name] = f'use "{leaf}"\n'
    for name, text in list(modules.items()):
        if name.endswith('.jo'):
            modules[name] = re.sub(
                r"(?m)^((?:use|import) )'((?!lower_group\.dewy)[^'\n]+\.dewy)'",
                lambda m: m[1] + json.dumps(m[2]), text)
            # Real service modules already resolve their dependencies. Keep the
            # leaf helper from inserting a test-driver initialization cycle.
            modules[name] += "\n# No use 'driver.jo' or use 'checker_resolve.dewy' needed.\n"
    # The generic leaf driver imports type modules before main, changing the
    # cycle's initializer order. Bind existing host records after all module
    # initializers have run, just before entering the compiler pipeline.
    rebind = []
    for name, text in list(modules.items()):
        if not name.endswith('.jo'):
            continue
        bindings = re.findall(r'(?m)^\w+_binding = (\w+_bind\([^\n]+\))$', text)
        if bindings:
            function = 'lower_test_bind_' + name[:-3]
            modules[name] += '\n' + function + ' = ():\n' + ''.join(
                '    ' + call + '\n' for call in bindings)
            rebind.append((name, function))
    modules['main.jo'] = ''.join(f'use "{name}"\n' for name, _ in rebind
                                 if name != 'main.jo') + modules['main.jo']
    command = ', '.join(json.dumps(str(s)) for s in
                        ('leaf-test', 'build', source, '-o', output))
    modules['main.jo'] = modules['main.jo'].replace('main = ():',
        'lower_test_cli = ():\n' + ''.join('    ' + function + '()\n'
                                           for _, function in rebind), 1)
    modules['main.jo'] = modules['main.jo'].replace('    a = args()', f'    a = [{command}]', 1)
    return modules


def test_lower_group_twins(compiler, tmp_path):
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text(PROGRAM)
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('lower_group',),
                         jo_doubles=modules_for(source, output))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == b'16\n-7\n18446744073709551615\n9\n[8 2]\ntrue\n2\n'


@pytest.mark.parametrize(('kind', 'message'), [
    ('nil', 'unsupported expression in codegen (nil)'),
    ('intrinsic', 'intrinsic not supported in codegen'),
])
def test_lower_group_errors(compiler, tmp_path, kind, message):
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    modules = modules_for(source, output)
    # A diagnostic service double makes the exact lowerer's message observable
    # without unrelated source-location rendering or process-wide error queues.
    modules['util.jo'], count = re.subn(
        r'(?m)^fatal = \(p0: int, msg0: str\):\n(?:[ \t].*\n|\n)*',
        'fatal = (p0: int, msg0: str):\n    print(msg0)\n    exit(41)\n\n',
        modules['util.jo'], count=1)
    assert count == 1
    driver = ("use 'main.jo'\nuse 'ast.jo'\nuse 'types.jo'\n"
              'main = ():\n    lower_test_cli()\n'
              f'    bad = mk(.{kind}, 0)\n    nodes[bad].type = i32(T_INT)\n'
              '    gen_expr(bad)\n    print("unreachable")\n')
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('lower_group',), jo_doubles=modules)
    assert out == (message + '\n').encode()
