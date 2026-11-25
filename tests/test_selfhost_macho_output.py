"""Check Mach-O publication, app bundles and permissions."""
import plistlib
import shutil
import stat

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

pytestmark = pytest.mark.nightly

DOUBLES = {
    'lower.jo': 'mac_imports: (int, str, str)[]\n',
    'util.jo': 'ice = (msg: str): print("ice: {msg}")\n',
    'x64_module.dewy': '$runtime_checks\n\nlet stub_addr:array<int64>=[-1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 256 -1]\n',
    'x64_module.jo': 'stub_addr: int[] = [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 256, -1]\n',
}

DRIVER = r'''
use 'lower.jo'
code: u8[]
binding = arm64_encoder_bind(&code)
main = ():
    mac_imports = [(0, "/usr/lib/libSystem.B.dylib", "munmap"), (8, "/usr/lib/libSystem.B.dylib", "mmap")]
    text = fill(u8(0xAA), 32)
    ro: u8[] = [1, 2]
    print(write_macho("plain", text, 0, ro, [], 16, "", false))
    print(write_macho("read_only", text, 0, ro, [u8(3)], 16, "Named <Game>", true))
    print(write_macho("linked", text, 8, ro, [], 16, "", false))
    print(write_macho("missing/plain", text, 0, ro, [], 16, "", false))
    print(macho_watch_loader(0x4000, 0x8000, 64, 8))
    icon = fill(u8(0x5A), 24)
    loop app in ["Game.app", "dir/Café & <Co>.app", "taken.app", "blocked/x.app", "Icon.app"]:
        loop name in ["", "My_Game 1.0 & <é>"]:
            print("[{macos_bundle(app, name, if app == "Icon.app": icon else: [])}]")
            print(macho_plist)
            print(macho_resources)
            if app == "Game.app" and name == "":
                print(write_macho("Game.app/Contents/MacOS/Game", text, 0, ro, [], 16, "Game", false))
    print(xml_text("a&b<c>d"))
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_macho_output_twins(compiler, tmp_path, release):  # noqa: F811
    run = tmp_path / 'run'

    def fresh():
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir()
        (run / 'dir').mkdir()
        (run / 'taken.app').write_text('')
        (run / 'blocked').write_text('')
        (run / 'read_only').write_text('stale')
        (run / 'read_only').chmod(0o400)
        (run / 'kept').write_text('kept')
        (run / 'linked').symlink_to('kept')
        return run

    output = compare_narrow(compiler, tmp_path, release,
                            ('elf_format', 'leb128', 'sha', 'arm64_encode', 'macho_format', 'module_paths', 'json_doc',
                             'base64', 'icns', 'macho_output'), DRIVER, doubles=DOUBLES, run_in=fresh, snapshot=False)
    assert output.split()[:4] == [b'true', b'true', b'true', b'false']
    assert b'[Game.app/Contents/MacOS/Game]' in output and b'[]' in output
    for name in ('plain', 'read_only', 'linked', 'Game.app/Contents/MacOS/Game'):
        path = run / name
        assert not path.is_symlink() and stat.S_IMODE(path.stat().st_mode) == 0o755, name
        assert path.read_bytes().startswith(b'\xcf\xfa\xed\xfe'), name
    assert (run / 'kept').read_text() == 'kept'
    assert plistlib.loads((run / 'Game.app/Contents/Info.plist').read_bytes())['CFBundleExecutable'] == 'Game'
    icon = (run / 'Icon.app/Contents/Resources/icon.icns').read_bytes()
    assert icon == b'icns' + (40).to_bytes(4, 'big') + b'ic09' + (32).to_bytes(4, 'big') + b'Z' * 24
