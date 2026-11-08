"""`$time.rules` names another rule pack; the accessors of civil values."""
import shutil
import subprocess
import sys

import pytest

from tests.support import ROOT, compiler  # noqa: F401 (fixture)


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=300, check=False, cwd=tmp_path)


def make_pack(tmp_path):
    zic = shutil.which('zic')
    if zic is None:
        pytest.skip('no zic to build test rules')
    data = tmp_path / 'zones'
    data.mkdir()
    source = '# version test1\nZ Test/Zone 3 - +03\nL Test/Zone Test/Link\n'
    (data / 'tzdata.zi').write_text(source)
    subprocess.run([zic, '-d', str(data), str(data / 'tzdata.zi')], check=True, capture_output=True)
    xml = tmp_path / 'windows.xml'
    xml.write_text('<mapZone other="Test Standard Time" territory="001" type="Test/Zone"/>\n')
    pack = tmp_path / 'test.bin'
    subprocess.run([sys.executable, str(ROOT / 'tools/time/gen_rules.py'), str(data), str(pack), str(xml)], check=True,
                   capture_output=True)
    return pack


def test_a_program_can_name_its_rules(compiler, tmp_path):
    make_pack(tmp_path)
    ran = run(compiler, tmp_path, """$time.rules = 'test.bin'
const m = zoned"2026-07-01T12:00[Test/Zone]"
printl(m)
let name = "Test/Link"
printl(zone(name))
""")
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['2026-07-01T12:00:00+03:00[Test/Zone]', 'Test/Link']
    ran = run(compiler, tmp_path, "$time.rules = 'test.bin'\nprintl(zone\"America/New_York\")\n")
    assert ran.returncode != 0
    assert 'no time zone is called America/New_York' in ran.stderr


def test_the_pack_is_checked(compiler, tmp_path):
    (tmp_path / 'bad.bin').write_text('not a pack')
    ran = run(compiler, tmp_path, "$time.rules = 'bad.bin'\nprintl(zone\"UTC\")\n")
    assert ran.returncode != 0
    assert 'is not a rule pack' in ran.stderr
    ran = run(compiler, tmp_path, "$time.rules = 'missing.bin'\nprintl(zone\"UTC\")\n")
    assert ran.returncode != 0
    assert 'cannot read' in ran.stderr


def test_rules_are_the_main_files_to_say(compiler, tmp_path):
    (tmp_path / 'other.dewy').write_text("$time.rules = 'x.bin'\nshown = () => 1\n")
    ran = run(compiler, tmp_path, 'import p"other.dewy" as other\nprintl(other.shown)\n')
    assert ran.returncode != 0
    assert 'top of the entry file' in ran.stderr


def test_zoned_accessors(compiler, tmp_path):
    ran = run(compiler, tmp_path, """const m = zoned"2026-10-26T09:05:30.25[America/New_York]"
printl"{m.date} {m.time_of_day} {m.local}"
printl"{m.year} {m.month} {m.day} {m.hour} {m.minute} {m.second} {m.nanosecond} {m.weekday}"
""")
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['2026-10-26 09:05:30.25 2026-10-26T09:05:30.25', '2026 10 26 9 5 30 250000000 0']


def test_local_times_and_times_of_day(compiler, tmp_path):
    ran = run(compiler, tmp_path, """const t = time_of_day"09:30"
printl"{t} {t.hour} {t.minute} {t <? time_of_day"10:00"} {time_of_day"23:59:59.5"}"
const l = local"2026-11-01T01:30"
printl"{l} {l.date} {l.time} {date"2026-11-01".at(t)} {l + 1day}"
const ny = zone"America/New_York"
printl(l.in_zone(ny fold='later'))
printl(local"2026-10-26T09:00".in_zone(ny))
printl(in_zone(instant"2026-10-26T13:00:00Z" ny))
let text = "2026-13-01T00:00"
printl(local(text) is? ParseError)
""")
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == [
        '09:30:00 9 30 true 23:59:59.5',
        '2026-11-01T01:30:00 2026-11-01 01:30:00 2026-11-01T09:30:00 2026-11-02T01:30:00',
        '2026-11-01T01:30:00-05:00[America/New_York]', '2026-10-26T09:00:00-04:00[America/New_York]',
        '2026-10-26T09:00:00-04:00[America/New_York]', 'true']


def test_local_literals_say_what_is_wrong(compiler, tmp_path):
    for expression, message in [
            ('local"2026-03-08T02:30".in_zone(zone"America/New_York")', "gap='preserve_displacement'"),
            ('local"2026-11-01T01:30".in_zone(zone"America/New_York")', "fold='earlier'"),
            ('local"2026-11-01T01:30-04:00"', 'a local time has no offset'),
            ('time_of_day"09:60:00"', '09:60 is not a time of day'),
    ]:
        ran = run(compiler, tmp_path, f'printl({expression})\n')
        assert ran.returncode != 0, expression
        assert message in ran.stderr, (expression, ran.stderr)
