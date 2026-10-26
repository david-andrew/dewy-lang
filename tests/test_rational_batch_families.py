"""A batch's rational program leaves its float neighbor's min and max alone.

The bundled rational's exact abs, min, max and sign join the prelude's families only in a
module that reaches its library. When membership followed whether any module had loaded it,
a float program batched after a rational one took the exact members for its decimal literals
and printed `0 0 0 0 1 2` for `-0.0 -0.0 0.0 0.0 1.0 2.0`.
"""
from tests.support import compiler  # noqa: F401 (fixture)
from tools import cases

# (the signature's rational loads the library before the float program is checked)
EXACT = '''f=(xs:array<rational>):>rational=>{if xs.length =? 0 return 0; let last=xs.last; if last =? 0 return 0; 1/last}
main=()=>{printl(f([2]) f([0]) f([]) min(f([2]) f([3])) max(f([2]) 1) abs(f([-4])) sign(f([-4])))}
'''
# (a family collected before the module's first fraction is collected again after it)
LATE = '''main=()=>{
    printl(min(3 4) abs(-2.5) max(0.1 0.2))
    let t=1/3
    printl(min(t 1/4) abs(-t) sign(-t) max(t 1))
}
'''


def test_rational_batch_keeps_float_families(compiler, tmp_path):
    source = tmp_path / 'exact.dewy'
    source.write_text(EXACT)
    source.with_suffix('.out').write_text('1/2 0 0 1/3 1 1/4 -1\n')
    late = tmp_path / 'late.dewy'
    late.write_text(LATE)
    late.with_suffix('.out').write_text('3 2.5 0.2\n1/4 1/3 -1 1\n')
    batch = [cases.parse(source, tmp_path), cases.parse(late, tmp_path),
             cases.parse(cases.CASES / 'float' / 'float_min_max_nan.dewy')]
    (tmp_path / 'work').mkdir()
    runner = cases.Runner(compiler, tmp_path / 'work', cases.clean_environment())
    outcomes = runner.value_batch(batch, 'native')
    assert [outcome.case.name for outcome in outcomes] == [case.name for case in batch]
    assert all(outcome.ok for outcome in outcomes), '\n'.join(o.message for o in outcomes if not o.ok)


def test_rational_reaches_generic_helper(compiler, tmp_path):
    # (the helper's module imports nothing exact: fractions passed in still take exact members)
    (tmp_path / 'helper.dewy').write_text('show=(x y):>void=>printl(min(x y) max(x y) abs(x) sign(y))\n')
    main = tmp_path / 'main.dewy'
    main.write_text('import p"helper.dewy"\nmain=()=>{show(1/6 (-1)/4) show(float64(0.5) float64(-2.0))}\n')
    main.with_suffix('.out').write_text('-1/4 1/6 1/6 -1\n-2.0 0.5 0.5 -1.0\n')
    (tmp_path / 'work').mkdir()
    runner = cases.Runner(compiler, tmp_path / 'work', cases.clean_environment())
    outcomes = runner.single(cases.parse(main, tmp_path), 'native')
    assert all(outcome.ok for outcome in outcomes), '\n'.join(o.message for o in outcomes if not o.ok)
