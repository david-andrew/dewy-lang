"""Constructor return fields carry proved lengths to checked API boundaries."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('maker,body,accepted', [
    ('make=():>Pair=>Pair[[4 7]]', 'let p=make(); take(p.items)', True),
    ('make=(xs:array<int>):>Pair=>Pair[xs]', 'let p=make([4 7]); take(p.items)', True),
    ('make=(n:int64):>Pair=>Pair[fill(4 n)]', 'let p=make(2); take(p.items)', True),
    ('make=(n:int64):>Pair=>Pair[fill(4 n)]', 'let p=make(1); take(p.items)', False),
    ('make=(b:bool):>Pair=>{if b return Pair[[4 7]]; Pair[[8 9]]}', 'let p=make(false); take(p.items)', True),
    ('make=(xs:array<int>):>Pair=>Pair[[loop x in xs x]]', 'let p=make([4 7]); take(p.items)', True),
    ('make=(b:bool):>Pair=>if b Pair[[4 7]] else Pair[[8 9]]', 'let p=make(false); take(p.items)', True),
    ('make=(xs:array<int>):>Pair=>Pair[xs]', 'let xs=[4 7]; let p=make(xs); xs.clear(); take(p.items)', True),
    ('make=():>Pair=>Pair[[4 7]]', 'let p=make(); p.items.clear(); take(p.items)', False),
    ('make=():>Pair=>Pair[[4 7]]', 'let p=make(); p.items=[4]; take(p.items)', False),
    ('make=(xs:array<int>):>Pair=>{let p=Pair[xs]; p.items.clear(); p}', 'let p=make([4 7]); take(p.items)', False),
    ('make=(xs:array<int>):>Pair=>Pair[xs]', 'let p=make([4]); take(p.items)', False),
    ('make=(b:bool):>Pair=>if b Pair[[4 7]] else Pair[[8]]', 'let p=make(false); take(p.items)', False),
    ('make=():>Pair=>{let p=Pair[[4 7]]; p.items.clear(); p}', 'let p=make(); take(p.items)', False),
])
def test_constructor_length_contract(compiler, tmp_path, maker, body, accepted):
    source = tmp_path / 'constructor.dewy'
    source.write_text('Pair:type=[items:array<int>]\n'
                      'take=(xs:array<int><length =? 2>)=>printl(xs[0])\n'
                      + maker + '\nmain=()=>{' + body + '}\n')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert (checked.returncode == 0) == accepted, checked.stdout + checked.stderr
    if not accepted:
        assert 'cannot prove' in checked.stderr or 'contract' in checked.stderr
    else:
        binary = tmp_path / 'constructor'
        built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout == ('8\n' if 'make(false)' in body else '4\n')


def test_unconstrained_record_entry(compiler, tmp_path):
    source = tmp_path / 'entry.dewy'
    source.write_text('Pair:type=[items:array<int>]\n'
                      'make=():>Pair=>Pair[[4 7]]\n'
                      'proved=()=>{let p=make(); $assert p.items.length =? 2}\n'
                      'first=(p:Pair):>int=>p.items[0]\n'
                      'main=()=>printl(first(Pair[[4 7]]))\n')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert checked.returncode != 0
    assert 'cannot prove index is in bounds' in checked.stderr
