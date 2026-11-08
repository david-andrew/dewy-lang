"""Rounding accepts its decided vocabulary, without compatibility spellings."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401

@pytest.mark.parametrize('expression', ["round(x ties='even')", "round(x rounding='even')", "round(x rounding='away')"])
def test_batch4_rounding_rejects_old_forms(compiler, tmp_path, expression):
    source=tmp_path/'old.dewy'
    source.write_text('let x:float64=2.5\nprintl('+expression+')\n')
    result=subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    assert result.returncode != 0, result.stdout+result.stderr


def test_batch4_rounding_time_uses_all_modes(compiler, tmp_path):
    modes=['nearest_away', 'nearest_even', 'nearest_toward_zero', 'nearest_up', 'nearest_down', 'floor', 'ceil', 'toward_zero', 'away_from_zero']
    values=['9*1ns/4', '0ns-9*1ns/4', '5*1ns/2', '0ns-5*1ns/2', '11*1ns/4', '0ns-11*1ns/4', '7*1ns/2', '0ns-7*1ns/2']
    rows=[[2,-2,3,-3,3,-3,4,-4], [2,-2,2,-2,3,-3,4,-4],
          [2,-2,2,-2,3,-3,3,-3], [2,-2,3,-2,3,-3,4,-3],
          [2,-2,2,-3,3,-3,3,-4], [2,-3,2,-3,2,-3,3,-4],
          [3,-2,3,-2,3,-2,4,-3], [2,-2,2,-2,2,-2,3,-3],
          [3,-3,3,-3,3,-3,4,-4]]
    text='import p"@lib/time/core.dewy" as core\n$runtime_checks\nshow=(q:rational*Time mode:core._Rounding)=>{\nlet [value lost]=quantize(q rounding=mode)\nprintl(core.ns_count(value))\n}\n'
    for mode in modes:
        for value in values:
            text+=f"show(({value}) '{mode}')\n"
    source=tmp_path/'time.dewy'
    source.write_text(text)
    result=subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60)
    assert result.returncode==0, result.stderr
    assert [int(x) for x in result.stdout.splitlines()]==[x for row in rows for x in row]
