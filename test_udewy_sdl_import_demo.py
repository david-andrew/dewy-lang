from pathlib import Path
from tempfile import TemporaryDirectory

from udewy import p0, t0, t1
from udewy.backend import get_backend


def test_sdl_demo_collects_link_artifact() -> None:
    loaded = t0.load_program(Path("udewy/tests/demo_sdl3.udewy"))
    assert any(path.endswith("third_party/sdl/SDL3-install-wayland-render/lib64/libSDL3.a") for path in loaded.link_artifacts)
    assert any(".so" in Path(path).name for path in loaded.link_artifacts)


def test_sdl_demo_compiles_with_imported_artifact() -> None:
    backend = get_backend("x86_64")
    loaded = t0.load_program(Path("udewy/tests/demo_sdl3.udewy"))
    code = p0.parse(t1.tokenize(loaded.source), loaded.source, backend)

    with TemporaryDirectory() as tmp_dir_name:
        output_path = backend.compile_and_link(
            code,
            "demo_sdl3_test",
            Path(tmp_dir_name),
            link_artifacts=loaded.link_artifacts,
        )

    assert output_path.name == "demo_sdl3_test"


def test_sdl_opengl_demo_compiles_with_imported_artifacts() -> None:
    backend = get_backend("x86_64")
    loaded = t0.load_program(Path("udewy/tests/demo_sdl_gl_wireframe.udewy"))
    code = p0.parse(t1.tokenize(loaded.source), loaded.source, backend)

    with TemporaryDirectory() as tmp_dir_name:
        output_path = backend.compile_and_link(
            code,
            "demo_sdl_gl_wireframe_test",
            Path(tmp_dir_name),
            link_artifacts=loaded.link_artifacts,
        )

    assert output_path.name == "demo_sdl_gl_wireframe_test"
