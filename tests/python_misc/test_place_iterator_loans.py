"""A loop can borrow a place field after earlier writes have completed."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = '''$explicit_copies
Box:type=[items:array<int64> count:int64]
collect=(@box:Box):>array<int64>=>{
    box.items.push(22)
    let output:array<int64>=[]
    loop item in box.items {output.push(item)}
    return output
}
main=():>int64=>{
    let box=Box[[20] 0]
    let values=collect(@box)
    if values.length not=?2 return 1
    values[0]=0
    return if box.items.length=?2 and box.items[0]=?20 and box.items[1]=?22 and values[1]=?22 42 else 2
}
'''
CASES = [SOURCE,
    SOURCE.replace('output.push(item)', 'box.count+=1 output.push(item)'),
    SOURCE.replace('loop item in box.items', 'loop item in box.items and index in [0..2)'),
    # Two places of one call never overlap, and no ambient alias names a
    # stable place parameter: writing `other` cannot change `box`.
    SOURCE.replace('collect=(@box:Box)', 'collect=(@box:Box @other:Box)')
          .replace('output.push(item)', 'other.items.clear output.push(item)')
          .replace('let values=collect(@box)', 'let other=Box[[1] 0]\n let values=collect(@box @other)'),
]
ERRORS = [SOURCE.replace('output.push(item)', 'box.items.clear output.push(item)'),
    SOURCE.replace('output.push(item)', 'let address=box.items transmute int64 output.push(item)'),
    SOURCE.replace('collect=', 'later=(@box:Box):>array<int64>=>{box.items.clear return [1]}\ncollect=')
          .replace('loop item in box.items', 'loop item in box.items and other in later(@box)'),
]


@pytest.mark.parametrize('source', CASES)
def test_place_iterator_interval(tmp_path, source):
    execute(tmp_path, 'place-iterator-loan', codegen(SrcFile(None, source),debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_place_iterator_requires_stability(source):
    with pytest.raises(ReportException,match='unproven copy|cannot mutate'):
        codegen(SrcFile(None, source),debug_locations=False)


def test_native_place_iterator_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)


def test_iteration_snapshot_is_reported_without_strict_policy():
    from dewy.backend.udewy import lower
    codegen(SrcFile(None, ERRORS[0].replace('$explicit_copies', '')), debug_locations=False)
    assert any(note.site == 'iterated' and note.runtime_sized and not note.explicit
               for note in lower.last_copy_notes)
