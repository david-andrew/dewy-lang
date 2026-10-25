"""Bounded parser scans: frozen Jo, Dewy and a token-boundary oracle agree.

The scans deliberately count bracket depth, not bracket types: malformed input
must keep the old stop index so the reader keeps ownership of its diagnostic.
"""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_twins import dewy_enumerations
from tests.test_selfhost_dewy_grammar import ranked

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/dewy_scan_jo.jo'
ENUMS = dewy_enumerations((ROOT / 'compiler/dewy_tokens.dewy').read_text())
OPEN = {'lparen', 'lbrack', 'lbrace'}
CLOSE = {'rparen', 'rbrack', 'rbrace'}
EOF = ('eof', 'none', False)


def token(symbol, newline=False):
    return ('op', symbol, newline)


def closing(ts, at):
    depths = []
    depth = 0
    for kind, symbol, _ in ts[at:]:
        if kind == 'eof':
            break
        depth += (symbol in OPEN) - (symbol in CLOSE)
        depths.append((symbol, depth))
    return next((at + i for i, (s, d) in enumerate(depths) if s in CLOSE and d == 0), -1)


def arm_end(ts, at):
    """Top-level boundaries; a stack assigns each else to the latest flow."""
    brackets, flows = [], []
    for i in range(at, len(ts)):
        kind, symbol, newline = ts[i]
        if kind == 'eof':
            return i
        if not brackets:
            if i > at and symbol == 'kw_else':
                if not flows:
                    return i
                flows.pop()
            elif i > at and newline and not ranked(symbol) and symbol not in {'kw_not', 'dot'}:
                return i
            if symbol in CLOSE:
                return i
            if symbol in {'kw_if', 'kw_match'}:
                flows.append(symbol)
        if symbol in OPEN:
            brackets.append(symbol)
        elif symbol in CLOSE:
            brackets.pop()
    raise AssertionError('arm inputs require EOF')


def corpus():
    runs = [[], [EOF]]
    for symbols in (
        ['lparen', 'rparen'], ['lparen', 'rbrack'], ['lparen', 'lbrace', 'rbrack', 'rparen'],
        ['lbrack', 'none'], ['rbrace'], ['none', 'kw_else'],
        ['kw_if', 'none', 'kw_else', 'none', 'kw_else'],
        ['kw_if', 'kw_match', 'none', 'kw_else', 'none', 'kw_else', 'none', 'kw_else'],
        ['lbrace', 'kw_if', 'kw_else', 'rbrace', 'kw_else'],
    ):
        ts = [token(s) for s in symbols]
        runs.extend([ts, ts + [EOF], [token('none')] + ts + [EOF]])
    # EOF wins even with a bracket symbol; tokens beyond it must never be read.
    runs.append([token('lparen'), ('eof', 'rparen', False), token('rparen'), EOF])
    for symbol in ENUMS['DewyToken']:
        runs.append([token('none'), token(symbol, True), token('none'), EOF])
    for size in (1, 2, 17, 256, 2048):
        runs.extend([
            [token('lparen')] * size + [token('rbrack')] * size + [EOF],
            [token('lbrace')] * size + [EOF],
            [token('kw_if'), token('kw_match')] * size + [token('kw_else')] * (2 * size + 1) + [EOF],
        ])
    rng = random.Random(7351)
    symbols = sorted(OPEN | CLOSE | {'none', 'kw_if', 'kw_match', 'kw_else', 'plus', 'dot', 'kw_not', 'semi'})
    for _ in range(1500):
        runs.append([token(rng.choice(symbols), rng.random() < .3) for _ in range(rng.randrange(60))] + [EOF])
    lines, expected = [], []
    for ts in runs:
        encoded = ' '.join(f'{ENUMS["DewyKind"].index(k)},{ENUMS["DewyToken"].index(s)},{int(n)}' for k, s, n in ts)
        positions = sorted({0, len(ts) // 2, max(0, len(ts) - 1), len(ts)})
        for at in positions:
            lines.append(f'C\t{at}\t{encoded}')
            expected.append(closing(ts, at))
            if any(k == 'eof' for k, _, _ in ts[at:]):
                lines.append(f'A\t{at}\t{encoded}')
                expected.append(arm_end(ts, at))
    return '\n'.join(lines) + '\n', expected


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_dewy_scan_match_jo(compiler, tmp_path, release):
    questions, expected = corpus()
    data = tmp_path / 'questions'
    data.write_text(questions)
    outputs = []
    for module in ('dewy_scan.dewy', 'dewy_scan.jo'):
        driver = DRIVER.read_text().replace("use '../../../compiler/dewy_scan.jo'", f"use '{ROOT / 'compiler' / module}'")
        source = tmp_path / f'{module.replace(".", "-")}.jo'
        source.write_text(driver.replace("use '../../../", f"use '{ROOT}/"))
        binary = source.with_suffix('')
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        run = subprocess.run([binary, data], capture_output=True, text=True, timeout=60)
        assert run.returncode == 0 and not run.stderr, run.stdout + run.stderr
        outputs.append(run.stdout)
        assert list(map(int, run.stdout.splitlines())) == expected
    assert outputs[0] == outputs[1]


@pytest.mark.core_quick
def test_selfhost_dewy_scan_ships_dewy(compiler, tmp_path):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_scan.dewy\0' in binary
    assert b'/compiler/dewy_scan.jo\0' not in binary
    source = tmp_path / 'arms.dewy'
    source.write_text('''if $target =? 'wasm32' {
    missing([nested({broken})])
} else {
    let result=42
}
if $target =? 'wasm32' missing(if yes match what {x => unknown} else y else z)
else {let other=7}
printl(result + other)
''')
    run = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0 and run.stdout == '49\n', run.stdout + run.stderr
