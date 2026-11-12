"""The Dewy frontend file services and their frozen Jo twin emit the same bytes."""
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tools.compiler import parser_diff


def build_pair(seed, work, release):
    tree = work / 'source'
    shutil.copytree(parser_diff.ROOT / 'compiler', tree / 'compiler')
    shutil.copytree(parser_diff.ROOT / 'lib', tree / 'lib')
    main = tree / 'compiler/main.jo'
    main.write_text(main.read_text().replace('build:\n    opt = release\n', ''))
    binaries = []
    for side in ('dewy', 'twin'):
        if side == 'twin':
            for path in (tree / 'compiler').iterdir():
                if path.suffix not in ('.jo', '.dewy') or path.name == 'dewy_fast_file.jo':
                    continue
                text = path.read_text()
                text = text.replace("'dewy_fast_file.dewy'", "'dewy_fast_file.jo'")
                text = text.replace('p"dewy_fast_file.dewy"', 'p"dewy_fast_file.jo"')
                path.write_text(text)
        binary = work / side
        run = subprocess.run([seed, 'build', main, '-o', binary,
                              *(['--release'] if release else [])],
                             env=parser_diff.environment(tree / 'lib'),
                             capture_output=True, timeout=300)
        assert run.returncode == 0, (run.stdout + run.stderr).decode(errors="replace")
        binaries.append(binary)
    return tuple(binaries)


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_fast_file_matches_twin(compiler, tmp_path, release):
    pair = build_pair(compiler, tmp_path, release)
    names = (
        'constant/shadowable_let',
        'constant/shadowable_function_assign',
        'directives/scope_module',
        'directives/no_nan_proven',
        'errors/proofs_after_unrelated_error',
        'frontend/declarations_direct_declarations_1',
        'testing/test_block_form',
    )
    cases = parser_diff.ROOT / 'tests/cases'
    sources = [cases / f'{name}.dewy' for name in names]
    assert all(path.is_file() for path in sources)
    failures = parser_diff.compare(pair, sources, tmp_path, release, workers=1)
    assert not failures, '\n'.join(f'{path}: {reason}' for path, reason in failures)


def test_fast_file_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_fast_file.dewy\0' in binary
    assert b'/compiler/dewy_fast_file.jo\0' not in binary
