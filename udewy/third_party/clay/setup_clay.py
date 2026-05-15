import shutil
import subprocess
import urllib.request
from pathlib import Path


CLAY_HEADER_URL = "https://raw.githubusercontent.com/nicbarker/clay/main/clay.h"
USER_AGENT = "udewy-clay-setup"
ARTIFACTS_DIR_NAME = "artifacts"
NATIVE_OBJECT_NAME = "udewy_clay.o"
WASM_MODULE_NAME = "udewy_clay.wasm"
WASM_HOST_SOURCE_NAME = "wasm_host.js"
WASM_HOST_ARTIFACT_NAME = "udewy_clay_host.js"
LINK_NATIVE_NAME = "link_native.udewy"
LINK_WASM_NAME = "link_wasm.udewy"


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Missing required tool: {name}")


def download_clay_header(header_path: Path) -> None:
    if header_path.exists():
        print(f"Reusing {header_path}")
        return

    request = urllib.request.Request(
        CLAY_HEADER_URL,
        headers={"User-Agent": USER_AGENT},
    )
    print(f"Downloading {CLAY_HEADER_URL}")
    with urllib.request.urlopen(request) as response:
        header_path.write_bytes(response.read())


def run(command: list[str]) -> None:
    print(" ".join(command))
    subprocess.run(command, check=True)


def write_link_bundle(path: Path, artifact_names: list[str]) -> None:
    path.write_text("".join(f'import p"{name}"\n' for name in artifact_names))


def main() -> None:
    here = Path(__file__).resolve().parent
    artifacts_dir = here / ARTIFACTS_DIR_NAME
    header_path = here / "clay.h"
    shim_path = here / "udewy_clay.c"

    require_tool("clang")
    download_clay_header(header_path)

    shutil.rmtree(artifacts_dir, ignore_errors=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    native_object = artifacts_dir / NATIVE_OBJECT_NAME
    run(
        [
            "clang",
            "-std=c99",
            "-O2",
            "-ffunction-sections",
            "-fdata-sections",
            "-c",
            str(shim_path),
            "-o",
            str(native_object),
        ]
    )

    wasm_artifacts: list[str] = [WASM_HOST_ARTIFACT_NAME]
    wasm_module = artifacts_dir / WASM_MODULE_NAME
    try:
        run(
            [
                "clang",
                "--target=wasm32",
                "-std=c99",
                "-Oz",
                "-nostdlib",
                "-ffunction-sections",
                "-fdata-sections",
                str(shim_path),
                "-Wl,--no-entry",
                "-Wl,--export-all",
                "-o",
                str(wasm_module),
            ]
        )
        wasm_artifacts.append(WASM_MODULE_NAME)
    except subprocess.CalledProcessError:
        print("Could not build the Clay wasm side module; wasm demos will use the JS rectangle-layout fallback.")

    shutil.copy2(here / WASM_HOST_SOURCE_NAME, artifacts_dir / WASM_HOST_ARTIFACT_NAME)
    write_link_bundle(artifacts_dir / LINK_NATIVE_NAME, [NATIVE_OBJECT_NAME])
    write_link_bundle(artifacts_dir / LINK_WASM_NAME, wasm_artifacts)

    print(f"Wrote Clay artifacts to {artifacts_dir}")


if __name__ == "__main__":
    main()
