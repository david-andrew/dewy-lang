"""Independent build plan over the same input; run with --write to refresh expected.out."""
from fractions import Fraction
from pathlib import Path
import json
import re
import sys

HERE = Path(__file__).parent
UNITS = {'ms': Fraction(1, 1000), 's': 1, 'min': 60, 'hour': 3600, 'h': 3600}


def command_line():
    return json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]['args']


def show(seconds):
    """A duration as Dewy prints one: in the largest unit it is a whole number of."""
    if seconds == 0:
        return '0s'
    for unit, size in (('h', 3600), ('min', 60), ('s', 1)):
        if seconds % size == 0:
            return f'{seconds // size}{unit}'
    raise ValueError(seconds)


def duration(text):
    m = re.fullmatch(r'(\d+(?:\.\d+)?)(ms|s|min|hour|h)', text)
    return None if m is None else Fraction(m[1]) * UNITS[m[2]]


def read(text, out):
    targets = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if ':' not in line:
            out.append(f'line {n}: expected `target: dependencies (time)`, got `{line}`')
            continue
        name, rest = (part.strip() for part in line.split(':', 1))
        if '(' not in rest:
            out.append(f'line {n}: {name} has no (time)')
            continue
        if not name or not rest.endswith(')'):
            out.append(f'line {n}: expected `target: dependencies (time)`, got `{line}`')
            continue
        open_ = rest.index('(')
        written = rest[open_ + 1:-1].strip()
        time = duration(written)
        if time is None:
            out.append(f'line {n}: {name}: must be a length of time, like 90s, 250ms or 1.5hour, not `{written}`')
            continue
        if name in targets:
            out.append(f'line {n}: {name} is already defined; keeping the first')
            continue
        targets[name] = (rest[:open_].split(), time)
    return targets


def classify(targets):
    """Each target's reason it cannot be built, by colouring a depth-first search."""
    done, failed = set(), {}

    def visit(name, path):
        if name in done or name in failed or name not in targets:
            return
        here = path + [name]
        for dep in targets[name][0]:
            if dep not in targets:
                failed[name] = f'needs {dep}, which nothing builds'
            elif dep in here:
                cycle = here[here.index(dep):] + [dep]
                for member in here[here.index(dep):]:
                    failed[member] = 'cycle ' + ' -> '.join(cycle)
            else:
                visit(dep, here)
                if dep in failed and name not in failed:
                    reason = failed[dep]
                    failed[name] = reason if reason.startswith('blocked') else f'blocked by {dep}'
        if name not in failed:
            done.add(name)

    for name in sorted(targets):
        visit(name, [])
    return done, failed


def topo(targets, ok):
    waiting = {name: len(targets[name][0]) for name in ok}
    users = {}
    for name in ok:
        for dep in targets[name][0]:
            users.setdefault(dep, []).append(name)
    ready = sorted(name for name in ok if waiting[name] == 0)
    order = []
    while ready:
        nxt = ready.pop(0)
        order.append(nxt)
        for user in users.get(nxt, []):
            waiting[user] -= 1
            if waiting[user] == 0:
                ready = sorted(ready + [user])
    return order


def run(argv):
    out = []
    workers = int(argv[0])
    targets = read((HERE / 'stdin.txt').read_text(), out)
    ok, failed = classify(targets)
    out += [f'cannot build {name}: {failed[name]}' for name in sorted(failed)]
    order = topo(targets, ok)
    out.append('build order: ' + ' '.join(order))
    finish, via = {}, {}
    for name in order:
        deps, time = targets[name]
        start = 0
        for dep in deps:
            if finish[dep] > start:
                start, via[name] = finish[dep], dep
        finish[name] = start + time
    last = max(order, key=lambda name: finish[name])
    chain = [last]
    while chain[-1] in via:
        chain.append(via[chain[-1]])
    out.append(f'critical path ({show(finish[last])}): ' + ' -> '.join(reversed(chain)))
    # Longest remaining chain from each target to the end of the build.
    tail = {}
    for name in reversed(order):
        tail[name] = targets[name][1] + max((tail[u] for u in order if name in targets[u][0]), default=0)
    out.append(f'schedule on {workers} workers:')
    busy = [None] * workers
    done, started, clock = set(), set(), 0
    while len(done) < len(order):
        ranked = sorted((n for n in order if n not in started and all(d in done for d in targets[n][0])),
                        key=lambda n: (-tail[n], n))
        for k in range(workers):
            if busy[k] is not None or not ranked:
                continue
            name = ranked.pop(0)
            busy[k] = (clock + targets[name][1], name)
            started.add(name)
            out.append(f'  {show(clock):>6}  w{k + 1}  {name} ({show(targets[name][1])})')
        clock = min(slot[0] for slot in busy if slot is not None)
        for k in range(workers):
            if busy[k] is not None and busy[k][0] == clock:
                done.add(busy[k][1])
                busy[k] = None
    out.append(f'finished at {show(clock)}, {show(sum(targets[n][1] for n in order))} of work')
    for changed in argv[1:]:
        if changed not in targets:
            out.append(f'no target {changed}')
            continue
        again = {changed}
        for name in order:
            if any(d in again for d in targets[name][0]):
                again.add(name)
        redo = [name for name in order if name in again]
        out.append(f'changing {changed} rebuilds {len(redo)}: ' + ' '.join(redo))
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    expected = HERE / 'expected.out'
    if sys.argv[1:] == ['--write']:
        expected.write_text(run(command_line()))
    elif expected.read_text() != run(command_line()):
        sys.exit('expected.out differs from the build plan')
