from pathlib import Path
from os import environ
from shutil import which
import subprocess
from tempfile import TemporaryDirectory

import pytest

from udewy import p0, t0, t1
from udewy.backend import Backend, get_backend


CORE_RUNTIME_SOURCE = """
let double = (x:int):>int => {
    return x * 2
}

let choose = ():>int => {
    return double
}

let main = ():>int => {
    let fn:int = choose()
    let piped:int = 6 |> fn
    let tmp:int = __alloca__(16)
    __store__(piped tmp)
    if __load__(tmp) not=? 12 {
        return 1
    }
    if __signed_shr__(0xFFFF_FFFF_FFFF_FFF0 2) not=? 0xFFFF_FFFF_FFFF_FFFC {
        return 2
    }
    return 0
}
"""


REFERENCE_INIT_SOURCE = """
let add1 = (n:int):>int => {
    return n + 1
}

let table:int = [add1]

let main = ():>int => {
    let fn:int = __load__(table)
    return (fn)(41)
}
"""


CALLOC_EXTERN_SOURCE = """
import p"__STDLIB_MODULE__"

let main = ():>int => {
    let buf:int = calloc(2 8)
    if buf =? 0 {
        return 1
    }
    if __load__(buf) not=? 0 {
        return 2
    }
    __store__(123 buf)
    if __load__(buf) not=? 123 {
        return 3
    }
    return 0
}
"""


def parse_udewy(src: str, backend: Backend) -> str:
    toks = t1.tokenize(src)
    return p0.parse(toks, src, backend)


def cc_available() -> bool:
    return which("cc") is not None


def compile_and_run(src: str, name: str) -> tuple[str, int | None]:
    backend = get_backend("c")
    code = parse_udewy(src, backend)

    with TemporaryDirectory() as tmp_dir:
        output_path = backend.compile_and_link(code, name, Path(tmp_dir))
        exit_code = backend.run(output_path, [])

    return code, exit_code


def compile_loaded_and_run(src: str, name: str) -> tuple[str, int | None]:
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        source_path = tmp_path / f"{name}.udewy"
        source_path.write_text(src)

        backend = get_backend("c")
        loaded = t0.load_program(source_path)
        backend.set_imported_sources([Path(path) for path in loaded.imported_sources])
        code = parse_udewy(loaded.source, backend)
        output_path = backend.compile_and_link(
            code,
            name,
            tmp_path,
            imported_sources=loaded.imported_sources,
        )
        exit_code = backend.run(output_path, [])

    return code, exit_code


def test_c_backend_codegen_includes_minimal_runtime() -> None:
    backend = get_backend("c")
    code = parse_udewy("let main = ():>int => { return 42 }", backend)

    assert "typedef uint64_t udewy_word;" in code
    assert "static udewy_word udewy_fn_main_" in code
    assert "#define UDEWY_ALLOCA(size)" not in code
    assert "static udewy_word udewy_bool_from_c(int cond)" not in code
    assert "_ud_v" not in code
    assert "_ud_saved" not in code
    assert "_ud_tmp" not in code
    assert "#include <string.h>" not in code
    assert "int main(int argc, char **argv)" in code


def test_c_backend_emits_helpers_on_demand() -> None:
    backend = get_backend("c")
    code = parse_udewy(
        "let main = ():>int => { let p:int = __alloca__(8) __store__(1 p) return __load__(p) }",
        backend,
    )

    assert "#define UDEWY_ALLOCA(size)" in code
    assert "UDEWY_ALLOCA((size_t)" in code
    assert "static udewy_word udewy_alloca_bytes" not in code
    assert "static udewy_word udewy_load_u64(udewy_word addr)" in code
    assert "static udewy_word udewy_store_u64(udewy_word value, udewy_word addr)" in code
    assert "_ud_v" not in code
    assert "_ud_saved" not in code
    assert "_ud_tmp" not in code
    assert "memcpy" not in code


def test_c_import_metadata_is_preserved() -> None:
    with TemporaryDirectory() as tmp_dir:
        source_path = Path(tmp_dir) / "imports.udewy"
        source_path.write_text(
            f'import p"{Path("udewy/third_party/c/stdio.udewy").resolve()}"\n'
            "let main = ():>int => { return 0 }\n"
        )

        loaded = t0.load_program(source_path)

    assert [Path(path).name for path in loaded.imported_sources] == [
        "stdio.udewy",
        "hosted.udewy",
    ]


def test_c_backend_uses_imported_stdlib_capability() -> None:
    with TemporaryDirectory() as tmp_dir:
        source_path = Path(tmp_dir) / "stdlib_import.udewy"
        source_path.write_text(
            f'import p"{Path("udewy/third_party/c/stdlib.udewy").resolve()}"\n'
            "let main = ():>int => { let buf:int = calloc(1 8) return buf =? 0 }\n"
        )

        backend = get_backend("c")
        loaded = t0.load_program(source_path)
        backend.set_imported_sources([Path(path) for path in loaded.imported_sources])
        code = parse_udewy(loaded.source, backend)

    assert "#include <stdlib.h>" in code
    assert "static udewy_word udewy_c_stdlib_calloc" in code
    assert "extern void calloc(void);" not in code


