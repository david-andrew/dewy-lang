"""Read-only helper chains lend roots only if no endpoint owns them."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute
from test_record_argument_loans import SOURCE

FORWARD = SOURCE.replace('read=(pair:Pair):>int64 & no_effects=>pair.items.length+pair.offset', '''size=(pair:Pair):>int64 & no_effects=>pair.items.length+pair.offset
middle=(pair:Pair):>int64 & no_effects=>size(pair)
read=(pair:Pair):>int64 & no_effects=>middle(pair)''')
CYCLE = SOURCE.replace('read=(pair:Pair):>int64 & no_effects=>pair.items.length+pair.offset', '''read=(pair:Pair count:int64=3):>int64 & no_effects=>if count=?0 pair.items.length+pair.offset else read(pair count-1)''')
CASES = [FORWARD, CYCLE, FORWARD.replace('=>middle(pair)', '=>middle(pair=pair)')]
ERRORS = [
    FORWARD.replace('size=(pair:Pair):>int64 & no_effects=>pair.items.length+pair.offset',
        'size=(pair:Pair):>int64=>{let saved=pair saved.items.clear return saved.offset}'),
    FORWARD.replace('middle=(pair:Pair):>int64 & no_effects=>size(pair)',
        'escape=(pair:Pair):>Pair=>pair\nmiddle=(pair:Pair):>int64=>size(escape(pair))'),
]

@pytest.mark.parametrize('source', CASES)
def test_forwarded_record_argument_loans(tmp_path, source):
    execute(tmp_path, 'forwarded-root', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_forwarded_root_cannot_enter_owning_protocol(source):
    with pytest.raises(ReportException, match='effect contract|unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_forwarded_record_argument_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
