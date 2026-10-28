"""Signed bitwise proof envelopes agree with integer semantics at sign boundaries."""
import itertools
import subprocess

from tests.support import compiler  # noqa: F401


def test_signed_bitwise_boundaries(compiler, tmp_path):  # noqa: F811
    points = [-128, -127, -65, -64, -33, -32, -2, -1, 0, 1, 2, 31, 32, 63, 64, 126, 127]
    source = tmp_path / "bits.dewy"
    source.write_text("""both=(x:int8 y:int8):>int8=>int8(int64(x) and int64(y))
either=(x:int8 y:int8):>int8=>int8(int64(x) or int64(y))
different=(x:int8 y:int8):>int8=>int8(int64(x) xor int64(y))
let points:array<int8>=[""" + " ".join(map(str, points)) + """]
loop x in points {loop y in points {printl(both(x y) either(x y) different(x y))}}
""")
    result = subprocess.run([compiler, "run", source], text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = [f"{x & y} {x | y} {x ^ y}" for x, y in itertools.product(points, repeat=2)]
    assert result.stdout.splitlines() == expected
