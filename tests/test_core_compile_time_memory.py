"""Running a library function at compile time costs memory in proportion to the work: a
literal regex is made while compiling, and writing into an array there once copied the whole
array each time and kept every copy (18 GB for the 10000 steps of (?:a{100}){100})."""
import resource
import subprocess
import sys

import pytest

from tests.support import ROOT, compiler

# (a nested repeat written out to 10000 steps, and a pattern 8000 characters long)
SOURCE = '''$runtime_checks
main=()=>{
    printl("aaab".find(regex(r"(?:a{100}){100}|b")))
    printl("x%s".find(regex(r"%s")))
}
''' % ('a' * 8000, 'a' * 8000)

CEILING = 1 << 30


def _limit():
    resource.setrlimit(resource.RLIMIT_AS, (CEILING, CEILING))


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='address-space limits are enforced on Linux')
def test_literal_regex_compiles_under_a_gigabyte(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    path = tmp_path / 'big_regex.dewy'
    path.write_text(SOURCE)
    binary = tmp_path / 'big_regex'
    built = subprocess.run([compiler, 'build', path, '-o', binary], capture_output=True, text=True,
                           timeout=120, check=False, preexec_fn=_limit)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=60, check=False)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['[start=3 end=4 text="b" groups=[]]',
                                       '[start=1 end=8001 text="%s" groups=[]]' % ('a' * 8000)]
