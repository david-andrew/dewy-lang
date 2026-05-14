from pathlib import Path
import subprocess
import sys

import pytest

from udewy import t0
from udewy.backend import BACKEND_NAMES


ROOT = Path(__file__).parents[2]


def test_allowed_backends_selects_first_backend_and_strips_metatags(tmp_path: Path) -> None:
    c_impl = tmp_path / "c_impl.udewy"
    c_impl.write_text("const VALUE:int = 11\n")
    wasm_impl = tmp_path / "wasm_impl.udewy"
    wasm_impl.write_text("const VALUE:int = 22\n")

    program = tmp_path / "main.udewy"
    program.write_text(
        """
$allowed_backends = ["c" "wasm32"]

if $selected_backend =? "wasm32" {
    import p"wasm_impl.udewy"
}

if $selected_backend in? ["c" "x86_64"] {
    import p"c_impl.udewy"
}

let main = ():>int => {
    return VALUE
}
"""
    )

    loaded = t0.load_program(program, known_backends=BACKEND_NAMES)

    assert loaded.selected_backend == "c"
    assert loaded.allowed_backends == ["c", "wasm32"]
    assert "const VALUE:int = 11" in loaded.source
    assert "const VALUE:int = 22" not in loaded.source
    assert "$allowed_backends" not in loaded.source
    assert "$selected_backend" not in loaded.source
    assert "import p" not in loaded.source


def test_requested_backend_controls_selected_backend_conditional_imports(tmp_path: Path) -> None:
    c_impl = tmp_path / "c_impl.udewy"
    c_impl.write_text("const VALUE:int = 11\n")
    wasm_impl = tmp_path / "wasm_impl.udewy"
    wasm_impl.write_text("const VALUE:int = 22\n")

    program = tmp_path / "main.udewy"
    program.write_text(
        """
$allowed_backends = ["c" "wasm32"]

if $selected_backend =? "wasm32" {
    import p"wasm_impl.udewy"
}

if $selected_backend in? ["c" "x86_64"] {
    import p"c_impl.udewy"
}

let main = ():>int => {
    return VALUE
}
"""
    )

    loaded = t0.load_program(
        program,
        requested_backend="wasm32",
        known_backends=BACKEND_NAMES,
    )

    assert loaded.selected_backend == "wasm32"
    assert "const VALUE:int = 22" in loaded.source
    assert "const VALUE:int = 11" not in loaded.source


def test_missing_allowed_backends_defaults_to_known_backends_for_conditions(tmp_path: Path) -> None:
    x86_impl = tmp_path / "x86_impl.udewy"
    x86_impl.write_text("const VALUE:int = 64\n")

    program = tmp_path / "main.udewy"
    program.write_text(
        """
if "x86_64" in? $allowed_backends {
    import p"x86_impl.udewy"
}

let main = ():>int => {
    return VALUE
}
"""
    )

    loaded = t0.load_program(program, known_backends=BACKEND_NAMES)

    assert loaded.selected_backend == "x86_64"
    assert loaded.allowed_backends == list(BACKEND_NAMES)
    assert "const VALUE:int = 64" in loaded.source


def test_requested_backend_must_be_allowed_by_entrypoint(tmp_path: Path) -> None:
    program = tmp_path / "main.udewy"
    program.write_text(
        """
$allowed_backends = "c"

let main = ():>int => {
    return 0
}
"""
    )

    with pytest.raises(SyntaxError, match="not allowed"):
        t0.load_program(
            program,
            requested_backend="wasm32",
            known_backends=BACKEND_NAMES,
        )


def test_imported_source_must_allow_selected_backend(tmp_path: Path) -> None:
    wasm_only = tmp_path / "wasm_only.udewy"
    wasm_only.write_text(
        """
$allowed_backends = "wasm32"

const VALUE:int = 1
"""
    )

    program = tmp_path / "main.udewy"
    program.write_text(
        """
$allowed_backends = ["c" "wasm32"]
import p"wasm_only.udewy"

let main = ():>int => {
    return VALUE
}
"""
    )

    with pytest.raises(SyntaxError, match="not allowed"):
        t0.load_program(program, known_backends=BACKEND_NAMES)


def test_allowed_backends_must_appear_before_imports(tmp_path: Path) -> None:
    library = tmp_path / "lib.udewy"
    library.write_text("const VALUE:int = 1\n")

    program = tmp_path / "main.udewy"
    program.write_text(
        """
import p"lib.udewy"
$allowed_backends = "x86_64"

let main = ():>int => {
    return VALUE
}
"""
    )

    with pytest.raises(SyntaxError, match="must appear before imports"):
        t0.load_program(program, known_backends=BACKEND_NAMES)


def test_conditional_import_blocks_reject_non_import_content(tmp_path: Path) -> None:
    program = tmp_path / "main.udewy"
    program.write_text(
        """
if $selected_backend =? "x86_64" {
    const VALUE:int = 1
}

let main = ():>int => {
    return VALUE
}
"""
    )

    with pytest.raises(SyntaxError, match="Only import directives"):
        t0.load_program(program, known_backends=BACKEND_NAMES)


def test_p0_entrypoint_uses_source_selected_backend(tmp_path: Path) -> None:
    program = tmp_path / "main.udewy"
    program.write_text(
        """
$allowed_backends = "c"

let main = ():>int => {
    return 5
}
"""
    )

    result = subprocess.run(
        [sys.executable, "-m", "udewy.p0", str(program)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "int main(int argc, char **argv)" in result.stdout
