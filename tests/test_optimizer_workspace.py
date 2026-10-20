"""Growing and reusing optimizer metadata must preserve arithmetic and branches."""
import pytest

from tests.support import compiler, run_value_batch


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_optimizer_workspace_growth(compiler, tmp_path, release, target):
    # Alternating large and small functions exercise both fresh metadata and
    # reused capacity. Constant division creates additional optimizer temps;
    # branch joins and loops require independent copy/version facts.
    sizes = [7, 193, 13, 389, 5]
    functions = []
    expected = 0
    for index, size in enumerate(sizes):
        lines = [f'work{index}=(x:int64):>int64=>{{', 'let a=x', 'let b=x+3']
        a, b = 11, 14
        for step in range(size):
            divisor = 3 + step % 11
            lines += [f'a=(a*17+{step + 1})%100003',
                      f'b+=(a//{divisor})']
            a = (a * 17 + step + 1) % 100003
            b += a // divisor
        lines += ['loop j in [0..7) {',
                  'if j%2=?0 {a+=b%97} else {b+=a%89}',
                  '}', 'return a+b', '}']
        for j in range(7):
            if j % 2 == 0:
                a += b % 97
            else:
                b += a % 89
        expected += a + b
        functions.append('\n'.join(lines))
    calls = '+'.join(f'work{i}(11)' for i in range(len(sizes)))
    source = '\n'.join(functions) + f'\nmain=():>int64=>{calls}\n'
    outcomes = run_value_batch(compiler, tmp_path, {'workspace': source}, release, target)
    code, diagnostic = outcomes['workspace']
    assert code == str(expected), diagnostic
