from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).parents[2]


def test_python_built_bootstrap_compiles_trivial_program_for_all_targets(tmp_path: Path) -> None:
    input_file = tmp_path / "input.udewy"
    input_file.write_text(
        "let main = ():>int => {\n"
        "    return 7\n"
        "}\n"
    )

    asm = subprocess.run(
        [
            sys.executable,
            "-m",
            "udewy.p0",
            str(ROOT / "udewy" / "bootstrap" / "main_linux_x86_64.udewy"),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    asm_path = tmp_path / "bootstrap.s"
    bootstrap_path = tmp_path / "bootstrap"
    asm_path.write_text(asm)
    subprocess.run(
        ["cc", "-nostdlib", "-no-pie", str(asm_path), "-o", str(bootstrap_path)],
        cwd=ROOT,
        check=True,
    )

    expected = {
        "x86_64": "mov $7, %rax",
        "riscv": "li a0, 7",
        "arm": "mov x0, #7",
        "wasm32": "i64.const 7",
        "c": "return 7;",
    }

    for target, snippet in expected.items():
        output_path = tmp_path / f"out.{target}"
        subprocess.run(
            [
                str(bootstrap_path),
                str(input_file),
                "-o",
                str(output_path),
                "--target",
                target,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert snippet in output_path.read_text()
