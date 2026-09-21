"""Value branches use the same proof-aware join as continuation facts."""
from dewy.reporting import SrcFile
from dewy.backend.udewy import codegen
from tests.python_misc.test_scalar_projection import execute


def test_exact_array_branch_is_covered_by_runtime_array_branch(tmp_path):
    source = SrcFile(None, '''
select=(flag:bool):>int64=>{
    let source:array<int64>=[40]
    let pending=if flag [40] else source
    pending.push(2)
    return if pending.length=?2 pending[0]+pending[1] else 0
}
main=():>int64=>if select(true)=?42 and select(false)=?42 42 else 1
''')
    execute(tmp_path, 'conditional-array-join', codegen(source, debug_locations=False))


BIGINT_BRANCHES = '''
let calls:int64=0
select=(flag:bool value:bigint?):>void=>{
    let joined=if flag {calls+=1 1} else value
    printl("{joined}")
}
annotated=(flag:bool value:bigint?):>void=>{
    let joined:bigint?=if flag {calls+=1 1} else value
    printl("{joined}")
}
main=():>int64=>{
    select(true none)
    select(false none)
    select(false 123456789012345678901234567890)
    annotated(true none)
    annotated(false none)
    annotated(false 123456789012345678901234567890)
    if calls not=? 2 return 4
    return 42
}
'''


OUTPUT = '1\nnone\n123456789012345678901234567890\n' * 2


def test_numeric_joins_and_annotated_conversions_keep_values_and_effects(tmp_path):
    source = SrcFile(None, BIGINT_BRANCHES)
    for result in execute(tmp_path, 'conditional-bigint-join', codegen(source, debug_locations=False)):
        assert result.stdout == OUTPUT


def test_native_numeric_joins_and_annotated_conversions(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text

    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[BIGINT_BRANCHES], errors=[], outputs=[OUTPUT])
