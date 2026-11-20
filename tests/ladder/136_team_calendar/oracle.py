"""Independent planner over Python's zoneinfo; run with --write to refresh expected.out."""
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import calendar
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

HERE = Path(__file__).parent
UTC = timezone.utc
MEETING = timedelta(minutes=30)


def resolve(local: datetime, zone: ZoneInfo, fold: str, gap: str) -> datetime:
    """A local time in a zone under explicit fold and gap policies, as an aware UTC time."""
    candidates = []
    for f in (0, 1):
        aware = local.replace(tzinfo=zone, fold=f)
        back = aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
        if back == local:
            candidates.append(aware.astimezone(UTC))
    candidates = sorted(set(candidates))
    if candidates:
        return candidates[0] if fold == 'earlier' else candidates[-1]
    if gap == 'next':  # the first instant after the gap
        return _gap_end(local, zone)
    # preserve_displacement: the offset in force before the gap, shown after it
    return (local - local.replace(tzinfo=zone, fold=0).utcoffset()).replace(tzinfo=UTC)


def _gap_end(local: datetime, zone: ZoneInfo) -> datetime:
    t = (local - local.replace(tzinfo=zone, fold=0).utcoffset()).replace(tzinfo=UTC)
    while t.astimezone(zone).replace(tzinfo=None) > local:
        t -= timedelta(minutes=1)
    while t.astimezone(zone).replace(tzinfo=None) < local:
        t += timedelta(minutes=1)
    return t


def clock(t: datetime) -> str:
    return t.astimezone(UTC).strftime('%H:%M')


def span(r) -> str:
    return f'{clock(r[0])}-{clock(r[1])}Z'


