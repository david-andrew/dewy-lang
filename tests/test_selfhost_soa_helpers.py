"""Legacy struct-of-arrays operations produce identical builds through both leaves."""
import subprocess
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

SOURCE = r'''struct Point:
    x: int
    y: int
main = ():
    ps: soa Point[] = [Point(1, 2), Point(3, 4)]
    print(ps.len())
    ps.push(Point(5, 6))
    point = ps[1]
    print(point.x)
    ps[0] = Point(7, 8)
    print(ps.x)
    q = ps.pop()
    print(q.y)
    ps.remove(0)
    ps.reserve(10)
    ps.truncate(0)
    ps.clear()
    print(ps.len())
'''


def test_soa_helpers_match_twin(compiler, tmp_path, monkeypatch):
    source = tmp_path / 'arrays.jo'
    source.write_text(SOURCE)
    paths = [source]
    for label, statement in [('push', 'ps.push()'), ('method', 'ps.missing()'),
                             ('assign', 'ps[0] += Point(1, 2)')]:
        bad = tmp_path / (label + '.jo')
        bad.write_text(SOURCE[:SOURCE.index('    print(ps.len())')] + '    ' + statement + '\n')
        paths.append(bad)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('soa_helpers',), paths)
    assert results[0][2] == 0, results[0][:5]
    assert all(r[2] == 1 for r in results[1:]), [r[:5] for r in results[1:]]
    for label in ('dewy', 'jo'):
        result = subprocess.run([tmp_path / label / 'p0-0'], capture_output=True, timeout=30)
        assert result.returncode == 0 and result.stderr == b''
        assert result.stdout == b'2\n3\n[7, 3, 5]\n6\n0\n'
