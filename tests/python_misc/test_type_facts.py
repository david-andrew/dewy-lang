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


def test_a_type_test_written_as_two_returns_proves_both_arms() -> None:
    family = 'let Tok:type = $abstract type of any & [text:string]\nlet Word = type of Tok & []\nlet Space = type of Tok & []\n'
    # the fall-through after `if tok is? Word return true` remembers the exclusion (`Tok & ~Word` is not a type)
    _check(family + 'let is_word = (tok:Tok):> tok is? Word => { if tok is? Word return true  return false }\n')
    _check(family + 'let not_space = (tok:Tok):> tok isnt? Space => { if tok is? Space { return false }  return true }\n')
    with pytest.raises(UserError, match='cannot prove type fact'):   # not a Space is not necessarily a Word
        _check(family + 'let wrong = (tok:Tok):> tok is? Word => { if tok is? Space return false  return true }\n')


def test_a_fact_on_a_local_names_a_binding_in_scope() -> None:
    program = '''let main = ():>int64 => {
    let src = "hello"
    let n:uint64<v => v <=? src.length> = 3     # proven: `src` is 5 long
    let piece = src[0..n)                        # the fact
    n = 5                                        # re-proven on assignment, the fact re-established
    let all = src[0..n)
    return 0
}
'''
    _check(program)
    with pytest.raises(UserError, match='cannot prove refinement'):
        _check(program.replace('n = 5', 'n = 6'))
    with pytest.raises(UserError, match='fact names a binding that is reassigned'):
        _check(program.replace('let src = "hello"', 'let src:string = "hello"').replace('n = 5', 'src = "hi"'))
    with pytest.raises(UserError, match='fact names an unknown binding'):
        _check('let main = ():>int64 => { let n:uint64<v => v <=? text.length> = 3  return 0 }\n')


def test_a_parameter_fact_may_name_a_sibling_parameter() -> None:
    take = 'let take = (src:string n:uint64<v => v <=? src.length>):>string => src[0..n)\n'   # `n` is in bounds by contract
    _check(take + 'let main = ():>int64 => { let text:string = "world!"  let k:uint64 = 9  if k <=? text.length { let h = take(text k) }  return 0 }\n')
    with pytest.raises(UserError, match='cannot prove refinement'):   # nothing bounds `k` by `text`
        _check(take + 'let main = ():>int64 => { let text:string = "world!"  let k:uint64 = 9  let h = take(text k)  return 0 }\n')
    with pytest.raises(UserError, match='cannot prove refinement'):   # a term needs a binding to name
        _check(take + 'let main = ():>int64 => { let k:uint64 = 2  let h = take("abc" k)  return 0 }\n')


def test_a_refined_local_is_rechecked_on_assignment() -> None:
    with pytest.raises(TypeCheckError, match='refinement refuted'):   # was silently accepted before
        _check('let main = ():>int64 => { let x:int64<i => i >? 0> = 1  x = -5  return x }\n')


def test_a_loop_keeps_its_counter_within_the_length_at_its_exit() -> None:
    scan = 'let f = (src:string):>uint64<n => n <=? src.length> => { let i:uint64 = 0  loop i <? src.length { i += STEP }  return i }\n'
    _check(scan.replace('STEP', '1'))          # `i <= src.length` from the entry (`i = 0`) through every step
    with pytest.raises(UserError, match='cannot prove refinement'):
        _check(scan.replace('STEP', '2'))


def test_facts_about_a_parameters_value_and_between_parameters() -> None:
    program = '''let positive = (n:int64):> true & <n >? 0> | false => n >? 0
let ordered = (a:uint64 b:uint64) => a <=? b                       # inferred: `a <=? b` / `a >? b`
let main = ():>int64 => {
    let x:int64 = 7
    if positive(x) { let p:int64<i => i >? 0> = x }               # the fact narrows the argument
    let a:uint64 = 2
    let b:uint64 = 5
    if ordered(a b) { let w:uint64 = b - a }                       # `b - a` fits: `a <= b`
    return 0
}
'''
    _check(program)
    assert type_to_dewy(_function_type(program, 'ordered').ret) == 'true & <a <=? b> | false & <a >? b>'
    with pytest.raises(UserError, match='cannot prove fact'):
        _check(program.replace('=> n >? 0', '=> n >=? 0'))
    with pytest.raises(UserError, match='cannot prove fact'):
        _check('let ordered = (a:uint64 b:uint64):> true & <a <=? b> | false => a >=? b\n')


def test_length_bounds_in_both_directions_and_windows() -> None:
    program = '''let at_least = (src:string):>uint64<n => n >=? src.length> => src.length + 2
let exactly = (src:string):>uint64<n => n =? src.length> => src.length
let take = (src:string):>uint64<n => n <=? src.length> => if src.length >? 3 3 else src.length
let f = (text:string i:uint64 j:uint64):>uint64 => {
    let n = at_least(text)
    let m = exactly(text)
    let whole = text[0..m)                       # exact: the whole text
    if i <=? j and j <? text.length {
        let k = take(text[i..j))                 # k <= j - i
        let piece = text[i..i+k)                 # i + k <= j <= text.length
        let l = take(text[i..j])                 # l <= j - i + 1
        return piece.length
    }
    return n
}
'''
    _check(program)
    with pytest.raises(UserError, match='cannot prove refinement'):
        _check(program.replace('=> src.length + 2', '=> src.length - 1'))
    with pytest.raises(UserError, match='string slice is not proven in bounds'):
        _check(program.replace('let piece = text[i..i+k)', 'let piece = text[i..i+k+2)'))   # `i + k + 1 <= j + 1 <= text.length` would still hold


