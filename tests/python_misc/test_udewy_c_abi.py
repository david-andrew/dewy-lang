from pathlib import Path
from shutil import which
from subprocess import run

import pytest


REPO_ROOT = Path(__file__).parents[2]
PROBE_PATH = REPO_ROOT / "udewy" / "backend" / "c_abi_probe.c"


@pytest.mark.parametrize("compiler", ["cc", "clang"])
@pytest.mark.parametrize("optimization", ["-O0", "-O2"])
def test_c_abi_probe(compiler: str, optimization: str, tmp_path: Path) -> None:
    compiler_path = which(compiler)
    if compiler_path is None:
        pytest.skip(f"{compiler} not available")

    output_path = tmp_path / f"c_abi_probe_{compiler}_{optimization.removeprefix('-')}"
    compile_result = run(
        [
            compiler_path,
            "-std=c99",
            optimization,
            str(PROBE_PATH),
            "-o",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    assert compile_result.returncode == 0, compile_result.stderr

    probe_result = run([str(output_path)], capture_output=True, text=True)
    assert probe_result.returncode == 0, probe_result.stderr
    assert probe_result.stdout == "udewy C ABI probe passed\n"
