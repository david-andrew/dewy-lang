"""A literal regex is checked while compiling, never made there: its value holds arrays, so it is
no plain record and the call stays a call (compiling the nested repeat once took 18 GB)."""
import resource
import subprocess
import sys

import pytest

from tests.support import ROOT, compiler

SOURCE = '''$runtime_checks

main=()=>{
    printl("aaab".find(regex(r"(?:a{100}){100}|b")))
}
'''

CEILING = 256 << 20


def _limit():
    resource.setrlimit(resource.RLIMIT_AS, (CEILING, CEILING))


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='address-space limits are enforced on Linux')
def test_literal_regex_is_not_built_while_compiling(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    path = tmp_path / 'nested_regex.dewy'
    path.write_text(SOURCE)
    binary = tmp_path / 'nested_regex'
    built = subprocess.run([compiler, 'build', path, '-o', binary], capture_output=True, text=True,
                           timeout=120, check=False, preexec_fn=_limit)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=60, check=False)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['[start=3 end=4 text="b" groups=[]]']


def test_literal_regex_error_is_still_a_compile_error(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    path = tmp_path / 'bad_regex.dewy'
    path.write_text('$runtime_checks\n\nmain=()=>{\n    printl("a".find(regex(r"(a")))\n}\n')
    built = subprocess.run([compiler, 'build', path, '-o', tmp_path / 'bad_regex'], capture_output=True,
                           text=True, timeout=120, check=False)
    assert built.returncode != 0
    assert 'not a valid pattern' in built.stdout + built.stderr
