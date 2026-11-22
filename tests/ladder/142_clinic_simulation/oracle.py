"""Independent replay of the clinic experiments; run with --write to refresh expected.out."""
from pathlib import Path
import heapq
import math
import sys

HERE = Path(__file__).parent
OPEN_MINUTES, MEAN_GAP, MEAN_VISIT, MEAN_URGENT_VISIT = 480.0, 4.0, 9.0, 14.0
URGENT_SHARE, WAITING_ROOM, SEEDS = 0.25, 8, 5
MASK = (1 << 64) - 1


class Random:
    def __init__(self, seed):
        self.state = seed

    def word(self):
        self.state = (self.state + 0x9e3779b97f4a7c15) & MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xbf58476d1ce4e5b9) & MASK
        z = ((z ^ (z >> 27)) * 0x94d049bb133111eb) & MASK
        return z ^ (z >> 31)

    def uniform(self):
        return float(self.word() >> 11) / 9007199254740992.0

    def exponential(self, mean):
        return -mean * math.log(1.0 - self.uniform())


def simulate(job_id, doctors, seed):
    r = Random(seed)
    patients = []
    clock = r.exponential(MEAN_GAP)
    while clock < OPEN_MINUTES:
        urgent = r.uniform() < URGENT_SHARE
        visit = r.exponential(MEAN_URGENT_VISIT if urgent else MEAN_VISIT)
        patients.append((clock, urgent, visit))
        clock += r.exponential(MEAN_GAP)
    events, seq = [], 0
    for p in patients:
        heapq.heappush(events, (p[0], seq, p, False))
        seq += 1
    urgent_line, normal_line = [], []
    free, waits, urgent_waits = doctors, [], []
    busy, away, longest, now = 0.0, 0, 0, 0.0
    while events:
        now, _, patient, leaving = heapq.heappop(events)
        if leaving:
            free += 1
        else:
            if free == 0 and len(urgent_line) + len(normal_line) >= WAITING_ROOM:
                away += 1
                continue
            (urgent_line if patient[1] else normal_line).append(patient)
            longest = max(longest, len(urgent_line) + len(normal_line))
        while free > 0 and (urgent_line or normal_line):
            p = urgent_line.pop(0) if urgent_line else normal_line.pop(0)
            wait = now - p[0]
            waits.append(wait)
            if p[1]:
                urgent_waits.append(wait)
            busy += p[2]
            free -= 1
            heapq.heappush(events, (now + p[2], seq, p, True))
            seq += 1
    order = sorted(waits)
    mean = lambda xs: sum(xs) / float(len(xs)) if xs else 0.0
    p90 = order[(9 * len(order) + 9) // 10 - 1] if order else 0.0
    return dict(id=job_id, doctors=doctors, seen=len(waits), away=away, mean=mean(waits), p90=p90,
                max=order[-1] if order else 0.0, urgent=mean(urgent_waits),
                util=busy / (float(doctors) * now), queue=longest, closed=now)


def spread(values):
    n = float(len(values))
    m = sum(values) / n
    var = sum([(v - m) ** 2 for v in values]) / (n - 1.0)
    return f'{m:6.2f} ± {math.sqrt(var):5.2f}'


def run():
    plan = [((d - 2) * SEEDS + s - 1, d, 1000 * d + s) for d in (2, 3) for s in range(1, SEEDS + 1)]
    days = [simulate(*job) for job in plan]
    out = ['job doctors  seen away  mean wait  p90 wait  max wait  urgent  busy  queue  closed']
    for d in days:
        out.append(f"{d['id']:>3} {d['doctors']:>7} {d['seen']:>5} {d['away']:>4} {d['mean']:>10.2f} {d['p90']:>9.2f} "
                   f"{d['max']:>9.2f} {d['urgent']:>7.2f} {d['util']:>4.0%} {d['queue']:>6} {d['closed']:>7.1f}")
    for doctors in (2, 3):
        group = [d for d in days if d['doctors'] == doctors]
        out.append(f'{doctors} doctors over {len(group)} days:')
        out.append(f"  mean wait   {spread([d['mean'] for d in group])} min")
        out.append(f"  urgent wait {spread([d['urgent'] for d in group])} min")
        out.append(f"  turned away {spread([float(d['away']) for d in group])} patients")
        out.append(f"  utilization {spread([100.0 * d['util'] for d in group])} %")
    return '\n'.join(out) + '\n'


def main():
    output = run()
    expected = HERE / 'expected.out'
    if sys.argv[1:] == ['--write']:
        expected.write_text(output)
    elif expected.read_text() != output:
        sys.exit('expected.out differs from the oracle')


if __name__ == '__main__':
    main()
