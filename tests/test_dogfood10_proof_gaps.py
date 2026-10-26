"""Value/version boundaries around the dogfood-ten proof transfers."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


REJECTED = {
    'sum_shrunk': '''f=(a:array<int> b:array<int>)=>{let xs=fill(0 a.length+b.length); xs.clear(); loop i in 0.. and x in a {loop j in 0.. and y in b printl(xs[i+j])}}''',
    'sum_inclusive': '''f=(a:array<int> b:array<int>)=>{let xs=fill(0 a.length+b.length); loop i in [0..a.length] {loop j in [0..b.length] printl(xs[i+j])}}''',
    'shift_end': '''f=(@xs:array<int> d:array<int>)=>{if xs.length <? d.length return; let shift=xs.length-d.length+1; loop j in 0.. and c in d xs[shift+j]=c}''',
    'sum_wrapped': '''f=(a:uint8<overflow='wrap'> b:uint8<overflow='wrap'> i:uint8 j:uint8)=>{if i >=? a or j >=? b return; let xs=fill(0 int(a+b)); printl(xs[int(i)+int(j)])}''',
    'const_call': '''zero=():>int=>0
const FLAT=[loop i in [1..4] zero()]
f=():>int=>{let n=0; loop x in FLAT n+=12//x; n}''',
    'const_copy': '''const FLAT=[loop i in [1..4] i]
f=():>int=>{let xs=FLAT; xs[0]=0; let n=0; loop x in xs n+=12//x; n}''',
    'pair_length_identity': '''main=()=>{let rows=[loop i in [1..3] fill(0 i)]; $assert rows[0].length =? rows[1].length}''',
    'pair_replaced': '''main=()=>{let rows=[loop i in [1..3] [i i]]; rows[0]=[]; loop row in rows {let [a b]=row; printl(a b)}}''',
    'last_reverse': '''f=(@xs:array<int>):>int=>{if xs.length =? 0 or xs.last =? 0 return 0; xs.reverse(); 12//xs.last}''',
    'last_overload': '''let calls=0
last=(xs:array<int>):>int=>{calls+=1; calls%2}
f=(xs:array<int>):>int=>{if xs.last =? 0 return 0; 12//xs.last}''',
    'record_replaced': '''C:type=[keys:array<int> prev:array<int>]
zap=(@c:C):>void=>{c=C[[] []]}
f=(@c:C):>int=>{if c.keys.length =? 0 return 0; zap(@c); c.keys[0]}''',
    'record_callback': '''C:type=[keys:array<int> prev:array<int>]
f=(@c:C change:<(@c:C):>void>):>int=>{if c.keys.length =? 0 return 0; change(@c); c.keys[0]}''',
    'remove_key_hook': '''Key:type=[value:int]
let xs:array<int>=[42]
hash=(key:Key):>uint64=>{xs.clear(); 0}
f=(@m:dict<Key int>):>int=>{if xs.length =? 0 return 0; m.remove(Key[1]); xs[0]}''',
    'recursive_cross_parameter': '''f=(@xs:array<int> @ys:array<int> n:int):>void=>{if n <=? 0 {ys.clear(); return}; f(@ys @xs n-1)}
g=(@xs:array<int> @ys:array<int>)=>{if xs.length =? 0 return; f(@xs @ys 1); printl(xs[0])}''',
    'recursive_mutual': '''f=(@xs:array<int> n:int):>void=>{if n <=? 0 return; g(@xs n-1)}
g=(@xs:array<int> n:int):>void=>{if n <=? 0 {xs.clear(); return}; f(@xs n-1)}
h=(@xs:array<int>)=>{if xs.length =? 0 return; f(@xs 2); printl(xs[0])}''',
    'count_snapshot_changed': '''let xs:array<int>=[42 3]
f=():>int=>{let n=xs.count((x:int):>bool=>{xs.clear(); true}); if n =? xs.length return 0; xs[n]}''',
    'count_overload': '''count=(xs:array<int> v:int):>int=>-1
f=(xs:array<int>):>int=>{let n=xs.count(0); if n =? xs.length return 0; xs[n]}''',
    'push_break': '''f=(stop:bool):>int=>{let xs:array<int>=[]; loop i in [1..3] {if stop break; xs.push(i)}; xs.last}''',
    'push_empty_range': '''main=()=>{let xs:array<int>=[]; loop i in [1..1) {xs.push(i); continue}; printl(xs.last)}''',
    'push_cleared': '''main=()=>{let xs:array<int>=[]; loop i in [1..3] {xs.push(i); xs.clear(); continue}; printl(xs.last)}''',
}


@pytest.mark.parametrize('name', REJECTED)
def test_dogfood10_stale_or_unestablished(compiler, tmp_path, name):
    source = tmp_path / f'{name}.dewy'
    source.write_text(REJECTED[name] + '\n')
    result = subprocess.run([compiler, 'check', source], text=True, capture_output=True, timeout=60)
    assert result.returncode != 0, result.stdout + result.stderr
    assert any(message in result.stderr for message in ('cannot prove', 'refuted', 'not in bounds')), result.stderr


PROVED = {
    'nested_field': ('''Inner:type=[keep:array<int> scratch:array<int>]
Outer:type=[inner:Inner other:int]
change=(@i:Inner):>void=>{i.scratch.clear()}
f=(@o:Outer):>int=>{if o.inner.keep.length =? 0 return 0; change(@o.inner); o.inner.keep[0]}
let o=Outer[Inner[[42] [0]] 1]; printl(f(@o))''', '42\n'),
    'element_length_lower_bound': ('''main=()=>{let rows=[loop i in [1..3] fill(7 i)]; loop row in rows printl(row[0]); printl(rows[0][0])}''', '7\n7\n7\n7\n'),
    'count_entry_snapshot': ('''let xs:array<int>=[42 3]
f=():>int=>{let saved=xs; let n=xs.count((x:int):>bool=>{xs.clear(); false}); if n =? saved.length return 0; saved[n]}
printl(f() xs.length)''', '42 0\n'),
}


@pytest.mark.parametrize('name', PROVED)
@pytest.mark.parametrize('release', [False, True])
def test_dogfood10_value_versions(compiler, tmp_path, name, release):
    text, expected = PROVED[name]
    source = tmp_path / f'{name}.dewy'
    source.write_text(text + '\n')
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])], text=True, capture_output=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    run = subprocess.run([binary], text=True, capture_output=True, timeout=20)
    assert run.returncode == 0 and run.stdout == expected, run.stdout + run.stderr


def test_dogfood10_imported_const_comprehension(compiler, tmp_path):
    (tmp_path / 'data.dewy').write_text('const FLAT=[loop i in [1..4] i]\n')
    source = tmp_path / 'read.dewy'
    source.write_text('from p"data.dewy" import FLAT\nf=():>int=>{let n=FLAT[3]; loop x in FLAT n+=12//x; n}\nprintl(f())\n')
    result = subprocess.run([compiler, 'check', source], text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('mode', ['native', 'native-release', 'web', 'web-release'])
def test_dogfood10_rational_endpoints(compiler, tmp_path, mode):
    import shutil
    from tools.cases import Case, Runner, clean_environment

    node = shutil.which('node')
    if mode.startswith('web') and node is None:
        pytest.skip('Node is unavailable')
    # Keep rational instantiation independent of other fixtures' decimal literals.
    source = tmp_path / 'rational_endpoints.dewy'
    source.write_text("""f=(xs:array<rational>):>rational=>{
    if xs.length =? 0 return 0
    if xs.last =? 0 return 0
    1/xs.last
}
main=()=>{printl(f([2]) f([0]) f([]))}
""")
    source.with_suffix('.out').write_text('1/2 0 0\n')
    runner = Runner(compiler, tmp_path, clean_environment(), node)
    results = runner.single(Case('rational_endpoints', source, exit=0), mode)
    assert all(result.ok for result in results), [result.message for result in results]
