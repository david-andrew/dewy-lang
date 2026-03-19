import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path


SDL_LINK_ARTIFACT_NAME = "libSDL3.a"
SDL_APP_ID_ENV = "SDL_APP_ID"
SDL_X11_WMCLASS_ENV = "SDL_VIDEO_X11_WMCLASS"


@dataclass(frozen=True)
class SdlDesktopLaunchInfo:
    app_id: str
    desktop_path: Path
    icon_path: Path
    env: dict[str, str]


def _normalize_app_id_component(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    if not normalized:
        normalized = "program"
    if normalized[0].isdigit():
        normalized = f"program_{normalized}"
    return normalized


def uses_sdl(link_artifacts: list[Path]) -> bool:
    return any(path.name == SDL_LINK_ARTIFACT_NAME for path in link_artifacts)


def derive_sdl_app_id(input_file: Path) -> str:
    resolved = input_file.resolve()
    name = _normalize_app_id_component(resolved.stem)
    suffix = hashlib.sha1(str(resolved).encode()).hexdigest()[:8]
    return f"dev.dewy.{name}_{suffix}"


def default_sdl_icon_source() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "assets" / "udewy_logo_128x128.png"


def prepare_sdl_desktop_launch(input_file: Path, output_path: Path) -> SdlDesktopLaunchInfo:
    app_id = derive_sdl_app_id(input_file)
    icon_path = default_sdl_icon_source().resolve()

    applications_dir = Path.home() / ".local" / "share" / "applications"
    applications_dir.mkdir(parents=True, exist_ok=True)
    desktop_path = applications_dir / f"{app_id}.desktop"
    output_path = output_path.resolve()
    desktop_path.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Version=1.0",
                f"Name={input_file.stem}",
                f"Exec=env {SDL_APP_ID_ENV}={app_id} {SDL_X11_WMCLASS_ENV}={app_id} {output_path}",
                f"Icon={icon_path}",
                "Terminal=false",
                f"StartupWMClass={app_id}",
                "Categories=Development;",
                "",
            ]
        )
    )

    env = os.environ.copy()
    env[SDL_APP_ID_ENV] = app_id
    env[SDL_X11_WMCLASS_ENV] = app_id
    return SdlDesktopLaunchInfo(app_id=app_id, desktop_path=desktop_path, icon_path=icon_path, env=env)


def apply_run_hook(
    *,
    input_file: Path | None,
    output_path: Path,
    link_artifacts: list[Path] | None,
    env: dict[str, str] | None,
) -> dict[str, str] | None:
    if input_file is None or link_artifacts is None or not uses_sdl(link_artifacts):
        return env

    launch_info = prepare_sdl_desktop_launch(input_file, output_path)
    if env is None:
        return launch_info.env

    merged_env = launch_info.env.copy()
    merged_env.update(env)
    return merged_env
