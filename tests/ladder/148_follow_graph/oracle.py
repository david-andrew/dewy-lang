"""Independent follow-graph report over the same input; run with --write to refresh expected.out."""
from pathlib import Path
import json
import sys

HERE = Path(__file__).parent


def command_line():
    return json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]['args']


def build(text, out):
    follows, dropped = {}, 0
    for n, raw in enumerate(text.split('\n'), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('->')
        source = parts[0].strip()
        target = parts[1].strip() if len(parts) > 1 else ''
        if len(parts) != 2 or not source or not target:
            out.append(f'line {n}: expected `name -> name`, got `{line}`')
            continue
        row = follows.get(source, [])
        follows.setdefault(target, [])
        if source == target or target in row:
            dropped += 1
        else:
            row.append(target)
        follows[source] = row
    if dropped:
        out.append(f'dropped {dropped} repeated or self follows')
    names = sorted(follows)
    return names, [sorted(names.index(t) for t in follows[name]) for name in names]


def groups(names, rows):
    n = len(names)
    seen, finished = [False] * n, []
    for root in range(n):
        if seen[root]:
            continue
        seen[root] = True
        stack = [root]
        while stack:
            v = stack[-1]
            nxt = [w for w in rows[v] if not seen[w]]
            if not nxt:
                finished.append(stack.pop())
            else:
                seen[nxt[0]] = True
                stack.append(nxt[0])
    incoming = [[] for _ in range(n)]
    for v in range(n):
        for w in rows[v]:
            incoming[w].append(v)
    placed, found = [False] * n, []
    for root in reversed(finished):
        if placed[root]:
            continue
        placed[root] = True
        members, todo = [], [root]
        while todo:
            v = todo.pop()
            members.append(names[v])
            for u in incoming[v]:
                if not placed[u]:
                    placed[u] = True
                    todo.append(u)
        found.append(sorted(members))
    return sorted(found, key=lambda m: -len(m))


def tree(kids, name, indent):
    yield indent + name
    for kid in kids.get(name, []):
        yield from tree(kids, kid, indent + '  ')


def reach(names, rows, root, out):
    reached, kids, frontier, rounds = [False] * len(names), {}, [root], 0
    while frontier:
        nxt = []
        for v in frontier:
            for w in rows[v]:
                if reached[w] or w == root:
                    continue
                reached[w] = True
                kids.setdefault(names[v], []).append(names[w])
                nxt.append(w)
        if nxt:
            rounds += 1
        frontier = nxt
    lines = list(tree(kids, names[root], '  '))
    out.append(f'{names[root]} reaches {len(lines) - 1} of {len(names) - 1} others within {rounds} steps:')
    out.extend(lines)


def suggest(names, rows, v, out):
    paths = {}
    for w in rows[v]:
        for x in rows[w]:
            if x != v and x not in rows[v]:
                paths[names[x]] = paths.get(names[x], 0) + 1
    picks = sorted(sorted(paths), key=lambda name: -paths[name])
    shown = [f'{name} ({paths[name]})' for name in picks]
    out.append(f"suggest for {names[v]}: {', '.join(shown) if shown else 'nobody'}")


def run(argv):
    out = []
    names, rows = build((HERE / 'stdin.txt').read_text(), out)
    n = len(names)
    out.append(f'{n} people, {sum(map(len, rows))} follows')
    followers = [0] * n
    for row in rows:
        for t in row:
            followers[t] += 1
    ranked = sorted(range(n), key=lambda v: -followers[v])
    out.append('most followed: ' + ', '.join(f'{names[v]} ({followers[v]})' for v in ranked[:3]))
    mutual = [f'{names[v]} <-> {names[w]}' for v in range(n) for w in rows[v] if v < w and v in rows[w]]
    out.append(f"mutual follows: {', '.join(mutual) if mutual else 'none'}")
    found = groups(names, rows)
    out.append('groups that all reach each other:')
    out.extend('  ' + ' '.join(m) for m in found if len(m) > 1)
    out.append(f'  and {sum(1 for m in found if len(m) == 1)} people on their own')
    for name in argv:
        if name not in names:
            out.append(f'nobody named {name}')
        elif name == argv[0]:
            reach(names, rows, names.index(name), out)
        else:
            suggest(names, rows, names.index(name), out)
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    expected = HERE / 'expected.out'
    if sys.argv[1:] == ['--write']:
        expected.write_text(run(command_line()))
    elif expected.read_text() != run(command_line()):
        sys.exit('expected.out differs from the follow-graph report')
