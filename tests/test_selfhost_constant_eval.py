"""Recursive constant evaluation, host re-entry, short circuits and first errors."""
import subprocess
from pathlib import Path

import pytest
from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('constant_eval', 'constant_host', 'evaluator_state', 'node_store', 'source_types', 'checker_tokens')
ERRORS = {1: "'missing' is not a compile-time constant",
          2: 'invalid operator on strings in compile-time expression',
          3: 'expression is not a compile-time constant',
          4: 'unsupported operator in compile-time expression',
          5: 'unsupported operator in compile-time expression'}
VALUES = [0, 1, 'a\0b', 0, 1, 0, 0, 1, 1, 5, 1, 6, 1, 12, 1, 0, 1, 1, 0,
          0, 3, 2, 2, -(1 << 63), (1 << 63)-1, -2, -(1 << 63), 0,
          -(1 << 63), 0, 1, 0, 42, 43, 43, 43, 43, 3, 4]
EXPECTED = ''.join(f'true 0 {v}\n' if isinstance(v, str) else f'false {v} \n' for v in VALUES) + '7 302 304\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_constant_eval_twins(compiler, tmp_path, release):  # noqa: F811
    driver = (ROOT / 'tests/fixtures/selfhost/constant_eval_jo.jo').read_text()
    outputs = []
    for extension in ('dewy', 'jo'):
        for module in MODULES:
            text = (ROOT / 'compiler' / f'{module}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (tmp_path / f'{module}.{extension}').write_text(text)
        source, binary = tmp_path / 'driver.jo', tmp_path / 'driver'
        source.write_text(driver.replace('../../../compiler/', '').replace(".jo'", f".{extension}'"))
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        runs = []
        for mode in [0, *ERRORS]:
            ran = subprocess.run([binary, str(mode)], capture_output=True, text=True, timeout=10)
            runs.append((ran.returncode, ran.stdout, ran.stderr))
            assert ran.returncode == (7 if mode else 0), ran.stdout + ran.stderr
            assert ran.stdout == (f'E 700 {ERRORS[mode]}\n' if mode else EXPECTED)
        outputs.append(runs)
    assert outputs[0] == outputs[1]


@pytest.mark.core_quick
def test_constant_eval_ships_dewy(compiler):  # noqa: F811
    assert b'/compiler/constant_eval.dewy\0' in compiler.read_bytes()
