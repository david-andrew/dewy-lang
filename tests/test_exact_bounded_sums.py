"""Static exact sums use finite trip ceilings without a progress assumption."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_bounded_scalar_sums(compiler, tmp_path, release):
    source = tmp_path / 'sums.dewy'
    source.write_text('''$runtime_checks=false
$no_assumed_bounds
sum=(x:int32 n:int64<0 <=? n and n <=? 64>):>int64=>{
    let total:int64=0
    loop i in [0..n) {if i%2 =? 0 total+=x}
    return total
}
difference=(x:int32):>int64=>{
    let total:int64=7
    loop i in [0..64) {total-=x}
    return total
}
printl(sum(int32.min 64) sum(int32.max 63))
printl(difference(int32.min) difference(int32.max))
''')
    result = subprocess.run([compiler, *(['--release'] if release else []), source],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f'{32 * -2**31} {32 * (2**31-1)}',
        f'{7 + 64 * 2**31} {7 - 64 * (2**31-1)}',
    ]


@pytest.mark.parametrize('body', [
    'loop i in [0..64) {total+=x; total+=x}',
    'loop i in [0..64) {loop j in [0..64) {total+=x}}',
    'loop i in [0..64) {total=int64.max; total+=x}',
])
def test_unmodeled_updates_do_not_gain_sum_bounds(compiler, tmp_path, body):
    source = tmp_path / 'unknown.dewy'
    source.write_text('''$runtime_checks=false
$no_assumed_bounds
sum=(x:int32):>int64=>{let total:int64=0
''' + body + '\nreturn total}\nprintl(sum(1))\n')
    result = subprocess.run([compiler, 'build', source, '-o', tmp_path/'unknown'],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'cannot prove exact integer result fits' in result.stderr


def test_overflowing_trip_total_is_rejected(compiler, tmp_path):
    source = tmp_path / 'overflow.dewy'
    source.write_text('''$runtime_checks=false
$no_assumed_bounds
sum=(x:int32):>int64=>{
    let total:int64=int64.max-1
    loop i in [0..2) {total+=x}
    return total
}
printl(sum(2))
''')
    result = subprocess.run([compiler, 'build', source, '-o', tmp_path/'overflow'],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'cannot prove exact integer result fits' in result.stderr
