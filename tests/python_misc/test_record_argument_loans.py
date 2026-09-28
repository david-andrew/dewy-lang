"""Call-scoped records lend stable fields without creating storage owners."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/record_argument_loans.dewy').read_text()
CASES = [SOURCE,
    SOURCE.replace('read(Pair[items 40])', 'read(pair=Pair[offset=40 items=items])'),
    SOURCE.replace('Pair:type=[', 'Pair:type=type of ['),
    SOURCE.replace('offset:int64]', 'offset:int64=items.length+38]').replace('Pair[items 40]', 'Pair[items]'),
    SOURCE.replace('forward=(items:array<int64>)', 'forward=(items:array<int64>|none)')
          .replace('work=(items:array<int64>)', 'work=(items:array<int64>|none)')
          .replace('=>read(Pair[items 40])', '=>if items is? none 0 else read(Pair[items 40])'),
    SOURCE.replace('forward=(items:array<int64>)', 'Box:type=[items:array<int64>]\nforward=(box:Box)')
          .replace('Pair[items 40]', 'Pair[box.items 40]').replace('work=(items:array<int64>)', 'work=(box:Box)')
          .replace('forward(items)', 'forward(box)').replace('work([20 22])', 'work(Box[[20 22]])'),
    # Named projections can supply the temporary's array field too.
    SOURCE.replace('forward=(items:array<int64>)', 'Box:type=[items:array<int64>]\nforward=(box:Box)')
          .replace('=>read(Pair[items 40])', '=>{let items=box.items return read(Pair[items 40])}')
          .replace('work=(items:array<int64>)', 'work=(box:Box)')
          .replace('forward(items)', 'forward(box)').replace('work([20 22])', 'work(Box[[20 22]])'),
    '''$explicit_copies
Pair:type=[a:int64 b:int64=a+2]
read=(pair:Pair):>int64 & no_effects=>pair.b
main=():>int64 & no_effects=>read(Pair[40])''',
    # The root is reusable inside a long loop, including literal calls in
    # the loop body itself rather than a wrapper's separate activation.
    SOURCE.split('work=')[0].replace('=>read(Pair[items 40])',
        '=>{loop i in 0.. and i<?200000 {if read(Pair[items 40]) not=?42 return 1} return 42}')
        + 'main=():>int64=>forward([20 22])',
    # Returning an array field still produces an independent ordinary value.
    '''Pair:type=[items:array<int64> offset:int64]
read=(pair:Pair):>array<int64>=>pair.items
forward=(items:array<int64>):>array<int64>=>read(Pair[items 0])
main=():>int64=>{
    let items:array<int64>=[20 22]
    let copy=forward(items)
    copy.clear()
    return if items.length=?2 42 else 1
}''',
]
ERRORS = [
    SOURCE.replace('pair.items.length+pair.offset', '{pair.items.clear() return pair.offset}'),
    SOURCE.replace('=>read(Pair[items 40])', '=>{items.clear() return read(Pair[items 40])}'),
    # New aggregate fields own storage; they cannot become borrowed roots.
    SOURCE.replace('Pair[items 40]', 'Pair[[20 22] 40]'),
    # Array length conversion changes representation; fixed arrays are not
    # dynamic handles even if their element type happens to agree.
    SOURCE.split('work=')[0].replace('forward=(items:array<int64>)', 'forward=(items:array<int64 length=2>)'),
    SOURCE.replace('read=(pair:Pair)', 'read=(pair:Pair other:int64)')
          .replace('read(Pair[items 40])', 'read(Pair[items 40] mutate(@items))')
          .replace('forward=', 'mutate=(@items:array<int64>):>int64=>{items.clear() return 0}\nforward='),
    # Opaque callbacks cannot establish this caller's storage stability.
    SOURCE.split('work=')[0].replace('forward=(items:array<int64>)',
                                  'forward=(items:array<int64> callback:():>int64 & no_effects)')
          .replace('Pair[items 40]', 'Pair[items callback()]'),
    # An entire record forwarded or consumed by a second callee keeps the
    # ordinary ownership protocol; this proof only lends projected roots.
    SOURCE.replace('read=(pair:Pair):>int64 & no_effects=>pair.items.length+pair.offset',
                   'size=(pair:Pair):>int64 & no_effects=>pair.items.length+pair.offset\nread=(pair:Pair):>int64 & no_effects=>size(pair)'),
]

# The finite frame budget is a proof limit, not a reason to allocate silently.
def roots(count):
    return (SOURCE.split('forward=')[0]
            + 'forward=(items:array<int64>):>int64 & no_effects=>{'
            + 'read(Pair[items 40]);' * count
            + 'return 42}\nmain=():>int64=>forward([20 22])')

CASES.append(roots(170))
ERRORS.append(roots(171))

@pytest.mark.parametrize('source', CASES)
def test_record_argument_loan(tmp_path, source):
    execute(tmp_path, 'record-loan', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_unproved_record_argument_keeps_storage_obligation(source):
    with pytest.raises(ReportException, match='effect contract|unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_record_argument_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
