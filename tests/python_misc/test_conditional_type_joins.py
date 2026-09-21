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
