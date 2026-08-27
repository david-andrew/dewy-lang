from pathlib import Path
from re import search
from shutil import which
from tempfile import TemporaryDirectory

import pytest

from udewy import p0, t1
from udewy.backend import Backend, get_backend


STATIC_WORDS_SOURCE = """
const handler_alias:int = table_only_handler
const text:int = "ok"
const scratch:int = __static_alloca__(8)
const nested:int = __static_words__(9)
const words:int = __static_words__(7 handler_alias text scratch nested)

let table_only_handler = (value:int):>int => {
    return value + 1
}

let main = ():>int => {
    if __load__(words) not=? 7 { return 1 }
    let fn:int = __load__(words + 8)
    if (@fn)(41) not=? 42 { return 2 }
    if __load__(words + 16) not=? text { return 3 }
    if __load__(words + 24) not=? scratch { return 4 }
    if __load__(words + 32) not=? nested { return 5 }
    if __load__(nested) not=? 9 { return 6 }
    return 0
}
"""


def parse_udewy(src: str, backend: Backend) -> str:
    return p0.parse(t1.tokenize(src), src, backend)


@pytest.mark.parametrize("target", ["x86_64", "riscv", "arm", "wasm32", "c"])
def test_static_words_codegen_supports_stable_word_kinds(target: str) -> None:
    code = parse_udewy(STATIC_WORDS_SOURCE, get_backend(target))

    assert "table_only_handler" in code
    if target == "x86_64":
        assert ".balign 8" in code
        assert "    .quad 7" in code
    elif target == "riscv":
        assert ".balign 8" in code
        assert "    .dword 7" in code
    elif target == "arm":
        assert ".balign 8" in code
        assert "    .xword 7" in code
    elif target == "wasm32":
        assert "\\07\\00\\00\\00\\00\\00\\00\\00" in code
    else:
        assert "static udewy_slot udewy_static_" in code


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            "let main = ():>int => { let words:int = __static_words__() return 0 }",
            "expects at least one compile-time stable word",
        ),
        (
            """
let main = ():>int => {
    let value:int = 1
    let words:int = __static_words__(value)
    return 0
}
""",
            "arguments must be compile-time stable words",
        ),
        (
            """
let host = ():>int => extern
const words:int = __static_words__(host)
let main = ():>int => { return 0 }
""",
            "does not accept extern function references",
        ),
        (
            """
const words:int = __static_words__(host)
let host = ():>int => extern
let main = ():>int => { return 0 }
""",
            "does not accept extern function references",
        ),
    ],
)
def test_static_words_rejects_invalid_arguments(source: str, message: str) -> None:
    with pytest.raises(SyntaxError, match=message):
        parse_udewy(source, get_backend("wasm32"))


def test_c_emits_address_bearing_values_as_static_initializers() -> None:
    source = """
const text:int = "ok"
const scratch:int = __static_alloca__(8)
const words:int = __static_words__(7 table_only_handler text scratch)
let function_global:int = table_only_handler
let string_global:int = text
let static_global:int = scratch
let runtime_global:int = seed()

let table_only_handler = (value:int):>int => { return value + 1 }
let seed = ():>int => { return 3 }
let main = ():>int => { return runtime_global }
"""
    code = parse_udewy(source, get_backend("c"))

    table = search(
        r"static udewy_slot udewy_static_\d+\[4\] = "
        r"\{ \{ \.w = UINT64_C\(0x0000000000000007\) \}, "
        r"\{ \.fn = \(udewy_fn\)udewy_fn_table_only_handler_\d+ \}, "
        r"\{ \.obj = .*? \}, \{ \.obj = .*? \} \};",
        code,
    )
    assert table is not None
    assert search(
        r"static udewy_slot udewy_global_\d+ = "
        r"\{ \.fn = \(udewy_fn\)udewy_fn_table_only_handler_\d+ \};",
        code,
    )
    assert search(r"static udewy_slot udewy_global_\d+ = \{ \.obj = ", code)
    assert "udewy_backend_init" not in code

    prototype = search(r"static udewy_word udewy_fn_table_only_handler_\d+\(udewy_word arg0\);", code)
    assert prototype is not None
    assert prototype.start() < table.start()


def test_c_mutable_address_initialized_globals() -> None:
    if which("cc") is None:
        pytest.skip("cc not available")

    source = """
const text:int = "ok"
let function_global:int = handler
let string_global:int = text

let handler = (value:int):>int => { return value + 1 }

let main = ():>int => {
    let fn:int = function_global
    if (@fn)(41) not=? 42 { return 1 }
    if string_global not=? text { return 2 }
    function_global = 7
    string_global = 9
    if function_global not=? 7 { return 3 }
    if string_global not=? 9 { return 4 }
    return 0
}
"""
    backend = get_backend("c")
    code = parse_udewy(source, backend)
    assert search(r"udewy_global_\d+\.w = UINT64_C\(0x0000000000000007\);", code)
    assert search(r"udewy_global_\d+\.w = UINT64_C\(0x0000000000000009\);", code)

    with TemporaryDirectory() as tmp_dir:
        output_path = backend.compile_and_link(code, "static_globals", Path(tmp_dir))
        exit_code = backend.run(output_path, [])

    assert exit_code == 0


@pytest.mark.parametrize("target", ["x86_64", "c"])
def test_static_words_runtime_and_table_only_reachability(target: str) -> None:
    if target == "x86_64" and (which("as") is None or which("ld") is None):
        pytest.skip("x86_64 toolchain not available")
    if target == "c" and which("cc") is None:
        pytest.skip("cc not available")

    backend = get_backend(target)
    code = parse_udewy(STATIC_WORDS_SOURCE, backend)
    with TemporaryDirectory() as tmp_dir:
        output_path = backend.compile_and_link(code, "static_words", Path(tmp_dir))
        exit_code = backend.run(output_path, [])

    assert exit_code == 0
