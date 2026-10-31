"""The effect-row lattice (effect_lattice) matches its frozen Jo twin."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

STEMS = ('dewy_reader_types', 'effect_types', 'effect_lattice')

DRIVER = r'''
contracts: EffectContract[] = [EffectContract()]
parents: PlaceIdentity[] = [PlaceIdentity(.local, 0, 0)]
input = EffectLatticeInput(&contracts, &parents)
binding = effect_lattice_bind(&input)
show = (c: int) -> str:
    row = contracts[c]
    s = "{c}:{row.open}:"
    loop a in row.atoms: s += "+{int(a.kind)}@{a.place.declaration}/{a.place.selector}/{a.row}"
    loop a in row.exclusions: s += "-{int(a.kind)}@{a.place.declaration}"
    s + ":{row.variables}"
main = ():
    g = PlaceIdentity(.global, 0, 7)
    parents.push(g)
    gx = PlaceIdentity(.global, 0, 7, 1, .field, 11)
    parents.push(gx)
    gxy = PlaceIdentity(.global, 0, 7, 2, .field, 12)
    gz = PlaceIdentity(.global, 0, 7, 1, .field, 13)
    f = PlaceIdentity(.formal, 0, 1)
    places = [PlaceIdentity(.local, 0, 0), g, gx, gxy, gz, f]
    covers = ""
    loop p in places:
        loop q in places: covers += if place_covers(p, q): "1" else: "0"
        covers += " {place_base(p).declaration}/{int(place_base(p).root)}"
        covers += "|"
    print(covers)
    # Rows: duplicates collapse and order does not matter when interning.
    r1 = effect_intern([EffectAtom(.read, g), EffectAtom(.read, g), EffectAtom(.write, gx)], [EffectAtom(.panic)])
    r2 = effect_intern([EffectAtom(.write, gx), EffectAtom(.read, g)], [EffectAtom(.panic), EffectAtom(.panic)])
    top = effect_top()
    no_block = effect_intern([], [EffectAtom(.block)], [], true)
    no_alloc = effect_intern([], [EffectAtom(.alloc)], [], true)
    allocs = effect_intern([EffectAtom(.alloc), EffectAtom(.read)])
    variable = effect_intern([EffectAtom(.io)], [], [41, 41, 42])
    fields = effect_intern([EffectAtom(.write, gxy), EffectAtom(.read, gz)], [EffectAtom(.write, g)])
    remainder = effect_intern([EffectAtom(.remainder, PlaceIdentity(.local, 0, 0), allocs), EffectAtom(.spawn)])
    empty = effect_intern([])
    print(r1, r2, top, no_block, no_alloc, allocs, variable, fields, remainder, empty, effect_top())
    kinds = [EffectKind.read, .write, .alloc, .detach, .costly_copy, .panic, .io, .block, .spawn, .escape, .opaque, .remainder]
    atoms: EffectAtom[]
    loop k in kinds: atoms.push(EffectAtom(k))
    loop p in places:
        atoms.push(EffectAtom(.write, p))
        atoms.push(EffectAtom(.read, p))
    atoms.push(EffectAtom(.remainder, PlaceIdentity(.local, 0, 0), no_block))
    overlap = ""
    loop a in atoms:
        loop b in atoms: overlap += if effect_overlap(a, b): "1" else: "0"
        overlap += "|"
    print(overlap)
    n = contracts.len()
    loop c in [0..n): print(show(c))
    loop c in [1..n):
        allowed = ""
        loop a in atoms: allowed += if effect_allows(c, a): "1" else: "0"
        excluded = ""
        loop a in atoms: excluded += if effect_excluded(contracts[c], a): "1" else: "0"
        fits = ""
        loop d in [0..n): fits += if effect_rows_fit(c, d): "1" else: "0"
        print("{c} {allowed} {excluded} {fits} {effect_rows_fit(0, c)}")
    joins = ""
    loop c in [1..n):
        loop d in [1..n): joins += "{effect_join(c, d)},"
    print(joins)
    loop c in [n..contracts.len()): print(show(c))
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_effect_lattice_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in STEMS:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in STEMS) + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
    lines = outputs[0].decode().splitlines()
    # A field is covered by its parents, never the reverse; the base is the root.
    assert lines[0].startswith('100000 0/0|011110 7/1|001100 7/1|000100 7/1|000010 7/1|000001 1/2|')
    # Interning collapses duplicates and order; the top row is shared.
    r1, r2, top, *rest = lines[1].split()
    assert r1 == r2 and top == rest[-1]
