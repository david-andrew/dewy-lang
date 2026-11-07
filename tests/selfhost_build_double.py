"""Build programs with a compiler made with Dewy leaves and with one made with their frozen twins:
the same exit codes, messages and output bytes."""
import subprocess

from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT


def build_all(binary, tmp_path, label, paths, flags=((),)):
    out = tmp_path / label
    out.mkdir()
    results = []
    for i, path in enumerate(paths):
        for j, extra in enumerate(flags):
            target = out / f'p{i}-{j}'
            r = subprocess.run([binary, 'build', *extra, path, '-o', target], cwd=tmp_path, capture_output=True,
                               text=True, timeout=120, check=False)
            # (everything the build wrote: a Windows build adds .exe and .pdb)
            made = {p.name: p.read_bytes() for p in sorted(out.glob(f'p{i}-{j}*')) if p.is_file()}
            results.append((str(path), extra, r.returncode, r.stdout,
                            r.stderr.replace(str(binary), 'dewy-core'), made))
    return results


def compare_builds(compiler, tmp_path, monkeypatch, leaves, paths, flags=((),)):
    """paths: test cases (relative to the repository) or programs written in tmp_path, each built
    with each of flags; the twin build's results (path, flags, exit code, stdout, stderr, files)."""
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    paths = [p if (tmp_path / p).exists() else ROOT / p for p in paths]
    dewy, jo = leaf_compilers(compiler, tmp_path, leaves)
    expected = build_all(jo, tmp_path, 'jo', paths, flags)
    assert build_all(dewy, tmp_path, 'dewy', paths, flags) == expected
    return expected
