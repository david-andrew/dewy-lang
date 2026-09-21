"""Runtime layout rewrites preserve the checked function's calling convention."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

CASES = [
    f'''change=(items:array<int64>):>{result}=>{{
        if items.length =? 0 return 0
        items[0]=42
        return 42
    }}
    invoke=(f:(items:array<int64>):>int64 xs:array<int64>):>int64=>f(xs)
    main=():>int64=>{{
        let original:array<int64>=[7]
        let answer=invoke(@change original)
        return if original[0]=?7 answer else 1
    }}'''
    for result in ('int64', 'int64<v=>v>=?0>')
]


@pytest.mark.parametrize('source', CASES)
def test_callable_owns_its_mutable_value_parameter(tmp_path, source):
    execute(tmp_path, 'callable-ownership', codegen(SrcFile(None, source), debug_locations=False))


def test_native_callable_ownership_identity(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
