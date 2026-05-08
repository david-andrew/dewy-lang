import pytest

from udewy import p0, t1
from udewy.backend import get_backend


def parse_udewy(src: str) -> str:
    toks = t1.tokenize(src)
    backend = get_backend("wasm32")
    return p0.parse(toks, src, backend)


def test_top_level_type_declaration_is_ignored() -> None:
    src = """
Point:type = [x:int y:int nested:[inner:int]]

let main = ():>int => {
    return 0
}
"""

    code = parse_udewy(src)

    assert "$__udewy_globals_init__" not in code


def test_top_level_let_type_declaration_is_ignored() -> None:
    src = """
let Point:type = [x:int y:int nested:[inner:int]]

let main = ():>int => {
    return 0
}
"""

    code = parse_udewy(src)

    assert "$__udewy_globals_init__" not in code


def test_top_level_const_type_declaration_is_ignored() -> None:
    src = """
const Point:type = [x:int y:int nested:[inner:int]]

let main = ():>int => {
    return 0
}
"""

    code = parse_udewy(src)

    assert "$__udewy_globals_init__" not in code


def test_nested_type_declaration_is_ignored() -> None:
    src = """
let main = ():>int => {
    Point:type = [x:int y:int]
    return 0
}
"""

    parse_udewy(src)


def test_nested_let_and_const_type_declarations_are_ignored() -> None:
    src = """
let main = ():>int => {
    let Point:type = [x:int y:int]
    const Line:type = [start:Point end:Point]
    return 0
}
"""

    parse_udewy(src)


def test_type_declarations_can_reference_prior_type_declarations() -> None:
    src = """
Point:type = [x:int y:int]
const Line:type = [start:Point end:Point extra:[focus:Point]]

let main = ():>int => {
    let origin:Point = 0
    return origin
}
"""

    parse_udewy(src)


def test_type_declaration_rhs_is_not_evaluated() -> None:
    src = """
let Point:type = helper([field:MissingType])

let main = ():>int => {
    return 0
}
"""

    code = parse_udewy(src)

    assert "$__udewy_globals_init__" not in code


def test_type_declaration_name_is_rejected_as_runtime_value() -> None:
    src = """
const Point:type = [x:int y:int]

let main = ():>int => {
    return Point
}
"""

    with pytest.raises(SyntaxError, match=r"Type declaration 'Point' cannot be used as a runtime value in udewy"):
        parse_udewy(src)


def test_type_declaration_name_is_rejected_as_assignment_target() -> None:
    src = """
let Point:type = [x:int y:int]

let main = ():>int => {
    Point = 1
    return 0
}
"""

    with pytest.raises(SyntaxError, match=r"Cannot assign to type declaration 'Point'"):
        parse_udewy(src)
