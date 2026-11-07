"""Writes during cyclic initialization wait for their target's declaration."""
import itertools
import shutil
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


def build_run(compiler, source, binary):
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    return ran.stdout


@pytest.mark.core_quick
@pytest.mark.parametrize('write', ['direct', 'call', 'recursive', 'record', 'tuple'])
@pytest.mark.parametrize('order', list(itertools.permutations(('a', 'b', 'c'))))
def test_cycle_writes_import_order(compiler, tmp_path, write, order):
    # All three modules form one cycle; vary both the entry and an internal
    # pair of imports. main observes the completed initialization sequence.
    imports = [m for m in order if m != 'a']
    a = ''.join(f'import p"{m}.dewy" as {m}\n' for m in imports)
    a += '''let value:int64=1
let other:int64=2
Box:type=[value:int64]
let box:Box=Box[1]
set=():>void=>{value=42}
set_values=():>void=>{[value other]=[42 43]}
left=(n:int64):>void=>{if n =? 0 {value=42} else {right(n - 1)}}
right=(n:int64):>void=>{left(n)}
'''
    writes = {'direct': 'a.value=42', 'call': 'a.set()',
              'recursive': 'a.left(2)', 'record': 'a.box.value=42',
              'tuple': 'a.set_values()'}
    (tmp_path / 'a.dewy').write_text('$runtime_checks\n' + a)
    (tmp_path / 'b.dewy').write_text('$runtime_checks\nimport p"a.dewy" as a\n' + writes[write] + '\n')
    (tmp_path / 'c.dewy').write_text('import p"a.dewy" as a\n')
    main = tmp_path / 'main.dewy'
    value = 'a.box.value' if write == 'record' else 'a.value'
    main.write_text(''.join(f'import p"{m}.dewy" as {m}\n' for m in order)
                    + f'main=():>void=>printl({value})\n')
    assert build_run(compiler, main, tmp_path / 'program') == '42\n'


@pytest.mark.parametrize('order', [('a', 'b'), ('b', 'a')])
def test_cycle_writes_report_chain(compiler, tmp_path, order):
    for name, peer in [('a', 'b'), ('b', 'a')]:
        (tmp_path / f'{name}.dewy').write_text(
            f'import p"{peer}.dewy" as peer\npeer.set()\n'
            'let value:int64=1\nset=():>void=>{value=42}\n')
    main = tmp_path / 'main.dewy'
    main.write_text(''.join(f'import p"{m}.dewy" as {m}\n' for m in order))
    built = subprocess.run([compiler, 'check', main], capture_output=True, text=True, timeout=30)
    assert built.returncode != 0
    for text in ['is used before it has its value', 'a.dewy:', 'b.dewy:', "needs 'value'", "calls 'set'", "accesses 'value'"]:
        assert text in built.stderr, built.stderr


def test_single_file_write_before_init(compiler, tmp_path):
    source = tmp_path / 'single.dewy'
    source.write_text('set()\nlet value:int64=1\nset=():>void=>{value=42}\n')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=30)
    assert checked.returncode != 0
    assert 'is used before it has its value' in checked.stderr
    assert "calls 'set'" in checked.stderr


def test_acyclic_initialization_stays_imports_first(compiler, tmp_path):
    (tmp_path / 'a.dewy').write_text('printl"a"\nlet value:int64=1\nset=():>void=>{value=42}\n')
    (tmp_path / 'b.dewy').write_text('import p"a.dewy" as a\nprintl"b"\na.set()\n')
    main = tmp_path / 'main.dewy'
    main.write_text('import p"b.dewy" as b\nimport p"a.dewy" as a\nprintl"main"\nmain=():>void=>printl(a.value)\n')
    assert build_run(compiler, main, tmp_path / 'program') == 'a\nb\nmain\n42\n'


@pytest.mark.parametrize('reverse', [False, True])
def test_compiled_compiler_scrambled_imports(compiler, tmp_path, monkeypatch, reverse):
    # Exercise the real host binding under the previously broken entry order.
    # Reuse an isolated compiler copy, never mutate the checkout under a test.
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    sources = tmp_path / 'compiler'
    shutil.copytree(ROOT / 'compiler', sources)
    hooks = sources / 'checks_type_hooks.dewy'
    lines = hooks.read_text().splitlines(keepends=True)
    imports = [line for line in lines if line.startswith('from ')]
    if reverse:
        imports.reverse()
    iter_imports = iter(imports)
    hooks.write_text(''.join(next(iter_imports) if line.startswith('from ') else line for line in lines))
    driver = sources / 'main.jo'
    driver.write_text(driver.read_text().replace('main = ():', 'init_test_cli = ():', 1))
    entry = sources / 'init_entry.jo'
    entry.write_text("use 'checks_type_hooks.dewy'\nuse 'main.jo'\nmain = (): init_test_cli()\n")
    binary = tmp_path / 'compiler-bin'
    built = subprocess.run([compiler, 'build', entry, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    program = tmp_path / 'hello.dewy'
    program.write_text('printl"initialized"\n')
    assert build_run(binary, program, tmp_path / 'hello') == 'initialized\n'


@pytest.mark.parametrize('order', [('leaf.dewy', 'host.jo'), ('host.jo', 'leaf.dewy')])
def test_cycle_host_record_binding(compiler, tmp_path, order):
    (tmp_path / 'leaf.dewy').write_text('''$runtime_checks
from p"host.jo" import (Input)
let input:ptr<Input>=$unsafe (uint64(0) as ptr<Input>)
bind=(p:ptr<Input>):>int64=>{input=p; 0}
read=():>int64=>$unsafe input[0].value
''')
    (tmp_path / 'host.jo').write_text('''use 'leaf.dewy'
struct Input:
    value: int
state = Input(42)
binding = bind(&state)
''')
    main = tmp_path / 'main.dewy'
    main.write_text(''.join(f'import p"{name}" as m{i}\n' for i, name in enumerate(order))
                    + 'from p"leaf.dewy" import (read)\n$runtime_checks\nmain=():>void=>printl(read())\n')
    assert build_run(compiler, main, tmp_path / 'program') == '42\n'
