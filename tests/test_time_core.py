"""lib/time/core.dewy against an independent reference: the UTC table, labels on the axis and back."""
import datetime as dt
from fractions import Fraction
import random
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)

# IERS tai-utc.dat, as (first MJD, a, b, c): TAI-UTC = a + (MJD - b) * c seconds.
STEPS = [(37300, '1.4228180', 37300, '0.001296'), (37512, '1.3728180', 37300, '0.001296'),
         (37665, '1.8458580', 37665, '0.0011232'), (38334, '1.9458580', 37665, '0.0011232'),
         (38395, '3.2401300', 38761, '0.001296'), (38486, '3.3401300', 38761, '0.001296'),
         (38639, '3.4401300', 38761, '0.001296'), (38761, '3.5401300', 38761, '0.001296'),
         (38820, '3.6401300', 38761, '0.001296'), (38942, '3.7401300', 38761, '0.001296'),
         (39004, '3.8401300', 38761, '0.001296'), (39126, '4.3131700', 39126, '0.002592'),
         (39887, '4.2131700', 39126, '0.002592')]
# Bulletin C: the dates TAI-UTC became 10s, 11s, ... 37s.
LEAPS = ['1972-01-01', '1972-07-01', '1973-01-01', '1974-01-01', '1975-01-01', '1976-01-01', '1977-01-01',
         '1978-01-01', '1979-01-01', '1980-01-01', '1981-07-01', '1982-07-01', '1983-07-01', '1985-07-01',
         '1988-01-01', '1990-01-01', '1991-01-01', '1992-07-01', '1993-07-01', '1994-07-01', '1996-01-01',
         '1997-07-01', '1999-01-01', '2006-01-01', '2009-01-01', '2012-07-01', '2015-07-01', '2017-01-01']
MJD_1970 = 40587
J0_DAYS = (dt.date(1977, 1, 1) - dt.date(1970, 1, 1)).days
LEAP_DAYS = {(dt.date.fromisoformat(d) - dt.date(1970, 1, 1)).days + MJD_1970: 10 + i for i, d in enumerate(LEAPS)}


def offset(mjd, in_day_seconds):
    """TAI-UTC in seconds at a UTC label, exactly."""
    if mjd >= min(LEAP_DAYS):
        return Fraction(max(v for day, v in LEAP_DAYS.items() if day <= mjd))
    row = max((r for r in STEPS if r[0] <= mjd), key=lambda r: r[0])
    return Fraction(row[1]) + (Fraction(mjd) + Fraction(in_day_seconds) / 86400 - row[2]) * Fraction(row[3])


def axis(moment, nanos=0):
    """ns from J0 of a UTC label, or None off the grid."""
    days = (moment.date() - dt.date(1970, 1, 1)).days
    in_day = moment.hour * 3600 + moment.minute * 60 + moment.second
    in_day_exact = Fraction(in_day) + Fraction(nanos, 10**9)
    value = (Fraction(days - J0_DAYS) * 86400 + in_day_exact + offset(days + MJD_1970, in_day_exact)) * 10**9
    return int(value) if value.denominator == 1 else None


def label(moment, nanos=0):
    text = moment.strftime('%Y-%m-%dT%H:%M:%S')
    if nanos:
        text += f'.{nanos:09}'.rstrip('0')
    return text + 'Z'


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=300, check=False, cwd=tmp_path)


def test_labels_match_the_reference(compiler, tmp_path):
    rng = random.Random(1977)
    cases = []
    while len(cases) < 400:
        moment = dt.datetime(1961, 1, 1) + dt.timedelta(seconds=rng.randrange(0, 4_000_000_000))
        nanos = rng.choice([0, 0, 500_000_000, 250_000_000, 1000])
        count = axis(moment, nanos)
        if count is None:
            continue
        cases.append((label(moment, nanos), count))
    # Each side of every 1972+ row, including the inserted second before it.
    for day in LEAP_DAYS:
        date = dt.datetime(1970, 1, 1) + dt.timedelta(days=day - MJD_1970)
        for moment in (date - dt.timedelta(seconds=1), date, date + dt.timedelta(seconds=1)):
            cases.append((label(moment), axis(moment)))
    table = ' '.join(f'"{text}"' for text, _ in cases)
    source = f"""import p"@lib/time/core.dewy" as core
loop text in [{table}] {{
    match instant(text) {{
        t:Instant => printl"{{core.ns_count(t)}} {{t}}"
        e:ParseError => printl"parse {{e.message}}"
        e:InvalidFields => printl"fields {{e.message}}"
        e:OutsideCoverage => printl"coverage {{e.message}}"
        <OffGrid> => printl"off grid"
    }}
}}
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    lines = ran.stdout.splitlines()
    assert len(lines) == len(cases)
    for (text, count), line in zip(cases, lines):
        expected_text = text
        assert line == f'{count} {expected_text}', text


def test_every_leap_second_and_only_those(compiler, tmp_path):
    days = sorted(LEAP_DAYS)
    good = [(dt.date(1970, 1, 1) + dt.timedelta(days=d - MJD_1970 - 1)).isoformat() for d in days[1:]]
    bad = ['2015-12-31', '2016-06-30', '1999-12-31', '2026-12-31', '1971-12-30']
    table = ' '.join(f'"{d}T23:59:60Z"' for d in good + bad)
    source = f"""loop text in [{table}] {{
    match instant(text) {{
        t:Instant => printl"{{t}}"
        e:InvalidFields => printl"invalid"
        e:ParseError => printl"parse"
        e:OutsideCoverage => printl"coverage"
        <OffGrid> => printl"off"
    }}
}}
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    lines = ran.stdout.splitlines()
    assert lines[:len(good)] == [f'{d}T23:59:60Z' for d in good]
    assert lines[len(good):] == ['invalid'] * len(bad)


