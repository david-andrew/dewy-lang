"""A fresh tagged result can widen without cloning identical payloads."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/fresh_union_widening.dewy'
SOURCE = FIXTURE.read_text()
CASES = [SOURCE,
    # Inject the narrower call directly into the wider element type.
    SOURCE.replace('values.push(widen(flag))', 'values.push(make(flag))'),
    SOURCE.replace('let values:array<Box|int64|none>=[]\n    values.push(widen(flag))',
                   'let values:array<Box|int64|none>=[make(flag)]'),
    # Fixed-array payloads still need their prepared layout conversion.
    SOURCE.replace('$explicit_copies', '').replace('items:array<int64>', 'items:array<int64 length=1>'),
    # Runtime arrays are payload handles too, without a containing record.
    '''$explicit_copies
make=(flag:bool):>array<int64>|none=>if flag [42] else none
widen=(flag:bool):>array<int64>|int64|none=>make(flag)
main=():>int64=>{
    let values=widen(true)
    if values is? array<int64> and values.length>?0 return values[0]
    return 1
}''',
]


@pytest.mark.parametrize('source', CASES)
def test_fresh_union_payload_widening(tmp_path, source):
    execute(tmp_path, 'fresh-widening', codegen(SrcFile(None, source), debug_locations=False))


def test_native_fresh_union_payload_widening(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
