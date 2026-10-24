"""Windows batch files: cmd.exe re-parses their command lines, so run refuses them."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

DETECTOR = '''
main = ():
    loop a in args()[1..]: print(__w32_batch_program(a))
'''

BATCH = ['x.bat', 'X.CMD', 'x.bat ', 'x.bat. .', 'C:\\dir\\x.Bat', 'C:x.bat', 'x.bat::$DATA',
         '/a/b.cmd', '.bat']
NOT_BATCH = ['prog.exe', 'prog', 'dir.bat\\prog.exe', 'a.bat.exe', 'x.cmdx', 'bat', 'C:\\tools\\cmd.exe']

RUNNER = '''main=()=>{
    let status=run(args()[1] ["a&echo injected>marker.txt"])
    if status is? SpawnError { printl"refused" } else { printl"ran" }
}
'''


@pytest.mark.core_quick
def test_batch_programs_detected(compiler, tmp_path):
    source = tmp_path / 'detector.jo'
    source.write_text(DETECTOR)
    binary = tmp_path / 'detector'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary, *BATCH, *NOT_BATCH], capture_output=True, text=True, timeout=30, check=False)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.split() == ['true'] * len(BATCH) + ['false'] * len(NOT_BATCH)


def test_windows_runner_builds(compiler, tmp_path):
    source = tmp_path / 'runner.dewy'
    source.write_text(RUNNER)
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'runner.exe', '--target', 'x86_64-windows'],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr


@pytest.mark.skipif(os.name != 'nt', reason='only Windows runs batch files through cmd.exe')
def test_windows_run_refuses_batch(compiler, tmp_path):
    source = tmp_path / 'runner.dewy'
    source.write_text(RUNNER)
    binary = tmp_path / 'runner.exe'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    script = tmp_path / 'echo.bat'
    script.write_text('@echo %1\r\n')
    ran = subprocess.run([binary, str(script)], cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip() == 'refused'
    assert 'batch file' in ran.stderr and 'cmd.exe' in ran.stderr
    assert not (tmp_path / 'marker.txt').exists()
