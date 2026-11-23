"""Build programs with a compiler made with Dewy leaves and with one made with their frozen twins:
the same exit codes, messages and output bytes."""
import subprocess
from functools import partial

from tests import leaf_oracle, whole_oracle
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT
from tools.cases import parse


def build_all(binary, tmp_path, label, paths, flags=((),)):
    out = tmp_path / label
    out.mkdir()
    results = []
    for i, path in enumerate(paths):
        for j, extra in enumerate(flags):
            target = out / f'p{i}-{j}'
            # (messages may quote source bytes that are not UTF-8: kept exactly)
            r = subprocess.run([binary, 'build', *extra, path, '-o', target], cwd=tmp_path, capture_output=True,
                               text=True, errors='surrogateescape', timeout=120, check=False)
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
    dewy, jo = leaf_compilers(compiler, tmp_path, leaves, recorded=False)
    got = build_all(dewy, tmp_path, 'dewy', paths, flags)
    expected = got if jo is None else build_all(jo, tmp_path, 'jo', paths, flags)
    for a, b in zip(got, expected):
        # (the first program that differs: its text, and which output files differ)
        assert a[:5] == b[:5] and a[5].keys() == b[5].keys(), (a[:5], b[:5])
        assert a[5] == b[5], (a[0], a[1], [name for name in a[5] if a[5][name] != b[5][name]])
    record_builds(got, tmp_path, 'dewy')
    return expected


def record_builds(got, tmp_path, label):
    """Hold build_all's results (made under tmp_path/label) to their records: recorded outcomes stand in
    for the twin's builds when it is not built (tests/whole_oracle.py)."""
    for path, extra, status, stdout, stderr, made in got:
        leaf_oracle.check_entry(partial(
            whole_oracle.build, ('build', *extra, path), status, stdout.encode(errors='surrogateescape'),
            stderr.encode(errors='surrogateescape'), [tmp_path / label / name for name in made], tmp_path))


def compare_golden_cases(compiler, tmp_path, monkeypatch, leaf, cases, flags=((),)):
    """Compare both compilers and require the build outcome specified by each golden case."""
    paths = [ROOT / 'tests' / 'cases' / f'{case}.dewy' for case in cases]
    should_build = {str(path): parse(path).kind != 'reject' for path in paths}
    results = compare_builds(compiler, tmp_path, monkeypatch, (leaf,), paths, flags)
    for path, _, status, *_ in results:
        assert (status == 0) == should_build[path], path
