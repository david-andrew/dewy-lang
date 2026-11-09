"""`upper` and `lower` follow Unicode's default full case mapping, as Python's str.upper and str.lower."""
import random
import subprocess
import unicodedata

import pytest

from tests.support import compiler  # noqa: F401
from tools.compiler import unicode_case

PROGRAM = '''main = (argv:array<string>):>void => {
    match read_text(argv[1]) {
        text:string => print(if argv[2] =? "up" text.upper else text.lower)
        _ => print"unreadable"
    }
}
$runtime_checks
'''


def sample_text():
    rng = random.Random(1109)
    scalars = [c for c in range(0x110000) if not 0xD800 <= c < 0xE000]
    cased = [c for c in scalars if chr(c).lower() != chr(c) or chr(c).upper() != chr(c)]
    lines = [chr(c) for c in cased]
    lines += [chr(c) for c in rng.sample(scalars, 2000)]
    pieces = ['Σ', 'σ', 'ς', 'A', 'a', 'ͅ', '́', '.', "'", 'ʰ', '1', ' ', 'İ', 'ß', 'ǅ', 'ﬃ', 'ᾳ', 'ΐ',
              '­', 'ᵃ', '日本', '🙂', 'é']
    for _ in range(3000):
        lines.append(''.join(rng.choice(pieces) if rng.random() < 0.6 else chr(rng.choice(cased))
                             for _ in range(rng.randint(1, 10))))
    return lines


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_case_mapping_matches_python(compiler, tmp_path, release):  # noqa: F811
    source = tmp_path / 'case.dewy'
    source.write_text(PROGRAM)
    binary = tmp_path / 'case'
    built = subprocess.run([compiler, 'build', source, '-o', binary] + (['--release'] if release else []),
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    lines = sample_text()
    text = tmp_path / 'text.txt'
    text.write_bytes('\n'.join(lines).encode())
    for mode, convert in (('up', str.upper), ('low', str.lower)):
        ran = subprocess.run([binary, text, mode], capture_output=True, timeout=60)
        got = ran.stdout.decode().split('\n')
        bad = [(a, convert(a), b) for a, b in zip(lines, got) if convert(a) != b]
        assert not bad and len(got) == len(lines), bad[:5]


def test_case_mapping_constants(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'const.dewy'
    source.write_text('const DOT = "İ".lower\nconst DZ = "ǅ".upper\n'
                      'main = ():>void => {\n'
                      '    printl"{DOT} {DZ} {"ΣΊΣΥΦΟΣ".lower} {"straße".upper} {"ǅ".lower} {"𐐨".upper}"\n'
                      '}\n')
    ran = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=120)
    assert ran.stdout.splitlines()[0] == 'i̇ Ǆ σίσυφος STRASSE ǆ 𐐀', ran.stdout + ran.stderr


def test_case_mapping_in_compile_time_evaluation(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'assert.dewy'
    source.write_text('$assert "é".upper =? "É"\n$assert "İ".lower =? "i\u0307"\n$assert "ǅ".upper =? "Ǆ"\n'
                      '$assert "straße".upper =? "STRASSE"\n$assert "ΟΔΥΣΣΕΥΣ".lower =? "οδυσσευς"\n'
                      '$assert "𐐨".upper =? "𐐀"\nmain = ():>void => {}\n')
    ran = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=120)
    assert ran.returncode == 0, ran.stderr


def test_case_mapping_table_reproducible():
    if unicodedata.unidata_version != unicode_case.UNICODE_VERSION:
        pytest.skip('Python has another Unicode version than the table')
    assert unicode_case.pack() == unicode_case.TARGET.read_bytes()
