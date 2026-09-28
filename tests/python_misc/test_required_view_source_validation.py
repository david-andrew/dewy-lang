"""Required storage views are source contracts, including in unused functions."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PREFIX = 'Box:type=[value:int64]\n'
BODIES = [
    'const view=@rows[0] rows.clear return view.value',
    'const view=@rows[0] const alias=@view rows.clear return alias.value',
    'const view=@rows[0] rows[0].value=99 return view.value',
    'const view=@rows[0] change(@rows) return view.value',
    'const view=@rows[0] let raw=rows transmute int64 return view.value',
]


def source(body, *, live=False):
    return (PREFIX + 'change=(@rows:array<Box>):>void=>{rows.clear}\n'
            'read=():>int64=>{let rows:array<Box>=[Box[42]] ' + body + '}\n'
            'main=():>int64=>' + ('read()' if live else '42'))


ERRORS = [source(body, live=live) for body in BODIES for live in (False, True)]
CASES = [source(body, live=live) for body in [
    'const view=@rows[0] return view.value',
    'const view=@rows[0] let answer=view.value rows.clear return answer',
    'const view=@rows[0] const alias=@view let answer=alias.value rows.clear return answer',
] for live in (False, True)]


@pytest.mark.parametrize('program', ERRORS)
def test_required_view_checked_in_every_function(program):
    with pytest.raises(ReportException, match='required local view'):
        codegen(SrcFile(None, program), debug_locations=False)


@pytest.mark.parametrize('program', CASES)
def test_valid_required_views_preserve_reachability(tmp_path, program):
    execute(tmp_path, 'view-source', codegen(SrcFile(None, program), debug_locations=False))


def test_native_required_view_source_contracts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)


def test_native_unused_import_view_diagnostic(tmp_path):
    from test_bootstrap_structural_text import build_program_driver
    from test_bootstrap_lowering import ROOT
    module = tmp_path / 'views.dewy'
    module.write_text(source(BODIES[0]))
    entry = tmp_path / 'entry.dewy'
    entry.write_text('import p"views.dewy" as views\nmain=():>int64=>42')
    with pytest.raises(ReportException, match='required local view'):
        codegen(SrcFile.from_path(entry), debug_locations=False)
    result = subprocess.run([build_program_driver(tmp_path), entry, ROOT / 'library',
                             tmp_path / 'prelude'], capture_output=True, text=True, timeout=120)
    assert result.returncode == 1, result.stderr
    assert 'cannot prove required local view' in result.stderr
    assert str(module) in result.stderr
    assert 'rows.clear' in result.stderr
