"""Independent token-bucket replay over the same log; run with --write to refresh expected.out."""
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
import json
import math
import re
import sys

HERE = Path(__file__).parent
UNITS = {'ms': Fraction(1, 1000), 's': 1, 'min': 60, 'hour': 3600, 'h': 3600}
NS = 10 ** 9


def command_line():
    return json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]['args']


def show(ns):
    """A duration in nanoseconds as Dewy prints one: in the largest unit it is a whole number of."""
    if ns == 0:
        return '0s'
    for unit, size in (('h', 3600 * NS), ('min', 60 * NS), ('s', NS), ('ms', 10 ** 6)):
        if ns % size == 0:
            return f'{ns // size}{unit}'
    raise ValueError(ns)


def period(text):
    m = re.fullmatch(r'(\d+(?:\.\d+)?)(ms|s|min|hour|h)', text)
    return None if m is None else Fraction(m[1]) * UNITS[m[2]] * NS


def instant(text):
    m = re.fullmatch(r'(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d{1,9}))?Z', text)
    if m is None:
        return None
    try:
        whole = datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), int(m[6]), tzinfo=timezone.utc)
    except ValueError:
        return None
    return int(whole.timestamp()) * NS + int((m[7] or '0').ljust(9, '0'))


def clock(ns):
    t = datetime.fromtimestamp(ns // NS, timezone.utc)
    return f'{t:%H:%M:%S}.{ns % NS // 10 ** 6:03d}'


def day(ns):
    return f'{datetime.fromtimestamp(ns // NS, timezone.utc):%Y-%m-%d}'


def policy(text):
    parts = text.split(',')
    count, per = parts[0].split('/')
    burst = int(count)
    for extra in parts[1:]:
        burst = int(extra.removeprefix('burst='))
    return int(count), period(per), burst


def run(argv, text):
    out = []
    policies, costs = {}, {}
    for word in argv[1:]:
        if word.startswith('cost='):
            costs = {m.upper(): int(n) for m, n in (item.split(':') for item in word[5:].split(','))}
            continue
        name, rule = word.split('=', 1)
        policies[name] = policy(rule)
    fallback = policies['*']
    requests = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        words = line.split()
        if len(words) != 4:
            out.append(f'line {n}: expected `TIME CLIENT METHOD PATH`')
            continue
        at = instant(words[0])
        if at is None:
            out.append(f'line {n}: `{words[0]}` is not a UTC time')
            continue
        if requests and at < requests[-1][0]:
            out.append(f'line {n}: {clock(at)} is before {clock(requests[-1][0])}; skipped')
            continue
        requests.append((at, words[1], words[2].upper(), words[3]))
    buckets, tallies, today = {}, {}, ''
    for at, client, method, path in requests:
        count, per, burst = policies.get(client, fallback)
        cost = costs.get(method, 1)
        tokens, last = buckets.get(client, (Fraction(burst), at))
        t = tallies.setdefault(client, dict(requests=0, allowed=0, denied=0, refused=0, run=0, longest=0, busiest=0, recent=[]))
        if day(at) != today:
            today = day(at)
            out.append(f'-- {today}')
        t['requests'] += 1
        head = f'{clock(at)} {client:<6} {method:<6} {path}'
        if cost > burst:
            t['denied'] += 1
            t['refused'] += cost
            t['run'] += 1
            out.append(f"{head}  denied: costs {cost}, more than {client}'s burst of {burst}")
        else:
            tokens = min(Fraction(burst), tokens + Fraction(at - last) / per * count)
            last = at
            if tokens >= cost:
                tokens -= cost
                t['allowed'] += 1
                t['run'] = 0
                t['recent'] = [seen for seen in t['recent'] if at - seen < NS] + [at]
                t['busiest'] = max(t['busiest'], len(t['recent']))
                out.append(f'{head}  ok, {math.floor(tokens)} left')
            else:
                wait = (cost - tokens) * per / count
                ms = math.ceil(wait / 10 ** 6)
                t['denied'] += 1
                t['refused'] += cost
                t['run'] += 1
                out.append(f'{head}  denied, retry in {show(ms * 10 ** 6)}')
        t['longest'] = max(t['longest'], t['run'])
        buckets[client] = (tokens, last)
    if requests:
        out.append(f'{len(requests)} requests over {show(requests[-1][0] - requests[0][0])}')
        for client in sorted(tallies):
            t = tallies[client]
            count, per, burst = policies.get(client, fallback)
            out.append(f"{client}: {t['requests']} requests, {t['allowed']} allowed, {t['denied']} denied (cost {t['refused']}), "
                       f"at most {t['busiest']} in a second, longest denial run {t['longest']}; {count} per {show(int(per))}, burst {burst}")
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    expected = HERE / 'expected.out'
    result = run(['rate_limiter'] + command_line(), (HERE / 'stdin.txt').read_text())
    if sys.argv[1:] == ['--write']:
        expected.write_text(result)
    elif expected.read_text() != result:
        sys.exit('expected.out differs from the token-bucket replay')
