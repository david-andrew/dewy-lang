"""`$time.zone_source = 'host'`: the machine's zone rules when the program runs, in place of the pack's."""
import os
import struct
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)
from tests.test_time_zone_bulk import program, stored
from tests.test_time_zones import same_rules

HOST = "$time.zone_source = 'host'\n\n"
READ = 'f=(s:string)=>printl(zoned(s zone=zone"America/New_York"))\nf("2026-07-01T12:00")\n'


def run(compiler, tmp_path, source, tzdir=None):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    env = dict(os.environ)
    if tzdir is not None:
        env['TZDIR'] = str(tzdir)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=600, check=False, cwd=tmp_path, env=env)


def tzif(offset, footer):
    """A version 2 TZif file with one kind of time, no changes, and this rule after them."""
    def header(chars):
        return b'TZif2' + bytes(15) + struct.pack('>6L', 0, 0, 0, 0, 1, chars)
    kind = struct.pack('>lBB', offset, 0, 0) + b'X\0'
    return header(2) + kind + header(2) + kind + b'\n' + footer + b'\n'


def machine(tmp_path, data):
    zones = tmp_path / 'zones' / 'America'
    zones.mkdir(parents=True)
    (zones / 'New_York').write_bytes(data)
    return tmp_path / 'zones'


def test_follows_the_machine_and_not_the_pack(compiler, tmp_path):
    tzdir = machine(tmp_path, tzif(5 * 3600, b'<+05>-5'))
    ran = run(compiler, tmp_path, HOST + READ, tzdir)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '2026-07-01T12:00:00+05:00[America/New_York]\n'
    ran = run(compiler, tmp_path, READ, tzdir)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '2026-07-01T12:00:00-04:00[America/New_York]\n'


def test_a_machine_rule_after_the_table(compiler, tmp_path):
    tzdir = machine(tmp_path, tzif(3600, b'<+01>-1<+02>,M3.2.0,M11.1.0'))
    ran = run(compiler, tmp_path, HOST + READ, tzdir)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '2026-07-01T12:00:00+02:00[America/New_York]\n'


def test_a_machine_without_the_zone_keeps_the_pack_and_says_so_once(compiler, tmp_path):
    for tzdir in (tmp_path / 'nothing', machine(tmp_path, b'not a zone file')):
        ran = run(compiler, tmp_path, HOST + READ + 'f("2026-07-01T13:00")\n', tzdir)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout.splitlines() == ['2026-07-01T12:00:00-04:00[America/New_York]',
                                           '2026-07-01T13:00:00-04:00[America/New_York]']
        assert ran.stderr.count('this machine has no rules for America/New_York') == 1


def test_a_truncated_zone_file_keeps_the_pack(compiler, tmp_path):
    tzdir = machine(tmp_path, tzif(5 * 3600, b'<+05>-5')[:50])
    ran = run(compiler, tmp_path, HOST + READ, tzdir)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '2026-07-01T12:00:00-04:00[America/New_York]\n'


def test_a_literal_cannot_be_worked_out(compiler, tmp_path):
    ran = run(compiler, tmp_path, f'{HOST}printl(zoned"2026-07-01T12:00[UTC]")\n')
    assert ran.returncode != 0
    assert 'a literal cannot be worked out' in ran.stderr
    # (a zone name is the pack's, so it needs no rules; the reading waits for the run)
    ran = run(compiler, tmp_path, f'{HOST}printl(zoned("2026-07-01T12:00" zone=zone"UTC"))\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '2026-07-01T12:00:00+00:00[UTC]\n'


def test_where_and_what_it_can_say(compiler, tmp_path):
    ran = run(compiler, tmp_path, "$time.zone_source = 'pack'\n")
    assert ran.returncode != 0
    assert "`$time.zone_source` is 'host'" in ran.stderr
    ran = run(compiler, tmp_path, "f=()=>{\n    $time.zone_source = 'host'\nprintl(1)\n}\nf\n")
    assert ran.returncode != 0
    assert "scoped `$time.zone_source` is not yet supported" in ran.stderr
    assert 'top of the entry file or its main body' in ran.stderr


@same_rules
def test_the_machines_real_rules_match_zoneinfo(compiler, tmp_path):
    cases = stored()
    ran = run(compiler, tmp_path, HOST + program(cases))
    assert ran.returncode == 0, ran.stderr[:2000]
    wrong = [f'{name}({text} {zone}): {got}, zoneinfo says {answer}'
             for (name, text, zone, answer), got in zip(cases, ran.stdout.splitlines()) if got != answer]
    assert len(ran.stdout.splitlines()) == len(cases)
    assert not wrong, f'{len(wrong)} of {len(cases)} differ:\n' + '\n'.join(wrong[:40])
