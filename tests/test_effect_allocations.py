"""Residual costs and implicit call edges, in check and both native modes."""
import subprocess

import pytest

from tests.support import compiler
from tests.test_effect_rows import compile_source


@pytest.mark.core_quick
@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
def test_effect_allocation_witness(compiler, tmp_path, mode):
    source = tmp_path / 'growth.dewy'
    source.write_text('''grow=(@xs:array<int64>):>void=>{xs.push(1)}
forward=(@xs:array<int64>):>void=>grow(@xs)
bad=(@xs:array<int64>):>void & no allocates=>forward(@xs)
main=():>void=>exit(0)
''')
    result = compile_source(compiler, source, tmp_path, mode)
    assert result.returncode != 0
    assert 'allocation exceeds' in result.stderr, result.stderr
    assert 'growth.dewy:3:' in result.stderr, result.stderr
    assert 'bad -> forward -> grow' in result.stderr, result.stderr
    assert 'witness at ' in result.stderr and 'growth.dewy:1:' in result.stderr


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
def test_effect_readonly_and_library_body(compiler, tmp_path, mode):
    source = tmp_path / 'read.dewy'
    source.write_text(('''Point:type=[x:int64 y:int64]
cell=(p:Point):>int64 & no_effects=>p.x//16+p.y
inspect=(xs:array<int64>):>int64 & no_effects=>xs.length
main=():>void=>{printl(cell(Point[-1 3])+inspect([1 2]))}
''') + "\n$runtime_checks\n")
    result = compile_source(compiler, source, tmp_path, mode)
    assert result.returncode == 0, result.stderr
    if mode != 'check':
        ran = subprocess.run([tmp_path / 'program'], capture_output=True, text=True, timeout=10)
        assert (ran.returncode, ran.stdout) == (0, '4\n'), ran.stderr


# The operation is deliberately hidden behind a helper, so a generic blocker
# on its result/parameter type cannot satisfy the diagnostic assertion.
ALLOCATIONS = {
    'default': '''make=():>array<int64>=>[1]
helper=(x:array<int64>=make()):>int64=>x.length
bad=():>int64 & no allocates=>helper()
''',
    'format': '''format=(x:int64):>string=>"value {x}"
bad=(x:int64):>string & no allocates=>format(x)
''',
    'equality': '''Key:type=[value:int64]
__eq__=(a:Key b:Key):>bool=>{let xs:array<int64>=[a.value] return xs.length =? b.value}
bad=(a:Key b:Key):>bool & no allocates=>a =? b
''',
    'hash': '''Key:type=[value:int64]
hash=(a:Key):>uint64=>{let xs:array<int64>=[a.value] return xs.length as uint64}
bad=(a:array<Key>):>uint64 & no allocates=>a.hash()
''',
    'capture': '''bad=(x:int64):>void & no allocates=>{let f=($capture x):>int64=>x f();}
''',
    'copy': '''bad=(xs:array<int64>):>array<int64> & no allocates=>xs.copy()
''',
    'closure_copy': '''bad=(f:<():>int64>):>void & no allocates=>{let g=(@f).copy() g();}
''',
    'sort_key': '''key=(x:int64):>int64=>{let xs:array<int64>=[x] return xs.length}
bad=(@xs:array<int64>):>void & no allocates=>{xs.sort(key=@key)}
''',
}


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
@pytest.mark.parametrize('name', ALLOCATIONS)
def test_effect_implicit_allocation(compiler, tmp_path, mode, name):
    source = tmp_path / f'{name}.dewy'
    source.write_text(ALLOCATIONS[name] + 'main=():>void=>exit(0)\n')
    result = compile_source(compiler, source, tmp_path, mode)
    assert result.returncode != 0
    assert 'allocation exceeds' in result.stderr, result.stderr


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
def test_effect_early_drop(compiler, tmp_path, mode):
    source = tmp_path / 'drop.dewy'
    source.write_text('''let released:int64=0
Ticket=type of [id:int64
    $__drop__
    release=():>void=>{released+=id}
]
bad=(n:int64):>int64 & no_effects=>{
    let ticket=Ticket[n]
    if n >? 0 return ticket.id
    return 0
}
main=():>void=>exit(0)
''')
    result = compile_source(compiler, source, tmp_path, mode)
    assert result.returncode != 0
    assert "mutation of 'released'" in result.stderr, result.stderr
    assert 'witness at ' in result.stderr


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
def test_effect_early_defer(compiler, tmp_path, mode):
    helper = tmp_path / 'deferred.jo'
    helper.write_text('''grow = (xs: mut i64[]): xs.push(1)
hidden = (xs: mut i64[], early: bool):
    defer grow(xs)
    if early: return
''')
    source = tmp_path / 'defer.dewy'
    source.write_text('''from p"deferred.jo" import hidden
bad=(@xs:array<int64>):>void & no allocates=>hidden(@xs true)
main=():>void=>exit(0)
''')
    result = compile_source(compiler, source, tmp_path, mode)
    assert result.returncode != 0
    assert 'allocation exceeds' in result.stderr, result.stderr
    assert 'deferred.jo:1:' in result.stderr


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
def test_effect_recursive_box_storage(compiler, tmp_path, mode):
    (tmp_path / 'boxes.jo').write_text('''struct Link:
    child: Child
struct Child:
    value: i64
    parent: Link?
hidden = (link: mut Link): link.child.value = 1
''')
    source = tmp_path / 'box.dewy'
    source.write_text('''from p"boxes.jo" import Link, hidden
bad=(@link:Link):>void & no allocates=>hidden(@link)
main=():>void=>exit(0)
''')
    result = compile_source(compiler, source, tmp_path, mode)
    assert result.returncode != 0
    assert 'allocation exceeds' in result.stderr, result.stderr
    assert 'boxes.jo:6:' in result.stderr


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
def test_effect_pending_argument_cleanup(compiler, tmp_path, mode):
    source = tmp_path / 'pending.dewy'
    source.write_text('''let released:int64=0
Owner=type of [value:int64
    $__drop__
    release=():>void=>{released+=value}
]
consume=(owner:Owner n:int64):>int64=>owner.value+n
fail=():>int64=>panic("argument panic")
bad=():>int64 & no mutates<released>=>consume(Owner[1] fail())
main=():>void=>exit(0)
''')
    result = compile_source(compiler, source, tmp_path, mode)
    assert result.returncode != 0
    assert "mutation of 'released'" in result.stderr, result.stderr


@pytest.mark.parametrize('allocate', [False, True])
def test_effect_wasm_plan(compiler, tmp_path, allocate):
    source = tmp_path / 'target.dewy'
    body = 'let xs:array<int64>=[x]; return xs.length' if allocate else 'return x//16'
    source.write_text(f'helper=(x:int64):>int64 & no_effects=>{{{body}}}\n'
                      'main=():>void=>exit(entry()) entry=():>int64=>helper(8)\n')
    result = subprocess.run([compiler, 'build', source, '--target', 'wasm32', '-o', tmp_path / 'web'],
                            capture_output=True, text=True, timeout=60)
    assert (result.returncode != 0) == allocate, result.stderr
    if allocate:
        assert 'allocation exceeds' in result.stderr, result.stderr
