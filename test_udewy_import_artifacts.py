from pathlib import Path

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
$cc_pthread
$cc_lm

let main = ():>int => {
    return VALUE + 1
}
"""
    )

    loaded = t0.load_program(program)

    assert "const VALUE:int = 41" in loaded.source
    assert "import p\"libnative.a\"" not in loaded.source
    assert "$cc_pthread" not in loaded.source
    assert "$cc_lm" not in loaded.source
    assert loaded.link_artifacts == [str(artifact.resolve())]
    assert loaded.link_flags == ["-pthread", "-lm"]


def test_unknown_meta_directive_is_rejected(tmp_path: Path) -> None:
    program = tmp_path / "main.udewy"
    program.write_text(
        """
$cc_not_real

let main = ():>int => {
    return 0
}
"""
    )

    try:
        t0.load_program(program)
    except SyntaxError as exc:
        assert "Unknown udewy meta directive $cc_not_real" in str(exc)
    else:
        raise AssertionError("expected unknown meta directive to raise SyntaxError")


def test_meta_directives_and_imports_can_be_interleaved(tmp_path: Path) -> None:
    artifact = tmp_path / "libnative.a"
    artifact.write_text("")

    library = tmp_path / "lib.udewy"
    library.write_text(
        """
const VALUE:int = 7
"""
    )

    program = tmp_path / "main.udewy"
    program.write_text(
        """
$cc_lm
import p"libnative.a"
import p"lib.udewy"
$cc_pthread

let main = ():>int => {
    return VALUE
}
"""
    )

    loaded = t0.load_program(program)

    assert "const VALUE:int = 7" in loaded.source
    assert loaded.link_artifacts == [str(artifact.resolve())]
    assert loaded.link_flags == ["-lm", "-pthread"]
