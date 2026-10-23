"""A Dewy enumeration (a union of string literals) is a Sloppy enum to Sloppy code: Sloppy switches on
it, names its members (`.lex`, `Phase.lex`), converts it to and from its position
(`int(p)`, `Phase(3)`) and keys tables with it, exactly as with the Sloppy enum a frozen twin
declares in its place (tests/test_selfhost_twins.py checks the twins' member order)."""
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

FIXTURES = Path(__file__).resolve().parent / 'fixtures/selfhost'
EXPECTED = """lexing lex 0
parsing parse 1
checking check 2
emitting emit 3
lexing lex 0
parsing parse 1
[2, 2, 1, 1]
parse emit true true
3 2
"""


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_jo_switches_on_a_dewy_enumeration_as_on_its_twin(compiler, tmp_path, release):
    main = (FIXTURES / 'enum_jo.jo').read_text()
    twin = tmp_path / 'enum_twin.jo'
    twin.write_text(main.replace("use 'enum_phase.dewy'", f"use '{FIXTURES / 'enum_phase.jo'}'"))
    flags = ['--release'] if release else []
    outputs = []
    for source in (FIXTURES / 'enum_jo.jo', twin):
        binary = tmp_path / source.stem
        built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs == [EXPECTED, EXPECTED]
