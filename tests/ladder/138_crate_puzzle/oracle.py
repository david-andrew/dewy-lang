"""Independent replay of the crate puzzle; run with --write to refresh expected.out."""
from pathlib import Path
import copy
import sys

HERE = Path(__file__).parent
LEVELS = [
    ('first', ['#######', '#     #', '# @$ .#', '#     #', '#######']),
    ('second', ['#########', '#   .   #', '# $ # $ #', '#  @  . #', '#       #', '#########']),
]
STEPS = {'U': (0, -1), 'D': (0, 1), 'L': (-1, 0), 'R': (1, 0)}


def play(name, rows, script):
    h, w = len(rows), len(rows[0])
    walls = {(c, r) for r in range(h) for c in range(w) if rows[r][c] == '#'}
    goals = {(c, r) for r in range(h) for c in range(w) if rows[r][c] == '.'}
    state = {'crates': {(c, r) for r in range(h) for c in range(w) if rows[r][c] == '$'},
             'pos': next((c, r) for r in range(h) for c in range(w) if rows[r][c] == '@'),
             'moves': 0, 'pushes': 0}
    start = copy.deepcopy(state)
    history, bumps, undos = [], 0, 0
    solved = lambda s: s['crates'] <= goals
    for key in script:
        if key == 'Z':
            if history:
                state = history.pop()
                undos += 1
            continue
        if key not in STEPS:
            continue
        dx, dy = STEPS[key]
        before = copy.deepcopy(state)
        x, y = state['pos']
        nxt = (x + dx, y + dy)
        ok = 0 <= nxt[0] < w and 0 <= nxt[1] < h and nxt not in walls
        if ok and nxt in state['crates']:
            past = (nxt[0] + dx, nxt[1] + dy)
            ok = 0 <= past[0] < w and 0 <= past[1] < h and past not in walls and past not in state['crates']
            if ok:
                state['crates'] = (state['crates'] - {nxt}) | {past}
                state['pushes'] += 1
        if ok:
            state['pos'] = nxt
            state['moves'] += 1
            history.append(before)
        else:
            bumps += 1
        if solved(state):
            break
    verdict = 'solved' if solved(state) else 'unsolved'
    out = [f'{name} ({w}x{h}): {verdict} in {state["moves"]} moves, {state["pushes"]} pushes, {bumps} bumps, {undos} undos']
    for r in range(h):
        line = ''
        for c in range(w):
            p = (c, r)
            if p in walls: line += '#'
            elif p == state['pos']: line += '+' if p in goals else '@'
            elif p in state['crates']: line += '*' if p in goals else '$'
            elif p in goals: line += '.'
            else: line += ' '
        out.append('  ' + line)
    out.append(f'  start state kept: player at {start["pos"][0]},{start["pos"][1]}, {start["moves"]} moves')
    return out


def expected():
    lines = (HERE / 'stdin.txt').read_text().split('\n')
    out = []
    for i, (name, rows) in enumerate(LEVELS):
        out += play(name, rows, lines[i] if i < len(lines) else '')
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    path = HERE / 'expected.out'
    if '--write' in sys.argv:
        path.write_text(expected())
    else:
        assert path.read_text() == expected()
        print('138 oracle: matched')
