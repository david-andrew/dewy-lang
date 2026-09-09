"""`const [...]`: immutable records, the write barrier through them, and sibling-field invariants."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import ty
from dewy.semantic.errors import TypeCheckError, UserError
from dewy.semantic.hir_display import type_to_dewy
from dewy.semantic.modules import typecheck_program

BASE_INFO = (
    'BaseInfo:type = const [\n'
    '    alphabet:string<2 <=? length <=? uint8.max>\n'
    '    case_sensitive:bool\n'
    '    extra_chars:dict<string int8?>\n'
    '    radix:uint8<radix =? alphabet.length> = alphabet.length\n'
    ']\n'
)


def _compile(body: str) -> None:
    codegen(SrcFile(None, BASE_INFO + body + 'let main = ():>int64 => 42\n'))


def test_the_qualifier_is_part_of_the_type() -> None:
    root = typecheck_program(SrcFile(None, 'let Opening:type = const [idx:int64 loc:string]\nlet Frame = type of any & const [opening:Opening]\nlet main = ():>int64 => 42\n'), include_prelude=False)
    declared = {item.name: item for item in root.items if hasattr(item, 'name')}
    opening = declared['Opening'].expr.value
    assert isinstance(opening, ty.ObjectType) and opening.immutable
    assert type_to_dewy(opening) == 'const [idx:int64 loc:string]'
    frame = declared['Frame'].expr.value
    assert isinstance(frame, ty.ObjectType) and frame.immutable and frame.brand == 'Frame'
    system = ty.TypeSystem()
    writable = ty.ObjectType(opening.fields)
    assert system.is_subtype(writable, opening)        # a writable value may be used as the immutable record (copied)
    assert not system.is_subtype(opening, writable)    # an immutable record is never a writable one


@pytest.mark.parametrize(('body', 'message'), [
    ("let x = BaseInfo['01' true [] 3]\n", 'refuted'),                                            # an explicit radix that is not the alphabet's length
    ("let x = BaseInfo['0' true []]\n", 'refuted'),                                               # too short an alphabet
    ("let f = (info:BaseInfo) => { info.radix = 3 }\n", 'assign a field of an immutable record'),
    ("let f = ():>void => { let info = BaseInfo['01' true []]  info.alphabet = \"abc\" }\n", 'assign a field of an immutable record'),
    ("let f = (info:BaseInfo) => { info.extra_chars.pop(\"z\") }\n", 'mutate a dictionary member of an immutable record'),
    ("let f = (info:BaseInfo) => { if \"z\" in? info.extra_chars { info.extra_chars[\"z\"] = 1 } }\n", 'store into a dictionary member of an immutable record'),
    ("let bump = (@n:uint8) => { n += 1 }\nlet f = (info:BaseInfo) => { bump(@info.radix) }\n", 'take the place of a field of an immutable record'),
    ("let f = (info:BaseInfo) => { let c = info  c.radix = 3 }\n", 'assign a field of an immutable record'),                       # a copy is the same immutable type
    ("let f = (infos:array<BaseInfo>) => { if infos.length >? 0 { infos[0].radix = 3 } }\n", 'assign a field of an immutable record'),   # through a container
    ("let g = (x:[alphabet:string case_sensitive:bool extra_chars:dict<string int8?> radix:uint8]) => { x.radix = 3 }\nlet f = (info:BaseInfo) => { g(info) }\n", 'type mismatch'),   # a writable contract
    ("let Counter:type = const [n:int64 bump = () => { n += 1 }]\n", 'changes an immutable record'),
    ("let Pair:type = [a:string b:uint8<b =? a.length> = a.length]\n", 'in a writable record'),
    ("let Pair:type = const [b:uint8<b =? a.length> a:string]\n", 'not an earlier field'),
])
def test_writes_through_an_immutable_record_and_broken_invariants_are_refused(body: str, message: str) -> None:
    with pytest.raises((TypeCheckError, UserError), match=message):
        _compile(body)


def test_a_sibling_invariant_is_proven_at_construction_and_known_on_reads() -> None:
    _compile("let x = BaseInfo['01' true []]\nlet y = BaseInfo['0123456789abcdef' false [] 16]\n")            # the default, and an explicit value
    _compile("let last = (info:BaseInfo):>string => info.alphabet[info.radix - 1]\n")                         # `radix - 1 <? alphabet.length` from `radix =? alphabet.length`
    _compile("let mk = (s:string<2 <=? length <=? uint8.max>):>BaseInfo => BaseInfo[s false []]\n")           # a runtime alphabet within the bounds
    _compile("let f = ():>void => { let a = BaseInfo['01' true []]  let b:BaseInfo = a  let c:[alphabet:string case_sensitive:bool extra_chars:dict<string int8?> radix:uint8] = [alphabet=\"ab\" case_sensitive=true extra_chars=[] radix=2]  let d:BaseInfo = c }\n")   # copies; a writable value copied in
