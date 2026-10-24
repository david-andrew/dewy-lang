"""Sloppy code orders a Dewy enumeration (a union of string literals) as it orders its frozen
twin's enum: by the members' positions, not by their names as text (Dewy's own comparisons of
such members are unchanged)."""
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

FIXTURES = Path(__file__).resolve().parent / 'fixtures/selfhost'
# (by name, check < emit < lex < parse: every answer of the first line but the last would flip)
EXPECTED = 'true true false false true true\nparse lex\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_jo_orders_a_dewy_enumeration_by_position(compiler, tmp_path, release):  # noqa: F811
    main = (FIXTURES / 'enum_order_jo.jo').read_text()
    twin = tmp_path / 'enum_order_twin.jo'
    twin.write_text(main.replace("use 'enum_phase.dewy'", f"use '{FIXTURES / 'enum_phase.jo'}'"))
    flags = ['--release'] if release else []
    outputs = []
    for source in (FIXTURES / 'enum_order_jo.jo', twin):
        binary = tmp_path / source.stem
        built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs == [EXPECTED, EXPECTED]
