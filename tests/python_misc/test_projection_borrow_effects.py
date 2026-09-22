"""Sibling writes preserve a projection; overlapping writes need a snapshot."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute


FLAT = '''Box:type=[text:string count:int64]
size=(text:string n:int64):>int64=>text.length+n
touch=(@n:int64):>int64=>{n=2 return n}
forward=(box:Box):>int64 & allocates=>size(box.text touch(@box.count))
main=():>int64=>{
    let box=Box["abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN" 0]
    let answer=forward(box)
    return if box.count=?0 and box.text.length=?40 answer else 1
}'''

NESTED = '''Inner:type=[text:string count:int64]
Box:type=[inner:Inner]
size=(text:string n:int64):>int64=>text.length+n
touch=(@n:int64):>int64=>{n=2 return n}
forward=(box:Box):>int64 & allocates=>size(box.inner.text touch(@box.inner.count))
main=():>int64=>forward(Box[Inner["abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN" 0]])'''

CASES = [FLAT, NESTED,
         FLAT.replace('size(box.text touch(@box.count))',
                      '{box.count=2 return size(box.text box.count)}')]

OVERLAPPING = [
    # A later argument replaces the exact field whose old value size needs.
    FLAT.replace('touch=(@n:int64):>int64=>{n=2 return n}',
                 'touch=(@text:string):>int64=>{text="changed" return 2}')
        .replace('touch(@box.count)', 'touch(@box.text)'),
    # Rebinding an ancestor invalidates all its projected storage.
    NESTED.replace('touch=(@n:int64):>int64=>{n=2 return n}',
                   'touch=(@inner:Inner):>int64=>{inner=Inner["changed" 2] return 2}')
          .replace('touch(@box.inner.count)', 'touch(@box.inner)'),
    # Borrowing a whole record includes its mutable descendants.
    NESTED.replace('size=(text:string n:int64):>int64=>text.length+n',
                   'size=(inner:Inner n:int64):>int64=>inner.text.length+n')
          .replace('size(box.inner.text', 'size(box.inner'),
]
ERRORS = [source.replace('& allocates', '& no allocates') for source in [*CASES, *OVERLAPPING]] + [
    # An unresolved callee cannot establish stable receiver storage.
    FLAT.replace('forward=(box:Box)', 'forward=(box:Box f:(@b:Box):>int64)')
        .replace('touch(@box.count)', 'f(@box)')
        .split('main=', 1)[0].replace('& allocates', '& no allocates'),
    # A projected scalar place can still detach runtime-length array storage.
    '''touch=(@n:int64):>void=>{n=42}
forward=(xs:array<int64>):>int64 & no allocates=>{
    if xs.length>?0 {touch(@xs[0])}
    return 42
}''',
]

PLACED_OR_READ_ONLY = [
    '''read=(@n:int64):>int64 & reads<n>=>n
forward=(xs:array<int64>):>int64 & no_effects=>{
    if xs.length>?0 return read(@xs[0])
    return 0
}
main=():>int64=>forward([42])''',
    '''touch=(@n:int64):>void=>{n=42}
main=():>int64 & no_effects=>{let x:int64=0 touch(@x) return x}''',
]


@pytest.mark.parametrize('source', CASES)
def test_disjoint_field_forwarding_executes(source, tmp_path):
    emitted = codegen(SrcFile(None, source))
    execute(tmp_path, 'projection-borrow', emitted)


@pytest.mark.parametrize('source', OVERLAPPING)
def test_overlapping_forwarding_keeps_its_snapshot(source, tmp_path):
    # Aggregate-place replacement still has an open public summary. Its
    # ordinary value behavior must nevertheless preserve the earlier argument.
    emitted = codegen(SrcFile(None, source.replace(' & allocates', '')))
    execute(tmp_path, 'projection-snapshot', emitted)


@pytest.mark.parametrize('source', ERRORS)
def test_overlapping_or_unknown_writes_still_need_storage(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


@pytest.mark.parametrize('source', PLACED_OR_READ_ONLY)
def test_proven_frame_or_read_only_place_needs_no_storage(source, tmp_path):
    execute(tmp_path, 'projection-place', codegen(SrcFile(None, source)))


def test_native_projection_borrows(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[*CASES, *PLACED_OR_READ_ONLY,
                                 *(s.replace(' & allocates', '') for s in OVERLAPPING)], errors=ERRORS)
