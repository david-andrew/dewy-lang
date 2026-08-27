from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tarfile


REPO_ROOT = Path(__file__).parents[2]


def _make_source_archive(path: Path) -> None:
    included = [
        REPO_ROOT / "VERSION",
        REPO_ROOT / "library" / "path.dewy",
        REPO_ROOT / "library" / "math.dewy",
        REPO_ROOT / "library" / "rational.dewy",
        REPO_ROOT / "library" / "fixed.dewy",
        REPO_ROOT / "library" / "bigint.dewy",
        REPO_ROOT / "library" / "io.dewy",
        REPO_ROOT / "library" / "reporting.dewy",
        REPO_ROOT / "library" / "units.dewy",
        REPO_ROOT / "library" / "linux" / "io.dewy",
        REPO_ROOT / "library" / "linux" / "system.dewy",
        REPO_ROOT / "assets" / "udewy_logo_128x128.png",
        *(REPO_ROOT / "dewy").rglob("*.py"),
        *(REPO_ROOT / "udewy").glob("*.py"),
        *(REPO_ROOT / "udewy" / "backend").glob("*.py"),
        REPO_ROOT / "udewy" / "third_party" / "sdl" / "desktop_launch.py",
    ]
    with tarfile.open(path, "w:gz") as archive:
        for source in included:
            relative = source.relative_to(REPO_ROOT)
            archive.add(source, arcname=Path("dewy-lang-master") / relative)
        archive.add(
            REPO_ROOT / "README.md",
            arcname=Path("dewy-lang-master") / "README.md",
        )


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


def test_installs_trimmed_python_runtime_and_caches_python_check(tmp_path: Path) -> None:
    home = tmp_path / "home"
    tools = tmp_path / "tools"
    home.mkdir()
    tools.mkdir()

    source_archive = tmp_path / "source.tar.gz"
    fake_udewy = tmp_path / "udewy"
    python_log = tmp_path / "python.log"
    _make_source_archive(source_archive)
    _write_executable(fake_udewy, "#!/bin/sh\nexit 0\n")

    _write_executable(
        tools / "curl",
        """#!/bin/sh
set -eu
output=''
url=''
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o) shift; output=$1 ;;
        http*) url=$1 ;;
    esac
    shift
done
case "$url" in
    */releases/*) cp "$FAKE_UDEWY" "$output" ;;
    *) cp "$SOURCE_ARCHIVE" "$output" ;;
esac
""",
    )
    compatible_python = shutil.which("python3")
    assert compatible_python is not None
    version_check = subprocess.run(
        [
            compatible_python,
            "-c",
            "import sys; raise SystemExit(sys.version_info < (3, 14))",
        ]
    )
    assert version_check.returncode == 0

    python_wrapper = """#!/bin/sh
set -eu
printf 'called\\n' >> "$PYTHON_LOG"
if [ "${FAKE_PYTHON_TOO_OLD:-}" = 1 ]; then
    exit 1
fi
exec "$REAL_PYTHON" "$@"
"""
    _write_executable(tools / "python3", python_wrapper)
    _write_executable(tools / "python", python_wrapper)

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "SHELL": "/bin/bash",
            "PATH": f"{tools}:{env['PATH']}",
            "FAKE_UDEWY": str(fake_udewy),
            "SOURCE_ARCHIVE": str(source_archive),
            "PYTHON_LOG": str(python_log),
            "REAL_PYTHON": compatible_python,
        }
    )
    subprocess.run(["bash", str(REPO_ROOT / "install.sh")], env=env, check=True)

    install_dir = home / ".dewy"
    runtime = install_dir / "runtime"
    assert (install_dir / "dewy").stat().st_mode & 0o111
    assert (install_dir / "udewy").stat().st_mode & 0o111
    assert (runtime / "dewy" / "__main__.py").is_file()
    assert (runtime / "udewy" / "frontend.py").is_file()
    assert (runtime / "library" / "path.dewy").is_file()
    assert (runtime / "library" / "units.dewy").is_file()
    assert (runtime / "library" / "linux" / "io.dewy").is_file()
    assert (runtime / "library" / "linux" / "system.dewy").is_file()
    assert not (runtime / "README.md").exists()
    assert not (runtime / "dewy" / "tests").exists()
    assert not (runtime / "udewy" / "stdlib").exists()

    first = subprocess.run(
        [str(install_dir / "dewy"), "--version"],
        env=env,
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    assert first.stdout.strip().startswith("dewy ")
    assert python_log.read_text().splitlines() == ["called", "called"]
    python_marker = install_dir / ".python-3.14-ok"
    assert python_marker.read_text().strip() == str(
        tools / "python3"
    )

    second = subprocess.run(
        [str(install_dir / "dewy"), "--version"],
        env=env,
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    assert second.stdout == first.stdout
    assert python_log.read_text().splitlines() == ["called", "called", "called"]

    dewy_source = tmp_path / "answer.dewy"
    dewy_source.write_text(
        """let answer:int64 = 40
answer = answer + 2
let main = ():>int64 => answer
"""
    )
    compiled = subprocess.run(
        [str(install_dir / "dewy"), str(dewy_source)],
        env=env,
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert compiled.returncode == 42

    python_marker.unlink()
    old_python_env = env | {"FAKE_PYTHON_TOO_OLD": "1"}
    rejected = subprocess.run(
        [str(install_dir / "dewy"), "--version"],
        env=old_python_env,
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert rejected.returncode == 1
    assert "requires Python 3.14 or newer" in rejected.stderr


def test_udewy_install_script_installs_only_the_binary(tmp_path: Path) -> None:
    home = tmp_path / "home"
    tools = tmp_path / "tools"
    home.mkdir()
    tools.mkdir()

    fake_udewy = tmp_path / "udewy"
    _write_executable(fake_udewy, "#!/bin/sh\necho udewy-ok\n")
    _write_executable(
        tools / "curl",
        """#!/bin/sh
set -eu
output=''
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o) shift; output=$1 ;;
    esac
    shift
done
cp "$FAKE_UDEWY" "$output"
""",
    )

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "SHELL": "/bin/bash",
            "PATH": f"{tools}:{env['PATH']}",
            "FAKE_UDEWY": str(fake_udewy),
        }
    )
    subprocess.run(["bash", str(REPO_ROOT / "udewy" / "install.sh")], env=env, check=True)

    install_dir = home / ".dewy"
    assert (install_dir / "udewy").stat().st_mode & 0o111
    assert not (install_dir / "dewy").exists()
    assert not (install_dir / "runtime").exists()
    assert str(install_dir) in (home / ".bashrc").read_text()

    ran = subprocess.run(
        [str(install_dir / "udewy")],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert ran.stdout.strip() == "udewy-ok"
