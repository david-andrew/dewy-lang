"""A call's argument snapshot ends with that call, not with the statement."""
import os
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

SOURCE = ROOT / 'tests' / 'cases' / 'argument' / 'snapshot_released_after_call.dewy'


@pytest.mark.parametrize('release', [False, True])
def test_mutating_call_after_snapshot_does_not_copy(compiler, tmp_path, release):
    # 3000 nodes of 40 bytes: a detaching push would copy arrays over 64 KB,
    # which SLOPPY_COPIES reports (the old behavior copied on every push).
    source = tmp_path / 'program.dewy'
    source.write_text(SOURCE.read_text()
                      .replace('bytes("abc")', 'bytes("a" * 3000)')
                      .replace('[0..3)', '[0..3000)')
                      .replace('p.nodes[3]', 'p.nodes[3000]'))
    binary = tmp_path / 'program'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], env={**os.environ, 'SLOPPY_COPIES': '1'},
                         capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '3001\na\n'
    assert 'copied an array' not in ran.stderr
