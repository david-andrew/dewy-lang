"""Pure parser builders preserve node/list bytes, intern order and failure positions."""
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/dewy_builders_jo.jo'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_dewy_builders_match_jo(compiler, tmp_path, release):
    outputs = []
    for module in ('dewy_builders.dewy', 'dewy_builders.jo'):
        source = tmp_path / f'{module.replace(".", "-")}.jo'
        source.write_text(DRIVER.read_text().replace("use '../../../compiler/dewy_builders.jo'",
                                                   f"use '{ROOT / 'compiler' / module}'").replace("use '../../../", f"use '{ROOT}/"))
        binary = source.with_suffix('')
        run = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                             capture_output=True, text=True, timeout=120)
        assert run.returncode == 0, run.stdout + run.stderr
        run = subprocess.run([binary], capture_output=True, text=True, timeout=60)
        assert run.returncode == 0, run.stdout + run.stderr
        outputs.append(run.stdout)
    assert outputs[0] == outputs[1]
    lines = outputs[0].splitlines()
    assert 'map 1 2' in lines and 'map 2 3' in lines
    assert 'type bigint __dewy_int' in lines and 'type addr addr' in lines
    assert lines.count('used true') == 64
    assert sum(line.startswith('result ') for line in lines) == 64 * 8
    assert any('multiple entry-point parameters' in line for line in lines)
    assert any('a mutable entry-point parameter' in line for line in lines)
    for name in ('__shape_rank', '__shape_dim', '__shape_check', '__shape_value', '__dewy_range_tail'):
        assert f'intern {name}' in lines


@pytest.mark.core_quick
def test_selfhost_dewy_builders_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_builders.dewy\0' in binary
    assert b'/compiler/dewy_builders.jo\0' not in binary
