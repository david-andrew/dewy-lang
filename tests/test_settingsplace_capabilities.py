"""Deferred setting capabilities reject use instead of installing partial frames."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('name,value', [
    ('time.zone_source', "'host'"),
])
@pytest.mark.parametrize('scope', ['function', 'block', 'imported_main'])
def test_zone_source_scopes_are_supported(compiler, tmp_path, name, value, scope):
    body = f'${name}={value}\nprintl(42)\n'
    source = tmp_path / 'app.dewy'
    if scope == 'function':
        source.write_text('work=()=>{\n'+body+'}\nmain=()=>work()\n')
    elif scope == 'block':
        source.write_text('main=()=>{\n{\n'+body+'}\n}\n')
    else:
        (tmp_path / 'lib.dewy').write_text('main=()=>{\n'+body+'}\n')
        source.write_text('import p"lib.dewy" as lib\nmain=()=>lib.main()\n')
    result = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0,result.stderr
    result = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0,result.stderr
    assert result.stdout == '42\n'


@pytest.mark.parametrize('name,kind,value', [
    ('time.rules', 'string', "'missing.bin'"),
])
def test_dynamic_entry_values_are_not_ignored(compiler, tmp_path, name, kind, value):
    source = tmp_path / 'app.dewy'
    source.write_text(f'choose=():>{kind}=>{value}\nmain=()=>{{\n${name}=choose\nprintl(42)\n}}\n')
    result = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert 'run-time rule-pack paths are not yet supported' in result.stderr


def test_time_frames_do_not_bypass_the_legacy_entry_core_cap(compiler, tmp_path):
    import sys
    if not sys.platform.startswith('linux'):
        pytest.skip('counts threads through /proc')
    from tests.test_program_max_cores import THREADS, threads
    source = tmp_path / 'app.dewy'
    source.write_text('$program.max_cores=2\n' + THREADS.replace('main=():>void=>{', "main=():>void=>{\n$time.zone='UTC'"))
    result = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=90)
    assert threads(result) == 2
