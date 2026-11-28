"""Independent job scheduler over the same jobs; run with --write to refresh expected.out."""
from fractions import Fraction
from pathlib import Path
import heapq
import json
import re
import sys

HERE = Path(__file__).parent


def command_line():
    return json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]['args']


def small(text):
    if not re.fullmatch(r'[+-]?\d+', text):
        return None
    n = int(text)
    return n if 0 <= n <= 1000000 else None


def jobs_in(text):
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line == '' or line.startswith('#'):
            continue
        w = line.split()
        if len(w) != 4 and not (len(w) == 6 and w[4] == 'after'):
            yield ('bad', n, line, 'expected NAME PRIORITY ARRIVAL DURATION [after DEP,...]')
            continue
        p, a, d = small(w[1]), small(w[2]), small(w[3])
        if p is None or a is None or d is None:
            yield ('bad', n, line, 'priority, arrival and duration are whole numbers up to 1000000')
            continue
        if d == 0:
            yield ('bad', n, line, 'a job takes some time')
            continue
        yield ('job', dict(name=w[0], priority=p, arrival=a, duration=d, after=w[5].split(',') if len(w) == 6 else []))


def urgency(job, now, age):
    return job['priority'] - max(0, now - job['arrival']) // age


def simulate(jobs, workers, age):
    pending = sorted(jobs, key=lambda j: j['arrival'])
    ready, done, running, free, now = [], set(), [], list(range(1, workers + 1)), 0
    while pending or ready or running:
        while pending and pending[0]['arrival'] <= now:
            ready.append(pending.pop(0))
        while free:
            runnable = [j for j in ready if all(d in done for d in j['after'])]
            if not runnable:
                break
            ordered = sorted(sorted(runnable, key=lambda j: j['name']), key=lambda j: j['arrival'])
            pick = min(ordered, key=lambda j: urgency(j, now, age))
            ready = [j for j in ready if j['name'] != pick['name']]
            worker = free.pop(0)
            yield ('start', now, pick['name'], worker, now - pick['arrival'], urgency(pick, now, age))
            heapq.heappush(running, ((now + pick['duration']) * 128 + worker, now + pick['duration'], pick['name'], worker))
        next_arrival = pending[0]['arrival'] if pending else None
        if running and (next_arrival is None or running[0][0] <= next_arrival * 128):
            _, t, name, worker = heapq.heappop(running)
            now = t
            done.add(name)
            free = sorted(free + [worker])
            yield ('finish', t, name, worker)
            while running and running[0][1] == now:
                _, t2, name2, worker2 = heapq.heappop(running)
                done.add(name2)
                free = sorted(free + [worker2])
                yield ('finish', t2, name2, worker2)
        elif next_arrival is not None:
            now = next_arrival
        else:
            for j in sorted(ready, key=lambda j: j['name']):
                yield ('stuck', j['name'], [d for d in j['after'] if d not in done])
            break


def half_up(f, places):
    scaled = f * 10 ** places
    q = int(scaled)
    if scaled - q >= Fraction(1, 2):
        q += 1
    s = str(q).rjust(places + 1, '0')
    return f'{s[:-places]}.{s[-places:]}'


def run(args, text):
    workers, age, out = 2, 4, []
    for arg in args:
        parts = arg.split('=')
        n = int(parts[1]) if len(parts) > 1 and re.fullmatch(r'[+-]?\d+', parts[1]) else -1
        if parts[0] == 'workers' and 1 <= n <= 64:
            workers = n
        elif parts[0] == 'age' and 1 <= n <= 1000:
            age = n
        else:
            out.append(f'ignored `{arg}`')
    jobs, names = [], set()
    for item in jobs_in(text):
        if item[0] == 'bad':
            out.append(f'line {item[1]}: {item[3]}: `{item[2]}`')
        elif item[1]['name'] in names:
            out.append(f'job {item[1]["name"]} repeated; the first one stays')
        else:
            names.add(item[1]['name'])
            jobs.append(item[1])
    for job in jobs:
        for d in job['after']:
            if d not in names:
                out.append(f'job {job["name"]} waits for {d}, which is not a job')
    out.append(f'{len(jobs)} jobs on {workers} workers, aging one step per {age}')
    starts, waits, ends, busy, stuck = {}, {}, {}, 0, 0
    for h in simulate(jobs, workers, age):
        if h[0] == 'start':
            _, t, name, worker, waited, urg = h
            out.append(f'{t:>4}  w{worker} starts {name} (waited {waited}, urgency {urg})')
            starts[name], waits[name] = t, waited
        elif h[0] == 'finish':
            _, t, name, worker = h
            out.append(f'{t:>4}  w{worker} finishes {name}')
            ends[name] = t
            busy += t - starts.get(name, t)
        else:
            out.append(f'   -  {h[1]} never runs: waiting for {", ".join(h[2])}')
            stuck += 1
    finish = max([0, *ends.values()])
    out.append(f'all done at {finish}; {len(ends)} finished, {stuck} stuck')
    if finish > 0:
        out.append(f'workers busy {half_up(Fraction(100 * busy, finish * workers), 1)}% of the time')
    by_priority = {}
    for job in jobs:
        if job['name'] in waits:
            by_priority.setdefault(job['priority'], []).append(waits[job['name']])
    for p in sorted(by_priority):
        ws = by_priority[p]
        out.append(f'priority {p}: {len(ws)} jobs, mean wait {half_up(Fraction(sum(ws), len(ws)), 2)}, longest {max([0, *ws])}')
    started = sorted([j for j in jobs if j['name'] in waits], key=lambda j: j['name'])
    if started:
        slowest = max(started, key=lambda j: waits[j['name']])
        out.append(f'longest wait: {slowest["name"]} ({waits[slowest["name"]]})')
    return '\n'.join(out) + '\n'


def main():
    got = run(command_line(), (HERE / 'stdin.txt').read_text())
    if '--write' in sys.argv:
        (HERE / 'expected.out').write_text(got)
    elif (HERE / 'expected.out').read_text() != got:
        sys.exit('expected.out differs from the oracle')


if __name__ == '__main__':
    main()
