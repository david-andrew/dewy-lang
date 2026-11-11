"""The --host-ir dump (each lowered function's header, value types, constants, slots, arguments and
instructions) agrees with frozen Jo: the same text, exit codes and messages."""
import platform
import sys

import pytest

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'amd64'),
    reason='--host-ir is a Linux x86-64 build')

PROGRAM = '''$runtime_checks

f=(xs:array<int64> k:int64):>int64=>{
    let total=0
    loop x in xs {total += x * k}
    total
}
main=()=>{
    let m:dict<string int64>=[]
    m["a"]=f([1 2 3] 4)
    printl("{m} {2.5 * 3.0}")
}
'''


def test_driver_host_ir_matches_twin(compiler, tmp_path, monkeypatch):
    (tmp_path / 'host.dewy').write_text(PROGRAM)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('driver_cli',),
                             ['host.dewy', 'examples/ring.dewy'], flags=(('--host-ir',),))
    assert all(r[2] == 0 and r[3].startswith('DEWY_HOST_IR 1\n') and '\nKV [' in r[3] for r in results)