def minutes(r) -> str:
    return str(int((r[1] - r[0]).total_seconds() // 60))


def offset(t: datetime) -> str:
    total = int(t.utcoffset().total_seconds())
    sign = '-' if total < 0 else '+'
    total = abs(total)
    return f'{sign}{total // 3600:02d}:{total % 3600 // 60:02d}'


def label(d: date) -> str:
    return f'{calendar.day_abbr[d.weekday()]} {d.day} {calendar.month_abbr[d.month]}'


def small(text: str, limit: int):
    try:
        n = int(text)
    except ValueError:
        return None
    return n if 1 <= n <= limit else None


def hhmm(text: str):
    parts = text.split(':')
    if len(parts) != 2 or not all(p.isdigit() and len(p) == 2 for p in parts):
        return None
    h, m = map(int, parts)
    return time(h, m) if h < 24 and m < 60 else None


def expected() -> str:
    out = []
    members, busy, pins, recurring = [], [], [], []
    first, weeks = date(2026, 1, 5), 1
    for n, raw in enumerate((HERE / 'stdin.txt').read_text().split('\n'), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        fields = line.split(' ')
        kind = fields[0]
        if kind == 'plan':
            first, weeks = date.fromisoformat(fields[1]), small(fields[2], 52)
        elif kind == 'member':
            try:
                zone = ZoneInfo(fields[2])
            except ZoneInfoNotFoundError:
                out.append(f'line {n}: unknown zone {fields[2]}')
                continue
            start, finish = hhmm(fields[3]), hhmm(fields[4])
            if start is None or finish is None:
                out.append(f'line {n}: working hours are written HH:MM')
                continue
            members.append((fields[1], fields[2], zone, start, finish))
        elif kind == 'busy':
            owner = next((m for m in members if m[0] == fields[1]), None)
            if owner is None:
                out.append(f'line {n}: no member called {fields[1]}')
                continue
            a, b = (resolve(datetime.fromisoformat(t), owner[2], 'earlier', 'next') for t in fields[2:4])
            busy.append((a, b))
        elif kind == 'pin':
            pins.append(fields[1])
        else:
            recurring.append(fields)

    out.append('team: ' + ', '.join(f'{m[0]} ({m[1]})' for m in members))
    slots = []
    day = first
    while day < first + timedelta(weeks=weeks):
        if day.weekday() < 5:
            windows = [(resolve(datetime.combine(day, m[3]), m[2], 'earlier', 'next'),
                        resolve(datetime.combine(day, m[4]), m[2], 'earlier', 'next')) for m in members]
            lo, hi = max(w[0] for w in windows), min(w[1] for w in windows)
            if lo >= hi:
                out.append(f'{label(day)}: no common working hours')
            else:
                free = [(lo, hi)]
                for a, b in busy:
                    rest = []
                    for x, y in free:
                        if b <= x or a >= y:
                            rest.append((x, y))
                            continue
                        if x < a:
                            rest.append((x, a))
                        if b < y:
                            rest.append((b, y))
                    free = rest
                shown = ' '.join(span(r) for r in free)
                chosen = next((r for r in free if r[1] - r[0] >= MEETING), None)
                if chosen is None:
                    out.append(f'{label(day)}: common {span((lo, hi))}, free [{shown}], no 30 minute slot')
                else:
                    out.append(f'{label(day)}: common {span((lo, hi))}, free [{shown}], meet {span(chosen)} ({minutes(chosen)} min)')
                    slots.append((day, chosen))
        day += timedelta(days=1)

    for office, zone_name in (('Berlin', 'Europe/Berlin'), ('New York', 'America/New_York')):
        zone = ZoneInfo(zone_name)
        for text in pins:
            t = resolve(datetime.fromisoformat(text), zone, 'earlier', 'next')
            local = t.astimezone(zone)
            shown = f'{label(local.date())} {local.strftime("%H:%M")} {offset(local)}'
            fits = next((s for s in slots if s[1][0] <= t < s[1][1]), None)
            if fits is None:
                out.append(f'{office}: {shown} ({clock(t)}Z) misses every slot')
            else:
                out.append(f'{office}: {shown} ({clock(t)}Z) fits {calendar.day_abbr[fits[0].weekday()]} {span(fits[1])}')

    for fields in recurring:
        if fields[0] == 'standup':
            home = ZoneInfo(fields[1])
            start = datetime.fromisoformat(fields[2])
            for k in range(small(fields[3], 60)):
                local = start + timedelta(weeks=k)
                t = resolve(local, home, 'earlier', 'next')
                seen = ', '.join(f'{m[0]} {t.astimezone(m[2]).strftime("%H:%M")}' for m in members)
                out.append(f'standup {local.day} {calendar.month_abbr[local.month]} {local.strftime("%H:%M")} {fields[1]}: {seen}')
        elif fields[0] == 'retro':
            anchor = date.fromisoformat(fields[1])
            for k in range(1, small(fields[2], 60) + 1):
                months = anchor.month - 1 + k
                y, m = anchor.year + months // 12, months % 12 + 1
                d = date(y, m, min(anchor.day, calendar.monthrange(y, m)[1]))
                out.append(f'retro {d} {calendar.day_name[d.weekday()]}, {(d - first).days} days after planning starts')
        elif fields[0] == 'handoff':
            home = ZoneInfo(fields[1])
            at = hhmm(fields[2])
            day = date.fromisoformat(fields[3])
            previous = None
            for k in range(small(fields[4], 60)):
                d = day + timedelta(days=k)
                t = resolve(datetime.combine(d, at), home, 'later', 'preserve_displacement')
                local = t.astimezone(home)
                gap = '' if previous is None else f', {int((t - previous).total_seconds() // 3600)} h after the last'
                out.append(f'handoff {d} {fields[2]} -> {local.strftime("%H:%M")} {offset(local)} ({clock(t)}Z){gap}')
                previous = t
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    path = HERE / 'expected.out'
    if '--write' in sys.argv:
        path.write_text(expected())
    else:
        assert path.read_text() == expected()
        print('136 oracle: matched')
