import pytest

from udewy import p0, t1
from udewy.backend import get_backend
from udewy.backend.wasm import Wasm32Backend

def parse_udewy(src: str) -> str:
    toks = t1.tokenize(src)
    backend = get_backend("wasm32")
    return p0.parse(toks, src, backend)


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


def test_core_intrinsic_arity_is_checked() -> None:
    src = """
let main = ():>int => {
    return __load__()
}
"""

    with pytest.raises(SyntaxError, match=r"Intrinsic '__load__' expects 1 argument, got 0"):
        parse_udewy(src)


def test_wasm_intrinsic_arity_is_checked() -> None:
    src = """
let main = ():>int => {
    return __host_time__(1)
}
"""

    with pytest.raises(SyntaxError, match=r"Intrinsic '__host_time__' expects 0 arguments, got 1 argument"):
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


@pytest.mark.parametrize("target", ["x86_64", "riscv", "arm", "wasm32"])
def test_runtime_global_initializer_emits_module_init(target: str) -> None:
    src = """
let seed:int = helper()
const twice:int = seed + seed

let helper = ():>int => {
    return 7
}

let main = ():>int => {
    return twice
}
"""

    backend = get_backend(target)
    code = p0.parse(t1.tokenize(src), src, backend)

    if target == "wasm32":
        assert '(export "main" (func $main))' in code
        assert "$__udewy_globals_init__" in code
        assert "$__main__" in code
    else:
        assert "__udewy_globals_init__" in code


def test_runtime_initialized_top_level_const_is_not_compile_time_stable() -> None:
    src = """
const seed:int = helper()

let helper = ():>int => {
    return 4
}

let main = ():>void => {
    let x:int = __static_alloca__(seed)
    return void
}
"""

    with pytest.raises(SyntaxError, match=r"compile-time constant"):
        parse_udewy(src)


def test_wasm_global_initializer_rejects_unknown_data_reference() -> None:
    backend = Wasm32Backend()

    with pytest.raises(ValueError, match=r"Unknown wasm data reference"):
        backend.define_global(0, ".missing+8")


def test_wasm_array_literal_rejects_unknown_data_reference() -> None:
    backend = Wasm32Backend()

    with pytest.raises(ValueError, match=r"Unknown wasm data reference"):
        backend.intern_array([".missing+8"])
