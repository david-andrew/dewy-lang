"""Copy policy belongs to the defining source module, including imports."""
import os
from pathlib import Path
import subprocess

import pytest

# (programs that keep runtime checks for their unproven obligations)
RUNTIME_CHECKS = '\n$runtime_checks\n'


@pytest.fixture(scope='module')
def compiler():
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER')
    return Path(value)


def test_imported_strict_body_is_checked(compiler, tmp_path):
    (tmp_path / 'strict.dewy').write_text('''$explicit_copies
bad=():>int64=>{
    let a:array<int64>=[42]
    let b=a
    b[0]=0
    return a[0]
}
''')
    source = tmp_path / 'main.dewy'
    source.write_text('import p"strict.dewy" as strict\nmain=():>void=>exit(entry()) entry=()=>0\n')
    for action in ('check', 'build'):
        args = [compiler, action, source]
        if action == 'build':
            args += ['-o', tmp_path / 'program']
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        assert result.returncode != 0
        assert 'strict.dewy:4:' in result.stderr
        assert 'implicit costly copy' in result.stderr


@pytest.mark.parametrize('strict_caller', [True, False])
def test_module_local_policy_and_owned_call(compiler, tmp_path, strict_caller):
    if strict_caller:
        library = '''change=(values:array<int64>):>int64=>{values[0]=99 return values[0]}
'''
        directive = '$explicit_copies\n'
    else:
        library = '''$explicit_copies
change=(values:array<int64>):>int64=>{values[0]=99 return values[0]}
'''
        directive = ''
    (tmp_path / 'library.dewy').write_text(library + RUNTIME_CHECKS)
    source = tmp_path / 'main.dewy'
    source.write_text((directive + '''import p"library.dewy" as library
main=():>void=>exit(entry()) entry=():>int64=>{
    let xs:array<int64>=[42]
    $runtime_assert library.change(xs)=?99
    $runtime_assert xs[0]=?42
    return 0
}
''') + RUNTIME_CHECKS)
    program = tmp_path / 'program'
    result = subprocess.run([compiler, 'build', source, '-o', program],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run([program], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
