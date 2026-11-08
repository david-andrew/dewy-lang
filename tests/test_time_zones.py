"""lib/time/zones.dewy against Python's zoneinfo, an independent reader of the same IANA data."""
import datetime as dt
import random
import subprocess
from zoneinfo import ZoneInfo, available_timezones

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ZONES = ['America/New_York', 'Europe/London', 'Europe/Dublin', 'Asia/Kolkata', 'Asia/Kathmandu', 'Asia/Tokyo',
         'Australia/Lord_Howe', 'Australia/Sydney', 'America/Sao_Paulo', 'Africa/Casablanca', 'Pacific/Apia',
         'America/St_Johns', 'Antarctica/Troll', 'UTC', 'America/Nuuk', 'Asia/Tehran']


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=300, check=False, cwd=tmp_path)


def offset_text(moment):
    seconds = int(moment.utcoffset().total_seconds())
    sign = '-' if seconds < 0 else '+'
    seconds = abs(seconds)
    return f'{sign}{seconds // 3600:02}:{seconds % 3600 // 60:02}'


def have_rules_version():
    try:
        from pathlib import Path
        return Path('/usr/share/zoneinfo/tzdata.zi').read_text().splitlines()[0].split()[-1]
    except OSError:
        return None


def pack_version():
    from pathlib import Path
    data = (Path(__file__).resolve().parents[1] / 'lib/time/rules/current.bin').read_bytes()
    at = int.from_bytes(data[8:12], 'little')
    return data[at:at + int.from_bytes(data[12:16], 'little')].decode().removeprefix('iana-')


same_rules = pytest.mark.skipif(have_rules_version() != pack_version(), reason='the host has other rules than the pack')


