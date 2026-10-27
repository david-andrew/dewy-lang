"""Allocation effects follow finite local representations and ABI escapes."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']])
def test_finite_exact_locals_do_not_allocate(compiler, tmp_path, flags):
    source = tmp_path / 'finite.dewy'
    source.write_text('''$runtime_checks
near=(a:int64 b:int64):>bool & no_effects=>{
 let x=a-b let y=a+b
 return x*x <=? y*y
}
mask=(a:int64 b:int64):>bool & no_effects=>{
 let x=not(a-1)
 let y=x and b
 return y =? x
}
main=(args:array<string>)=>{
 let a=int64(to_int(args[1]) ?? 0) let b=int64(to_int(args[2]) ?? 0)
 printl(near(a b) mask(a b))
}
''')
    binary = tmp_path / 'finite'
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    for a, b in [(0, 0), (2**63-1, 1), (-2**63, -1), (-2**63, -2**63), (2**63-1, -2**63)]:
        ran = subprocess.run([binary, str(a), str(b)], capture_output=True, text=True)
        x = ~(a-1)
        expected = f'{str((a-b)**2 <= (a+b)**2).lower()} {str((x & b) == x).lower()}\n'
        assert ran.returncode == 0 and ran.stdout == expected, ran.stdout + ran.stderr


def test_finite_local_escape_still_reports_allocation(compiler, tmp_path):
    source = tmp_path / 'escape.dewy'
    source.write_text('''$runtime_checks
escape=(a:int64):>int & no_effects=>{let x=a+1 return x}
main=()=>printl(escape(9223372036854775807))
''')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert checked.returncode != 0 and 'allocation' in checked.stderr, checked.stderr


def test_narrowed_operand_still_reports_allocation(compiler, tmp_path):
    source = tmp_path / 'hidden.dewy'
    source.write_text('''$runtime_checks
hidden=(a:int b:int):>bool & no allocates=>{
 let x=int64(a+b)+1
 return x =? 0
}
main=()=>printl(hidden(1 2))
''')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert checked.returncode != 0 and 'allocation' in checked.stderr, checked.stderr
