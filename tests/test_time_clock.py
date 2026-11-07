"""Clocks and waits, and calendar arithmetic against Python's datetime."""
import datetime as dt
import os
import random
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)


def run(compiler, tmp_path, source, **environment):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    env = dict(os.environ)
    env.update(environment)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=300, check=False,
                          cwd=tmp_path, env=env)


def test_stopwatch_and_deadline(compiler, tmp_path):
    source = """let start = now
sleep(3ms)
let took = now - start
printl"{took >? 3ms} {took <? 30s}"
let deadline = now + 5ms
let spins = 0
loop now <? deadline { spins = spins + 1 }
printl"{spins >? 0} {now - start >? 8ms}"
let dt = (now - start) / 1s as float64
printl"{dt >? 0.0}"
sleep(now - now)
let a = monotonic
let b = monotonic
printl"{a <=? b} {b - a <? 30s} {(a + 1s) - a}"
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['true true', 'true true', 'true', 'true true 1s']


def test_wall_clock_agrees_with_this_machine(compiler, tmp_path):
    # 37s TAI-UTC is what makes a J0 count print as today's UTC.
    source = 'printl"{now.nominal}"\n'
    before = dt.datetime.now(dt.timezone.utc)
    ran = run(compiler, tmp_path, source)
    after = dt.datetime.now(dt.timezone.utc)
    assert ran.returncode == 0, ran.stderr
    shown = dt.datetime.fromisoformat(ran.stdout.strip().replace('Z', '+00:00'))
    assert before - dt.timedelta(seconds=2) <= shown <= after + dt.timedelta(seconds=2)


def test_readings_print_as_measured(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'printl"{now}"\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.startswith('~20')


def test_within_takes_a_duration(compiler, tmp_path):
    source = """slow = ():>void|Canceled => {
    sleep(2s) or_throw
}
main = () => {
    let start = now
    let r = within((now + 5ms) - now @slow)
    printl"{r is? Timeout} {now - start <? 1s}"
}
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'true true\n'


def test_periods_are_refused_as_lengths(compiler, tmp_path):
    for expression, message in [
            ('sleep(1day)', 'write `sleep(24hour)`'), ('sleep(2week)', 'write `sleep(24hour)`'),
            ('sleep(1month)', 'calendar period'),
            ('within(1day @f)', 'calendar period'),
            ('instant"2026-10-24T12:00:00Z" + 1day', 'write `24hour`'),
            ('instant"2026-10-24T12:00:00Z" - 1week', 'write `24hour`'),
            ('instant"2026-10-24T12:00:00Z" + 1month', 'date or a zoned time'),
            ('(now - now) + 1day', 'write `24hour`'),
    ]:
        ran = run(compiler, tmp_path, f'f = ():>void|Canceled => {{}}\nlet x = {expression}\n')
        assert ran.returncode != 0, expression
        assert message in ran.stderr, (expression, ran.stderr)


def test_the_assumed_zone_is_named(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'let d = today\nprintl"{d =? d}"\n', TZ='Asia/Tokyo')
    assert ran.returncode == 0, ran.stderr
    assert "main.dewy:1:9: warning: `today` has no time zone here, so it assumes the zone of the machine" in ran.stderr
    assert "`$time.zone = 'system'`" in ran.stderr
    for setting in ("'system'", "'Asia/Tokyo'"):
        ran = run(compiler, tmp_path, f'$time.zone = {setting}\nlet d = today\nprintl"{{d =? d}}"\n')
        assert ran.returncode == 0, ran.stderr
        assert 'time zone' not in ran.stderr
    ran = run(compiler, tmp_path, 'printl"{age(date"2000-05-12") >? 20}"\n')
    assert ran.returncode == 0, ran.stderr
    assert '`age` with no `on=`' in ran.stderr


