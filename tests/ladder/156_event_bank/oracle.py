"""Independent event-sourced bank over the same commands; run with --write to refresh expected.out."""
from pathlib import Path
import copy
import json
import re
import sys

HERE = Path(__file__).parent
LIMIT = 100000000000


class Refused(Exception):
    pass


def command_line():
    return json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]['args']


def cents(text):
    parts = text.split('.')
    if len(parts) > 2 or parts[0] == '':
        return None
    if not re.fullmatch(r'[+-]?\d+', parts[0]):
        return None
    frac = parts[1] if len(parts) == 2 else '0'
    if len(frac) > 2 or frac == '' or not re.fullmatch(r'[+-]?\d+', frac):
        return None
    whole, part = int(parts[0]), int(frac)
    if whole < 0 or part < 0:
        return None
    total = whole * 100 + part * (10 if len(frac) == 1 else 1)
    return None if total > LIMIT else total


def money(c):
    sign = '-' if c < 0 else ''
    m = abs(c)
    return f'{sign}{m // 100}.{m % 100:02d}'


USAGE = {'open': (3, 'usage: open NAME AMOUNT'), 'deposit': (3, 'usage: deposit NAME AMOUNT'),
         'withdraw': (3, 'usage: withdraw NAME AMOUNT'), 'transfer': (4, 'usage: transfer FROM TO AMOUNT'),
         'close': (2, 'usage: close NAME'), 'freeze': (2, 'usage: freeze NAME')}


def parse(line):
    w = line.split()
    kind = w[0] if w else ''
    if kind not in USAGE:
        return 'unknown command'
    count, usage = USAGE[kind]
    if len(w) != count:
        return usage
    if kind in ('open', 'deposit', 'withdraw', 'transfer'):
        amount = cents(w[count - 1])
        if amount is None:
            return 'bad amount'
        return (kind, *w[1:count - 1], amount)
    return (kind, w[1])


def usable(state, name):
    if name not in state:
        raise Refused(f'no account `{name}`')
    if state[name]['frozen']:
        raise Refused(f'`{name}` is frozen')
    return state[name]


def decide(state, e):
    kind = e[0]
    if kind == 'open' and e[1] in state:
        raise Refused(f'`{e[1]}` already exists')
    if kind in ('deposit', 'freeze'):
        usable(state, e[1])
    if kind == 'withdraw':
        a = usable(state, e[1])
        if a['balance'] < e[2]:
            raise Refused(f'`{e[1]}` has only {money(a["balance"])}')
    if kind == 'transfer':
        if e[1] == e[2]:
            raise Refused('a transfer needs two accounts')
        a = usable(state, e[1])
        usable(state, e[2])
        if a['balance'] < e[3]:
            raise Refused(f'`{e[1]}` has only {money(a["balance"])}')
    if kind == 'close':
        if e[1] not in state:
            raise Refused(f'no account `{e[1]}`')
        if state[e[1]]['balance'] != 0:
            raise Refused(f'`{e[1]}` still holds {money(state[e[1]]["balance"])}')


def apply(state, e):
    kind = e[0]
    if kind == 'open':
        state[e[1]] = {'balance': e[2], 'frozen': False}
    elif kind == 'deposit':
        state[e[1]]['balance'] += e[2]
    elif kind == 'withdraw':
        state[e[1]]['balance'] -= e[2]
    elif kind == 'transfer':
        state[e[1]]['balance'] -= e[3]
        state[e[2]]['balance'] += e[3]
    elif kind == 'close':
        del state[e[1]]
    else:
        state[e[1]]['frozen'] = True


def show(e):
    kind = e[0]
    if kind == 'transfer':
        return f'transfer {e[1]} -> {e[2]} {money(e[3])}'
    if kind in ('close', 'freeze'):
        return f'{kind} {e[1]}'
    return f'{kind} {e[1]} {money(e[2])}'


def replay(log, snaps, k):
    at, base = 0, {}
    for s_at, s_state in snaps:
        if s_at <= k:
            at, base = s_at, s_state
    state = copy.deepcopy(base)
    for e in log[at:max(at, k)]:
        apply(state, e)
    return state


def balances(state):
    if not state:
        return '(no accounts)'
    return ' '.join(f'{n}={money(a["balance"])}{"*" if a["frozen"] else ""}' for n, a in sorted(state.items()))


def fingerprint(log):
    h = 14695981039346656037
    for e in log:
        for b in show(e).encode() + b'\n':
            h = ((h ^ b) * 1099511628211) % 2 ** 64
    return h


def run(args, text):
    every, points, out = 3, [], []
    for arg in args:
        parts = arg.split('=')
        key = parts[0]
        try:
            n = int(parts[1]) if len(parts) > 1 else -1
        except ValueError:
            n = -1
        if key == 'every' and 1 <= n <= 1000:
            every = n
        elif key == 'at' and 0 <= n <= 1000000:
            points.append(n)
        else:
            out.append(f'ignored `{arg}`')
    log, snaps, state, refused = [], [], {}, 0
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line == '' or line.startswith('#'):
            continue
        e = parse(line)
        if isinstance(e, str):
            out.append(f'line {n}: {e}: `{line}`')
            continue
        try:
            decide(state, e)
        except Refused as no:
            refused += 1
            out.append(f'line {n}: refused {show(e)}: {no}')
            continue
        apply(state, e)
        log.append(e)
        out.append(f'#{len(log)} {show(e)}')
        if len(log) % every == 0:
            snaps.append((len(log), copy.deepcopy(state)))
    out.append(f'{len(log)} events, {refused} refused, {len(snaps)} snapshots every {every}')
    out.append(f'now: {balances(state)}')
    total = sum(a['balance'] for a in state.values())
    opened = sum(e[2] for e in log if e[0] == 'open')
    added = sum(e[2] for e in log if e[0] == 'deposit')
    gone = sum(e[2] for e in log if e[0] == 'withdraw')
    kept = 'conserved' if total == opened + added - gone else 'LOST'
    out.append(f'held {money(total)}: opened {money(opened)}, deposited {money(added)}, withdrawn {money(gone)} ({kept})')
    full = replay(log, [], len(log))
    fast = replay(log, snaps, len(log))
    m = lambda s: 'matches' if balances(s) == balances(state) else 'DIFFERS'
    out.append(f'replay from the start {m(full)}, from snapshots {m(fast)}')
    for k in points:
        past, slow = replay(log, snaps, k), replay(log, [], k)
        agree = '' if balances(past) == balances(slow) else ' (snapshot replay DIFFERS)'
        out.append(f'as of #{min(k, len(log))}: {balances(past)}{agree}')
    if snaps:
        out.append(f'first snapshot, at #{snaps[0][0]}: {balances(snaps[0][1])}')
    out.append(f'fingerprint {fingerprint(log):016x}')
    return '\n'.join(out) + '\n'


def main():
    got = run(command_line(), (HERE / 'stdin.txt').read_text())
    if '--write' in sys.argv:
        (HERE / 'expected.out').write_text(got)
    elif (HERE / 'expected.out').read_text() != got:
        sys.exit('expected.out differs from the oracle')


if __name__ == '__main__':
    main()