def test_a_result_of_only_facts_is_a_procedure_that_establishes_them() -> None:
    # `:> <facts>`: no value; owed at every return and at the end of the body; the caller
    # gets them after the call — a library `require`, an in-place `ensure`, a type guard
    program = '''let require = (ok:bool msg:string):> <ok =? true> => { if not ok { printl"{msg}"  exit(1) } }
let ensure_nonempty = (@xs:array<int64>):> <xs.length >? 0> => { if xs.length =? 0 { xs.push(0) } }
let Tok:type = $abstract type of any & [text:string]
let Word = type of Tok & []
let must_be_word = (tok:Tok):> <tok is? Word> => { if tok isnt? Word { exit(2) } }
let main = ():>int64 => {
    let xs:array<int64> = []
    ensure_nonempty(@xs)
    let first = xs[0]
    let i:uint64 = 3
    let text = "hello"
    require(i <? text.length "i out of range")
    let c = text[i]
    let t:Tok = Word[text="hi"]
    must_be_word(t)
    let w:Word = t
    return 0
}
'''
    _check(program)
    with pytest.raises(UserError, match='cannot prove refinement'):  # `require` that does not exit on failure
        _check(program.replace('{ if not ok { printl"{msg}"  exit(1) } }', '{ printl"{msg}" }'))
    with pytest.raises(UserError, match='cannot prove refinement'):  # `ensure` that does not ensure
        _check(program.replace('{ if xs.length =? 0 { xs.push(0) } }', '{ }'))
    with pytest.raises(UserError, match='cannot prove type fact'):   # a guard that does not guard
        _check(program.replace('{ if tok isnt? Word { exit(2) } }', '{ }'))
    with pytest.raises(UserError, match='a fact block as a result speaks of the parameters'):
        _check('let f = (n:int64):> <i => i >? 0> => { }\n')


def test_facts_on_a_union_member_apply_where_the_result_is_narrowed_to_it() -> None:
    program = '''let Tok:type = $abstract type of any & [text:string]
let Word = type of Tok & []
let Ok = type of any & []
let Trouble = type of error & [why:string]
let check = (tok:Tok src:string n:uint64):> Ok & <tok is? Word n <=? src.length> | Trouble => {
    if tok isnt? Word return Trouble[why="not a word"]
    if n >? src.length return Trouble[why="too long"]
    return Ok
}
let main = ():>int64 => {
    let t:Tok = Word[text="hi"]
    let text = "hello world"
    let n:uint64 = 4
    let r = check(t text n)
    if r isnt? exception { let w:Word = t  let head = text[0..n) }
    return 0
}
'''
    _check(program)
    with pytest.raises(UserError, match='cannot prove refinement'):   # `return Ok` without the length guard
        _check(program.replace('    if n >? src.length return Trouble[why="too long"]\n', ''))
    with pytest.raises(UserError, match='cannot prove type fact'):
        _check(program.replace('    if tok isnt? Word return Trouble[why="not a word"]\n', ''))
    with pytest.raises(TypeCheckError, match='type mismatch'):        # reassigned: the remembered call no longer speaks for `r`
        _check(program.replace('    if r isnt? exception', '    r = Trouble[why="later"]\n    if r isnt? exception'))


def test_an_error_object_is_an_exception_for_a_type_test() -> None:
    # `if r isnt? exception` on `Ok | Trouble` used to be decided true at compile time (the arm always taken)
    program = '''let Ok = type of any & []
let Trouble = type of error & [why:string]
let check = (n:int64):> Ok | Trouble => if n >? 0 Ok else Trouble[why="bad"]
let main = ():>int64 => { let r = check(-1)  if r isnt? exception { return 1 }  return 0 }
'''
    root = check.typecheck_and_resolve(SrcFile(None, program), include_prelude=True)
    from dewy.semantic import hir
    main_body = next(item for item in root.items if getattr(item, 'name', None) == 'main').expr.body
    assert any(isinstance(item, hir.Flow) for item in main_body.items)   # a real test, not a folded arm


def test_a_bare_fact_block_is_not_a_type_elsewhere() -> None:
    with pytest.raises(UserError, match='a fact block is not a type by itself') as caught:
        _check('let f = (n:<n >? 0>):>int64 => 1\n')
    assert 'T & <n >? 0>' in str(caught.value) and ':> <n >? 0>' in str(caught.value)
    with pytest.raises(UserError, match='a fact block is not a type by itself'):
        _check('let main = ():>int64 => { let n:<length >? 0> = "a"  return 0 }\n')
