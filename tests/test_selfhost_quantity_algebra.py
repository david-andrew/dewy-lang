"""Dimension algebra, offset-unit identity, display ladders and reentrant diagnostics."""
import subprocess
import pytest
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
quantity_dimensions: int[][] = [[0, 0, 0, 0, 0, 0, 0, 0]]
quantity_dimension_names: str[] = ["Time", "Length", "Mass", "Current", "Temperature", "Amount", "Luminosity", "Angle"]
quantity_scales: QuantityScale[]
quantity_units: QuantityUnit[] = [QuantityUnit("", 1, 1, 0, 1)]
quantity_tags: QuantityTag[] = [QuantityTag(0, 0, false)]
quantity_si_prefixes: str[] = ["n", "µ", "m", "", "k", "M", "G"]
quantity_base_order: int[] = [2, 1, 0, 3, 4, 5, 6, 7]
quantity_base_symbols: str[] = ["s", "m", "kg", "A", "K", "mol", "cd", "turn"]
quantity_named_symbols: str[] = ["Hz", "N", "Pa", "J", "W", "C", "V", "Ω"]
quantity_named_powers: int[][] = [[-1, 0, 0, 0], [-2, 1, 1, 0], [-2, -1, 1, 0], [-2, 2, 1, 0], [-3, 2, 1, 0], [1, 0, 0, 1], [-3, 2, 1, -1], [-3, 2, 1, -2]]

events: str[]
grew = false
report = (pos: int, text: str):
    events.push("{pos}:{text}")
    if grew: return
    grew = true
    loop i in [1..64):
        quantity_dimensions.push([i, 0, 0, 0, 0, 0, 0, 0])
        quantity_scales.push(QuantityScale(i, 1))
        quantity_units.push(QuantityUnit("padding:{i}", 1, 1, 0, 1))
        quantity_tags.push(QuantityTag(i, 0, false))
    qa_quantity_scale(12, -18, 2)
    qa_quantity_si_ladder("reentrant")
input = QuantityAlgebraInput(&quantity_dimensions, &quantity_dimension_names, &quantity_scales, &quantity_units, &quantity_tags, &quantity_si_prefixes, &quantity_base_order, &quantity_base_symbols, &quantity_named_symbols, &quantity_named_powers, report)
binding = quantity_algebra_bind(&input)

show_ladder = (dim: int):
    ladder = qa_quantity_ladder(dim)
    print("dimension:{qa_dimension_str(dim)}:{ladder.base}")
    loop id in ladder.units:
        u = quantity_units[id]
        print("{u.sym}:{u.num}:{u.den}:{u.onum}:{u.oden}")
main = ():
    old_dims = quantity_dimensions
    old_units = quantity_units
    old_tags = quantity_tags
    old_scales = quantity_scales
    # No named/composite entries exist yet: ladder selection must reacquire the
    # dimension arena after its own interning grows and replaces that arena.
    cold = int(qa_combine_dimensions(qa_base_dimension(0), qa_base_dimension(1), 1, 1))
    show_ladder(cold)
    assert(qa_intern_dimension([0, 0, 0, 0, 0, 0, 0, 0]) == 0)
    bases: int[]
    loop i in [0..8):
        d = int(qa_base_dimension(i))
        assert(qa_base_dimension(i) == d)
        bases.push(d)
        show_ladder(d)
    loop i in [0..quantity_named_symbols.len()): show_ladder(int(qa_quantity_named_dimension(i)))
    loop a in [0..8):
        loop b in [0..8):
            d = int(qa_combine_dimensions(bases[a], bases[b], -1, 10))
            print(qa_dimension_str(d))
            assert(qa_combine_dimensions(d, bases[b], 1, 10) == bases[a])
    loop num in [-3, -1, 0, 1, 2, 3]:
        loop den in [1, 2, 3, 4, 16]:
            d = int(qa_power_dimension(bases[0], num, 11, den))
            print(qa_dimension_str(d))
            print(qa_quantity_power_text(quantity_dimensions[d][0]))
            print(qa_quantity_power_suffix(quantity_dimensions[d][0]))
    volt = int(qa_quantity_named_dimension(6))
    hz = int(qa_quantity_named_dimension(0))
    root_hz = int(qa_power_dimension(hz, 1, 12, 2))
    show_ladder(int(qa_combine_dimensions(volt, root_hz, -1, 12)))
    show_ladder(int(qa_combine_dimensions(bases[7], bases[0], -1, 13)))
    show_ladder(int(qa_combine_dimensions(bases[0], bases[7], -1, 13)))
    show_ladder(0)
    unit = int(qa_intern_quantity_unit("°C", 1, 1, 5463, 20))
    assert(qa_intern_quantity_unit("°C", 1, 1, 5463, 20) == unit)
    assert(qa_intern_quantity_unit("°C", 2, 2, 5463, 20) != unit)
    tag = int(qa_intern_quantity_tag(unit, unit, false))
    assert(qa_intern_quantity_tag(unit, unit, false) == tag)
    assert(qa_intern_quantity_tag(unit, unit, true) != tag)
    loop num in [-1000000, -18, -1, 0, 1, 12, 1000000]:
        loop den in [-1000, -18, -1, 1, 2, 12, 1000]:
            id = int(qa_quantity_scale(num, den, 2))
            q = quantity_scales[id]
            assert(q.denominator > 0)
            print("scale:{q.numerator}:{q.denominator}:{q.shown}:{qa_quantity_gcd(num, den)}")
    loop a in [-9223372036854775807 - 1, -9223372036854775807, -1, 0, 1, 2, 9223372036854775807]:
        loop b in [-9223372036854775807 - 1, -1, 0, 1, 2, 9223372036854775807]: print("gcd:{a}:{b}:{qa_quantity_gcd(a, b)}")
    # Returning error service deliberately grows every shared arena before the
    # remaining arithmetic resumes; production's diagnostic service exits.
    qa_power_dimension(bases[0], 1, 20, 17)
    assert(grew)
    huge = int(qa_intern_dimension([32767 * 720720, 0, 0, 0, 0, 0, 0, 0]))
    qa_combine_dimensions(huge, huge, 1, 30)
    qa_power_dimension(bases[0], 32768, 40)
    assert(old_dims.len() == 1 and old_units.len() == 1 and old_tags.len() == 1 and old_scales.len() == 0)
    assert(old_dims[0] == [0, 0, 0, 0, 0, 0, 0, 0])
    print(events)
    quantity_algebra_bind(&input)
    assert(qa_base_dimension(0) == bases[0])
    print("ok")

'''

@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_quantity_algebra_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('quantity_algebra',)
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in stems) + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
