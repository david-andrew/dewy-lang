import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

from generate_udewy_icon import generate_icon_module


RELEASE_API_URL = "https://api.github.com/repos/libsdl-org/SDL/releases/latest"
USER_AGENT = "udewy-sdl-setup"
REQUIRED_TOOLS = ("clang", "cmake", "ld", "pkg-config")
REQUIRED_PACKAGES = (
    "wayland-client",
    "wayland-cursor",
    "wayland-egl",
    "xkbcommon",
    "libdecor-0",
    "egl",
    "glesv2",
    "gl",
)
OPTIONAL_SHARED_PACKAGES = (
    "gbm",
    "libdrm",
)
BUNDLE_DIR_NAME = "artifacts"
BUNDLE_LINK_NAME = "link.udewy"
DEFAULT_ICON_MODULE_NAME = "default_window_icon.udewy"
DEFAULT_ICON_SYMBOL_NAME = "SDL_DEFAULT_WINDOW_ICON_DATA"
CMAKE_FLAGS = (
    "-DCMAKE_BUILD_TYPE=Release",
    "-DCMAKE_C_COMPILER=clang",
    "-DSDL_SHARED=OFF",
    "-DSDL_STATIC=ON",
    "-DSDL_TEST_LIBRARY=OFF",
    "-DSDL_TESTS=OFF",
    "-DSDL_EXAMPLES=OFF",
    "-DSDL_DOCS=OFF",
    "-DSDL_DISABLE_INSTALL_DOCS=ON",
    "-DSDL_UNINSTALL=OFF",
    "-DSDL_WAYLAND=ON",
    "-DSDL_X11=OFF",
    "-DSDL_OPENGL=ON",
    "-DSDL_OPENGLES=ON",
    "-DSDL_VULKAN=OFF",
    "-DSDL_GPU=OFF",
    "-DSDL_RENDER=ON",
    "-DSDL_RENDER_VULKAN=OFF",
    "-DSDL_AUDIO=ON",
    "-DSDL_JOYSTICK=OFF",
    "-DSDL_HAPTIC=OFF",
    "-DSDL_HIDAPI=OFF",
    "-DSDL_POWER=OFF",
    "-DSDL_SENSOR=OFF",
    "-DSDL_CAMERA=OFF",
    "-DSDL_DBUS=OFF",
    "-DSDL_IBUS=OFF",
    "-DSDL_FCITX=OFF",
    "-DSDL_UNIX_CONSOLE_BUILD=OFF",
)


def discover_latest_sdl3_release() -> tuple[str, str, str]:
    request = urllib.request.Request(
        RELEASE_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request) as response:
        data = json.load(response)

    for asset in data.get("assets", []):
        name = asset["name"]
        if re.fullmatch(r"SDL3-\d+\.\d+\.\d+\.tar\.gz", name):
            return name[:-7], asset["browser_download_url"], name

    raise RuntimeError("Could not find the latest SDL3 source tarball in the official release assets")


def require_tools() -> None:
    missing = [tool for tool in REQUIRED_TOOLS if shutil.which(tool) is None]
    if missing:
        raise RuntimeError(f"Missing required tools: {' '.join(missing)}")


def prepend_pkg_config_path(path: Path) -> None:
    if not path.is_dir():
        return
    existing = os.environ.get("PKG_CONFIG_PATH", "")
    if existing:
        os.environ["PKG_CONFIG_PATH"] = f"{path}:{existing}"
    else:
        os.environ["PKG_CONFIG_PATH"] = str(path)


