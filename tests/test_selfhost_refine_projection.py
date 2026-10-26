"""Projection statuses, first diagnostic, inference, reentry and host trace."""
import subprocess
from pathlib import Path

import pytest
from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('9 1', 'Q 8 0'),
    ('9 1 11 -1', 'R 1\nR 2\nN 1 0\nQ 1 0'),
    ('9 1 11 -1', 'Q 1 0'),
    ('9 1 14 21 14 21 11 -1', 'Q 1 0'),
    ('9 1 12 -1', 'L\nQ 1 0'),
    ('9 0 12 -1', 'Q 0 1'),
    ('9 1 12 -1 -1', 'L\nQ 0 1'),
    ('9 1 12 -1 11', 'L\nQ 0 2'),
    ('9 1 13 999 -1', 'Q 6 0'),
    ('9 1 15', 'Q 5 0'),  # preserve last-match behavior
    ('9 1 15 -1', 'Q 1 0'),
    ('9 1 99', 'Q 0 3'),
    ('9 1 -1', 'Q 0 1'),
    ('1 1 99', 'Q 0 2'),
    ('1 1 -1', 'Q 0 1'),
    ('7 1', 'Q 1 0'),
    ('12 1', 'Q 2 0'),  # representation unwraps one refined layer
    ('6 1 -1 99', 'Q 6 0'),
    ('4 0 -1', 'Q 1 0'),
    ('5 0 -1', 'Q 1 0'),
    ('11 1 -1', 'Q 0 1'),
    ('11 1 99', 'Q 0 2'),
    ('3 1 -1', 'L\nQ 1 0'),
    ('3 0 -1', 'Q 0 1'),
]


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_projection_twins_and_trace(compiler, tmp_path, release):  # noqa: F811
    (tmp_path / 'steps').write_text('\n'.join('Q ' + case for case, _ in CASES) + '\n')
    expected = '\n'.join(out for _, out in CASES).splitlines()
    driver = (ROOT / 'tests/fixtures/selfhost/refine_projection_jo.jo').read_text()
    modules = ('checker_services', 'checker_types', 'refine_queries', 'refinement_types',
               'refine_predicates', 'checker_tokens', 'refine_projection')
    for extension in ('dewy', 'jo'):
        for name in modules:
            text = (ROOT / 'compiler' / f'{name}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (tmp_path / f'{name}.{extension}').write_text(text)
        source, binary = tmp_path / 'driver.jo', tmp_path / 'driver'
        source.write_text(driver.replace('../../../compiler/', '').replace(".jo'", f".{extension}'"))
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary, tmp_path / 'steps'], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout.splitlines() == expected


@pytest.mark.core_quick
def test_projection_ships_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/refine_projection.dewy\0' in binary
    assert b'/compiler/refine_projection.jo\0' not in binary
