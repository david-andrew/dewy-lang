"""Decided civil ranges and Date iteration, checked against Python's calendar."""
import datetime as dt
import random
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, release=False, ir=False):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    binary = tmp_path / 'main'
    built = subprocess.run([compiler, 'build', path, '-o', binary,
                            *(['--release'] if release else []), *(['--ir'] if ir else [])],
                           capture_output=True, text=True, timeout=180, check=False)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=60, check=False)
    assert ran.returncode == 0, ran.stderr
    return ran.stdout.splitlines(), built.stdout


@pytest.mark.parametrize('release', [False, True])
def test_date_ranges_match_datetime(compiler, tmp_path, release):
    rng = random.Random(29)
    spans = [(dt.date(2024, 2, 28), dt.date(2024, 3, 2)),
             (dt.date(1999, 12, 30), dt.date(2000, 1, 2)),
             (dt.date(2100, 2, 27), dt.date(2100, 3, 2))]
    for _ in range(12):
        first = dt.date(rng.randrange(100, 9900), rng.randrange(1, 13), rng.randrange(1, 29))
        spans.append((first, first + dt.timedelta(days=rng.randrange(-2, 6))))
    spans.extend([(dt.date(2026, 1, 1), dt.date(2026, 1, 1))])
    source, expected = [], []
    for first, last in spans:
        for opened, closed in (('[', ')'), ('[', ']'), ('(', ')'), ('(', ']')):
            interval = f'{opened}date"{first}"..date"{last}"{closed}'
            for stored in (False, True):
                source.append(f'let r{len(source)}={interval}\nloop d in r{len(source)} {{printl(d)}}' if stored
                              else f'loop d in {interval} {{printl(d)}}')
                current = first + dt.timedelta(days=opened == '(')
                while current < last or (closed == ']' and current == last):
                    expected.append(current.isoformat())
                    current += dt.timedelta(days=1)
    actual, _ = run(compiler, tmp_path, '\n'.join(source), release)
    assert actual == expected


@pytest.mark.parametrize('release', [False, True])
def test_date_loop_keeps_value_semantics_and_evaluates_bounds_once(compiler, tmp_path, release):
    source = '''let calls:int=0
bound=(s:string):>Date=>{calls+=1;date(s) ?? date"2000-01-01"}
make=():>Range<Date>=>{calls+=1;[date"2024-02-28"..date"2024-03-02")}
main=()=>{
loop d in [bound("2024-02-28")..bound("2024-03-02")) {
    printl(d)
    d=date"2000-01-01"
    if d.year =? 2000 {continue}
}
printl(calls)
loop d in make() {printl(d)}
printl(calls)
$outer
loop d in [date"2024-02-28"..date"2024-03-03") {
    loop n in [0..1) {
        if d.day =? 28 {continue $outer}
        printl(d)
        break $outer
    }
}
loop n in [1..4) {printl(n)}
}
'''
    actual, _ = run(compiler, tmp_path, source, release)
    dates = [(dt.date(2024, 2, 28) + dt.timedelta(days=n)).isoformat() for n in range(3)]
    assert actual == dates + ['2'] + dates + ['3', '2024-02-29', '1', '2', '3']


@pytest.mark.parametrize('release', [False, True])
def test_civil_field_ranges_are_usable_without_runtime_checks(compiler, tmp_path, release):
    # Every range is consumed at a strict call boundary, not just printed.
    source = '''month_value=(n:int64<n => n >=? 1 and n <=? 12>)=>printl(n)
day_value=(n:int64<n => n >=? 1 and n <=? 31>)=>printl(n)
weekday_value=(n:int64<n => n >=? 0 and n <=? 6>)=>printl(n)
hour_value=(n:int64<n => n >=? 0 and n <=? 23>)=>printl(n)
minute_value=(n:int64<n => n >=? 0 and n <=? 59>)=>printl(n)
second_value=(n:int64<n => n >=? 0 and n <=? 59>)=>printl(n)
nanos_value=(n:int64<n => n >=? 0 and n <=? 999999999>)=>printl(n)
show=(d:Date t:TimeOfDay z:ZonedDateTime)=>{
    month_value(d.month);day_value(d.day);weekday_value(d.weekday)
    hour_value(t.hour);minute_value(t.minute);second_value(t.second);nanos_value(t.nanosecond)
    month_value(z.month);day_value(z.day);weekday_value(z.weekday)
    hour_value(z.hour);minute_value(z.minute);second_value(z.second);nanos_value(z.nanosecond)
    const labels=[0 1 2 3 4 5 6 7 8 9 10 11]
    printl(labels[d.month-1])
}
show(date"2024-02-29" time_of_day"23:59:58.123456789" instant"2024-02-29T23:59:58.123456789Z".in_zone(zone"UTC"))
'''
    actual, _ = run(compiler, tmp_path, source, release)
    value = dt.datetime(2024, 2, 29, 23, 59, 58)
    fields = [value.month, value.day, value.weekday(), value.hour, value.minute, value.second, 123456789]
    assert actual == list(map(str, fields * 2 + [value.month - 1]))


@pytest.mark.parametrize('release', [False, True])
def test_date_loop_handles_extreme_ordinals(compiler, tmp_path, release):
    # Date stores signed 64-bit day ordinals. Inclusive termination and an open
    # first bound must work at either extreme without adding one to a bound.
    source = '''import p"@lib/time/civil.dewy" as civil
let top=civil.Date<Gregorian>[9223372036854775807]
let bottom=civil.Date<Gregorian>[-9223372036854775808]
loop d in [top-1day..top] {printl(d._days)}
loop d in (top-1day..top] {printl(d._days)}
let r=(bottom..bottom+1day]
loop d in r {printl(d._days)}
loop d in [top..top) {printl"unexpected"}
'''
    actual, _ = run(compiler, tmp_path, source, release)
    assert actual == list(map(str, [2**63-2, 2**63-1, 2**63-1, -2**63+1]))


def test_utc_fields_include_the_leap_second(compiler, tmp_path):
    source = '''show=(u:UtcLabel)=>{
    let m:int64<n => n >=? 1 and n <=? 12>=u.month
    let d:int64<n => n >=? 1 and n <=? 31>=u.day
    let h:int64<n => n >=? 0 and n <=? 23>=u.hour
    let minute:int64<n => n >=? 0 and n <=? 59>=u.minute
    let second:int64<n => n >=? 0 and n <=? 60>=u.second
    let ns:int64<n => n >=? 0 and n <=? 999999999>=u.nanosecond
    printl"{m} {d} {h} {minute} {second} {ns}"
}
show(utc"2016-12-31T23:59:60.123456789")
'''
    actual, _ = run(compiler, tmp_path, source)
    # datetime supplies the date and minute before the inserted second; the
    # IERS leap label, already covered by the UTC-table tests, contributes 60.
    before = dt.datetime(2016, 12, 31, 23, 59, 59)
    assert actual == [f'{before.month} {before.day} {before.hour} {before.minute} 60 123456789']
