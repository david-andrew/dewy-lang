"""An owning parameter's implicit cleanup participates in ordinary proofs."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic import check

OWNER = '''let changed:int64=0
Handle=type of [token:int64
$__drop__
release=():>void=>{changed=1}
]
'''
CASES = [
    OWNER + 'consume=(owner:Handle):>int64 & allocates=>owner.token\nmain=():>int64=>consume(Handle[42])',
    OWNER + 'consume=(owner:Handle):>int64=>owner.token\nmain=():>int64=>{changed=0 consume(Handle[42]); $assert changed=?0 return 42}',
]


@pytest.mark.parametrize('source,diagnostic', list(zip(CASES, ['effect contract', 'assert'])))
def test_parameter_cleanup_enters_fact_and_effect_checks(source, diagnostic):
    for compile_ in (check.typecheck_and_resolve, codegen):
        with pytest.raises(ReportException, match=diagnostic):
            compile_(SrcFile(None, source))


def test_native_parameter_cleanup_contracts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[], errors=CASES)
