"""The bit operations take the whole uint64 range (and int64's, as 64 bits), as Python computes them."""
import random
import subprocess

from tests.support import compiler  # noqa: F401

MASK = (1 << 64) - 1


def reference(x, n):
    def rotate(v, k):
        k &= 63
        return ((v << k) | (v >> (64 - k))) & MASK if k else v
    return [bin(x).count('1'), 64 - x.bit_length(), 64 if x == 0 else (x & -x).bit_length() - 1,
            rotate(x, n), rotate(x, 64 - (n & 63)), int.from_bytes(x.to_bytes(8, 'little'), 'big')]


def test_unsigned_64_bit_operations(compiler, tmp_path):  # noqa: F811
    rng = random.Random(64)
    values = [0, 1, 2**63 - 1, 2**63, 2**63 + 1, MASK, MASK - 1, 0x00FF00FF00FF00FF, 0xF0F0F0F0F0F0F0F0]
    values += [rng.getrandbits(64) for _ in range(40)] + [1 << k for k in range(64)]
    shifts = [rng.randrange(0, 70) for _ in values]
    source = tmp_path / 'bits.dewy'
    source.write_text(
        'main = ():>void => {\n'
        f'    let xs:array<uint64> = [{" ".join(map(str, values))}]\n'
        f'    let ns:array<int64> = [{" ".join(map(str, shifts))}]\n'
        '    loop i in [0..xs.length) {\n'
        '        let x = xs[i]\n'
        '        let n = ns[i]\n'
        '        printl"{x.popcount} {x.leading_zeros} {x.trailing_zeros} {x.rotate_left(n)} {x.rotate_right(n)} {x.byte_swap}"\n'
        '    }\n}\n'
        '$runtime_checks\n')
    ran = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=120)
    assert ran.returncode == 0, ran.stderr
    want = ['{} {} {} {} {} {}'.format(*reference(x, n)) for x, n in zip(values, shifts)]
    assert ran.stdout.splitlines() == want


def test_signed_operations_use_the_64_bit_pattern(compiler, tmp_path):  # noqa: F811
    values = [-1, -2, -(2**63), 5, 0, 2**63 - 1]
    source = tmp_path / 'signed.dewy'
    source.write_text(
        f'main = ():>void => {{\n    let xs:array<int64> = [{" ".join("(%d)" % v if v < 0 else str(v) for v in values)}]\n'
        '    loop x in xs {\n'
        '        printl"{x.popcount} {x.leading_zeros} {x.trailing_zeros} {x.rotate_left(1)} {x.byte_swap}"\n    }\n}\n')
    ran = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=120)
    assert ran.returncode == 0, ran.stderr

    def signed(v):
        return v - (1 << 64) if v >> 63 else v
    want = []
    for v in values:
        u = v & MASK
        p, lz, tz, rot, _, swap = reference(u, 1)
        want.append(f'{p} {lz} {tz} {signed(rot)} {signed(swap)}')
    assert ran.stdout.splitlines() == want


def test_unsigned_values_go_into_byte_buffers(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'put.dewy'
    source.write_text('main = ():>void => {\n    let b:array<uint8> = []\n    let w:uint64 = 0xFFFFFFFFFFFFFFF1\n'
                      '    b.append_le(w 8)\n    b.append_be(w 8)\n    printl(b)\n}\n$runtime_checks\n')
    ran = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=120)
    assert ran.returncode == 0 and ran.stdout.strip() == '[241 255 255 255 255 255 255 255 255 255 255 255 255 255 255 241]', ran.stderr
