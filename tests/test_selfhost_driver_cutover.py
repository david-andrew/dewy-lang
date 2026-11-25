"""Run the live CLI and build pipeline against their independent frozen Jo bodies."""
import platform
import sys

from tests.selfhost_build_double import compare_builds
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_driver_cli import run
import pytest

pytestmark = pytest.mark.nightly


def test_driver_compile_twins(compiler, tmp_path, monkeypatch):
    program = tmp_path / "entry.dewy"
    program.write_text('let greeting="hello"\n$export\nspare=():>int32=>7\nmain=():>void=>printl(greeting)\n')
    flags = ((), ("--release",), ("--target", "wasm32"), ("--target", "aarch64-linux"),
             ("--target", "x86_64-windows"), ("--target", "aarch64-mac"))
    if sys.platform.startswith("linux") and platform.machine().lower() in ("x86_64", "amd64"):
        flags += (("--host-ir",),)
    results = compare_builds(compiler, tmp_path, monkeypatch, ("driver_compile",), (program,), flags=flags)
    for _, options, status, output, _, artifacts in results:
        assert status == 0
        if "--host-ir" in options:
            assert output.startswith("DEWY_HOST_IR 1\n") and "spare" in output
        else:
            assert artifacts


def test_driver_entry_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv("DEWY_CORE_LIB", str(ROOT / "lib"))
    (tmp_path / "good.dewy").write_text('main=():>void=>printl"ok"\n')
    (tmp_path / "bad.dewy").write_text('main=():>int64=>"oops"\n')
    compilers = leaf_compilers(compiler, tmp_path, ("driver_entry",))
    for arguments, status in [
        (["--version"], 0), (["--eager-bodies", "--print-lib"], 0),
        (["--skip-fns", "", "", "check", "good.dewy"], 1),
        (["check", "--obligations", "good.dewy"], 0), (["check", "bad.dewy"], 1),
        (["run", "good.dewy"], 0), (["--print-lib", "extra"], 2),
    ]:
        a, b = (run(binary, arguments, tmp_path) for binary in compilers)
        assert a == b and a[0] == status, (arguments, a, b)

    # The Windows watch-child entry is selected when the compiler itself targets Windows.
    # Build the same source to the same path so PE names and debug records also agree.
    arguments = ["build", str(ROOT / "compiler/main.jo"), "--target", "x86_64-windows", "-o", "compiler.exe"]
    images = []
    for binary in compilers:
        status, _, errors = run(binary, arguments, tmp_path)
        assert status == 0, errors
        output = tmp_path / "compiler.exe"
        images.append(output.read_bytes())
        output.unlink()
    assert images[0].startswith(b"MZ") and images[0] == images[1]