def test_counts_past_64_bits_stay_exact(compiler, tmp_path):
    rng = random.Random(128)
    pairs = [(rng.randrange(-2**126, 2**126), rng.randrange(-2**126, 2**126)) for _ in range(60)]
    body = '\n'.join(
        f'show(core.instant_at({a}) core.duration_of({b}))' for a, b in pairs)
    source = f"""import p"@lib/time/core.dewy" as core
show = (t:Instant d:Duration) => printl"{{core.ns_count(t+d)}} {{core.ns_count(t-d)}} {{core.ns_count(d+d)}} {{core.ns_count(-d)}} {{t <? t+d}} {{d <? d+d}}"
{body}
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    lines = ran.stdout.splitlines()
    for (a, b), line in zip(pairs, lines):
        words = line.split()
        assert words[:4] == [str(a + b), str(a - b), str(b + b), str(-b)], (a, b)
        assert words[4] == ('true' if a < a + b else 'false')
        assert words[5] == ('true' if b < b + b else 'false')


def test_leaving_the_range_is_reported(compiler, tmp_path):
    source = """import p"@lib/time/core.dewy" as core
let top = core.instant_at(170141183460469231731687303715884105727)
printl"{core.checked_add(top core.duration_of(1)) is? OutOfRange}"
printl"{top + core.duration_of(1)}"
"""
    ran = run(compiler, tmp_path, source)
    assert ran.stdout == 'true\n'
    assert ran.returncode != 0
    assert '128-bit range' in ran.stderr


def test_compile_errors_say_what_to_write(compiler, tmp_path):
    for expression, message in [
            ('instant"2015-12-31T23:59:60Z"', 'no leap second'),
            ('instant"2026-10-24T12:00:00"', 'a local time is `zoned`'),
            ('instant"2026-02-30T12:00:00Z"', 'no day 30'),
            ('instant"1950-01-01T00:00:00Z"', 'UTC starts in 1961'),
            ('instant"2026-10-24T12:00:00Z" + 1ns/3', "quantize"),
            ('(instant"2026-10-24T12:00:00Z" + 1ns/3)', "off the nanosecond grid"),
            ('utc"2015-12-31T23:59:60"', 'no leap second'),
    ]:
        ran = run(compiler, tmp_path, f'printl({expression})\n')
        assert ran.returncode != 0, expression
        assert message in ran.stderr, (expression, ran.stderr)


def test_float_time_says_quantize(compiler, tmp_path):
    source = 'let x:float64*Time = 1.5s\nprintl(instant"2026-10-24T12:00:00Z" + x)\n'
    ran = run(compiler, tmp_path, source)
    assert ran.returncode != 0
    assert 'quantize' in ran.stderr


def test_literal_leaves_no_parser_in_the_program(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    source.write_text('let t = instant"2026-10-24T12:00:00Z"\nprintl(t =? t)\n')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'main'], capture_output=True, timeout=300,
                           check=False, cwd=tmp_path)
    assert built.returncode == 0, built.stderr
    assert b'needs an offset' not in (tmp_path / 'main').read_bytes()
    assert subprocess.run([tmp_path / 'main'], capture_output=True, text=True, check=False).stdout == 'true\n'


def test_no_time_loads_nothing(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    source.write_text('printl"hi"\n')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'main'], capture_output=True, timeout=300,
                           check=False, cwd=tmp_path)
    assert built.returncode == 0, built.stderr
    assert b'128-bit range' not in (tmp_path / 'main').read_bytes()
