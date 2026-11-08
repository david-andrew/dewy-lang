"""Date ranges count discrete days, and projections must preserve their range."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=120)


def test_open_date_ranges_count_successors(compiler, tmp_path):
    result = run(compiler, tmp_path, '''from p"@lib/time/civil.dewy" import (Date)
main=()=>{
    let a=date"2026-11-07"
    let b=date"2026-11-08"
    let c=date"2026-11-09"
    printl((a..b).is_empty)
    printl([a..b).is_empty)
    printl((a..b].is_empty)
    printl([a..b].is_empty)
    printl((a..c).is_empty)
    printl((a..a).is_empty)
    printl([a..a].is_empty)
    printl([b..a].is_empty)
    let low:Date=Date[-9223372036854775808]
    let high:Date=Date[9223372036854775807]
    printl((low..high).is_empty)
}
''')
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        'true', 'false', 'false', 'false', 'false', 'true', 'false', 'true', 'false',
    ]


@pytest.mark.parametrize('day', [-9223372036854775809, 9223372036854775808])
def test_out_of_range_date_fails_instead_of_becoming_epoch(compiler, tmp_path, day):
    result = run(compiler, tmp_path, f'''from p"@lib/time/civil.dewy" import (_of_days)
project=(n:int)=>_of_days(n)
main=()=>printl(project({day})._days)
''')
    assert result.returncode != 0
    assert 'date is outside the int64 day range' in result.stderr
    assert result.stdout == ''


def test_date_projection_keeps_boundary_days(compiler, tmp_path):
    result = run(compiler, tmp_path, '''from p"@lib/time/civil.dewy" import (_of_days)
main=()=>{
    printl(_of_days(-9223372036854775808)._days)
    printl(_of_days(9223372036854775807)._days)
    printl(_of_days(0)._days)
}
''')
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['-9223372036854775808', '9223372036854775807', '0']


@pytest.mark.parametrize('count', [-(1 << 127), (1 << 127) - 1])
def test_zoned_date_projection_reports_its_smaller_range(compiler, tmp_path, count):
    result = run(compiler, tmp_path, f'''import p"@lib/time/core.dewy" as core
main=()=>{{
    let t=core.instant_at({count})
    printl(t.in_zone(zone"UTC").date)
}}
''')
    assert result.returncode != 0
    assert 'date is outside the int64 day range' in result.stderr
    assert result.stdout == ''
