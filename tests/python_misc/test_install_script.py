"""Published native pairs install together without invoking Python."""
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / 'install.sh'


def executable(path, body):
    path.write_text(body)
    path.chmod(0o755)


def release_archive(folder, archive, *, broken=False):
    folder.mkdir()
    executable(folder / 'dewy', '#!/bin/sh\nprintf "dewy native fixture\\n"\n')
    executable(folder / 'udewy', '#!/bin/sh\nprintf "udewy fixture\\n"\n')
    for name in ('VERSION', 'library/path.dewy', 'library/unicode/grapheme_break.bin',
                 'tools/dewy_gdb.py', 'tools/dewy_lldb.py', 'udewy-stdlib/linux.udewy'):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture\n')
    files = sorted(path for path in folder.rglob('*') if path.is_file())
    (folder / 'SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(folder)}\n'
        for path in files))
    if broken:
        (folder / 'VERSION').write_text('corrupted\n')
    with tarfile.open(archive, 'w:gz') as packed:
        for path in folder.rglob('*'):
            packed.add(path, arcname=str(path.relative_to(folder)), recursive=False)


def environment(tmp_path):
    home = tmp_path / 'home'
    fake = tmp_path / 'tools'
    home.mkdir()
    fake.mkdir()
    executable(fake / 'curl', '''#!/bin/sh
set -eu
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o) shift; output=$1 ;;
        https:*) printf '%s\n' "$1" >> "$DOWNLOAD_LOG" ;;
    esac
    shift
done
cp "$RELEASE_ARCHIVE" "$output"
''')
    for name in ('python', 'python3'):
        executable(fake / name, '#!/bin/sh\necho unexpected-python >> "$PYTHON_LOG"\nexit 97\n')
    return os.environ | {'HOME': str(home), 'SHELL': '/bin/bash',
                         'PATH': f'{fake}:{os.environ["PATH"]}',
                         'DOWNLOAD_LOG': str(tmp_path / 'downloads'),
                         'PYTHON_LOG': str(tmp_path / 'python-invocations'),
                         'RELEASE_ARCHIVE': str(tmp_path / 'release.tar.gz')}


def install(env):
    return subprocess.run(['bash', str(INSTALLER)], env=env,
                          capture_output=True, text=True, check=False)


def test_native_pair_install_and_reinstall(tmp_path):
    env = environment(tmp_path)
    release_archive(tmp_path / 'package', Path(env['RELEASE_ARCHIVE']))
    for _ in range(2):
        result = install(env)
        assert result.returncode == 0, result.stdout + result.stderr
    root = Path(env['HOME']) / '.dewy'
    current = (root / 'current').resolve()
    assert (root / 'dewy').resolve() == current / 'dewy'
    assert (root / 'udewy').resolve() == current / 'udewy'
    assert (current / 'library/unicode/grapheme_break.bin').is_file()
    assert (current / 'udewy-stdlib/linux.udewy').is_file()
    assert not (root / 'runtime/dewy/__main__.py').exists()
    assert not Path(env['PYTHON_LOG']).exists()
    assert (Path(env['HOME']) / '.bashrc').read_text().count('# Include dewy tools in PATH') == 1
    assert all(url.endswith('/releases/latest/download/dewy-linux-x86_64.tar.gz')
               for url in Path(env['DOWNLOAD_LOG']).read_text().splitlines())


def test_invalid_update_preserves_installed_pair(tmp_path):
    env = environment(tmp_path)
    release_archive(tmp_path / 'good', Path(env['RELEASE_ARCHIVE']))
    result = install(env)
    assert result.returncode == 0, result.stderr
    root = Path(env['HOME']) / '.dewy'
    before = (root / 'current').resolve()
    release_archive(tmp_path / 'broken', Path(env['RELEASE_ARCHIVE']), broken=True)
    result = install(env | {'DEWY_RELEASE': 'dewy-example-tag'})
    assert result.returncode != 0
    assert (root / 'current').resolve() == before
    assert (root / 'dewy').resolve() == before / 'dewy'
    assert (root / 'udewy').resolve() == before / 'udewy'
    assert '/releases/download/dewy-example-tag/' in Path(env['DOWNLOAD_LOG']).read_text()
    assert not Path(env['PYTHON_LOG']).exists()


def test_udewy_install_script_installs_only_the_binary(tmp_path: Path) -> None:
    home = tmp_path / "home"
    tools = tmp_path / "tools"
    home.mkdir()
    tools.mkdir()

    fake_udewy = tmp_path / "udewy"
    executable(fake_udewy, "#!/bin/sh\necho udewy-ok\n")
    executable(
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
