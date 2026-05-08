from pathlib import Path
from tempfile import TemporaryDirectory

from udewy import p0, t0, t1
from udewy.backend.sdl_desktop import SDL_APP_ID_ENV, SDL_X11_WMCLASS_ENV, default_sdl_icon_source, prepare_sdl_desktop_launch
from udewy.backend import get_backend


def test_sdl_demo_collects_link_artifact() -> None:
    loaded = t0.load_program(Path("udewy/tests/demo_sdl3.udewy"))
    assert any(Path(path).name == "libSDL3.a" for path in loaded.link_artifacts)
    assert any(".so" in Path(path).name for path in loaded.link_artifacts)


def test_generated_default_icon_module_compiles() -> None:
    backend = get_backend("x86_64")
    icon_module = (Path("udewy/third_party/sdl/artifacts/default_window_icon.udewy")).resolve()
    with TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        program = tmp_dir / "generated_default_icon_module_test.udewy"
        program.write_text(
            f"""
import p"{icon_module}"

let main = ():>int => {{
    return __load_u64__(SDL_DEFAULT_WINDOW_ICON_DATA + 16)
}}
"""
        )
        loaded = t0.load_program(program)
        code = p0.parse(t1.tokenize(loaded.source), loaded.source, backend)
        output_path = backend.compile_and_link(code, "generated_default_icon_module_test", tmp_dir)
        exit_code = backend.run(output_path, [])

    assert output_path.name == "generated_default_icon_module_test"
    assert exit_code == 128


def test_prepare_sdl_desktop_launch_writes_desktop_entry(tmp_path, monkeypatch) -> None:
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    input_file = tmp_path / "demo_sdl3.udewy"
    input_file.write_text("")
    output_path = tmp_path / "__dewycache__" / "demo_sdl3"
    output_path.parent.mkdir()
    output_path.write_text("")

    launch_info = prepare_sdl_desktop_launch(input_file, output_path)

    assert launch_info.desktop_path == home_dir / ".local" / "share" / "applications" / f"{launch_info.app_id}.desktop"
    assert launch_info.desktop_path.exists()
    assert launch_info.icon_path == default_sdl_icon_source().resolve()
    assert launch_info.env[SDL_APP_ID_ENV] == launch_info.app_id
    assert launch_info.env[SDL_X11_WMCLASS_ENV] == launch_info.app_id

    desktop_text = launch_info.desktop_path.read_text()
    assert f"Exec=env {SDL_APP_ID_ENV}={launch_info.app_id} {SDL_X11_WMCLASS_ENV}={launch_info.app_id} {output_path.resolve()}" in desktop_text
    assert f"Icon={launch_info.icon_path}" in desktop_text


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


def test_sdl_opengl_neon_runner_demo_compiles_with_imported_artifacts() -> None:
    backend = get_backend("x86_64")
    loaded = t0.load_program(Path("udewy/tests/demo_sdl_gl_neon_runner.udewy"))
    code = p0.parse(t1.tokenize(loaded.source), loaded.source, backend)

    with TemporaryDirectory() as tmp_dir_name:
        output_path = backend.compile_and_link(
            code,
            "demo_sdl_gl_neon_runner_test",
            Path(tmp_dir_name),
            link_artifacts=loaded.link_artifacts,
        )

    assert output_path.name == "demo_sdl_gl_neon_runner_test"


def test_sdl_opengl_muzero_demo_compiles_with_imported_artifacts() -> None:
    backend = get_backend("x86_64")
    loaded = t0.load_program(Path("udewy/tests/demo_sdl_gl_muzero.udewy"))
    code = p0.parse(t1.tokenize(loaded.source), loaded.source, backend)

    with TemporaryDirectory() as tmp_dir_name:
        output_path = backend.compile_and_link(
            code,
            "demo_sdl_gl_muzero_test",
            Path(tmp_dir_name),
            link_artifacts=loaded.link_artifacts,
        )

    assert output_path.name == "demo_sdl_gl_muzero_test"


def test_sdl_icon_diagnostic_demo_compiles_with_imported_artifacts() -> None:
    backend = get_backend("x86_64")
    loaded = t0.load_program(Path("udewy/tests/demo_sdl_icon_diagnostic.udewy"))
    code = p0.parse(t1.tokenize(loaded.source), loaded.source, backend)

    with TemporaryDirectory() as tmp_dir_name:
        output_path = backend.compile_and_link(
            code,
            "demo_sdl_icon_diagnostic_test",
            Path(tmp_dir_name),
            link_artifacts=loaded.link_artifacts,
        )

    assert output_path.name == "demo_sdl_icon_diagnostic_test"


def test_sdl_audio_demo_compiles_with_imported_artifacts() -> None:
    backend = get_backend("x86_64")
    loaded = t0.load_program(Path("udewy/tests/demo_sdl_audio_tones.udewy"))
    code = p0.parse(t1.tokenize(loaded.source), loaded.source, backend)

    with TemporaryDirectory() as tmp_dir_name:
        output_path = backend.compile_and_link(
            code,
            "demo_sdl_audio_tones_test",
            Path(tmp_dir_name),
            link_artifacts=loaded.link_artifacts,
        )

    assert output_path.name == "demo_sdl_audio_tones_test"
