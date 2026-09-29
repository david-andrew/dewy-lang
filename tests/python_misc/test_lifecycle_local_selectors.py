"""Local selector identities require dominating, once-only initialization."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute
from test_lifecycle_distinct_indices import SOURCE

LOCAL = SOURCE.replace('work=(i:int64 j:int64):>void=>{',
    'work=(left:int64 right:int64):>void=>{\n    let i:int64=left\n    let j:int64=right')
CASES = [LOCAL,
    LOCAL.replace('let i:int64', 'const i:int64').replace('let j:int64', 'const j:int64'),
    LOCAL.replace('    let i:int64=left', '    if left>=?0 {\n    let i:int64=left')
         .replace('    consume(values[j])\n}', '    consume(values[j])\n}\n}'),
    LOCAL.replace('    let values=', '    left=0 right=0\n    let values='),
]
# The second selector is initialized later: introducing a read at the first
# transfer would be wrong even though its future value is source-checkable.
LATE = LOCAL.replace('    let j:int64=right', '').replace('j<?0 or j>=?values.length or i=?j', 'right<?0 or right>=?values.length or i=?right').replace('    consume(values[j])', '    let j:int64=right\n    consume(values[j])')
ERRORS = [LATE,
    LOCAL.replace(' or i=?j', ''),
    LOCAL.replace('    consume(values[j])', '    i=j\n    consume(values[j])'),
    LOCAL.replace('    let i:int64=left', '    loop turn in [0..2) {\n    let i:int64=left')
         .replace('    consume(values[j])\n}', '    consume(values[j])\n}\n}'),
]

@pytest.mark.parametrize('source', CASES)
def test_local_selector_identity(tmp_path, source):
    execute(tmp_path, 'local-selectors', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_unavailable_or_changing_local_selectors(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_local_selectors(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
