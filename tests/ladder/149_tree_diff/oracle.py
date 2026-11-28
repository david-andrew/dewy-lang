"""Independent tree diff over the same trees; run with --write to refresh expected.out.

Besides printing the report, it applies every printed hunk to the old file and
checks the result is the new file (compared by line keys under --ignore-space).
"""
from pathlib import Path
import json
import sys

HERE = Path(__file__).parent
MARK = '\n\\ No newline at end of file'


def command_line():
    words = json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]['args']
    words = [w.replace('{dir}', str(HERE)) for w in words]
    trees = [Path(w) for w in words if '=' not in w and not w.startswith('-')]
    context = next((int(w.split('=')[1]) for w in words if w.startswith(('context=', '-U='))), 3)
    return trees[0], trees[1], context, '--ignore-space' in words or '-i' in words, '--stat' in words or '-s' in words


def lines(text, ignore_space):
    raw = text.split('\n')
    if raw and raw[-1] == '':
        raw.pop()
    open_end = text != '' and not text.endswith('\n')
    shown = [line + MARK if open_end and i == len(raw) - 1 else line for i, line in enumerate(raw)]
    return [(s, ' '.join(s.split()) if ignore_space else s) for s in shown]


def script(a, b):
    n, m = len(a), len(b)
    lcs = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            lcs[i][j] = lcs[i + 1][j + 1] + 1 if a[i][1] == b[j][1] else max(lcs[i + 1][j], lcs[i][j + 1])
    ops, i, j = [], 0, 0
    while i < n and j < m:
        if a[i][1] == b[j][1]:
            ops.append((' ', a[i][0], i, j)); i += 1; j += 1
        elif lcs[i + 1][j] >= lcs[i][j + 1]:
            ops.append(('-', a[i][0], i, j)); i += 1
        else:
            ops.append(('+', b[j][0], i, j)); j += 1
    ops += [('-', a[k][0], k, j) for k in range(i, n)]
    ops += [('+', b[k][0], n, k) for k in range(j, m)]
    return ops


def span(start, count):
    return f'{start},0' if count == 0 else f'{start + 1}' if count == 1 else f'{start + 1},{count}'


def hunks(ops, context):
    shown = [False] * len(ops)
    for at, op in enumerate(ops):
        if op[0] != ' ':
            for k in range(max(0, at - context), min(len(ops), at + context + 1)):
                shown[k] = True
    out, at = [], 0
    while at < len(ops):
        if not shown[at]:
            at += 1
            continue
        stop = at
        while stop < len(ops) and shown[stop]:
            stop += 1
        out.append(ops[at:stop])
        at = stop
    return out


def apply(old, printed):
    """Apply printed hunk lines (header first) to old's line texts."""
    result, pos, k = [], 0, 0
    while k < len(printed):
        header = printed[k].split()
        start = int(header[1][1:].split(',')[0])
        count = int(header[1].split(',')[1]) if ',' in header[1] else 1
        begin = start if count == 0 else start - 1
        result += old[pos:begin]
        pos = begin
        k += 1
        while k < len(printed) and not printed[k].startswith('@@'):
            line = printed[k]
            if line.startswith('\\'):
                k += 1
                continue
            text = line[1:]
            if k + 1 < len(printed) and printed[k + 1].startswith('\\'):
                text += MARK
            if line[0] in ' -':
                pos += 1
            if line[0] in ' +':
                result.append(text)
            k += 1
    return result + old[pos:]


def run():
    before, after, context, ignore_space, stat = command_line()
    left = {str(f.relative_to(before)): f for f in sorted(before.rglob('*')) if f.is_file()}
    right = {str(f.relative_to(after)): f for f in sorted(after.rglob('*')) if f.is_file()}
    out, changes = [], []
    for name in sorted(set(left) | set(right)):
        if name not in left:
            out.append(f'Only in b: {name}')
            changes.append((name, 0, 0))
            continue
        if name not in right:
            out.append(f'Only in a: {name}')
            changes.append((name, 0, 0))
            continue
        x, y = left[name].read_bytes(), right[name].read_bytes()
        if x == y:
            continue
        try:
            a = lines(x.decode('utf-8'), ignore_space)
            b = lines(y.decode('utf-8'), ignore_space)
        except UnicodeDecodeError:
            if not stat:
                out.append(f'Binary files a/{name} and b/{name} differ')
            changes.append((name, 0, 0))
            continue
        ops = script(a, b)
        added = sum(op[0] == '+' for op in ops)
        removed = sum(op[0] == '-' for op in ops)
        if added + removed == 0:
            continue
        printed = []
        for run_ in hunks(ops, context):
            olds = sum(op[0] != '+' for op in run_)
            news = sum(op[0] != '-' for op in run_)
            printed.append(f'@@ -{span(run_[0][2], olds)} +{span(run_[0][3], news)} @@')
            for kind, text, _, _ in run_:
                printed.append(kind + text)
        patched = apply([t for t, _ in a], '\n'.join(printed).split('\n'))
        key = (lambda s: ' '.join(s.split())) if ignore_space else (lambda s: s)
        assert [key(t) for t in patched] == [k for _, k in b], f'patch for {name} does not rebuild it'
        if not stat:
            out += [f'--- a/{name}', f'+++ b/{name}'] + '\n'.join(printed).split('\n')
        changes.append((name, added, removed))
    out.append('summary:')
    width = max((len(c[0]) for c in changes), default=0)
    for name, added, removed in changes:
        bar = '+' * added + '-' * removed
        out.append(f'  {name.ljust(width)} | {added + removed}{" " if bar else ""}{bar}')
    out.append(f'{len(changes)} files changed, {sum(c[1] for c in changes)} insertions(+), '
               f'{sum(c[2] for c in changes)} deletions(-)')
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    expected = HERE / 'expected.out'
    if sys.argv[1:] == ['--write']:
        expected.write_text(run())
    elif expected.read_text() != run():
        sys.exit('expected.out differs from the tree diff report')
