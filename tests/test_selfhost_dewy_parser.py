"""Parser context and host hooks preserve stores, cache ids and first diagnostics."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/dewy_parser_jo.jo'
WORDS = 'set b main _ array ptr dict totaldict addr no_effects reads mutates allocates blocks panics length overflow p'.split()


def corpus():
    rng = random.Random(417)
    # Arbitrary source bytes must reach the Jo miss hook without UTF-8 validation.
    names = [b'', *[s.encode() for s in WORDS], b'ordinary', b'Set', b'\x80', b'\xff\x00', 'λ'.encode()]
    names += [f'name_{i}'.encode() for i in range(1100)]
    blob, spans = bytearray(), []
    for name in names:
        spans.append((len(blob), len(name)))
        blob.extend(name + b'\n')
    ids, known = {b'': 0}, [b'']
    lines, expected = [], []
    misses, count = 0, 1
    initialized = False
    for index in list(range(len(names))) + [rng.randrange(len(names)) for _ in range(700)]:
        name = names[index]
        if not initialized or name not in ids:
            misses += 1
            initialized = True
            if name not in ids:
                ids[name] = len(known)
                known.append(name)
        start, size = spans[index]
        pos = 17 + 3 * index
        lines.append(f'W {start} {size} {pos}')
        expected.append(f'{count} {count + 2} {ids[name] + 100} {pos} {misses} {len(known)} true')
        count += 2
        # Query every new id and a random warm hit after interning grows the table.
        for id in (ids[name], rng.randrange(len(known))):
            lines.append(f'Q {id}')
            text = known[id]
            value = next((i + 1 for i, word in enumerate(WORDS) if text == word.encode()), 0)
            expected.append(f'{value} {value}')
    expected += ['11 2 first 21 hint', '31 3 next 32 next hint other']
    return bytes(blob), '\n'.join(lines) + '\n', expected


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_dewy_parser_match_jo(compiler, tmp_path, release):
    blob, script, expected = corpus()
    data, steps = tmp_path / 'blob', tmp_path / 'steps'
    data.write_bytes(blob)
    steps.write_text(script)
    results = []
    for module in ('dewy_parser.dewy', 'dewy_parser.jo'):
        source = tmp_path / f'{module.replace(".", "-")}.jo'
        driver = DRIVER.read_text().replace("use '../../../compiler/dewy_parser.jo'", f"use '{ROOT / 'compiler' / module}'")
        source.write_text(driver.replace("use '../../../", f"use '{ROOT}/"))
        binary = source.with_suffix('')
        run = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                             capture_output=True, text=True, timeout=120)
        assert run.returncode == 0, run.stdout + run.stderr
        run = subprocess.run([binary, data, steps], capture_output=True, text=True, timeout=60)
        assert run.returncode == 0, run.stdout + run.stderr
        assert run.stdout.splitlines() == expected
        results.append(run.stdout)
    assert results[0] == results[1]


@pytest.mark.core_quick
def test_selfhost_dewy_parser_ships_dewy(compiler, tmp_path):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_parser.dewy\0' in binary
    assert b'/compiler/dewy_parser.jo\0' not in binary
    # Enter the cold word-operator name path and flush its original diagnostic.
    source = tmp_path / 'word-name.dewy'
    source.write_text('let in=1\nprintl(in + 1)\n')
    run = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    assert run.returncode != 0
    assert '`in` is a word operator, not a name' in run.stdout + run.stderr
