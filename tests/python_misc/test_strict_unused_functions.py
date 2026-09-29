"""Dead-code removal must not bypass a module's strict-copy obligations."""
from pathlib import Path
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/strict_unused_function.dewy').read_text()
ERRORS = [SOURCE]
CONSUMING = [
    '''$explicit_copies
unused=(values:array<int64>):>array<int64>=>values
main=():>int64=>42''',
    '''$explicit_copies
unused=(value:array<int64>|bool):>array<int64>|bool|none=>value
helper=():>int64=>42
main=():>int64=>helper()''',
]
UNUSED = '''$explicit_copies
unused=():>int64=>153276824
main=():>int64=>42'''
CALLBACK = '''$explicit_copies
increment=(value:int64):>int64=>value+1
decrement=(value:int64):>int64=>value-1
const handlers=[@increment @decrement]
unused=():>int64=>153276824
main=():>int64=>handlers[0](41)'''
RECURSIVE = '''$explicit_copies
even=(n:int64):>bool=>if n=?0 true else odd(n-1)
odd=(n:int64):>bool=>if n=?0 false else even(n-1)
unused=():>int64=>153276824
main=():>int64=>if even(8) and odd(7) 42 else 1'''
CASES = [UNUSED, CALLBACK, RECURSIVE, *CONSUMING,
         SOURCE.replace('$explicit_copies', ''),
         SOURCE.replace('let saved=value return value',
                        'let saved=value.copy() return value.copy()')]


def test_native_strict_parser_report(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    source = (ROOT/'tests/fixtures/parser_token_report.dewy').read_text().replace(
        '../../dewy/bootstrap/parser/cli.dewy', str(ROOT/'dewy/bootstrap/parser/cli.dewy'))
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[source], errors=[])

@pytest.mark.parametrize('source', ERRORS)
def test_unused_strict_body_still_requires_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)

@pytest.mark.parametrize('source', CASES)
def test_unused_valid_body(tmp_path, source):
    execute(tmp_path, 'unused-body', codegen(SrcFile(None, source), debug_locations=False))


def test_native_unused_strict_bodies(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    driver = build_program_driver(tmp_path)
    check_structural_text(driver, tmp_path, cases=CASES, errors=ERRORS)
    for index, source in enumerate((UNUSED, CALLBACK, RECURSIVE)):
        path = tmp_path / f'pruned-{index}.dewy'
        path.write_text(source)
        result = subprocess.run([driver, path, ROOT/'library', tmp_path/'pruning-cache'],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stderr
        assert '153276824' not in result.stdout  # Checked, then omitted from runtime code.


def test_imported_unused_strict_function(tmp_path):
    from test_bootstrap_structural_text import build_program_driver
    strict = tmp_path / 'strict.dewy'
    strict.write_text(SOURCE.replace('main=():>int64=>42', ''))
    path = tmp_path / 'main.dewy'
    path.write_text('import p"strict.dewy" as unused\nmain=():>int64=>42')
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile.from_path(path), debug_locations=False)
    result = subprocess.run([build_program_driver(tmp_path), path, ROOT/'library', tmp_path/'cache'],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 1 and 'unproven copy' in result.stderr, result.stderr
    assert 'strict.dewy' in result.stderr


@pytest.mark.parametrize('explicit', [False, True])
def test_unused_strict_body_keeps_imported_dependencies(tmp_path, explicit):
    from test_bootstrap_structural_text import build_program_driver
    (tmp_path / 'ordinary.dewy').write_text(
        'mutate=(values:array<int64>):>void=>{values.push(99)}')
    strict = tmp_path / 'strict.dewy'
    strict.write_text('$explicit_copies\nimport p"ordinary.dewy" as ordinary\n'
                      'unused=(values:array<int64>):>int64=>{'
                      'ordinary.mutate(values' + ('.copy()' if explicit else '') + ')\n'
                      'return if values.length=?0 0 else values[0]}')
    path = tmp_path / 'main.dewy'
    path.write_text('import p"strict.dewy" as unused\nmain=():>int64=>42')
    if explicit:
        execute(tmp_path, 'explicit-dependency', codegen(SrcFile.from_path(path), debug_locations=False))
    else:
        with pytest.raises(ReportException, match='unproven copy') as error:
            codegen(SrcFile.from_path(path), debug_locations=False)
        assert 'strict.dewy' in str(error.value)
    result = subprocess.run([build_program_driver(tmp_path), path, ROOT/'library', tmp_path/'cache'],
                            capture_output=True, text=True, timeout=120)
    if explicit:
        assert result.returncode == 0, result.stderr
        execute(tmp_path, 'native-explicit-dependency', result.stdout)
    else:
        assert result.returncode == 1 and 'unproven copy' in result.stderr, result.stderr
        assert 'strict.dewy' in result.stderr
