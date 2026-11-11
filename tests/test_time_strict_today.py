"""`strict_today`, the careful `today`; `age` counting to today; `Date - Date` as a `Period`."""
import datetime as dt
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=300, check=False, cwd=tmp_path)


def test_strict_today_is_a_date_or_says_why(compiler, tmp_path):
    source = """$time.zone = 'UTC'

match strict_today {
    d:Date => printl"date {d =? today or d + 1day =? today}"
    a:AmbiguousToday => printl"ambiguous {a.dates.first <? a.dates.last}"
    u:UnknownToday => printl"unknown {u.message}"
}
printl"{(strict_today ?? today) =? today}"
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    first, second = ran.stdout.splitlines()
    assert first in ('date true', 'ambiguous true') or first.startswith('unknown '), first
    # (a day can turn between the two reads)
    assert second in ('true', 'false')


def test_strict_today_warns_like_today_without_a_zone(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'printl"{strict_today ?? today}"\n')
    assert ran.returncode == 0, ran.stderr
    assert '`strict_today` has no time zone here' in ran.stderr
    control = run(compiler, tmp_path, '$time.zone = \'UTC\'\n\nprintl"{strict_today ?? today}"\n')
    assert control.returncode == 0, control.stderr
    assert 'time zone' not in control.stderr


def test_today_stays_a_plain_date(compiler, tmp_path):
    ran = run(compiler, tmp_path, '$time.zone = \'UTC\'\n\nlet d:Date = today\nprintl"{d}"\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip() in {str(dt.datetime.now(dt.timezone.utc).date()),
                                  str(dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1))}


def test_removed_today_names(compiler, tmp_path):
    for name in ('today_support', 'possible_todays'):
        ran = run(compiler, tmp_path, f'$time.zone = \'UTC\'\n\nprintl"{{{name}}}"\n')
        assert ran.returncode != 0, name
        assert name in ran.stderr


def test_age_counts_to_today_by_default(compiler, tmp_path):
    source = '$time.zone = \'UTC\'\n\nlet born = date"2000-02-29"\nprintl"{age(born) =? age(born on=today())}"\nprintl(age(born on=date"2027-02-28"))\n'
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['true', '26']


def test_date_difference_is_a_period(compiler, tmp_path):
    source = """let gap = date"2027-02-28" - date"2000-02-29"
let p:Period = gap
let q:Period = 1month
printl"{gap.years} {gap.total_days} {date"2000-02-29" + gap}"
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['26 9861 2027-02-28']
    # (the provisional name is gone: a date difference is a Period)
    gone = run(compiler, tmp_path, 'let s:Span = date"2027-02-28" - date"2000-02-29"\n')
    assert gone.returncode != 0
    assert 'Span' in gone.stderr
