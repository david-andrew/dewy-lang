"""Headless validation of nested shader input and output record layout."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.core_glsl_driver import DriverUnavailable, ShaderDriver
from tests.support import compiler  # noqa: F401


SOURCE = Path(__file__).parent / 'fixtures/coverlayout_shader/record_io.dewy'


def test_shader_record_io(compiler, tmp_path):
    env = dict(os.environ, DISPLAY='', WAYLAND_DISPLAY='', DEWY_NO_AUDIO='1')
    binary = tmp_path / 'shader'
    built = subprocess.run([compiler, 'build', SOURCE, '-o', binary], env=env,
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], env=env, cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    try:
        driver = ShaderDriver()
    except DriverUnavailable as error:
        pytest.skip(str(error))
    try:
        driver.validate((tmp_path / 'record.vert').read_text(),
                        (tmp_path / 'record.frag').read_text())
    finally:
        driver.close()
