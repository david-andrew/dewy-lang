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

let main = ():>int => {
    return VALUE + 1
}
"""
    )

    loaded = t0.load_program(program)

    assert "const VALUE:int = 41" in loaded.source
    assert "import p\"libnative.a\"" not in loaded.source
    assert loaded.link_artifacts == [str(artifact.resolve())]


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
