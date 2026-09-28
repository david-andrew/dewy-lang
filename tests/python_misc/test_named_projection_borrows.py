"""Named stable projections retain their storage proof at subsequent calls."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/named_projection_borrows.dewy'
SOURCE = FIXTURE.read_text()
CASES = [SOURCE,
    SOURCE.replace('size(items)+40', 'size(items=items)+40'),
    SOURCE.replace('Box:type=[items:array<int64> count:int64]',
                   'Inner:type=[values:array<int64>]\nBox:type=[items:Inner count:int64]')
          .replace('size(items)+40', 'size(items.values)+40')
          .replace('Box[[20 22] 0]', 'Box[Inner[[20 22]] 0]'),
    '''$explicit_copies
Box:type=[item:array<int64>|none]
read=(item:array<int64>|none):>int64 & no_effects=>if item is? none 0 else item.length
forward=(box:Box):>int64 & no allocates=>{let item=box.item return read(item)+40}
main=():>int64=>forward(Box[[20 22]])''',
    # The underlying parameter can change a disjoint field. That write has
    # its own allocation obligation, independent of this named loan.
    SOURCE.replace(':>int64 & no allocates=>{', ':>int64=>{')
          .replace('return size(items)+40', 'box.count=40\n    return size(items)+box.count')
          .split('work=')[0] + 'main=():>int64=>forward(Box[[20 22] 0])',
]
# A linear dependency chain must carry the same owner evidence all the way
# to the final call, without assuming a failed intermediate view is stable.
CHAIN = SOURCE.replace('Box:type=[items:array<int64> count:int64]',
                       'Inner:type=[values:array<int64>]\nBox:type=[items:Inner count:int64]')
CHAIN = CHAIN.replace('return size(items)+40', 'let values=items.values\n    return size(values)+40')
CHAIN = CHAIN.replace('Box[[20 22] 0]', 'Box[Inner[[20 22]] 0]')
CASES.append(CHAIN)

ERRORS = [
    CHAIN.replace('return size(values)+40', 'items.values.clear()\n    return size(values)+40'),
    CHAIN.replace('return size(values)+40', 'items=Inner[[]]\n    return size(values)+40'),
    SOURCE.replace('return size(items)+40', 'box.items.clear()\n    return size(items)+40'),
    SOURCE.replace('return size(items)+40', 'items.clear()\n    return size(items)+40'),
    SOURCE.replace(':>int64 & no_effects=>items.length', ':>int64=>{items.clear() return items.length}'),
    SOURCE.replace('forward=(box:Box)', 'forward=(box:Box f:(values:array<int64>):>int64 & no_effects)')
          .replace('size(items)+40', 'f(items)+40').split('work=')[0],
    SOURCE.replace('return size(items)+40', 'box=Box[[] 0]\n    return size(items)+40'),
]

@pytest.mark.parametrize('source', CASES)
def test_named_projection_borrows(tmp_path, source):
    execute(tmp_path, 'named-projection', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_unproved_named_projection_requires_allocation(source):
    with pytest.raises(ReportException, match='effect contract|unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_named_projection_borrows(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
