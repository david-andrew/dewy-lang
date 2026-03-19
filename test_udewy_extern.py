from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import subprocess

import pytest

from udewy import p0, t1
from udewy.backend import Backend, BackendName, get_backend


NATIVE_TARGETS: list[BackendName] = ["x86_64", "riscv", "arm"]

EXTERN_SOURCE = """
let triple = (x:int):>int => extern
let ext_value:int = extern

let main = ():>int => {
    return triple(ext_value)
}
"""


def parse_udewy(src: str, backend: Backend) -> str:
    toks = t1.tokenize(src)
    return p0.parse(toks, src, backend)


@pytest.mark.parametrize("target", NATIVE_TARGETS)
def test_extern_function_and_global_codegen(target: BackendName) -> None:
    backend = get_backend(target)
    code = parse_udewy(EXTERN_SOURCE, backend)

    assert ".extern triple" in code
    assert ".extern ext_value" in code


@pytest.mark.parametrize("target", NATIVE_TARGETS)
def test_named_symbols_use_distinct_backend_ids(target: BackendName) -> None:
    backend = get_backend(target)

    foo_id = backend.declare_function("foo", 0)
    bar_id = backend.declare_function("bar", 0)

    assert foo_id != bar_id
    assert backend.function_ref(foo_id) == "foo"
    assert backend.function_ref(bar_id) == "bar"

    first_global_id = backend.define_global("first_global", 1)
    second_global_id = backend.define_global("second_global", 2)

    assert first_global_id != second_global_id
    assert getattr(backend, "_global_labels")[first_global_id] == "first_global"
    assert getattr(backend, "_global_labels")[second_global_id] == "second_global"


def test_extern_is_top_level_only() -> None:
    src = """
let main = ():>int => {
    let ext:int = extern
    return ext
}
"""

    with pytest.raises(SyntaxError, match=r"`extern` declarations are only allowed at top level"):
        parse_udewy(src, get_backend("x86_64"))


def test_wasm_rejects_extern_declarations() -> None:
    with pytest.raises(RuntimeError, match=r"extern functions are not supported on the wasm32 backend"):
        parse_udewy(EXTERN_SOURCE, get_backend("wasm32"))


def test_x86_64_can_link_extern_artifact() -> None:
    if which("cc") is None or which("as") is None or which("ld") is None:
        pytest.skip("x86_64 artifact-link toolchain not available")

    c_source = """
long ext_value = 7;

long triple(long x) {
    return x * 3;
}
"""

    backend = get_backend("x86_64")
    code = parse_udewy(EXTERN_SOURCE, backend)
    recorded_commands: list[str] = []
    real_run = subprocess.run

    def recording_run(command: list[str], *args, **kwargs):
        recorded_commands.append(Path(command[0]).name)
        return real_run(command, *args, **kwargs)

    with TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        c_path = tmp_dir / "externs.c"
        obj_path = tmp_dir / "externs.o"
        c_path.write_text(c_source)
        subprocess.run(["cc", "-c", str(c_path), "-o", str(obj_path)], check=True)

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(subprocess, "run", recording_run)
            output_path = backend.compile_and_link(code, "extern_demo", tmp_dir, link_artifacts=[str(obj_path)])
        exit_code = backend.run(output_path, [])

    assert exit_code == 21
    assert "clang" not in recorded_commands
    assert recorded_commands[:2] == ["as", "ld"]


def test_x86_64_can_link_shared_library_artifact() -> None:
    if which("cc") is None or which("as") is None or which("ld") is None:
        pytest.skip("x86_64 shared-library link toolchain not available")

    libc_candidates = [Path("/usr/lib64/libc.so.6"), Path("/lib64/libc.so.6")]
    libc_path = next((path for path in libc_candidates if path.exists()), None)
    if libc_path is None:
        pytest.skip("shared libc not available")

    c_source = """
long call_strlen(void);

long call_strlen(void) {
    extern unsigned long strlen(const char *);
    return (long)strlen("abcd");
}
"""

    backend = get_backend("x86_64")
    code = parse_udewy(
        """
let call_strlen = ():>int => extern

let main = ():>int => {
    return call_strlen()
}
""",
        backend,
    )
    recorded_commands: list[str] = []
    real_run = subprocess.run

    def recording_run(command: list[str], *args, **kwargs):
        recorded_commands.append(Path(command[0]).name)
        return real_run(command, *args, **kwargs)

    with TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        c_path = tmp_dir / "externs.c"
        obj_path = tmp_dir / "externs.o"
        c_path.write_text(c_source)
        subprocess.run(["cc", "-c", str(c_path), "-o", str(obj_path)], check=True)

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(subprocess, "run", recording_run)
            output_path = backend.compile_and_link(
                code,
                "extern_shared_demo",
                tmp_dir,
                link_artifacts=[str(obj_path), str(libc_path)],
            )
        exit_code = backend.run(output_path, [])

    assert exit_code == 4
    assert "clang" not in recorded_commands
    assert recorded_commands[:2] == ["as", "ld"]
