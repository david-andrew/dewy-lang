"""Legacy compound units and scaled literals produce identical executable bytes."""
import subprocess
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

SOURCE = r'''main = ():
    print(36(km/h))
    print(500ms)
    print([1, 2](cm))
    x = 4.0
    print([x, 2](cm))
    print([x, 2](m))
    print(2(cm^2))
    print(2(kg*m/s^2))
'''


def test_parser_units_program_matches_twin(compiler, tmp_path, monkeypatch):
    source = tmp_path / 'units.jo'
    source.write_text(SOURCE)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('parser_units',), [source])
    assert results[0][2] == 0, results[0][:5]
    for label in ('dewy', 'jo'):
        result = subprocess.run([tmp_path / label / 'p0-0'], capture_output=True, timeout=30)
        assert result.returncode == 0 and result.stderr == b''
        assert result.stdout == b'10.0\n0.5\n[0.01, 0.02]\n[0.04, 0.02]\n[4.0, 2.0]\n0.0002\n2.0\n'
