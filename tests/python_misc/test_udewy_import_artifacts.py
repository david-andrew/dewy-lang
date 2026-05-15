from pathlib import Path

import pytest

from udewy import t0


def test_import_non_udewy_path_becomes_link_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "libnative.a"
    artifact.write_text("")

    library = tmp_path / "lib.udewy"
    library.write_text(
        """
const VALUE:int = 41
"""
    )

    program = tmp_path / "main.udewy"
    program.write_text(
        """
import p"lib.udewy"
import p"libnative.a"

let main = ():>int => {
    return VALUE + 1
}
"""
    )

    loaded = t0.load_program(program)

    assert "const VALUE:int = 41" in loaded.source
    assert "import p\"libnative.a\"" not in loaded.source
    assert loaded.link_artifacts == [str(artifact.resolve())]
    assert loaded.imported_sources == [str(library.resolve())]


def test_duplicate_imported_artifact_is_only_linked_once(tmp_path: Path) -> None:
    artifact = tmp_path / "libnative.a"
    artifact.write_text("")

    inner = tmp_path / "inner.udewy"
    inner.write_text(
        """
import p"libnative.a"

const VALUE:int = 7
"""
    )

    library = tmp_path / "lib.udewy"
    library.write_text(
        """
import p"inner.udewy"
import p"libnative.a"
"""
    )

    program = tmp_path / "main.udewy"
    program.write_text(
        """
import p"lib.udewy"

let main = ():>int => {
    return VALUE
}
"""
    )

    loaded = t0.load_program(program)

    assert "const VALUE:int = 7" in loaded.source
    assert loaded.link_artifacts == [str(artifact.resolve())]
    assert loaded.imported_sources == [str(library.resolve()), str(inner.resolve())]


def test_duplicate_imported_source_is_only_recorded_once(tmp_path: Path) -> None:
    library = tmp_path / "lib.udewy"
    library.write_text("const VALUE:int = 1\n")

    program = tmp_path / "main.udewy"
    program.write_text(
        """
import p"lib.udewy"
import p"lib.udewy"

let main = ():>int => {
    return VALUE
}
"""
    )

    loaded = t0.load_program(program)

    assert loaded.link_artifacts == []
    assert loaded.imported_sources == [str(library.resolve())]


def test_target_conditional_imports_use_selected_target(tmp_path: Path) -> None:
    c_library = tmp_path / "backend_c.udewy"
    c_library.write_text("const SELECTED:int = 7\n")
    wasm_library = tmp_path / "backend_wasm.udewy"
    wasm_library.write_text("const SELECTED:int = 9\n")

    program = tmp_path / "main.udewy"
    program.write_text(
        """
if $target =? "c" {
    import p"backend_c.udewy"
}
if $target =? "wasm32" {
    import p"backend_wasm.udewy"
}

let main = ():>int => {
    return SELECTED
}
"""
    )

    c_loaded = t0.load_program(program, target_backend="c")
    wasm_loaded = t0.load_program(program, target_backend="wasm32")

    assert "const SELECTED:int = 7" in c_loaded.source
    assert "const SELECTED:int = 9" not in c_loaded.source
    assert c_loaded.imported_sources == [str(c_library.resolve())]
    assert "const SELECTED:int = 9" in wasm_loaded.source
    assert "const SELECTED:int = 7" not in wasm_loaded.source
    assert wasm_loaded.imported_sources == [str(wasm_library.resolve())]


def test_supported_targets_rejects_unsupported_imported_file(tmp_path: Path) -> None:
    library = tmp_path / "wasm_only.udewy"
    library.write_text(
        """
$supported_targets = ["wasm32"]

const VALUE:int = 1
"""
    )
    program = tmp_path / "main.udewy"
    program.write_text(
        """
import p"wasm_only.udewy"

let main = ():>int => {
    return VALUE
}
"""
    )

    with pytest.raises(SyntaxError, match="supports targets: wasm32; current target is c"):
        t0.load_program(program, target_backend="c")


def test_inactive_target_branch_does_not_load_missing_import(tmp_path: Path) -> None:
    program = tmp_path / "main.udewy"
    program.write_text(
        """
if $target =? "wasm32" {
    import p"missing.udewy"
}

let main = ():>int => {
    return 0
}
"""
    )

    loaded = t0.load_program(program, target_backend="c")

    assert loaded.imported_sources == []
    assert "missing.udewy" not in loaded.source


def test_meta_warning_only_fires_in_active_target_branch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    program = tmp_path / "main.udewy"
    program.write_text(
        """
if $target =? "c" {
    $warning("active warning")
}
if $target =? "wasm32" {
    $warning("inactive warning")
}

let main = ():>int => {
    return 0
}
"""
    )

    t0.load_program(program, target_backend="c")

    stderr = capsys.readouterr().err
    assert "active warning" in stderr
    assert "inactive warning" not in stderr


def test_meta_error_only_fires_in_active_target_branch(tmp_path: Path) -> None:
    inactive_program = tmp_path / "inactive.udewy"
    inactive_program.write_text(
        """
if $target =? "wasm32" {
    $error("inactive error")
}

let main = ():>int => {
    return 0
}
"""
    )
    active_program = tmp_path / "active.udewy"
    active_program.write_text(
        """
if $target =? "c" {
    $error("active error")
}

let main = ():>int => {
    return 0
}
"""
    )

    t0.load_program(inactive_program, target_backend="c")
    with pytest.raises(SyntaxError, match="active error"):
        t0.load_program(active_program, target_backend="c")


def test_uzero_multi_unified_entrypoint_selects_target_module() -> None:
    source_path = Path("udewy/tests/uzero_multi/race.udewy")

    c_loaded = t0.load_program(source_path, target_backend="c")
    wasm_loaded = t0.load_program(source_path, target_backend="wasm32")

    assert any(path.endswith("race_sdl.udewy") for path in c_loaded.imported_sources)
    assert not any(path.endswith("race_wasm.udewy") for path in c_loaded.imported_sources)
    assert any(path.endswith("race_wasm.udewy") for path in wasm_loaded.imported_sources)
    assert not any(path.endswith("race_sdl.udewy") for path in wasm_loaded.imported_sources)
