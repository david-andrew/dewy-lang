"""Typed literal/read compaction preserves widths and operand arithmetic policies."""
import subprocess
import pytest
from tests.support import compiler


@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']], ids=['default', 'release', 'debug'])
def test_compact_integer_values_and_operand_policies(compiler, tmp_path, flags):
    source = tmp_path / 'words.dewy'
    source.write_text('''$runtime_checks
W:type=int64<overflow='wrap'>
S:type=int64<overflow='saturate'>
Box:type=[value:int64]
main=(args:array<string>)=>{
    let x:int64=int64(to_int(args[1]) ?? 0)
    let box=Box(x)
    let values:array<int64>=[x]
    printl"{W(x)} {S(x)} {W(box.value)} {S(box.value)} {W(values[0])} {S(values[0])}"
    let wrapped:W=W(x)
    let saturated:S=S(x)
    printl"{W(x+1)} {S(x+1)} {S(wrapped+1)} {W(saturated+1)}"
    let u:uint32=uint32.max
    printl"{uint32<overflow='wrap'>(u)} {uint32<overflow='saturate'>(u)}"
    printl"{uint8<overflow='wrap'>(257)} {int8<overflow='saturate'>(128)} {uint64<overflow='wrap'>(-1)}"
    printl"{int64<overflow='wrap'>(18446744073709551615)} {uint64<overflow='wrap'>(18446744073709551615)}"
    let small:int8=127
    let zero:W=0
    let literal:uint64=18446744073709551615
    printl"{small} {zero} {literal}"
}
''')
    binary = tmp_path / 'words'
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    lo, hi = -(2**63), 2**63-1
    wrap = lambda x: (x + 2**63) % 2**64 - 2**63
    sat = lambda x: min(hi, max(lo, x))
    for value in (lo, -1, 0, 1, hi-1, hi):
        ran = subprocess.run([binary, str(value)], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout.splitlines() == [
            ' '.join([str(value)] * 6),
            f'{wrap(value+1)} {sat(value+1)} {wrap(value+1)} {sat(value+1)}',
            '4294967295 4294967295',
            '1 127 18446744073709551615',
            '-1 18446744073709551615',
            '127 0 18446744073709551615',
        ]


def test_compact_unsigned_remainder_still_rejects_unproved_narrowing(compiler, tmp_path):
    source = tmp_path / 'boundary.dewy'
    source.write_text('''over=(s:uint64<overflow='wrap'>):>int16=>int16(s % 32768) + 1
main=():>void=>printl(over(5))
''')
    checked = subprocess.run([compiler, 'check', '--obligations', source],
                             capture_output=True, text=True, timeout=30)
    assert checked.returncode != 0
    assert 'cannot prove exact integer result fits int16' in checked.stderr
    # A policy literal cannot be reconstructed as an untyped guard: its
    # contextual conversion would itself demand the unproved upper bound.
    assert 'nothing bounds `s % 32768 + 1`' not in checked.stderr
    assert 'establish `int16.min <=?' not in checked.stderr
    # The rejected endpoint really is outside the destination, although this
    # caller's sample value happens to fit: the function must cover all inputs.
    assert (32767 % 32768) + 1 == 32768 > 32767
