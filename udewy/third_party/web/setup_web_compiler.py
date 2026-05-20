"""Set up the build artifacts udewy programs need to drive a web playground.

Produces `artifacts/web_compiler.wasm` (the udewy bootstrap compiler packaged
as a wasm32 library that JS can drive) and `artifacts/wabt.js` (downloaded
from unpkg, pinned to a known version). The playground page imports both:

    import p"../../third_party/web/artifacts/web_compiler.wasm"
    import p"../../third_party/web/artifacts/wabt.js"

Once this script has been run, building the playground itself is just:

    python -m udewy -c --target wasm32 udewy/tests/web/playground.udewy

which writes the self-contained `__dewycache__/playground.html`.
"""

import shutil
import subprocess
import sys
from os import environ
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent.parent
ARTIFACTS_DIR = HERE / "artifacts"
WEB_COMPILER_SRC = REPO_ROOT / "udewy" / "bootstrap" / "web_compiler.udewy"

WABT_VERSION = "1.0.39"
WABT_URL = f"https://unpkg.com/wabt@{WABT_VERSION}/index.js"


def fetch_wabt(dest: Path) -> None:
    if dest.exists():
        print(f"Reusing {dest}")
        return
    print(f"Downloading {WABT_URL}")
    with urlopen(WABT_URL) as r:
        dest.write_bytes(r.read())


def build_web_compiler(dest: Path) -> None:
    env = {**environ, "PYTHONPATH": str(REPO_ROOT)}
    subprocess.run(
        [sys.executable, "-m", "udewy", "-c", "--target", "wasm32", str(WEB_COMPILER_SRC)],
        cwd=REPO_ROOT, check=True, env=env,
    )
    shutil.copy(REPO_ROOT / "__dewycache__" / "web_compiler.wasm", dest)


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    fetch_wabt(ARTIFACTS_DIR / "wabt.js")
    build_web_compiler(ARTIFACTS_DIR / "web_compiler.wasm")
    print(f"Wrote web artifacts to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