def test_c_backend_supports_mixed_extern_codegen() -> None:
    backend = get_backend("c")
    code = parse_udewy(
        """
let glClearColor = (r:int g:int b:int a:int):>void => extern

let main = ():>int => {
    __call_extern_mixed_4__(
        glClearColor
        1 __i64_to_f32_bits__(1)
        1 __i64_to_f32_bits__(2)
        1 __i64_to_f32_bits__(3)
        1 __i64_to_f32_bits__(4)
    )
    return 0
}
""",
        backend,
    )

    assert "static udewy_word udewy_i64_to_f32_bits(udewy_word value)" in code
    assert "static float udewy_f32_from_bits(udewy_word value)" in code
    assert "udewy_f32_from_bits" in code
    assert "float, float, float, float" in code


def test_c_backend_direct_extern_calls_use_raw_prototypes() -> None:
    backend = get_backend("c")
    code = parse_udewy(
        """
let raw_extern = (value:int):>int => extern

let main = ():>int => {
    return raw_extern(3)
}
""",
        backend,
    )

    assert "extern udewy_word raw_extern(udewy_word arg0);" in code
    assert "raw_extern(UINT64_C(0x0000000000000003))" in code
    assert "(&raw_extern)" not in code


def test_c_backend_exposes_no_builtin_constants() -> None:
    backend = get_backend("c")
    assert backend.get_builtin_constants() == {}


@pytest.mark.skipif(not cc_available(), reason="cc not available")
def test_c_backend_runs_core_runtime_features() -> None:
    _, exit_code = compile_and_run(CORE_RUNTIME_SOURCE, "core_runtime")
    assert exit_code == 0


@pytest.mark.skipif(not cc_available(), reason="cc not available")
def test_c_backend_initializes_reference_data_before_main() -> None:
    _, exit_code = compile_and_run(REFERENCE_INIT_SOURCE, "reference_init")
    assert exit_code == 42


@pytest.mark.skipif(not cc_available(), reason="cc not available")
def test_c_backend_supports_libc_extern_calls() -> None:
    _, exit_code = compile_loaded_and_run(
        CALLOC_EXTERN_SOURCE.replace(
            "__STDLIB_MODULE__",
            str(Path("udewy/third_party/c/stdlib.udewy").resolve()),
        ),
        "calloc_extern",
    )
    assert exit_code == 0


@pytest.mark.skipif(not cc_available(), reason="cc not available")
def test_c_backend_runs_mixed_extern_call() -> None:
    c_source = """
long mix_value(float a, long b, double c, float d) {
    return (long)a + (b * 10) + ((long)c * 100) + ((long)d * 1000);
}
"""
    src = """
let mix_value = (a:int b:int c:int d:int):>int => extern

let main = ():>int => {
    return __call_extern_mixed_4__(
        mix_value
        1 __i64_to_f32_bits__(2)
        0 3
        2 __i64_to_f64_bits__(4)
        1 __i64_to_f32_bits__(5)
    )
}
"""
    backend = get_backend("c")
    code = parse_udewy(src, backend)

    with TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        c_path = tmp_dir / "mixed.c"
        obj_path = tmp_dir / "mixed.o"
        c_path.write_text(c_source)
        subprocess.run(
            ["cc", "-c", str(c_path), "-o", str(obj_path)],
            check=True,
            env=environ | {"CCACHE_DISABLE": "1"},
        )

        output_path = backend.compile_and_link(
            code,
            "mixed_extern_c",
            tmp_dir,
            link_artifacts=[str(obj_path)],
        )
        exit_code = backend.run(output_path, [])

    assert exit_code == 56


def test_c_backend_parses_sdl_wrapper_without_source_changes() -> None:
    source_path = Path("udewy/tests/uzero_multi/race_sdl.udewy")
    backend = get_backend("c")
    loaded = t0.load_program(source_path)
    backend.set_imported_sources([Path(path) for path in loaded.imported_sources])
    code = parse_udewy(loaded.source, backend)

    assert "udewy_f32_from_bits" in code
    assert "udewy_i64_to_f64_bits" in code
    assert "udewy_fn_backend_init_" in code


@pytest.mark.skipif(not cc_available(), reason="cc not available")
def test_c_backend_builds_sdl_demo_when_artifacts_are_available() -> None:
    source_path = Path("udewy/tests/uzero_multi/race_sdl.udewy")
    loaded = t0.load_program(source_path)
    missing = [path for path in loaded.link_artifacts if not Path(path).exists()]
    if missing:
        pytest.skip("SDL link artifacts unavailable")

    backend = get_backend("c")
    backend.set_imported_sources([Path(path) for path in loaded.imported_sources])
    code = parse_udewy(loaded.source, backend)

    with TemporaryDirectory() as tmp_dir_name:
        output_path = backend.compile_and_link(
            code,
            "race_sdl_c",
            Path(tmp_dir_name),
            link_artifacts=loaded.link_artifacts,
            imported_sources=loaded.imported_sources,
        )

    assert output_path.name == "race_sdl_c"
