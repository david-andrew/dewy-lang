"""compiler/habits.dewy (the hints for names from other languages, `append`: "`push`") and
spelling.dewy's did_you_mean (the checker's nearest name): they ship, and their frozen
implementation-language twins compiler/habits.jo and spelling.jo give the same answers. The
oracle reads the tables' pairs from habits.dewy and looks names up in them, says whether a hint
reads as written for Sloppy, and chooses the nearest name, each independently."""
import random
import re
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)
from tests.test_selfhost_spelling import distance

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/selfhost'
TABLES = ['dewy_habit', 'sloppy_habit', 'dewy_map_habit', 'sloppy_map_habit']
SLOPPY_WORDS = {'str', 'f64', 'f32', 'i64', 'i32', 'i16', 'i8', 'u64', 'u32', 'u16', 'u8', 'mut', 'struct', 'enum',
                'elif', 'len'}
SURFACE = {'read_file', 'eprint', 'zip'}
COLORS = (' (the colors with names are WHITE, BLACK, RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE, CYAN, MAGENTA and '
          'GRAY; any other is rgb(0.5, 0.3, 0.1), each from 0 to 1)')


def unescape(text):
    return re.sub(r'\\(.)', lambda m: m.group(1), text)


def tables():
    """Each table's (name, hint) pairs as habits.dewy's matches write them."""
    source = (ROOT / 'compiler/habits.dewy').read_text()
    out = {}
    for name in TABLES:
        body = re.search(name + r'=\(name:string\):>string=>match name \{\n(.*?)\n    _ => ""\n\}', source, re.S).group(1)
        pairs = re.findall(r'^    <"((?:[^"\\]|\\.)*)"> => "((?:[^"\\]|\\.)*)"$', body, re.M)
        assert len(pairs) == len(body.splitlines()), name
        out[name] = [(unescape(k), unescape(v)) for k, v in pairs]
    return out


def sloppy_shaped(hint):
    if any(mark in hint for mark in [', ', '[]', '): ', '->', 'if let']):
        return True
    words = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', hint)
    return any(w in SLOPPY_WORDS or w in SURFACE for w in words)


def nearest(name, candidates):
    for c in candidates:
        if c != name and len(c.encode()) == len(name.encode()) and c.lower() == name.lower():
            return f" (did you mean '{c}'? names care about capital letters)"
    x = name.encode()
    caps = len(x) >= 3 and not any(97 <= b <= 122 for b in x)
    limit = 0 if len(x) <= 2 else 2 if len(x) > 4 else 1
    scored = []
    for c in candidates:
        y = c.encode()
        if (caps and c != c.upper()) or c == name or not y or y[0] == ord('_'):
            continue
        d = distance(x, y, limit)
        pre = next((i for i in range(min(len(x), len(y))) if x[i:i + 1].lower() != y[i:i + 1].lower()),
                   min(len(x), len(y)))
        if d > limit and pre == len(y) and pre >= 3:
            d = limit
        longer = 0
        if pre == len(x) >= 3 and len(y) > pre and y[pre] == ord('_'):
            d, longer = 0, len(y)
        elif d > limit and pre == len(x) and pre >= 4 and len(y) <= 2 * len(x):
            d, longer = limit, len(y)
        if d <= limit:
            scored.append((d * 100 - pre + longer, len(scored), c))
    if scored:
        return f" (did you mean '{min(scored)[2]}'?)"
    return COLORS if caps else ''


def words(table):
    rng = random.Random(7)
    names = sorted({k for pairs in table.values() for k, _ in pairs})
    picked = rng.sample(names, 40)
    out = ['append', 'clone', 'size', 'index', 'lenght', 'length', 'len', 'Score', 'score', 'SKYBLU', 'BROWN',
           'poly', 'polygon', 'polyline', 'save', 'save_data', '_hidden', 'x', 'ab', 'AB', 'données', 'DONNÉES',
           'containsKey', 'not_a_habit', 'a, b', 'i32 here', 'café i8', 'mut_x', 'zip(xs)', *names]
    for word in picked[:20]:
        w = list(word)
        i = rng.randrange(len(w))
        w[i:i + 2] = reversed(w[i:i + 2])
        out.append(''.join(w))
    return out


def build(compiler, source, binary, release):
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_habits_match_jo(compiler, tmp_path, release):
    dewy = build(compiler, FIXTURES / 'habits_dewy.dewy', tmp_path / 'habits-dewy', release)
    jo = build(compiler, FIXTURES / 'habits_jo.jo', tmp_path / 'habits-jo', release)
    table = tables()
    names = words(table)
    outputs = []
    for binary in (dewy, jo):
        ran = subprocess.run([binary, *names], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    lines = outputs[0].decode().split('\n')
    expected = []
    for w in names:
        hints = [dict(table[t]).get(w, '') for t in TABLES]
        expected += ['|'.join([w, *hints]), ' '.join(str(sloppy_shaped(t)).lower() for t in [*hints, w]),
                     nearest(w, names)]
    assert lines == expected + ['']
    # (the oracle's own reading of the tables: Dewy's hints and Sloppy's both kept)
    sloppy = dict(table['sloppy_habit'])
    assert sloppy['clone'].startswith('nothing: `ys = xs` copies') and sloppy['size'] == '`len`'
    assert dict(table['dewy_habit'])['append'] == '`push`' and len(sloppy) == 314
    assert sum(sloppy_shaped(v) for v in sloppy.values()) > 20


@pytest.mark.core_quick
def test_selfhost_habits_ship_dewy(compiler, tmp_path):
    binary = compiler.read_bytes()
    assert b'/compiler/habits.dewy\0' in binary
    assert b'/compiler/habits.jo\0' not in binary
    source = tmp_path / 'hint.dewy'
    source.write_text('main=():>void=>{let xs=[1 2] xs.append(3)}\n')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    assert checked.returncode != 0
    assert "no field or function 'append' for type array<int> (use `push`)" in checked.stdout + checked.stderr
