"""Real zones and dates in bulk against zoneinfo, an independent reader of the same IANA data.

The cases and answers live in time_zone_bulk.expected, generated from zoneinfo by running this
file with --generate, so they run on hosts whose zone data differs from the pack; a host with the
pack's rules also checks that the file is what zoneinfo says. Every transition of each zone in the
years below gets its gap or fold under each policy, the instants around it, and civil steps into it.
"""
import datetime as dt
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))

from tests.support import compiler  # noqa: E402,F401 (fixture)
from tests.test_time_zones import same_rules  # noqa: E402

EXPECTED = Path(__file__).with_name('time_zone_bulk.expected')
ZONES = ['Africa/Cairo', 'Africa/Casablanca', 'Africa/Monrovia', 'America/Havana', 'America/Los_Angeles',
         'America/New_York', 'America/Nuuk', 'America/Santiago', 'America/St_Johns', 'Antarctica/Troll',
         'Asia/Gaza', 'Asia/Kathmandu', 'Asia/Tehran', 'Asia/Tokyo', 'Australia/Lord_Howe', 'Australia/Sydney',
         'Europe/Dublin', 'Europe/London', 'Pacific/Apia', 'Pacific/Chatham', 'UTC']
# Under UTC's old rates, through the table, the last table years, and well into the zone's standing rule.
YEARS = [1961, 1970, 2000, 2026, 2037, 2040, 2100]
UTC = dt.timezone.utc
MINUTE = dt.timedelta(minutes=1)


def utc_reading(moment, info):
    return moment.replace(tzinfo=UTC).astimezone(info).utcoffset()


def transitions(info, year):
    """(utc moment of the change, offset before, offset after), by bisecting each day of the year."""
    found = []
    moment = dt.datetime(year, 1, 1) - dt.timedelta(days=1)
    stop = dt.datetime(year + 1, 1, 1) - dt.timedelta(days=1)
    while moment < stop:
        step = moment + dt.timedelta(hours=6)
        before, after = utc_reading(moment, info), utc_reading(step, info)
        if before != after:
            low, high = moment, step
            while high - low > dt.timedelta(seconds=1):
                middle = low + (high - low) // 2
                middle = middle.replace(microsecond=0)
                if utc_reading(middle, info) == before:
                    low = middle
                else:
                    high = middle
            found.append((high, before, after))
        moment = step
    return found


def offset_text(offset):
    seconds = int(offset.total_seconds())
    sign = '-' if seconds < 0 else '+'
    seconds = abs(seconds)
    text = f'{sign}{seconds // 3600:02}:{seconds % 3600 // 60:02}'
    return f'{text}:{seconds % 60:02}' if seconds % 60 else text


def zoned_text(local, offset, zone):
    return f'{local.strftime("%Y-%m-%dT%H:%M:%S")}{offset_text(offset)}[{zone}]'


