"""A `get` bound to a read-only local views the stored element; writes keep copies."""
from pathlib import Path

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/get_views.dewy'


def test_get_views(tmp_path):
    source = SrcFile.from_path(FIXTURE)
    code = codegen(source, debug_locations=False)
    lines = source.body.splitlines()
    rows = {source.offset_to_row_col(note.loc.start)[0] + 1 for note in lower.last_copy_notes
            if note.srcfile.path == source.path and note.site == 'looked up with get'}
    expected = {index + 1 for index, line in enumerate(lines)
                if 'let before=d.get' in line or 'let found=d.get(k)' in line and 'first' in lines[index + 1]
                or "found=d.get('beta')" in line}
    assert rows == expected, (rows, expected)
    execute(tmp_path, 'get-views', code)


def test_native_get_views(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[FIXTURE.read_text()], errors=[])
