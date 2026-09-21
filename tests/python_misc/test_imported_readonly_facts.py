"""Imported summaries preserve borrowed facts without concealing writes."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

HELPERS = '''count=(@items:array<int64>):>int64=>items.length
clear=(@items:array<int64>):>void=>items.clear
'''
CASES = ['''import p"readonly_helpers.dewy" as helpers
main=():>int64=>{let xs:array<int64>=[42] helpers.count(@xs); return xs[0]}
''']
ERRORS = ['''import p"readonly_helpers.dewy" as helpers
main=():>int64=>{let xs:array<int64>=[42] helpers.clear(@xs) return xs[0]}
''']


def test_imported_readonly_facts(tmp_path):
    (tmp_path / 'readonly_helpers.dewy').write_text(HELPERS)
    path = tmp_path / 'main.dewy'
    path.write_text(CASES[0])
    execute(tmp_path, 'imported-readonly', codegen(SrcFile.from_path(path), debug_locations=False))
    path.write_text(ERRORS[0])
    with pytest.raises(ReportException):
        codegen(SrcFile.from_path(path))


def test_native_imported_readonly_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    (tmp_path / 'readonly_helpers.dewy').write_text(HELPERS)
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
