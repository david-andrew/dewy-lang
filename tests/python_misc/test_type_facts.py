"""Type facts: `true & <facts> | false & <facts>` on a boolean result, a proposition
as a result type (`:> tok is? Word`), inferred predicates, `T & <facts>`, and the
prelude's `startswith`/`endswith` declared as predicates."""
from pathlib import Path

import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, ty
from dewy.semantic.errors import NotImplementedYet, TypeCheckError, UserError
from dewy.semantic.hir_display import type_to_dewy

repo = Path(__file__).resolve().parents[2]
FIXTURE = (repo / 'dewy' / 'tests' / 'type_facts.dewy').read_text()


def _check(source: str) -> None:
    check.typecheck_and_resolve(SrcFile(None, source), include_prelude=True)


def _function_type(source: str, name: str) -> ty.FunctionType:
    root = check.typecheck_and_resolve(SrcFile(None, source), include_prelude=True)
    declaration = next(item for item in root.items if getattr(item, 'name', None) == name)
    assert isinstance(declaration.expr.type, ty.FunctionType)
    return declaration.expr.type


def test_the_fixture_proves() -> None:
    _check(FIXTURE)


def test_a_predicate_is_spelled_by_its_arms_and_inferred_from_its_body() -> None:
    program = '''let Tok:type = $abstract type of any & [text:string]
let Word = type of Tok & []
let declared = (tok:Tok):> tok is? Word => tok is? Word
let inferred = (tok:Tok) => tok isnt? Word
let fits = (prefix:string src:string) => prefix.length <=? src.length
let plain = (tok:Tok):>bool => tok is? Word
'''
    assert type_to_dewy(_function_type(program, 'declared').ret) == 'true & <tok is? Word> | false & <tok isnt? Word>'
    assert type_to_dewy(_function_type(program, 'inferred').ret) == 'true & <tok isnt? Word> | false & <tok is? Word>'
    assert type_to_dewy(_function_type(program, 'fits').ret) == 'true & <prefix.length <=? src.length> | false & <prefix.length >? src.length>'
    assert _function_type(program, 'plain').ret == 'bool'   # `:>bool` opts out


def test_the_prelude_predicates_carry_their_facts() -> None:
    program = '''let f = (s:string):>uint64<n => n <=? s.length> | none => {
    let i:uint64 = 0
    if s.startswith("ab") { i += 2  return i }
    if s.endswith("xyz") { return s.length - 3 }
    return none
}
'''
    _check(program)
    with pytest.raises(UserError, match='cannot prove refinement'):   # a fact the predicate did not promise
        _check(program.replace('if s.startswith("ab") { i += 2  return i }', 'if s.startswith("ab") { i += 3  return i }'))


def test_a_promised_fact_is_proven_at_every_return() -> None:
    with pytest.raises(UserError, match='cannot prove fact'):   # `return true` with nothing establishing the fact
        _check('let has = (src:string prefix:string):> true & <prefix.length <=? src.length> | false => { return true }\n')
    _check('let has = (src:string prefix:string):> true & <prefix.length <=? src.length> | false => { return false }\n')   # the other arm is free
    with pytest.raises(UserError, match='cannot prove type fact'):
        _check('let Tok:type = $abstract type of any & [text:string]\nlet Word = type of Tok & []\nlet bad = (tok:Tok):> tok is? Word => true\n')
    _check('let Tok:type = $abstract type of any & [text:string]\nlet Word = type of Tok & []\nlet ok = (tok:Tok):> true & <tok is? Word> | false => { if tok is? Word { return true }  return false }\n')


def test_a_fact_names_a_parameter_and_type_facts_stay_in_the_checker() -> None:
    with pytest.raises(UserError, match='fact names something that is not a parameter'):
        _check('let has = (src:string):> true & <prefix.length <=? src.length> | false => false\n')
    with pytest.raises(TypeCheckError, match='a boolean fact type has a `true` arm and a `false` arm'):
        _check('let has = (src:string):> true & <src.length >? 0> | true => false\n')
    with pytest.raises(NotImplementedYet):   # `T & <…>` on a union member the facts do not apply to
        _check('let f = (src:string):> (uint64 | none) & <n => n <=? src.length> => none\n')


def test_facts_intersect_a_type_like_a_parameterize_block() -> None:
    program = '''let f = (src:string):> uint64 & <n => n <=? src.length> => src.length
let g = (src:string):> uint64<n => n <=? src.length> => src.length
let main = ():>int64 => { let t = "abc"  let n = f(t)  let m = g(t)  if t[0..n) =? t[0..m) { return 0 }  return 1 }
'''
    assert _function_type(program, 'f').ret == _function_type(program, 'g').ret


def test_a_predicate_slot_dispatches_through_a_type_value() -> None:
    program = '''let matcher:type = (src:string):> true & <src.length >=? 2> | false
let Kind:type = $abstract type of any & [matches:matcher]
let Pair = type of Kind & [
    matches = (src:string):>bool => {
        if src.length <? 2 return false
        return src[0] =? src[1]
    }
]
let Solo = type of Kind & [
    matches = (src:string):>bool => src.length >=? 2 and src[0] not=? src[1]
]
let count = (s:string):>int64 => {
    let kinds:array<type<Kind>> = [Pair Solo]
    let n:int64 = 0
    loop k in kinds { if k.matches(s) { let two = s[0..2)  n += 1 } }   # the slot's fact proves the slice
    return n
}
'''
    _check(program)
    with pytest.raises(UserError, match='cannot prove fact'):   # an implementation that does not establish the slot's promise
        _check(program.replace("    matches = (src:string):>bool => src.length >=? 2 and src[0] not=? src[1]\n", "    matches = (src:string):>bool => src.length >=? 1\n"))
