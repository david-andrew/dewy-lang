"""Build programs with a compiler made with Dewy leaves and with one made with their frozen twins:
the same exit codes, messages and output bytes."""
import subprocess

from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT


def build_all(binary, tmp_path, label, paths):
    out = tmp_path / label
    out.mkdir()
    results = []
    for i, path in enumerate(paths):
        target = out / f'p{i}'
        r = subprocess.run([binary, 'build', path, '-o', target], cwd=tmp_path, capture_output=True,
                           text=True, timeout=120, check=False)
        made = target.read_bytes() if target.exists() else b''
        results.append((str(path), r.returncode, r.stdout, r.stderr.replace(str(binary), 'dewy-core'), made))
    return results


def compare_builds(compiler, tmp_path, monkeypatch, leaves, paths):
    """paths: test cases (relative to the repository) or programs written in tmp_path; the twin
    build's results."""
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    paths = [p if (tmp_path / p).exists() else ROOT / p for p in paths]
    dewy, jo = leaf_compilers(compiler, tmp_path, leaves)
    expected = build_all(jo, tmp_path, 'jo', paths)
    assert build_all(dewy, tmp_path, 'dewy', paths) == expected
    return expected
