"""Byte positions in text agree with frozen Jo, on text with multi-byte characters."""
import subprocess

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = '''use '@@'
main = ():
    texts = ["", "a", "abcabc", "é(x(é", "((", "日本語.dewy"]
    parts = ["", "a", "(", "bc", "é", "語", ".dewy", "zzzzzzzzzzzz"]
    loop t in texts:
        loop p in parts:
            print("{byte_rfind(t, p)}")
            loop start in [-1, 0, 1, 2, 3, 40]:
                print("{byte_find(t, p, start)}")
'''


def test_checks_text_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    outputs = []
    for leaf in ('checks_text.dewy', 'checks_text.jo'):
        directory = tmp_path / leaf.replace('.', '_')
        directory.mkdir()
        (directory / leaf).write_text((ROOT / 'compiler' / leaf).read_text())
        (directory / 'driver.jo').write_text(DRIVER.replace('@@', leaf))
        binary = directory / 'driver'
        built = subprocess.run([compiler, 'build', directory / 'driver.jo', '-o', binary],
                               capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0]
