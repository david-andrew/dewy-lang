"""A read-only single-place parameter can lend a checked local view."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = ['''read=(@xs:array<int64>):>int64=>{const saved=@xs return saved.length}
main=():>int64=>{let xs:array<int64>=[20 22] return read(@xs)+40}''',
'''length=(@xs:array<int64>):>int64=>xs.length
read=(@xs:array<int64>):>int64=>{const saved=@xs return saved.length+length(@xs)}
main=():>int64=>{let xs:array<int64>=[20 22] return read(@xs)+38}''']
ERRORS = ['''let xs:array<int64>=[42]
change=():>void=>{xs.clear}
read=(@values:array<int64>):>int64=>{const saved=@values change() return saved.length}
main=():>int64=>read(@xs)''',
'''read=(@xs:array<int64> @ys:array<int64>):>int64=>{const saved=@xs ys.clear return saved.length}
main=():>int64=>{let xs:array<int64>=[42] let ys:array<int64>=[42] return read(@xs @ys)}''',
'''let values:array<int64>=[42]
change=():>void=>{values.clear}
read=(@xs:array<int64> f:():>void):>int64=>{const saved=@xs f() return saved.length}
main=():>int64=>read(@values @change)''']

@pytest.mark.parametrize('source', CASES)
def test_place_parameter_view(tmp_path, source):
    execute(tmp_path, 'place-view', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_place_parameter_view_conflicts(source):
    with pytest.raises(ReportException, match='required local view'):
        codegen(SrcFile(None, source), debug_locations=False)

def test_native_place_parameter_views(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
