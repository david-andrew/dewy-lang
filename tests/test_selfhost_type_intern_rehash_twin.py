"""Rehashing excludes appended type and module records in both implementations."""

import subprocess

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_type_intern_rehash import DRIVER


def test_rehash_twin(compiler, tmp_path):
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in ('checker_types', 'type_intern'):
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(f"use 'checker_types.{extension}'\nuse 'type_intern.{extension}'\n" + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs == [b'ok\n', b'ok\n']
