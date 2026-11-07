"""Writing and reading times by a pattern, against Python's datetime."""
import datetime as dt
import random
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=300, check=False, cwd=tmp_path)


# Dewy's letters, and strftime's for the same text.
FORMS = [('yyyy-MM-dd', '%Y-%m-%d'), ('EEEE d MMMM y', '%A %-d %B %Y'), ('EEE, MMM d', '%a, %b %-d'),
         ('M/d/y', '%-m/%-d/%Y'), ("yyyy'W'", '%YW')]


def test_dates_write_as_datetime_does(compiler, tmp_path):
    rng = random.Random(1582)
    lines = []
    expected = []
    for _ in range(80):
        day = dt.date(rng.randrange(1000, 9000), rng.randrange(1, 13), rng.randrange(1, 29))
        ours, theirs = rng.choice(FORMS)
        lines.append(f'printl(date"{day.isoformat()}".format("{ours}"))')
        expected.append(day.strftime(theirs))
    ran = run(compiler, tmp_path, '\n'.join(lines) + '\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == expected


def test_times_and_zoned_values_write(compiler, tmp_path):
    ran = run(compiler, tmp_path, """const t = time_of_day"15:04:09.25"
printl(t.format("HH:mm:ss.SSS"))
printl(t.format("h:mm a"))
printl(time_of_day"00:05".format("h:mm a"))
printl(time_of_day"12:05".format("h:mm a"))
const m = zoned"2026-10-26T09:05:30[America/New_York]"
printl(m.format("yyyy-MM-dd'T'HH:mm:ssXXX'['VV']'"))
printl(local"2026-11-01T01:30".format("M/d/y H:mm"))
printl(instant"2026-10-26T13:05:30Z".format("d MMM y HH:mm VV"))
printl(utc"2016-12-31T23:59:60".nominal.format("HH:mm:ss"))
""")
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['15:04:09.250', '3:04 PM', '12:05 AM', '12:05 PM',
                                       '2026-10-26T09:05:30-04:00[America/New_York]', '11/1/2026 1:30',
                                       '26 Oct 2026 13:05 UTC', '23:59:60']


def test_reading_by_a_pattern(compiler, tmp_path):
    ran = run(compiler, tmp_path, """let text = "5/3/2027"
printl(date(text "d/M/y"))
printl(date"2027-01-01" =? date("2027-01-01" "yyyy-MM-dd"))
printl(date("March 5, 2027" "MMMM d, y"))
printl(time_of_day("3:04 PM" "h:mm a"))
printl(time_of_day("12:04 am" "h:mm a"))
printl(local("05.03.2027 15:04" "dd.MM.yyyy HH:mm"))
let wrong = "31/2/2027"
printl(date(wrong "d/M/y"))
let short = "2027"
printl(date(short "d/M/y"))
""")
    assert ran.returncode == 0, ran.stderr
    lines = ran.stdout.splitlines()
    assert lines[:6] == ['2027-03-05', 'true', '2027-03-05', '15:04:00', '00:04:00', '2027-03-05T15:04:00']
    assert '2027-02 has no day 31' in lines[6]
    assert "does not read as `d/M/y`" in lines[7]


def test_constant_mistakes_are_compile_errors(compiler, tmp_path):
    for expression, message in [
            ('date"2027-01-01".format("HH:mm")', "'HH' is part of a time of day, and this value has none"),
            ('time_of_day"09:00".format("yyyy")', "'yyyy' is part of a date, and this value has none"),
            ('date"2027-01-01".format("yy")', "'yy' is not a pattern field"),
            ('date"2027-01-01".format("q")', "'q' is not a pattern field"),
            ('date"2027-01-01".format("\'x")', 'a quote in a pattern closes'),
            ('date("31/2/2027" "d/M/y")', '2027-02 has no day 31'),
            ('date("5/3/27" "d/M/yyyy")', 'does not read as'),
    ]:
        ran = run(compiler, tmp_path, f'printl({expression})\n')
        assert ran.returncode != 0, expression
        assert message in ran.stderr, (expression, ran.stderr)
    # A constant pattern is checked though the text is not known yet.
    ran = run(compiler, tmp_path, 'let t = "x"\nprintl(date(t "qq"))\n')
    assert ran.returncode != 0
    assert "'qq' is not a pattern field" in ran.stderr
