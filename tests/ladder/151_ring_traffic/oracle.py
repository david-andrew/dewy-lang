"""Independent Nagel-Schreckenberg run with the same seed; run with --write to refresh expected.out."""
from fractions import Fraction
from pathlib import Path
import json
import sys

HERE = Path(__file__).parent
MASK = (1 << 64) - 1


def command_line():
    words = json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]['args']
    opts = dict(cells=60, cars=18, steps=30, limit=5, dawdle=25, seed=7, light=None, red=6, green=9)
    quiet = False
    for w in words:
        if w in ('--quiet', '-q'):
            quiet = True
        else:
            name, value = w.split('=')
            opts[name] = int(value)
    return opts, quiet


class Rng:
    def __init__(self, seed):
        self.state = (seed ^ 0x9e3779b97f4a7c15) & MASK

    def percent(self):
        x = self.state
        x ^= x >> 12
        x ^= (x << 25) & MASK
        x ^= x >> 27
        self.state = x
        return (((x * 2685821657736338717) & MASK) >> 32) % 100


def run():
    o, quiet = command_line()
    n, light = o['cells'], o['light']
    road = [None] * n
    car = 0
    for at in range(n):
        if car < o['cars'] and at * o['cars'] >= car * n:
            road[at] = [car, 0]
            car += 1
    cars = sum(slot is not None for slot in road)
    rng = Rng(o['seed'])
    out, moved, passed, longest, stopped_at = [], 0, 0, 0, 0
    for t in range(o['steps']):
        red = light is not None and t % (o['red'] + o['green']) < o['red']
        wall = light if red else None
        nxt = [None] * n
        for i in range(n):
            if road[i] is None:
                continue
            ident, speed = road[i]
            speed = min(speed + 1, o['limit'])
            free = speed
            for d in range(1, speed + 1):
                cell = (i + d) % n
                if road[cell] is not None or cell == wall:
                    free = d - 1
                    break
            speed = min(speed, free)
            if speed > 0 and rng.percent() < o['dawdle']:
                speed -= 1
            if light is not None and (i < light <= i + speed or i + speed >= n + light):
                passed += 1
            nxt[(i + speed) % n] = [ident, speed]
            moved += speed
        road = nxt
        if not quiet:
            cells = ''.join(str(s[1]) if s else '|' if i == wall else '.' for i, s in enumerate(road))
            out.append(f'{t:>3} {cells}')
        queue = run_ = 0
        for slot in road:
            if slot is not None and slot[1] == 0:
                run_ += 1
                queue = max(queue, run_)
            else:
                run_ = 0
        if queue > longest:
            longest, stopped_at = queue, t
    out.append(f"{cars} cars on {n} cells for {o['steps']} steps, limit {o['limit']}, dawdle {o['dawdle']}%")
    mean = Fraction(moved, cars * o['steps'])
    out.append(f"mean speed {float(mean):.3f} cells per step ({float(mean * 100 / o['limit']):.1f}% of the limit)")
    if light is not None:
        out.append(f'{passed} cars past the light at cell {light}')
    out.append(f'longest queue {longest} cars, at step {stopped_at}')
    out.append('order on the ring: ' + ' '.join(str(s[0]) for s in road if s))
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    expected = HERE / 'expected.out'
    if sys.argv[1:] == ['--write']:
        expected.write_text(run())
    elif expected.read_text() != run():
        sys.exit('expected.out differs from the traffic run')
