"""Result refinements bounded by a parameter's length (`:>uint64<n => n <=? src.length>`):
proven at every return, and carried from a call through records, arrays, sorts,
element reads and unpacking to the slice that needs them."""
from pathlib import Path

import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import UserError

repo = Path(__file__).resolve().parents[2]
TOKENIZER = (repo / 'dewy' / 'tests' / 'length_terms.dewy').read_text()


def _check(source: str) -> None:
    check.typecheck_and_resolve(SrcFile(None, source), include_prelude=True)


def _variant(old: str, new: str) -> str:
    assert old in TOKENIZER, old
    return TOKENIZER.replace(old, new)


def test_the_tokenizer_shape_proves_without_a_guard() -> None:
    _check(TOKENIZER)


def test_a_return_past_the_promise_is_rejected() -> None:
    with pytest.raises(UserError, match=r'cannot prove refinement') as caught:
        _check(_variant("            if src[i] not=? ' ' return i\n", "            if src[i] not=? ' ' return i + 2\n"))
    assert 'value <=? src.length' in str(caught.value)


def test_an_implementation_is_checked_against_its_slot() -> None:
    word = TOKENIZER[TOKENIZER.index('let Word'):TOKENIZER.index('let tokenize')]
    with pytest.raises(UserError, match=r'`Word.eat` does not fit its slot'):   # the result
        _check(TOKENIZER.replace(word, word.replace(':>uint64? => {', ':>int64 => {').replace('return none', 'return 0').replace('return i + 1', 'return 3').replace('return src.length', 'return 7')))
    with pytest.raises(UserError, match=r'`Word.eat` does not fit its slot'):   # a parameter's name (the slot names it)
        _check(TOKENIZER.replace(word, word.replace('src', 's')))


def test_the_fact_drops_when_the_offset_moves_or_a_foreign_element_joins() -> None:
    with pytest.raises(UserError, match='string slice is not proven in bounds'):
        _check(_variant("        out.push(src[i..i+length))", "        i = 0\n        out.push(src[i..i+length))"))
    with pytest.raises(UserError, match='string slice is not proven in bounds'):
        _check(_variant("        [length k] = matches[0]", "        matches.push([length=(src.length + 5) k=Spaces])\n        [length k] = matches[0]"))


def test_a_promise_is_about_the_argument_not_a_name() -> None:
    promise = 'let h = (src:string):>uint64<n => n <=? src.length> => src.length\n'
    with pytest.raises(UserError, match='cannot prove refinement'):   # `h` speaks of *its* `src`, which was `other`
        _check(promise + 'let g = (src:string other:string):>uint64<n => n <=? src.length> => h(other)\n')
    _check(promise + 'let g = (src:string other:string):>uint64<n => n <=? src.length> => h(src)\n')
    _check(promise + 'let g = (text:string):>uint64<n => n <=? text.length> => h(text)\n')


def test_a_term_must_name_a_parameter_and_be_an_upper_bound() -> None:
    from dewy.semantic.errors import NotImplementedYet
    with pytest.raises(UserError, match='fact names a length that is not a parameter'):
        _check('let f = (src:string):>uint64<n => n <=? text.length> => src.length\n')
    with pytest.raises(NotImplementedYet):
        _check('let f = (src:string):>uint64<n => n >=? src.length> => src.length\n')


def test_the_spelling_round_trips() -> None:
    from dewy.semantic import ty
    from dewy.semantic.hir_display import type_to_dewy
    refined = ty.RefinedType('uint64', (ty.Proposition('self', '<=?', 0, term='src'),))
    assert type_to_dewy(refined) == 'uint64<i => i <=? src.length>'
    assert ty.Proposition('self', '<=?', 0, term='src', term_id=7) == ty.Proposition('self', '<=?', 0, term='src', term_id=9)   # identity is the name


def test_a_refined_member_of_a_wider_union_lowers_and_a_transmute_is_seen_through() -> None:
    from dewy.backend.udewy import codegen
    program = '''let Trouble = type of error & [why:string]
let scan = (src:string):>uint64< n => n <=? src.length > | none | Trouble => {
    if src.length =? 0 return none
    let i:int64 = 0
    loop i <? src.length {
        if src[i] =? '!' return Trouble[why="bang"]
        i += 1
    }
    if i <=? src.length return i transmute uint64   # a non-negative transmute is the same number
    return Trouble[why="ran past the end"]
}
let main = ():>int64 => {
    let text = "abc"
    let n = scan(text)
    if n is? uint64 { let all = text[0..n)  if all =? "abc" { return 42 } }
    return 0
}
'''
    assert 'scan' in codegen(SrcFile(None, program), debug_locations=False)   # checks, proves, and lowers
