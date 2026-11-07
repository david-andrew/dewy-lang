"""`zoned(s)` with no zone anywhere: it reads the running machine's zone, and says so at the call."""
import os
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)

ASSUMES = 'reads in the zone of the machine it runs on'


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=300, check=False, cwd=tmp_path,
                          env={**os.environ, 'TZ': 'Asia/Tokyo'})


def test_runtime_text_warns_and_reads_the_machine(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'f=(s:string)=>printl(zoned(s))\nf("2026-01-01T12:00")\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '2026-01-01T12:00:00+09:00[Asia/Tokyo]\n'
    assert ASSUMES in ran.stderr
    assert 'main.dewy:1:' in ran.stderr


def test_saying_where_keeps_it_quiet(compiler, tmp_path):
    for source, output in [
            ("$time.zone = 'system'\nf=(s:string)=>printl(zoned(s))\nf(\"2026-01-01T12:00\")\n",
             '2026-01-01T12:00:00+09:00[Asia/Tokyo]\n'),
            ("$time.zone = 'Europe/Paris'\nf=(s:string)=>printl(zoned(s))\nf(\"2026-01-01T12:00\")\n",
             '2026-01-01T12:00:00+01:00[Europe/Paris]\n'),
            ('f=(s:string)=>printl(zoned(s zone=zone"UTC"))\nf("2026-01-01T12:00")\n',
             '2026-01-01T12:00:00+00:00[UTC]\n'),
            ('printl(zoned"2026-01-01T12:00[UTC]")\n', '2026-01-01T12:00:00+00:00[UTC]\n'),
            ('printl(zoned("2026-01-01T12:00[UTC]"))\n', '2026-01-01T12:00:00+00:00[UTC]\n'),
    ]:
        ran = run(compiler, tmp_path, source)
        assert ran.returncode == 0, (source, ran.stderr)
        assert ran.stdout == output, source
        assert ASSUMES not in ran.stderr, source


def test_text_that_names_its_zone_reads_there_at_run_time(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'f=(s:string)=>printl(zoned(s))\nf("2026-01-01T12:00[UTC]")\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '2026-01-01T12:00:00+00:00[UTC]\n'


def test_a_literal_still_cannot_assume(compiler, tmp_path):
    for source in ('printl(zoned"2026-07-01T12:00")\n', 'printl(zoned("2026-07-01T12:00"))\n',
                   "$time.zone = 'system'\nprintl(zoned\"2026-07-01T12:00\")\n"):
        ran = run(compiler, tmp_path, source)
        assert ran.returncode != 0, source
        assert 'a literal cannot assume' in ran.stderr, source


def test_a_checked_scope_still_warns_for_today_and_age(compiler, tmp_path):
    for source, words in [('printl(today() is? Date)\n', 'it assumes the zone of the machine it runs on'),
                          ('printl(age(date"2000-01-01") >=? 0)\n', 'it assumes the zone of the machine it runs on')]:
        ran = run(compiler, tmp_path, source)
        assert ran.returncode == 0, ran.stderr
        assert words in ran.stderr, source
