"""Frozen validation analyses retain cross-module and callback obligations."""
import os
import subprocess
from pathlib import Path

import pytest

from udewy.cache import cache_artifact

ROOT = Path(__file__).resolve().parents[2]
NOMINAL = 'Base=type of [token:int64]\nDerived=type of Base & [extra:int64]\n'
CASES = [
    pytest.param('helper=(@x:int64):>void=>{x=42}',
                 'main=():>int64 & no_effects=>{let x:int64=0 helper(@x) return x}',
                 None, id='private-place'),
    pytest.param('helper=(@x:int64):>void=>{x=42}',
                 'f=(@x:int64):>void & reads<x>=>helper(@x)\nmain=():>int64=>42',
                 'effect contract', id='imported-write'),
    pytest.param('helper=():>int64 & no_effects=>{printl("unused") return 42}',
                 'main=():>int64=>42', 'effect contract', id='unused-imported-contract'),
    pytest.param('leaf=(x:int64):>int64=>x+1\nhelper=(x:int64):>int64=>leaf(x)',
                 'main=():>int64 & no_effects=>helper(41)', None, id='transitive-read'),
    pytest.param('', 'f=(callback:():>int64):>int64 & no_effects=>callback()\nmain=():>int64=>42',
                 'effect contract', id='unknown-callback'),
    pytest.param('', 'answer=():>int64 & no_effects=>42\napply=(f:():>int64 & no_effects):>int64 & no_effects=>f()\nmain=():>int64=>apply(@answer)',
                 None, id='pure-callback'),
    pytest.param('', NOMINAL + 'set=(@p:Base):>void=>{p.token=40}\nupdate=(@p:Base):>void=>set(@p)\nmain=():>int64=>{let d=Derived[0 2] update(@d) return d.token+d.extra}',
                 None, id='nominal-field-update'),
    pytest.param('', NOMINAL + 'set=(@p:Base):>void=>{p=Base[0]}\nreplace=(@p:Base):>void=>set(@p)\nmain=():>int64=>{let d=Derived[42 1] replace(@d) return 42}',
                 'parent place may replace or escape the child', id='nominal-owner-replacement'),
    pytest.param('', (ROOT / 'tests/fixtures/generic_effect_guarantees.dewy').read_text(),
                 None, id='generic-guarantees'),
    pytest.param('', (ROOT / 'tests/fixtures/generic_effect_guarantees_rejected.dewy').read_text(),
                 'effect contract', id='generic-unknown-callback'),
]


@pytest.mark.parametrize(('helper', 'body', 'diagnostic'), CASES)
def test_native_validation_effects(tmp_path, helper, body, diagnostic):
    compiler = os.environ.get('DEWY_TEST_DRIVER_COMPILER')
    if not compiler:
        pytest.skip('set DEWY_TEST_DRIVER_COMPILER to the current native CLI')
    (tmp_path / 'helper.dewy').write_text(helper)
    source = tmp_path / 'main.dewy'
    source.write_text(('from p"helper.dewy" import helper\n' if helper else '') + body)
    env = os.environ | {'DEWY_LIBRARY_ROOT': str(ROOT / 'library'), 'DEWY_FAILURE_LOG': '0'}
    result = subprocess.run([compiler, '-c', source], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30, check=False)
    binary = tmp_path / cache_artifact(source, cwd=tmp_path)
    if diagnostic:
        assert result.returncode != 0 and diagnostic in result.stderr, result.stdout + result.stderr
        assert not binary.exists()
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        executed = subprocess.run([binary], capture_output=True, timeout=10, check=False)
        assert executed.returncode == 42, (executed.returncode, executed.stdout, executed.stderr)
