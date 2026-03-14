import pytest

from udewy import p0, t0


def parse_udewy(src: str) -> tuple[str, object]:
    toks = t0.tokenize(src)
    return p0.parse(toks, src, target="wasm32")


def test_local_const_assignment_is_rejected() -> None:
    src = """
let main = ():>void => {
    const n:int = 4
    n = 8
    return void
}
"""

    with pytest.raises(SyntaxError, match=r"Cannot assign to constant 'n'"):
        parse_udewy(src)


def test_global_const_update_assignment_is_rejected() -> None:
    src = """
const n:int = 4
let main = ():>void => {
    n += 1
    return void
}
"""

    with pytest.raises(SyntaxError, match=r"Cannot assign to constant 'n'"):
        parse_udewy(src)


def test_local_const_can_be_used_for_static_alloca_size() -> None:
    src = """
let main = ():>void => {
    const n:int = 4
    let x:int = __static_alloca__(n)
    return void
}
"""

    parse_udewy(src)


def test_local_let_cannot_be_used_for_static_alloca_size() -> None:
    src = """
let main = ():>void => {
    let n:int = 4
    let x:int = __static_alloca__(n)
    return void
}
"""

    with pytest.raises(SyntaxError, match=r"compile-time constant"):
        parse_udewy(src)


def test_array_literal_rejects_non_const_bindings() -> None:
    src = """
let main = ():>void => {
    let n:int = 4
    let xs:int = [n]
    return void
}
"""

    with pytest.raises(SyntaxError, match=r"Array elements must be constants"):
        parse_udewy(src)


def test_array_literal_accepts_local_const_bindings() -> None:
    src = """
let main = ():>void => {
    const n:int = 4
    let xs:int = [n]
    return void
}
"""

    parse_udewy(src)


def test_array_literal_accepts_const_string_aliases() -> None:
    src = """
let main = ():>void => {
    const msg:int = "hi"
    let xs:int = [msg]
    return void
}
"""

    parse_udewy(src)


def test_array_literal_accepts_const_array_aliases() -> None:
    src = """
let main = ():>void => {
    const base:int = [1 2]
    let xs:int = [base]
    return void
}
"""

    parse_udewy(src)


def test_array_literal_accepts_let_declared_function_identifiers() -> None:
    src = """
let helper = ():>int => {
    return 1
}

let main = ():>void => {
    let xs:int = [helper]
    return void
}
"""

    parse_udewy(src)


def test_top_level_const_alias_to_function_is_allowed() -> None:
    src = """
const helper_ref:int = helper

let helper = ():>int => {
    return 1
}

let main = ():>void => {
    let xs:int = [helper_ref]
    return void
}
"""

    parse_udewy(src)
