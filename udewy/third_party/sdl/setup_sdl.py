import json
import os
import re
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path


RELEASE_API_URL = "https://api.github.com/repos/libsdl-org/SDL/releases/latest"
USER_AGENT = "udewy-sdl-setup"
REQUIRED_TOOLS = ("cmake", "clang", "pkg-config")
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
    "-DSDL_AUDIO=OFF",
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


def main() -> None:
    here = Path(__file__).resolve().parent
    build_dir = here / "SDL3-build-wayland-render"
    install_dir = here / "SDL3-install-wayland-render"

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
    run(["cmake", "--build", str(build_dir), f"-j{jobs}"])
    run(["cmake", "--install", str(build_dir)])

    print()
    print("SDL3 setup complete.")
    print()
    print("Built artifact:")
    print("  SDL3-install-wayland-render/lib64/libSDL3.a")
    print()
    print("udewy import/link prelude:")
    print('import p"SDL3-install-wayland-render/lib64/libSDL3.a"')
    print("$cc_pthread")
    print("$cc_lm")
    print()
    print("Notes:")
    print("- This reproduces the working Wayland renderer-enabled SDL3 build used for the udewy SDL demo.")
    print("- The resulting artifact is a static libSDL3.a, but it still expects a usable Wayland/EGL/OpenGL stack on the host.")
    print("- If the build fails, the first thing to check is whether pkg-config can find the required Wayland, xkbcommon, libdecor, EGL, GLES, and GL development packages.")


if __name__ == "__main__":
    main()
