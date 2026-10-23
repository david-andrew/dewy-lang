"""Platform packages of the VS Code extension carry a verified toolchain."""
import hashlib
import io
import json
import sys
import tarfile
import zipfile

import pytest

from tools.compiler import vsix


def toolchain_archive(path, host, tamper=False):
    payload = {'bin/dewy-core': b'compiler', 'lib/core/rt.jo': b'runtime', 'LICENSE': b'license'}
    files = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    if tamper:
        payload['lib/core/rt.jo'] = b'changed'
    payload['PACKAGE.json'] = json.dumps({'format': 1, 'host': host, 'files': files}).encode()
    with tarfile.open(path, 'w:gz') as archive:
        for name, data in payload.items():
            member = tarfile.TarInfo(f'dewy-core/{name}')
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return path


# Stands in for vsce: zips the staged extension the way it would be packaged.
FAKE_VSCE = '''
import sys, zipfile, pathlib
out = pathlib.Path(sys.argv[sys.argv.index('--out') + 1])
target = sys.argv[sys.argv.index('--target') + 1] if '--target' in sys.argv else 'universal'
with zipfile.ZipFile(out, 'w') as z:
    z.writestr('target', target)
    for p in sorted(pathlib.Path('.').rglob('*')):
        if p.is_file():
            info = zipfile.ZipInfo('extension/' + p.as_posix())
            info.external_attr = (p.stat().st_mode & 0o777) << 16
            z.writestr(info, p.read_bytes())
'''


def test_platform_package_bundles_the_toolchain(tmp_path):
    archive = toolchain_archive(tmp_path / 'linux.tar.gz', 'linux-x86_64')
    fake = tmp_path / 'vsce.py'
    fake.write_text(FAKE_VSCE)
    out = vsix.package(tmp_path / 'out' / 'dewy-linux-x64.vsix', 'linux-x64', archive, vsce=[sys.executable, str(fake)])
    with zipfile.ZipFile(out) as z:
        assert z.read('target') == b'linux-x64'
        assert z.read('extension/toolchain/bin/dewy-core') == b'compiler'
        assert z.getinfo('extension/toolchain/bin/dewy-core').external_attr >> 16 & 0o111
        assert z.read('extension/toolchain/lib/core/rt.jo') == b'runtime'
        assert z.read('extension/toolchain/LICENSE') == b'license'
        assert z.read('extension/LICENSE') == (vsix.ROOT / 'LICENSE').read_bytes()
        assert 'extension/package.json' in z.namelist() and 'extension/compiler.js' in z.namelist()
    assert not (vsix.EXTENSION / 'toolchain').exists()
    universal = vsix.package(tmp_path / 'dewy.vsix', vsce=[sys.executable, str(fake)])
    with zipfile.ZipFile(universal) as z:
        assert z.read('target') == b'universal'
        assert not [n for n in z.namelist() if '/toolchain/' in n]


@pytest.mark.parametrize(('host', 'tamper', 'message'), [
    ('macos', False, 'is for macos, not linux-x64'),
    ('linux-x86_64', True, 'does not match PACKAGE.json'),
])
def test_platform_package_rejects_wrong_toolchains(tmp_path, host, tamper, message):
    archive = toolchain_archive(tmp_path / 'toolchain.tar.gz', host, tamper)
    with pytest.raises(ValueError, match=message):
        vsix.package(tmp_path / 'dewy.vsix', 'linux-x64', archive, vsce=[sys.executable, '-c', 'pass'])
    with pytest.raises(ValueError, match='both --target and --toolchain'):
        vsix.package(tmp_path / 'dewy.vsix', 'linux-x64')
