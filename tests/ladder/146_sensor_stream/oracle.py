"""Independent sensor-stream report with Python generators; run with --write to refresh expected.out."""
from fractions import Fraction
from pathlib import Path
import json
import sys

HERE = Path(__file__).parent


def command_line():
    entry = json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]
    return entry['args']


def clock(text):
    parts = text.split(':')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    h, m, s = map(int, parts)
    if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
        return None
    return h * 3600 + m * 60 + s


def show_clock(seconds):
    return f'{seconds // 3600:02}:{seconds // 60 % 60:02}'


def show(x):
    cents = abs(x) * 100
    whole = int(cents) + (1 if cents - int(cents) >= Fraction(1, 2) else 0)
    sign = '-' if x < 0 and whole else ''
    return f'{sign}{whole // 100}.{whole % 100:02}'


def parse(line, text):
    fields = text.split(',')
    if len(fields) != 3:
        return ('bad', line, 'expected time,sensor,value')
    seconds = clock(fields[0].strip())
    if seconds is None:
        return ('bad', line, f'bad time {fields[0].strip()}')
    sensor = fields[1].strip()
    if not sensor:
        return ('bad', line, 'missing sensor')
    try:
        value = Fraction(fields[2].strip())
    except ValueError:
        return ('bad', line, f'bad value {fields[2].strip()}')
    return ('reading', line, seconds, sensor, value)


def rows(text, out):
    for n, raw in enumerate(text.split('\n'), 1):
        line = raw.strip()
        if not line or line.startswith('#') or line == 'time,sensor,value':
            continue
        yield parse(n, line)


def readings_for(sensor, source, out):
    last, kept = -1, 0
    try:
        for item in source:
            if item[0] == 'reading' and item[3] == sensor:
                if item[2] <= last:
                    out.append(f'  line {item[1]}: {sensor} at {show_clock(item[2])} is out of order, dropped')
                else:
                    last = item[2]
                    kept += 1
                    yield item
    finally:
        out.append(f'  ({sensor}: {kept} readings pulled)')


def windows(step, source):
    started, start, total, count = False, 0, Fraction(0), 0
    for r in source:
        window = r[2] - r[2] % step
        if started and window != start and count > 0:
            average = total / count
            yield (start, average, count)
            start += step
            while start < window:
                yield (start, average, 0)
                start += step
            total, count = Fraction(0), 0
        started = True
        start = window
        total += r[4]
        count += 1
    if count > 0:
        yield (start, total / count, count)


def smooth(width, source):
    recent, total = [], Fraction(0)
    for start, value, samples in source:
        recent.append(value)
        total += value
        if len(recent) > width:
            total -= recent.pop(0)
        yield (start, total / len(recent), samples)


def alarms(high, band, step, source):
    active, start, last, peak = False, 0, 0, Fraction(0)
    for start_b, value, _ in source:
        last = start_b
        if active:
            peak = max(peak, value)
            if value <= high - band:
                yield (start, start_b, peak, False)
                active = False
        elif value >= high:
            active, start, peak = True, start_b, value
    if active:
        yield (start, last + step, peak, True)


def run(argv):
    step, width, head, watches = 300, 3, 6, []
    for word in argv:
        name, _, value = word.partition('=')
        if name in ('step', 'width', 'head') and _:
            if name == 'step':
                step = int(value)
            elif name == 'width':
                width = int(value)
            else:
                head = int(value)
        else:
            sensor, high, band = word.split(':')
            watches.append((sensor, Fraction(high), Fraction(band)))
    text = (HERE / 'stdin.txt').read_text()
    out = []
    good = 0
    for item in rows(text, out):
        if item[0] == 'reading':
            good += 1
        else:
            out.append(f'line {item[1]}: {item[2]}')
    out.append(f'{good} readings')

    def pipeline(sensor):
        return smooth(width, windows(step, readings_for(sensor, rows(text, out), out)))

    for sensor, high, band in watches:
        out.append(f'{sensor}: alarm at {show(high)}, clear at {show(high - band)}')
        out.append(f'  first {head} windows:')
        g = pipeline(sensor)
        for _ in range(head):
            b = next(g, None)
            if b is None:
                break
            note = 'gap' if b[2] == 0 else '1 sample' if b[2] == 1 else f'{b[2]} samples'
            out.append(f'    {show_clock(b[0])}  {show(b[1])}  {note}')
        g.close()
        del g
        found = list(alarms(high, band, step, pipeline(sensor)))
        if not found:
            out.append('  no alarms')
            continue
        for start, stop, peak, still in found:
            state = 'still open' if still else 'cleared'
            out.append(f'  alarm {show_clock(start)}-{show_clock(stop)} peak {show(peak)} {state}')
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    expected = HERE / 'expected.out'
    if sys.argv[1:] == ['--write']:
        expected.write_text(run(command_line()))
    elif expected.read_text() != run(command_line()):
        sys.exit('expected.out differs from the sensor-stream report')