def read_local(local, zone, policy):
    """A local reading under a fold and gap policy, written out as the library should print it."""
    info = ZoneInfo(zone)
    first, second = local.replace(tzinfo=info, fold=0), local.replace(tzinfo=info, fold=1)
    if first.utcoffset() == second.utcoffset():
        return zoned_text(local, first.utcoffset(), zone)
    if first.utcoffset() > second.utcoffset():
        if policy[0] is None:
            return 'ambiguous'
        chosen = first if policy[0] == 'earlier' else second
        return zoned_text(local, chosen.utcoffset(), zone)
    if policy[1] is None:
        return 'gap'
    # (fold=0 in a gap reads with the offset before it, so converting walks past the gap: displacement)
    displaced = first.astimezone(UTC).astimezone(info)
    if policy[1] == 'preserve_displacement':
        return zoned_text(displaced.replace(tzinfo=None), displaced.utcoffset(), zone)
    # (the change itself: search back from the displaced moment for where the reading began)
    low, high = local - second.utcoffset(), local - first.utcoffset()
    while high - low > dt.timedelta(seconds=1):
        middle = (low + (high - low) // 2).replace(microsecond=0)
        if utc_reading(middle, info) == first.utcoffset():
            low = middle
        else:
            high = middle
    after = high.replace(tzinfo=UTC).astimezone(info)
    return zoned_text(after.replace(tzinfo=None), after.utcoffset(), zone)


def generate():
    cases = []

    def reads(local, zone):
        text = local.strftime('%Y-%m-%dT%H:%M:%S')
        cases.append(('read', text, zone, read_local(local, zone, (None, None))))
        if cases[-1][3] == 'gap':
            cases.append(('next', text, zone, read_local(local, zone, (None, 'next'))))
            cases.append(('displace', text, zone, read_local(local, zone, (None, 'preserve_displacement'))))
        elif cases[-1][3] == 'ambiguous':
            cases.append(('earlier', text, zone, read_local(local, zone, ('earlier', None))))
            cases.append(('later', text, zone, read_local(local, zone, ('later', None))))

    def steps(local, zone):
        """One civil day and one civil month forward onto a reading, from a start that reads plainly."""
        for name, start in (('day', local - dt.timedelta(days=1)), ('month', month_before(local))):
            if start is None or read_local(start, zone, (None, None)) in ('gap', 'ambiguous'):
                continue
            cases.append((name, start.strftime('%Y-%m-%dT%H:%M:%S'), zone,
                          read_local(local, zone, ('later', 'next'))))

    for zone in ZONES:
        info = ZoneInfo(zone)
        for year in YEARS:
            for change, before, after in transitions(info, year):
                inner = (change + min(before, after)).replace(second=0)
                width = abs(after - before)
                for local in (inner - MINUTE, inner + width // 2, inner + width):
                    local = local.replace(microsecond=0)
                    reads(local, zone)
                steps((inner + width // 2).replace(microsecond=0), zone)
                for moment in (change - dt.timedelta(seconds=1), change):
                    reading = moment.replace(tzinfo=UTC).astimezone(info)
                    cases.append(('moment', moment.strftime('%Y-%m-%dT%H:%M:%SZ'), zone,
                                  zoned_text(reading.replace(tzinfo=None), reading.utcoffset(), zone)))
            # (an ordinary reading each season, with its civil steps, whatever the zone's changes)
            for month in (1, 7):
                local = dt.datetime(year, month, 15, 9, 41, 7)
                reads(local, zone)
                steps(local, zone)
    # Total Instant.in_zone, independently of the UTC reader's 1961 lower bound.
    # Before that bound the projection uses TT civil labels; Python supplies only the
    # zone mapping of those coordinates, never an invented historical UTC realization.
    epoch = dt.datetime(1977, 1, 1)
    for zone in ZONES:
        info = ZoneInfo(zone)
        for year in (1800, 1850, 1900, 1950, 2200, 2400, 2500, 9998):
            for month in (1, 7):
                moment = dt.datetime(year, month, 15, 9, 41, 7)
                reading = moment.replace(tzinfo=UTC).astimezone(info)
                answer = zoned_text(reading.replace(tzinfo=None), reading.utcoffset(), zone)
                if year < 1961:
                    count = (moment - epoch) // dt.timedelta(seconds=1) * 10**9 - 32184000000
                    cases.append(('tt_moment', str(count), zone, answer))
                else:
                    cases.append(('moment', moment.strftime('%Y-%m-%dT%H:%M:%SZ'), zone, answer))
    return cases


def month_before(local):
    # (a month back from the first month of the UTC table would start before the axis does)
    if local.day > 28 or (local.year, local.month) == (1961, 1):
        return None
    return local.replace(year=local.year - 1, month=12) if local.month == 1 else local.replace(month=local.month - 1)


def lines_of(cases):
    return [f'{name}|{text}|{zone}|{answer}' for name, text, zone, answer in cases]


def program(cases):
    calls = '\n'.join(f'check_tt_moment({text} "{zone}")' if name == 'tt_moment'
                      else f'check_{name}("{text}" "{zone}")'
                      for name, text, zone, _ in cases)
    return '''import p"@lib/time/core.dewy" as core
show = (r:ZonedDateTime|Gap|Ambiguous|OutsideCoverage|ParseError|UnknownZone|MissingContext|InvalidFields|InvalidDate|OffGrid) => {
    if r is? ZonedDateTime {printl(r)}
    else if r is? Gap {printl"gap"}
    else if r is? Ambiguous {printl"ambiguous"}
    else {printl"failed"}
}
at = (name:string) => zone(name) ?? zone"UTC"
check_read = (text:string name:string) => show(zoned(text zone=at(name)))
check_next = (text:string name:string) => show(zoned(text zone=at(name) gap='next'))
check_displace = (text:string name:string) => show(zoned(text zone=at(name) gap='preserve_displacement'))
check_earlier = (text:string name:string) => show(zoned(text zone=at(name) fold='earlier'))
check_later = (text:string name:string) => show(zoned(text zone=at(name) fold='later'))
check_moment = (text:string name:string) => {
    let t = instant(text)
    if t is? Instant {show(in_zone(t at(name)))} else {printl"failed"}
}
check_tt_moment = (count:int name:string) => {
    let z:ZonedDateTime = core.instant_at(count).in_zone(at(name))
    printl(z)
}
check_day = (text:string name:string) => {
    let z = zoned(text zone=at(name))
    if z is? ZonedDateTime {
        let moved = z.add(1day fold='later' gap='next')
        show(moved)
    } else {printl"failed"}
}
$time.fold = 'later'
$time.gap = 'next'
check_month = (text:string name:string) => {
    let z = zoned(text zone=at(name))
    if z is? ZonedDateTime {
        let moved = z + 1month
        show(moved)
    } else {printl"failed"}
}
''' + calls + '\n'


def stored():
    return [tuple(line.split('|')) for line in EXPECTED.read_text().splitlines()]


def test_library_matches_the_generated_answers(compiler, tmp_path):
    cases = stored()
    path = tmp_path / 'main.dewy'
    path.write_text(program(cases))
    ran = subprocess.run([compiler, path], capture_output=True, text=True, timeout=600, check=False, cwd=tmp_path)
    assert ran.returncode == 0, ran.stderr[:2000]
    wrong = [f'{name}({text} {zone}): {got}, zoneinfo says {answer}'
             for (name, text, zone, answer), got in zip(cases, ran.stdout.splitlines()) if got != answer]
    assert len(ran.stdout.splitlines()) == len(cases)
    assert not wrong, f'{len(wrong)} of {len(cases)} differ:\n' + '\n'.join(wrong[:40])


def test_every_printed_reading_reads_back(compiler, tmp_path):
    readings = sorted({answer for name, _, _, answer in stored() if '[' in answer and name != 'tt_moment'})
    calls = '\n'.join(f'back("{text}")' for text in readings)
    path = tmp_path / 'main.dewy'
    path.write_text(f"back = (text:string) => printl(zoned(text))\n{calls}\n")
    ran = subprocess.run([compiler, path], capture_output=True, text=True, timeout=600, check=False, cwd=tmp_path)
    assert ran.returncode == 0, ran.stderr[:2000]
    wrong = [(want, got) for want, got in zip(readings, ran.stdout.splitlines()) if want != got]
    assert len(ran.stdout.splitlines()) == len(readings)
    assert not wrong, wrong[:20]


def test_total_projection_preserves_extreme_instants(compiler, tmp_path):
    # Python's calendar repeats every 400 years. Reduce the day into datetime's
    # domain, restoring the cycles in the printed year. The positive end uses
    # continuous UTC's inherited 37s; the negative end uses the TT label.
    cases = []
    base = dt.datetime(2400, 1, 1)
    epoch_days = (dt.datetime(1977, 1, 1) - base).days
    for count in (-2**127, 2**127 - 1):
        label_ns = count + (32184000000 if count < 0 else -37000000000)
        seconds, nanos = divmod(label_ns, 10**9)
        days, in_day = divmod(seconds, 86400)
        cycles, within = divmod(days + epoch_days, 146097)
        coordinate = base + dt.timedelta(days=within, seconds=in_day)
        for name in ('UTC', 'Africa/Monrovia', 'America/New_York'):
            info = ZoneInfo(name)
            if count < 0:
                # All three zones are still on their first offset in 1800.
                offset = dt.datetime(1800, 1, 1, tzinfo=info).utcoffset()
            else:
                offset = coordinate.replace(tzinfo=UTC).astimezone(info).utcoffset()
            local = coordinate + offset
            year = local.year + cycles * 400
            year_text = f'{year:04}' if year >= 0 else f'-{abs(year):04}'
            fraction = f'.{nanos:09}'.rstrip('0') if nanos else ''
            answer = (f'{year_text}-{local.month:02}-{local.day:02}T'
                      f'{local.hour:02}:{local.minute:02}:{local.second:02}'
                      f'{fraction}{offset_text(offset)}[{name}]')
            cases.append((count, name, answer))
    calls = '\n'.join(f'show({count} "{name}")' for count, name, _ in cases)
    path = tmp_path / 'main.dewy'
    path.write_text('import p"@lib/time/core.dewy" as core\n'
                    'show=(count:int name:string)=>{\n'
                    'let t=core.instant_at(count)\n'
                    'let z:ZonedDateTime=t.in_zone(zone(name) ?? zone"UTC")\n'
                    'printl(z)\nprintl(z.nominal =? t)\n}\n' + calls)
    ran = subprocess.run([compiler, path], capture_output=True, text=True, timeout=120, check=False, cwd=tmp_path)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == [line for _, _, answer in cases for line in (answer, 'true')]


@same_rules
def test_generated_answers_are_what_zoneinfo_says():
    assert lines_of(generate()) == EXPECTED.read_text().splitlines()


if __name__ == '__main__' and '--generate' in sys.argv:
    EXPECTED.write_text('\n'.join(lines_of(generate())) + '\n')
