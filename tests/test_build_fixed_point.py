"""The fixed-point step of tools/compiler/build.py compares the bytes of generation N+1 with N."""
import pytest

from tools.compiler.build import check_fixed_point, first_difference


def test_first_difference_names_the_offset(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.write_bytes(b'abcdef')
    b.write_bytes(b'abcdef')
    assert first_difference(a, b) is None
    b.write_bytes(b'abcxef')
    assert first_difference(a, b) == 3
    b.write_bytes(b'abc')
    assert first_difference(a, b) == 3 and first_difference(b, a) == 3
    b.write_bytes(b'')
    assert first_difference(a, b) == 0
    a.write_bytes(b'')
    assert first_difference(a, b) is None


def test_first_difference_across_chunks(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    data = bytes(range(256)) * 40
    a.write_bytes(data)
    b.write_bytes(data[:5000] + b'\xff' + data[5001:])
    assert first_difference(a, b, chunk=64) == 5000
    assert first_difference(a, b) == 5000
    b.write_bytes(data + b'x')
    assert first_difference(a, b, chunk=64) == len(data)


def test_fixed_point_matches(tmp_path):
    binary = tmp_path / 'dewy-core'
    binary.write_bytes(b'generation')
    calls = []

    def rebuild(compiler, output):
        calls.append((compiler.read_bytes(), output))
        assert not output.exists()
        output.write_bytes(b'generation')

    check_fixed_point(binary, rebuild)
    assert calls == [(b'generation', binary)]
    assert binary.read_bytes() == b'generation' and [p.name for p in tmp_path.iterdir()] == ['dewy-core']


def test_fixed_point_mismatch_fails_loudly(tmp_path):
    binary = tmp_path / 'dewy-core'
    binary.write_bytes(b'generation one')
    with pytest.raises(RuntimeError, match=r'not a fixed point.*byte offset 11'):
        check_fixed_point(binary, lambda compiler, output: output.write_bytes(b'generation two'))
    assert binary.read_bytes() == b'generation two'
    assert (tmp_path / 'dewy-core.generation-n').read_bytes() == b'generation one'