def configure_pkg_config_path() -> None:
    brew = shutil.which("brew")
    if brew is None:
        return

    brew_prefix = subprocess.run(
        [brew, "--prefix"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    prefix = Path(brew_prefix)
    prepend_pkg_config_path(prefix / "lib" / "pkgconfig")
    prepend_pkg_config_path(prefix / "share" / "pkgconfig")


def check_pkg_config_deps() -> None:
    missing: list[str] = []
    for package in REQUIRED_PACKAGES:
        result = subprocess.run(
            ["pkg-config", "--exists", package],
            check=False,
        )
        if result.returncode != 0:
            missing.append(package)

    if not missing:
        return

    message = [
        f"Missing pkg-config packages: {' '.join(missing)}",
        "",
        "This setup reproduces the working udewy SDL3 Wayland build.",
        "",
        "Expected tools:",
        "  cmake",
        "  clang",
        "  ld",
        "  pkg-config",
        "",
        "Expected development libraries visible through pkg-config:",
        "  wayland-client",
        "  wayland-cursor",
        "  wayland-egl",
        "  xkbcommon",
        "  libdecor-0",
        "  egl",
        "  glesv2",
        "  gl",
        "",
        "On Homebrew-based setups this usually means:",
        "  brew install pkg-config wayland libxkbcommon libdecor mesa",
        "",
        "If pkg-config still cannot see them, make sure PKG_CONFIG_PATH includes:",
        "  $(brew --prefix)/lib/pkgconfig",
        "  $(brew --prefix)/share/pkgconfig",
    ]
    raise RuntimeError("\n".join(message))


def download_archive(url: str, destination: Path) -> None:
    print(f"Downloading {url}")
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ) as response:
        destination.write_bytes(response.read())


def extract_archive(archive_path: Path, destination_dir: Path) -> None:
    print(f"Extracting {archive_path.name}")
    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(destination_dir)


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


# Written at CMake configure time; not the same as per-config SDL_build_config.h under include-config-*/.
_SDL_BUILD_CONFIG_INTERMEDIATE = Path("CMakeFiles") / "SDL_build_config.h.intermediate"

# Playback-capable drivers (exclude DUMMY / DISK and *_DYNAMIC lines).
_SDL_REAL_AUDIO_DRIVER_MACROS = (
    "SDL_AUDIO_DRIVER_ALSA",
    "SDL_AUDIO_DRIVER_PIPEWIRE",
    "SDL_AUDIO_DRIVER_PULSEAUDIO",
    "SDL_AUDIO_DRIVER_JACK",
    "SDL_AUDIO_DRIVER_SNDIO",
    "SDL_AUDIO_DRIVER_OSS",
)


def assert_sdl_real_audio_backend_configured(build_dir: Path) -> None:
    header = build_dir / _SDL_BUILD_CONFIG_INTERMEDIATE
    if not header.is_file():
        raise RuntimeError(
            f"Expected SDL build config header after configure (SDL version mismatch?): {header}"
        )

    text = header.read_text()
    for macro in _SDL_REAL_AUDIO_DRIVER_MACROS:
        if re.search(rf"^#define {macro}\s+1\s*$", text, re.MULTILINE):
            return

    raise RuntimeError(
        "SDL3 configured with -DSDL_AUDIO=ON but no playback audio driver was enabled in "
        f"{_SDL_BUILD_CONFIG_INTERMEDIATE.as_posix()} (only CMake warnings, e.g. missing ALSA). "
        "Install dev packages for at least one of: ALSA, PipeWire, PulseAudio, JACK, sndio, or OSS "
        "(e.g. Fedora: alsa-lib-devel; Debian: libasound2-dev)."
    )


def run_capture(command: list[str], *, cwd: Path | None = None) -> str:
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def configured_pkg_config_env(install_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    install_pkgconfig_dirs: list[Path] = []
    for candidate in (
        install_dir / "lib64" / "pkgconfig",
        install_dir / "lib" / "pkgconfig",
        install_dir / "share" / "pkgconfig",
    ):
        if candidate.is_dir() and candidate not in install_pkgconfig_dirs:
            install_pkgconfig_dirs.append(candidate)

    for pc_file in install_dir.rglob("*.pc"):
        pc_dir = pc_file.parent
        if pc_dir not in install_pkgconfig_dirs:
            install_pkgconfig_dirs.append(pc_dir)

    existing = env.get("PKG_CONFIG_PATH", "")
    joined_install_dirs = ":".join(str(path) for path in install_pkgconfig_dirs)
    if joined_install_dirs and existing:
        env["PKG_CONFIG_PATH"] = f"{joined_install_dirs}:{existing}"
    elif joined_install_dirs:
        env["PKG_CONFIG_PATH"] = joined_install_dirs
    elif existing:
        env["PKG_CONFIG_PATH"] = existing
    return env


def pkg_config_exists(package: str, *, env: dict[str, str]) -> bool:
    result = subprocess.run(["pkg-config", "--exists", package], env=env, check=False)
    return result.returncode == 0


def pkg_config_libs(package: str, *, env: dict[str, str], static: bool) -> list[str]:
    command = ["pkg-config"]
    if static:
        command.append("--static")
    command.extend(["--libs", package])
    output = subprocess.run(
        command,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return shlex.split(output)


def pkg_config_variable(package: str, variable: str, *, env: dict[str, str]) -> str:
    return subprocess.run(
        ["pkg-config", f"--variable={variable}", package],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def default_library_search_dirs() -> list[Path]:
    output = run_capture(["ld", "--verbose"])
    search_dirs: list[Path] = []
    for match in re.finditer(r'SEARCH_DIR\("=([^"]+)"\)', output):
        path = Path(match.group(1))
        if path not in search_dirs:
            search_dirs.append(path)
    return search_dirs


def resolve_shared_library_path(library_stem: str, search_dirs: list[Path]) -> Path | None:
    for directory in search_dirs:
        exact = directory / f"{library_stem}.so"
        if exact.exists():
            return exact.resolve()
        matches = sorted(directory.glob(f"{library_stem}.so*"))
        if matches:
            return matches[0].resolve()

    return None


def collect_link_artifacts(install_dir: Path) -> list[Path]:
    env = configured_pkg_config_env(install_dir)
    sdl_libdir = Path(pkg_config_variable("sdl3", "libdir", env=env))
    tokens = pkg_config_libs("sdl3", env=env, static=True)
    for package in REQUIRED_PACKAGES:
        tokens.extend(pkg_config_libs(package, env=env, static=False))
    for package in OPTIONAL_SHARED_PACKAGES:
        if pkg_config_exists(package, env=env):
            tokens.extend(pkg_config_libs(package, env=env, static=False))
    tokens.extend(["-lc", "-lm", "-ldl", "-lpthread", "-lrt"])

    search_dirs = [sdl_libdir, *default_library_search_dirs()]
    artifacts: list[Path] = [sdl_libdir / "libSDL3.a"]
    seen: set[Path] = set()
    missing_shared: list[str] = []

    def add_artifact(path: Path) -> None:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            artifacts.append(resolved)

    for token in tokens:
        if token == "-pthread":
            token = "-lpthread"

        if token.startswith("-L"):
            search_dir = Path(token[2:]).resolve()
            if search_dir not in search_dirs:
                search_dirs.insert(0, search_dir)
            continue

        if token.startswith("-l"):
            if token == "-lSDL3":
                continue
            shared_path = resolve_shared_library_path(f"lib{token[2:]}", search_dirs)
            if shared_path is None:
                missing_name = f"lib{token[2:]}.so"
                if missing_name not in missing_shared:
                    missing_shared.append(missing_name)
                continue
            add_artifact(shared_path)
            continue

        if ".so" in token:
            shared_path = Path(token)
            if not shared_path.is_absolute():
                shared_path = (install_dir / shared_path).resolve()
            if not shared_path.exists():
                raise RuntimeError(f"Shared library not found: {shared_path}")
            add_artifact(shared_path)
            continue

        raise RuntimeError(f"Unsupported pkg-config linker token: {token}")

    if missing_shared:
        raise RuntimeError(
            "Could not resolve the shared-library inputs needed for the SDL udewy link bundle. "
            f"Missing shared libraries: {' '.join(missing_shared)}"
        )

    return artifacts


def write_link_bundle(bundle_link: Path, link_artifacts: list[Path]) -> None:
    bundle_link.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    source_dir = bundle_link.parent
    for artifact in link_artifacts:
        if artifact.is_relative_to(source_dir.parent):
            import_path = os.path.relpath(artifact, source_dir)
        else:
            import_path = str(artifact)
        lines.append(f'import p"{import_path}"')
    bundle_link.write_text("\n".join(lines) + "\n")


def stage_bundle_artifacts(bundle_dir: Path, install_dir: Path, link_artifacts: list[Path]) -> list[Path]:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    staged_artifacts: list[Path] = []
    install_dir = install_dir.resolve()
    for artifact in link_artifacts:
        artifact = artifact.resolve()
        if artifact.is_relative_to(install_dir):
            staged_artifact = bundle_dir / artifact.name
            shutil.copy2(artifact, staged_artifact)
            staged_artifacts.append(staged_artifact)
            continue
        staged_artifacts.append(artifact)
    return staged_artifacts


def remove_intermediate_results(*, archive_path: Path, source_dir: Path, build_dir: Path, install_dir: Path) -> None:
    archive_path.unlink(missing_ok=True)
    shutil.rmtree(source_dir, ignore_errors=True)
    shutil.rmtree(build_dir, ignore_errors=True)
    shutil.rmtree(install_dir, ignore_errors=True)


def write_default_icon_module(bundle_dir: Path, root_dir: Path) -> Path:
    return generate_icon_module(
        root_dir / "assets" / "udewy_logo_128x128.png",
        bundle_dir / DEFAULT_ICON_MODULE_NAME,
        symbol_name=DEFAULT_ICON_SYMBOL_NAME,
    )


def main() -> None:
    here = Path(__file__).resolve().parent
    root_dir = here.parent.parent.parent
    build_dir = here / "SDL3-build-wayland-render"
    install_dir = here / "SDL3-install-wayland-render"
    bundle_dir = here / BUNDLE_DIR_NAME
    bundle_link = bundle_dir / BUNDLE_LINK_NAME

    require_tools()
    configure_pkg_config_path()
    check_pkg_config_deps()

    release_dir_name, archive_url, archive_name = discover_latest_sdl3_release()
    archive_path = here / archive_name
    source_dir = here / release_dir_name

    if not archive_path.exists():
        download_archive(archive_url, archive_path)
    else:
        print(f"Reusing {archive_path.name}")

    if not source_dir.exists():
        extract_archive(archive_path, here)
    else:
        print(f"Reusing extracted source {source_dir.name}")

    shutil.rmtree(build_dir, ignore_errors=True)
    shutil.rmtree(install_dir, ignore_errors=True)
    shutil.rmtree(bundle_dir, ignore_errors=True)

    jobs = os.cpu_count() or 4
    run(
        [
            "cmake",
            "-S",
            str(source_dir),
            "-B",
            str(build_dir),
            f"-DCMAKE_INSTALL_PREFIX={install_dir}",
            *CMAKE_FLAGS,
        ]
    )
    assert_sdl_real_audio_backend_configured(build_dir)
    run(["cmake", "--build", str(build_dir), f"-j{jobs}"])
    run(["cmake", "--install", str(build_dir)])
    staged_link_artifacts = stage_bundle_artifacts(
        bundle_dir,
        install_dir,
        collect_link_artifacts(install_dir),
    )
    write_default_icon_module(bundle_dir, root_dir)
    write_link_bundle(bundle_link, staged_link_artifacts)
    remove_intermediate_results(
        archive_path=archive_path,
        source_dir=source_dir,
        build_dir=build_dir,
        install_dir=install_dir,
    )

    print()
    print("SDL3 setup complete.")
    print()
    print("Built artifacts:")
    print(f"  {BUNDLE_DIR_NAME}/libSDL3.a")
    print(f"  {BUNDLE_DIR_NAME}/{BUNDLE_LINK_NAME}")
    print(f"  {BUNDLE_DIR_NAME}/{DEFAULT_ICON_MODULE_NAME}")
    print()
    print("udewy import prelude:")
    print(f'import p"{BUNDLE_DIR_NAME}/{BUNDLE_LINK_NAME}"')
    print()
    print("Notes:")
    print("- The final udewy step still uses as/ld only.")
    print("- SDL itself is linked from the local static libSDL3.a, while its transitive graphics/runtime dependencies are linked as shared libraries available on this machine.")
    print("- The generated bundle is a plain udewy import wrapper, not a custom manifest format.")


if __name__ == "__main__":
    main()
