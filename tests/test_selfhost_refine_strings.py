"""String-set publication and constants borrow arenas and intern through a host."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def corpus():
    rng = random.Random(3811)
    blob, steps, expected = bytearray(), [], []
    sets, published, names, records = [], [], [], {}
    types = structs = variants = nodes = 0

    def reset():
        nonlocal sets, published, names, records, types, structs, variants, nodes
        steps.append('R')
        sets, published, names, records = [[]], [0], [b''], {}
        types, structs, variants, nodes = 1, 1, 0, 1

    def intern(text):
        if text not in names:
            names.append(text)
        return names.index(text)

    def publish(values, fields=0):
        nonlocal types, structs, variants
        spans = []
        for value in values:
            spans.extend((len(blob), len(value)))
            blob.extend(value)
        steps.append(f'S {fields} {len(values)} ' + ' '.join(map(str, spans)))
        # Preserve the existing matching relation, including repeated inputs.
        id = next((i for i, old in enumerate(sets[1:], 1)
                   if len(old) == len(values) and all(v in old for v in values)), 0)
        if not id:
            id = len(sets)
            sets.append(list(values))
            published.append(0)
        calls = []
        if not published[id]:
            published[id] = types
            rows = []
            for i, value in enumerate(sets[id]):
                name = intern(value)
                calls.append(name)
                rows.append(f'V {name} {fields} 0 {i} {i}')
            text = b' | '.join(b"'" + value + b"'" for value in sets[id]).hex()
            records[types] = (text, rows)
            types += 1
            structs += 1
            variants += len(values)
        t = published[id]
        text, rows = records[t]
        expected.append(f'T {t} {id} true {types} {structs} {variants} {t} true {text}')
        expected.extend(rows)
        expected.extend(f'I {name}' for name in calls)
        return id

    def constant(id, i, pos):
        nonlocal nodes
        steps.append(f'C {id} {i} {pos}')
        name = intern(sets[id][i])
        expected.append(f'C {nodes} true {name} {i} {published[id]} {pos} 128 0 0 0')
        expected.append(f'I {name}')
        nodes += 1

    def pad(n):
        nonlocal types, structs, variants, nodes
        steps.append(f'P {n}')
        types += n
        structs += n
        variants += n
        nodes += n

    reset()
    publish([])
    words = [b'north', b'south', b'east', b'west']
    first = publish(words, 7)
    publish(list(reversed(words)), 999)
    for i in range(4):
        constant(first, i, (1 << 40) + i)
    odd = publish([b'', b"a'b", 'é'.encode(), b'\x80\xff\x00', b'\x00'], 12)
    for i in range(5):
        constant(odd, i, i - 1)
    publish([b'x', b'x'])
    publish([b'x', b'y'])
    publish([b'x', b'x'])  # first matching spelling wins
    steps.append(f'X {first}')
    published[first] = 0
    publish(words[::-1], 3)  # unpublished row keeps its original order
    for round in range(3):
        reset()
        pad(round + 1)
        for j in range(80):
            values = [bytes(rng.randrange(256) for _ in range(rng.randrange(15)))
                      for _ in range(rng.randrange(1, 9))]
            id = publish(values, j + 40)
            rng.shuffle(values)
            publish(values, 9999)  # no host calls or publication on hits
            constant(id, rng.randrange(len(values)), j * 16)
            if j % 20 == 0:
                pad(9)
        # Force array growth in one publication, then reuse all its IDs.
        values = [f'member-{round}-{i}'.encode() for i in range(320)]
        id = publish(values, 999)
        publish(values[::-1])
        for i in (0, 127, 255, 319):
            constant(id, i, -1)
    return bytes(blob), '\n'.join(steps) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_refine_strings_twins_and_oracle(compiler, tmp_path, release):  # noqa: F811
    blob, steps, expected = corpus()
    (tmp_path / 'blob').write_bytes(blob)
    (tmp_path / 'steps').write_text(steps)
    driver = (ROOT / 'tests/fixtures/selfhost/refine_strings_jo.jo').read_text()
    for extension in ('dewy', 'jo'):
        for name in ('checker_services', 'checker_types', 'node_store', 'refine_strings'):
            text = (ROOT / 'compiler' / f'{name}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (tmp_path / f'{name}.{extension}').write_text(text)
        source, binary = tmp_path / 'driver.jo', tmp_path / 'driver'
        source.write_text(driver.replace('../../../compiler/', '').replace(".jo'", f".{extension}'"))
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary, tmp_path / 'steps', tmp_path / 'blob'],
                             capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout.splitlines() == expected.splitlines()


@pytest.mark.core_quick
def test_refine_strings_ship_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/refine_strings.dewy\0' in binary
    assert b'/compiler/refine_strings.jo\0' not in binary
