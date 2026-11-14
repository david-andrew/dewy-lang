"""Formatter CLI ownership preserves stdin, check mode, tree writes and errors across twins."""
import subprocess

from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


def test_formatter_cli_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    binaries = leaf_compilers(compiler, tmp_path, ('formatter_cli',))
    originals = {'tree/a.dewy': b'main=()=>{printl(1)}\n',
                 'tree/sub/b.jo': b'main = ():\n print(42)\n', 'tree/keep.txt': b'untouched\xff'}
    results = []
    for binary in binaries:
        for name, data in originals.items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        rows = []
        for args, source in [(('fmt',), b''), (('fmt', '--check', 'tree'), b''),
                             (('fmt', 'tree'), b''), (('fmt', '--check', 'tree'), b''),
                             (('fmt', '-'), b'main=()=>{printl(1)}\n'),
                             # Pipe reads and resizes cross the 64 KiB input-buffer boundary.
                             (('fmt', '-'), b'# ' + b'x' * 70000 + b'\nmain=()=>{printl(1)}\n'),
                             (('fmt', '-'), b'main=()=>{(}\n'), (('fmt', 'missing.dewy'), b'')]:
            r = subprocess.run([binary, *args], cwd=tmp_path, input=source, capture_output=True, timeout=60)
            rows.append((r.returncode, r.stdout, r.stderr))
        rows.append({name: (tmp_path / name).read_bytes() for name in originals})
        results.append(rows)
    assert results[0] == results[1]
    assert [row[0] for row in results[0][:-1]] == [2, 1, 0, 0, 0, 0, 1, 1]
    assert results[0][-1]['tree/a.dewy'] != originals['tree/a.dewy']
    assert results[0][-1]['tree/keep.txt'] == originals['tree/keep.txt']