def test_system_zone_reads_its_name_and_pinned_rules(compiler, tmp_path):
    source = "$time.zone = 'system'\nprintl\"{today}\"\n"
    for zone in ('Pacific/Kiritimati', 'Pacific/Pago_Pago'):
        ran = run(compiler, tmp_path, source, TZ=zone)
        assert ran.returncode == 0, ran.stderr
        from zoneinfo import ZoneInfo
        expected = dt.datetime.now(ZoneInfo(zone)).date().isoformat()
        assert ran.stdout.strip() == expected


def test_date_arithmetic_matches_datetime(compiler, tmp_path):
    rng = random.Random(1752)
    lines = []
    expected = []
    for _ in range(150):
        day = dt.date(rng.randrange(100, 9000), rng.randrange(1, 13), rng.randrange(1, 29))
        count = rng.randrange(-20000, 20000)
        target = day + dt.timedelta(days=count)
        other = dt.date(rng.randrange(100, 9000), rng.randrange(1, 13), rng.randrange(1, 29))
        lines.append(f'printl"{{date"{day.isoformat()}" + {count if count >= 0 else f"({count})"}*day}} '
                     f'{{(date"{other.isoformat()}" - date"{day.isoformat()}")/1day}} '
                     f'{{(date"{day.isoformat()}").weekday}}"')
        expected.append(f'{target.isoformat()} {(other - day).days} {day.weekday()}')
    ran = run(compiler, tmp_path, '\n'.join(lines) + '\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == expected


def test_month_overflow(compiler, tmp_path):
    source = """let jan = date"2027-01-31"
printl"{jan.add(1month overflow='clamp')} {jan.add(1month overflow='next')} {jan.add(2month overflow='clamp')}"
printl"{(jan + 1month) is? InvalidDate} {jan + 2month} {date"2024-02-29" + 1year} {date"2024-02-29" + 4year}"
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['2027-02-28 2027-03-01 2027-03-31',
                                       'true 2027-03-31 InvalidDate[message="2025-02 has no day 29"] 2028-02-29']


def test_ages(compiler, tmp_path):
    source = """printl(age(date"2000-05-12" on=date"2026-10-24"))
printl(age(date"2000-05-12" on=date"2026-05-11"))
printl(age(date"2000-05-12" on=date"2026-05-12"))
printl(age(date"2000-02-29" on=date"2027-02-28"))
printl(age(date"2000-02-29" on=date"2027-03-01"))
printl(age(date"2000-02-29" on=date"2027-02-28" leap_day='february_28'))
printl(age(date"2000-02-29" on=date"2028-02-29"))
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.split() == ['26', '25', '26', '26', '27', '27', '28']


def test_date_differences(compiler, tmp_path):
    source = """let gap = date"2027-02-28" - date"2000-02-29"
printl"{gap.years} {gap.total_days} {gap} {gap/1day} {date"2000-02-29" + gap}"
let g2 = date"2026-12-25" - date"2024-10-24"
printl"{g2.years} {g2.months} {g2.days} {g2.total_days}"
let g3 = date"2024-10-24" - date"2026-12-25"
printl"{g3.years} {g3.months} {g3.days} {g3.total_days} {date"2026-12-25" + g3}"
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert (dt.date(2027, 2, 28) - dt.date(2000, 2, 29)).days == 9861
    assert ran.stdout.splitlines() == ['26 9861 9861day 9861 2027-02-28', '2 2 1 792', '-2 -2 -1 -792 2024-10-24']


def test_zone_chosen_at_build(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    source.write_text("$time.zone = 'build'\nprintl\"{today}\"\n")
    env = dict(os.environ, TZ='Pacific/Kiritimati')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'main'], capture_output=True, text=True,
                           timeout=300, check=False, cwd=tmp_path, env=env)
    assert built.returncode == 0, built.stderr
    assert 'time zone' not in built.stderr
    from zoneinfo import ZoneInfo
    env = dict(os.environ, TZ='Pacific/Pago_Pago')
    ran = subprocess.run([tmp_path / 'main'], capture_output=True, text=True, check=False, env=env)
    assert ran.stdout.strip() == dt.datetime.now(ZoneInfo('Pacific/Kiritimati')).date().isoformat()


def test_main_file_pins_the_whole_program(compiler, tmp_path):
    (tmp_path / 'other.dewy').write_text('shown = () => "{today}"\n')
    source = "$time.zone = 'Pacific/Kiritimati'\nimport p\"other.dewy\" as other\nprintl(other.shown)\n"
    ran = run(compiler, tmp_path, source, TZ='Pacific/Pago_Pago')
    assert ran.returncode == 0, ran.stderr
    assert 'time zone' not in ran.stderr
    from zoneinfo import ZoneInfo
    assert ran.stdout.strip() == dt.datetime.now(ZoneInfo('Pacific/Kiritimati')).date().isoformat()


def test_a_scope_setting_must_name_a_zone(compiler, tmp_path):
    ran = run(compiler, tmp_path, "$time.zone = 'Mars/Olympus'\nprintl(today)\n")
    assert ran.returncode != 0
    assert 'no time zone is called Mars/Olympus' in ran.stderr


def test_unbuilt_settings_say_so(compiler, tmp_path):
    for line in ("$time.zone_source = 'host'", "$time.rules = 'x'"):
        ran = run(compiler, tmp_path, line + '\n')
        assert ran.returncode != 0
        assert 'not implemented yet' in ran.stderr


def test_date_literal_reports_its_validators_text(compiler, tmp_path):
    for literal, message in [('date"2026-02-30"', 'not a date: 2026-02 has no day 30'),
                             ('date"2026-13-01"', 'not a date: month 13 is not 1 to 12'),
                             ('date"2026-01-01T09:00"', 'not a date: a date is written YYYY-MM-DD')]:
        ran = run(compiler, tmp_path, f'printl({literal})\n')
        assert ran.returncode != 0, literal
        assert message in ran.stderr, (literal, ran.stderr)
    # Runtime text passes the check and is the value it always was.
    ran = run(compiler, tmp_path, 'let t = "2026-02-30"\nprintl(date(t) is? ParseError)\nprintl(date"2026-02-28")\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['true', '2026-02-28']


def test_old_spellings_point_to_the_new(compiler, tmp_path):
    for expression, message in [
            ('unix_time()', 'now.nominal'), ('parse_date("2026-01-01")', 'date(text)'),
    ]:
        ran = run(compiler, tmp_path, f'printl({expression})\n')
        assert ran.returncode != 0, expression
        assert message in ran.stderr, (expression, ran.stderr)


def test_a_programs_own_function_keeps_an_old_name(compiler, tmp_path):
    source = 'parse_date = (t:string):>string => "mine {t}"\nzip = (a:int64):>int64 => a\nprintl(parse_date("x"))\nprintl(zip(2))\n'
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['mine x', '2']


def test_a_machine_with_no_readable_zone_says_so(compiler, tmp_path):
    source = "$time.zone = 'system'\nlet a = today\nlet b = today\nprintl(a =? b)\n"
    ran = run(compiler, tmp_path, source, TZ='Nowhere/Land')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'true\n'
    assert ran.stderr.count("this machine's time zone is called 'Nowhere/Land'") == 1
    assert 'so times here read as UTC' in ran.stderr
    ran = run(compiler, tmp_path, source, TZ='Asia/Tokyo')
    assert ran.returncode == 0 and 'warning' not in ran.stderr, ran.stderr


def test_windows_name_for_the_machines_zone(compiler, tmp_path):
    ran = run(compiler, tmp_path, "$time.zone = 'system'\nprintl(today)\n", TZ='Tokyo Standard Time')
    assert ran.returncode == 0, ran.stderr
    assert 'warning' not in ran.stderr
    from zoneinfo import ZoneInfo
    assert ran.stdout.strip() == dt.datetime.now(ZoneInfo('Asia/Tokyo')).date().isoformat()
