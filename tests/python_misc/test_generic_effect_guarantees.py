"""Generic row substitutions retain guarantees without inventing absences."""
from pathlib import Path
import pytest
from dewy.semantic import effect_rows as rows
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'
FS = rows.Atom('reads', rows.Subject('resource', 'Filesystem'))
NO_FS = rows.Contract(excluded=(FS,))
E = rows.Contract(rows.Row(variables=('E',)))


def test_generic_guarantee_requires_every_contributing_callback():
    bindings = {}
    assert rows.infer(E, NO_FS, {'E'}, bindings)
    assert rows.implies(rows.replace_contracts(E, bindings), NO_FS)
    assert rows.infer(E, rows.Contract(rows.Row()), {'E'}, bindings)
    assert rows.implies(rows.replace_contracts(E, bindings), NO_FS)
    assert rows.infer(E, None, {'E'}, bindings)
    assert not rows.implies(rows.replace_contracts(E, bindings), NO_FS)


def test_added_permission_can_invalidate_a_substituted_exclusion():
    with_read = rows.Contract(rows.Row((FS,), ('E',)))
    assert not rows.implies(rows.replace_contracts(with_read, {'E': NO_FS}), NO_FS)
    explicit = rows.Contract(with_read.allowed, (FS,))
    assert rows.implies(rows.replace_contracts(explicit, {'E': NO_FS}), NO_FS)


def test_callback_relative_exclusion_does_not_escape_its_scope():
    private = rows.Atom('reads', rows.Subject('parameter', '0'))
    assert not rows.infer(E, rows.Contract(excluded=(private,)), {'E'}, {})


def test_generic_negative_rows_execute(tmp_path):
    execute(tmp_path, 'generic-guarantees', codegen(SrcFile.from_path(FIXTURES / 'generic_effect_guarantees.dewy')))


def test_unknown_callback_invalidates_generic_guarantee():
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile.from_path(FIXTURES / 'generic_effect_guarantees_rejected.dewy'))


def test_native_generic_negative_rows(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[(FIXTURES / 'generic_effect_guarantees.dewy').read_text()],
                          errors=[(FIXTURES / 'generic_effect_guarantees_rejected.dewy').read_text()])


def test_native_cached_generic_guarantees(tmp_path):
    import os
    import subprocess
    from test_bootstrap_structural_text import build_program_driver
    driver = build_program_driver(tmp_path)
    root = Path(__file__).resolve().parents[2]
    declarations, body = (FIXTURES / 'generic_effect_guarantees.dewy').read_text().split('main=', 1)
    extra = tmp_path / 'effect-prelude.dewy'
    extra.write_text(declarations)
    source = tmp_path / 'entry.dewy'
    source.write_text('main=' + body)
    emitted = []
    for expected in ('miss', 'hit'):
        result = subprocess.run([driver, source, root / 'library', tmp_path / 'cache', extra],
                                env=os.environ | {'DEWY_TEST_PRELUDE_CACHE': expected},
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        execute(tmp_path, 'cached-generic-' + expected, result.stdout)
        emitted.append(result.stdout)
    assert emitted[0] == emitted[1]
