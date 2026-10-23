"""Assigned Boolean results and folded IMUL and narrowing sources."""
import subprocess
import pytest
from tests.support import compiler

@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']])
def test_copy_coalescing_under_register_pressure(compiler, tmp_path, flags):
    # Opaque inputs and calls keep both spill and high-register paths live.
    # Unsigned and signed narrowing also exercise folded stack reloads.
    text = '@noinline\nopaque = (x: int) -> int: x\n'
    text += '@noinline\njoin = (a: int, f: f64, b: int, c: int, d: int, e: int, g: int, h: int) -> int:\n'
    text += '    a + int(f) * 3 + b * 7 + c * 11 + d * 17 + e * 19 + g * 23 + h * 29\n'
    text += '@noinline\nwork = (seed: int) -> int:\n'
    for i in range(20):
        text += f'    v{i} = opaque(seed + {i})\n'
    comparisons = ('<', '<=', '>', '>=', '==', '!=')
    for i in range(18):
        text += f'    b{i} = v{i} {comparisons[i % 6]} v{(i * 7 + 3) % 20}\n'
    text += '    total = join(v19, f64(v3), v18, v17, v16, v15, v14, v13)\n'
    for i in range(18):
        text += f'    if b{i}: total += {1 << i}\n'
    for i in range(20):
        text += f'    total += v{i} * {37 + i * 2}\n'
        text += f'    total += int(i8(v{i})) + int(u8(v{i})) + int(i16(v{i})) + int(u16(v{i}))\n'
    text += '    return total\n'
    seeds = [-32770, -129, -1, 127, 65530]
    text += ''.join(f'print(work({s}))\n' for s in seeds)
    source = tmp_path / 'copies.jo'
    source.write_text(text)
    binary = tmp_path / 'copies'
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary], capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    run = subprocess.run([binary], capture_output=True, text=True, timeout=15)
    assert run.returncode == 0, run.stdout + run.stderr
    def signed(v, bits):
        v &= (1 << bits) - 1
        return v - (1 << bits) if v & (1 << (bits - 1)) else v
    expected = []
    for seed in seeds:
        v = [seed + i for i in range(20)]
        total = v[19] + v[3] * 3 + v[18] * 7 + v[17] * 11 + v[16] * 17 + v[15] * 19 + v[14] * 23 + v[13] * 29
        for i in range(18):
            a, b = v[i], v[(i * 7 + 3) % 20]
            if (a < b, a <= b, a > b, a >= b, a == b, a != b)[i % 6]: total += 1 << i
        for i, x in enumerate(v):
            total += x * (37 + i * 2) + signed(x, 8) + (x & 255) + signed(x, 16) + (x & 65535)
        expected.append(str(total))
    assert run.stdout.splitlines() == expected
