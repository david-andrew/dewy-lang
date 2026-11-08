"""Quoted-call adjacency and interpolation agree with the bootstrap reader."""

import shutil
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tools.compiler import parser_diff


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_quoted_callable_twins(compiler, tmp_path, monkeypatch, release):
    try:
        pair = parser_diff.build_pair(compiler, tmp_path, release)
    except RuntimeError as error:
        logs = '\n'.join(f'{p.name}:\n{p.read_text()}'
                         for p in sorted(tmp_path.glob('build-*.log')))
        pytest.fail(f'{error}\n{logs}')
    # The frozen reader predates fmt's constant-check directives. Isolate
    # the call grammar; the golden cases exercise the production formatter
    # in native/web and default/release modes.
    library = tmp_path / 'grammar-lib'
    shutil.copytree(ROOT / 'lib', library)
    (library / 'prelude/formats.dewy').write_text(
        'fmt=(pattern:string)=>(x:int):>string=>"{pattern} {x}"\n')
    environment = parser_diff.environment
    monkeypatch.setattr(parser_diff, 'environment', lambda _: environment(library))
    cases = ROOT / 'tests/cases/quoted_callable'
    sources = [p for p in sorted(cases.glob('*.dewy')) if p.stem != 'interpolation']
    interpolation = tmp_path / 'interpolation.dewy'
    interpolation.write_text((cases / 'interpolation.dewy').read_text()
                             .replace('let x=1.25', 'let x=7'))
    sources.append(interpolation)
    accepted = subprocess.run([pair[0], 'check', interpolation],
                              env=parser_diff.environment(library), capture_output=True,
                              text=True, timeout=30)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    failures = parser_diff.compare(pair, sources, tmp_path, release, workers=1)
    details = '\n'.join(f'{p}: {p.read_text()}'
                        for p in sorted(tmp_path.glob('difference-*/*.stderr')))
    assert not failures, '\n'.join(f'{path}: {reason}' for path, reason in failures) + details
    shared = tmp_path / 'shared-panics'
    assert not shared.exists(), shared.read_text()
