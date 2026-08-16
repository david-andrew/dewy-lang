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
    if (fn)(41) not=? 42 { return 2 }
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
        assert "static udewy_word udewy_static_" in code


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


def test_c_static_words_patch_references_before_module_initialization() -> None:
    source = """
const words:int = __static_words__(7 table_only_handler)
let runtime_global:int = seed()

let table_only_handler = (value:int):>int => { return value + 1 }
let seed = ():>int => { return 3 }
let main = ():>int => { return runtime_global }
"""
    code = parse_udewy(source, get_backend("c"))

    definition = search(
        r"static udewy_word (udewy_static_\d+)\[2\] = "
        r"\{ UINT64_C\(0x0000000000000007\), UINT64_C\(0\) \};",
        code,
    )
    assert definition is not None
    table_name = definition.group(1)
    assert f"{table_name}[1] = " in code
    assert code.rindex("udewy_backend_init();") < code.rindex("globals_init")


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
