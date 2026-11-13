"""Prelude reductions check plain fixed-width storage and preserve explicit policies."""
import subprocess
import pytest
from tests.support import compiler

@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('kind,maximum', [('int64', 2**63-1), ('uint64', 2**64-1)])
def test_sum_storage_boundary(compiler, tmp_path, release, kind, maximum):
    source = tmp_path / 'sum.dewy'
    source.write_text(('$runtime_checks\n\n') + (f'''main=(args:array<string>)=>{{
let a={kind}(to_int(args[1]) ?? 0)
printl([a {kind}(1)].sum())
}}
'''))
    binary = tmp_path / 'sum'
    built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    safe = subprocess.run([binary, str(maximum-1)], capture_output=True, text=True)
    assert safe.returncode == 0 and safe.stdout.strip() == str(maximum), safe.stderr
    overflow = subprocess.run([binary, str(maximum)], capture_output=True, text=True)
    assert overflow.returncode != 0 and not overflow.stdout

def test_sum_overflow_is_a_panic_effect(compiler, tmp_path):
    source = tmp_path / 'effect.dewy'
    source.write_text('f=(xs:array<int64>):>int64 & no panics=>xs.sum()\nmain=()=>printl(f([1 2]))\n')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert checked.returncode != 0 and 'panic' in checked.stderr, checked.stderr