@same_rules
def test_local_times_match_zoneinfo(compiler, tmp_path):
    rng = random.Random(2026)
    cases = []
    while len(cases) < 300:
        zone = rng.choice(ZONES)
        # Mostly near now and across the POSIX rule past the table, a few back to 1972.
        year = rng.choice([1975, 1999, 2010, 2024, 2026, 2030, 2036, 2040, 2100, 2399])
        local = dt.datetime(year, 1, 1) + dt.timedelta(seconds=rng.randrange(0, 365 * 86400) // 60 * 60)
        earlier = local.replace(tzinfo=ZoneInfo(zone), fold=0)
        later = local.replace(tzinfo=ZoneInfo(zone), fold=1)
        if earlier.utcoffset() != later.utcoffset():
            continue  # gaps and folds are the next test's
        cases.append((local, zone, earlier))
    lines = [f'show("{local.strftime("%Y-%m-%dT%H:%M")}" "{zone}")' for local, zone, _ in cases]
    source = """show = (text:string name:string) => {
    let z = zone(name) ?? zone"UTC"
    match zoned(text zone=z) {
        v:ZonedDateTime => printl(v)
        e:Gap => printl"gap"
        e:Ambiguous => printl"ambiguous"
        e:ParseError => printl"parse"
        e:UnknownZone => printl"unknown"
        e:MissingContext => printl"missing"
        e:OutsideCoverage => printl"coverage"
        e:InvalidFields => printl"fields"
        <OffGrid> => printl"grid"
    }
}
""" + '\n'.join(lines) + '\n'
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    got = ran.stdout.splitlines()
    assert len(got) == len(cases)
    for (local, zone, aware), line in zip(cases, got):
        expected = f'{local.strftime("%Y-%m-%dT%H:%M:%S")}{offset_text(aware)}[{zone}]'
        assert line == expected, (local, zone)


@same_rules
def test_every_transition_near_now(compiler, tmp_path):
    """Walk New York, Dublin, Lord Howe and Apia hour by hour through a year: gaps and folds included."""
    lines = []
    expected = []
    for zone in ['America/New_York', 'Europe/Dublin', 'Australia/Lord_Howe', 'Pacific/Apia', 'America/Sao_Paulo']:
        info = ZoneInfo(zone)
        local = dt.datetime(2026, 1, 1, 0, 30)
        for _ in range(0, 366 * 24, 7):
            text = local.strftime('%Y-%m-%dT%H:%M')
            lines.append(f'show("{text}" "{zone}")')
            first, second = local.replace(tzinfo=info, fold=0), local.replace(tzinfo=info, fold=1)
            if first.utcoffset() == second.utcoffset():
                expected.append(f'{local.strftime("%Y-%m-%dT%H:%M:%S")}{offset_text(first)}[{zone}]')
            elif first.utcoffset() > second.utcoffset():
                expected.append('ambiguous')
            else:
                expected.append('gap')
            local += dt.timedelta(hours=7)
    source = """show = (text:string name:string) => {
    let z = zone(name) ?? zone"UTC"
    match zoned(text zone=z) {
        v:ZonedDateTime => printl(v)
        e:Gap => printl"gap"
        e:Ambiguous => printl"ambiguous"
        e:ParseError => printl"parse"
        e:UnknownZone => printl"unknown"
        e:MissingContext => printl"missing"
        e:OutsideCoverage => printl"coverage"
        e:InvalidFields => printl"fields"
        <OffGrid> => printl"grid"
    }
}
""" + '\n'.join(lines) + '\n'
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == expected


GAPS = [('2026-03-08T02:30', 'America/New_York'), ('2026-03-29T01:30', 'Europe/London'),
        ('2026-10-04T02:15', 'Australia/Lord_Howe')]
FOLDS = [('2026-11-01T01:30', 'America/New_York'), ('2026-10-25T01:30', 'Europe/London'),
         ('2026-04-05T01:45', 'Australia/Lord_Howe')]


def test_gaps_and_folds_under_policies(compiler, tmp_path):
    lines = []
    expected = []
    for text, zone in GAPS:
        info = ZoneInfo(zone)
        local = dt.datetime.fromisoformat(text)
        before = local.replace(tzinfo=info, fold=0)
        # fold=0 in a gap reads with the offset before it: PEP 495's "displacement".
        moved = before.astimezone(dt.timezone.utc).astimezone(info)
        lines.append(f'printl(zoned("{text}" zone=zone"{zone}" gap=\'preserve_displacement\'))')
        expected.append(f'{moved.strftime("%Y-%m-%dT%H:%M:%S")}{offset_text(moved)}[{zone}]')
    for text, zone in FOLDS:
        info = ZoneInfo(zone)
        local = dt.datetime.fromisoformat(text)
        for name, fold in (('earlier', 0), ('later', 1)):
            aware = local.replace(tzinfo=info, fold=fold)
            lines.append(f'printl(zoned("{text}" zone=zone"{zone}" fold=\'{name}\'))')
            expected.append(f'{local.strftime("%Y-%m-%dT%H:%M:%S")}{offset_text(aware)}[{zone}]')
    ran = run(compiler, tmp_path, '\n'.join(lines) + '\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == expected


def test_literal_errors_name_the_policy(compiler, tmp_path):
    for expression, message in [
            ('zoned"2026-03-08T02:30[America/New_York]"', "gap='preserve_displacement'"),
            ('zoned"2026-11-01T01:30[America/New_York]"', "fold='earlier'"),
            ('zoned"2026-07-01T12:00"', 'a literal cannot assume'),
            ('zone"Mars/Olympus"', 'no time zone is called Mars/Olympus'),
            ('zoned"2026-07-01T12:00+09:00[America/New_York]"', 'was not at +09:00'),
    ]:
        ran = run(compiler, tmp_path, f'printl({expression})\n')
        assert ran.returncode != 0, expression
        assert message in ran.stderr, (expression, ran.stderr)
    ran = run(compiler, tmp_path, "$time.zone = 'system'\nprintl(zoned\"2026-07-01T12:00\")\n")
    assert ran.returncode != 0
    assert 'a literal cannot assume' in ran.stderr


def test_scope_settings(compiler, tmp_path):
    source = """$time.zone = 'America/New_York'
f = () => {
    # lexical gap and fold policies
    $time.gap = 'next'
    $time.fold = 'later'
    printl(zoned"2026-07-01T12:00")
    printl(zoned"2026-03-08T02:30")
    printl(zoned"2026-11-01T01:30")
    let z = zoned"2026-03-07T02:30"
    let step = z + 1day
    printl(step)
    printl(step.nominal)
}
g = () => {
    printl(zoned("2026-07-01T12:00" zone=zone"Asia/Tokyo"))
}
f
g
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == [
        '2026-07-01T12:00:00-04:00[America/New_York]',
        '2026-03-08T03:00:00-04:00[America/New_York]', '2026-11-01T01:30:00-05:00[America/New_York]',
        '2026-03-08T03:00:00-04:00[America/New_York]', '2026-03-08T07:00:00Z',
        '2026-07-01T12:00:00+09:00[Asia/Tokyo]']


PIN = "$time.zone = 'Asia/Tokyo'\n"


def test_main_file_zone_reaches_every_module(compiler, tmp_path):
    (tmp_path / 'other.dewy').write_text('shown = () => "{zoned"2026-07-01T12:00"}"\n')
    ran = run(compiler, tmp_path, PIN + 'import p"other.dewy" as other\nprintl(other.shown)\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '2026-07-01T12:00:00+09:00[Asia/Tokyo]\n'


def test_main_file_zone_cannot_be_overridden(compiler, tmp_path):
    # An inner scope that is reached, and one that is not.
    for body in ("f = () => {\n    $time.zone = 'America/New_York'\n    printl(today)\n}\nf\n",
                 "f = () => {\n    $time.zone = 'America/New_York'\n    printl(today)\n}\nprintl(1)\n"):
        ran = run(compiler, tmp_path, PIN + body)
        assert ran.returncode != 0, body
        assert "`$time.zone` is program-wide" in ran.stderr
        assert 'main.dewy:3' in ran.stderr
        assert "first lines of any file's main" in ran.stderr
    (tmp_path / 'other.dewy').write_text("$time.zone = 'system'\nshown = () => 1\n")
    ran = run(compiler, tmp_path, PIN + 'import p"other.dewy" as other\nprintl(other.shown)\n')
    assert ran.returncode != 0
    assert "`$time.zone` is program-wide" in ran.stderr


def test_the_same_zone_elsewhere_is_fine(compiler, tmp_path):
    (tmp_path / 'other.dewy').write_text("shown = () => 1\nmain=()=>{\n$time.zone = 'Asia/Tokyo'\nprintl(shown)\n}\n")
    source = PIN + "import p\"other.dewy\" as other\nmain = () => {\n    $time.zone = 'Asia/Tokyo'\n    printl(other.shown)\n}\n"
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '1\n'


def test_a_stopwatch_links_no_zone_data(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    source.write_text('let start = now\nprintl"{now - start <? 5s}"\n')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'main'], capture_output=True, timeout=300,
                           check=False, cwd=tmp_path)
    assert built.returncode == 0, built.stderr
    assert b'America/New_York' not in (tmp_path / 'main').read_bytes()
    assert subprocess.run([tmp_path / 'main'], capture_output=True, text=True, check=False).stdout == 'true\n'


def test_a_folded_literal_links_no_zone_data(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    source.write_text('const m = zoned"2026-10-26T09:00[America/New_York]"\nprintl"{m.nominal} {m.offset}"\n')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'main'], capture_output=True, timeout=300,
                           check=False, cwd=tmp_path)
    assert built.returncode == 0, built.stderr
    assert b'America/New_York' not in (tmp_path / 'main').read_bytes()
    ran = subprocess.run([tmp_path / 'main'], capture_output=True, text=True, check=False)
    assert ran.stdout == '2026-10-26T13:00:00Z -14400\n'


def test_pack_covers_every_name_python_knows(compiler, tmp_path):
    names = sorted(n for n in available_timezones() if '/' in n and not n.startswith(('posix/', 'right/')))
    if have_rules_version() != pack_version():
        pytest.skip('the host has other rules than the pack')
    table = ' '.join(f'"{n}"' for n in names)
    source = f"""let missing = 0
loop name in [{table}] {{
    if zone(name) is? UnknownZone {{
        printl(name)
        missing += 1
    }}
}}
printl(missing)
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines()[-1] == '0', ran.stdout
