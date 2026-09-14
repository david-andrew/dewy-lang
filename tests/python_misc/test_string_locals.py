"""String locals own their values: released at scope exit, moved by `return s`, and every returned string is the caller's."""
import re

import pytest
from tests.python_misc.test_scalar_projection import execute

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def _function(emitted: str, name: str) -> str:
    start = emitted.index(f'let {name} = ')
    end = emitted.find('\nlet ', start)
    return emitted[start:] if end == -1 else emitted[start:end]


HEAD = (
    'let join2 = (a:string b:string):>string => [a b].join"-"\n'
    'let pick = (text:string flag:bool):>string => if flag text else text.trim\n'
)


def test_a_returned_parameter_comes_back_as_a_view_and_a_fresh_result_as_it_is() -> None:
    emitted = _compile(HEAD + 'let main = ():>int64 => pick("ab" true).length\n')
    pick = _function(emitted, 'pick')
    # `return text` (the parameter) is distributed into its arm and wrapped in a view (owner 2) …
    assert re.search(r'__store_i64__\(2 __dewy_string_returned_view_\d+ \+ 40\)', pick)
    # … while `text.trim` (a call) is returned as it is
    assert re.search(r'let __dewy_string_returned_\d+:int64 = \S+string_trim\(text\)\n\s*return __dewy_string_returned_\d+', pick)


def test_stack_descriptors_clear_their_owner_word() -> None:
    emitted = _compile('let main = ():>int64 => {\n    let n:int64 = 3\n    let s:string = "{n}!"\n    return s.length\n}\n')
    stack_descriptors = re.findall(r'let (__dewy_string_value_\d+):int64 = __alloca__\(48\)', emitted)
    assert stack_descriptors
    for name in stack_descriptors:
        assert f'__store_i64__(0 {name} + 40)' in emitted


@pytest.mark.parametrize('definitions, exercise', [
    ('', 'let s:string=join2("a" "b") s=join2(s "x") if s not=? "a-b-x" return 1'),
    ('let moved=():>string=>{let s:string=join2("a" "b") return s}\n'
     'let copied=():>string=>{let s:string=join2("a" "b") return pick(s true)}',
     'let a=moved() let b=copied() if a not=? "a-b" or b not=? "a-b" return 1'),
    ('', 'join2("a" "b");'),
    ('let count=(text:string):>int64=>text.split" ".length', 'if count("a b") not=? 2 return 1'),
    ('let choose=(flag:bool):>string|none=>if flag join2("a" "b") else none\n'
     'let moved=():>string|none=>{let maybe:string|none=choose(true) return maybe}\n'
     'let aliased=():>string|none=>{let maybe:string|none=choose(true) let other:string|none=maybe return other}',
     'let a=moved() let b=aliased() if a is? none or b is? none return 1 if a not=? "a-b" or b not=? "a-b" return 2'),
])
def test_local_result_and_temporary_lifetimes(tmp_path, definitions, exercise):
    # Values survive their producers' exits; repeated visits release their
    # storage regardless of whether cleanup is inline or shared in helpers.
    source = HEAD + definitions + '\nexercise=():>int64=>{' + exercise + '\nreturn 42}\n' + '''
main=():>int64=>{
    if exercise() not=? 42 return 1
    let before:int64=_arena_live_bytes
    loop i in 0.. and i <? 100 {if exercise() not=? 42 return 2}
    if _arena_live_bytes not=? before return 3
    return 42
}
'''
    execute(tmp_path, 'local-lifetimes', _compile(source))
