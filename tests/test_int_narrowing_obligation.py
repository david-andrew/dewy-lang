"""An `int` narrowed to a fixed width is the proven narrowing (docs/design/decisions.md, fixed-width
integers; docs/design/effects.md, the `panics` effect): `int32(x)`, `x as int32` and a store of an
`int` into a fixed-width binding, field, parameter or return is an obligation. Unproven, it is an
error under `$bulletproof`, and a runtime check that makes its function panic under
`$runtime_checks`. Wrapping and saturating conversions are total."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, command='check'):
    (tmp_path / 'main.dewy').write_text(source)
    return subprocess.run([compiler, command, 'main.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)


MAIN = ('main = ():>(void | OutOfMemory) & no panics => {\n'
        '    let x:int = 10^12\n'
        '    if args().length >? 5 x = 3\n')

# Each form of narrowing an unguarded `int`.
FORMS = {
    'call': ('', '    printl(int32(x))\n'),
    'as': ('', '    printl(x as int32)\n'),
    'binding': ('', '    let y:int32 = x\n    printl(y)\n'),
    'assign': ('', '    let y:int32 = 0\n    y = x\n    printl(y)\n'),
    'field': ('P:type = [v:int32]\n', '    let p = P[x]\n    printl(p.v)\n'),
    'param': ('take = (v:int32):>int32 => v\n', '    printl(take(x))\n'),
    'return': ('give = (n:int):>int32 => n\n', '    printl(give(x))\n'),
    'int64': ('', '    printl(int64(x * x))\n'),
    'uint64': ('', '    printl(uint64(x - 10^13))\n'),
}


@pytest.mark.parametrize('form', sorted(FORMS))
def test_unguarded_rejected_bulletproof(compiler, tmp_path, form):
    before, body = FORMS[form]
    result = run(compiler, tmp_path, '$bulletproof\n' + before + MAIN + body + '}\n')
    # (unknown, or refuted: x - 10^13 is always negative)
    message = 'does not fit uint64' if form == 'uint64' else 'for the conversion to '
    assert result.returncode != 0 and message in result.stderr, result.stdout + result.stderr


@pytest.mark.parametrize('form', ['call', 'binding', 'return', 'int64'])
def test_unguarded_panics_under_runtime_checks(compiler, tmp_path, form):
    before, body = FORMS[form]
    result = run(compiler, tmp_path, '$runtime_checks\n' + before + MAIN + body + '}\n')
    assert result.returncode != 0 and 'may panic' in result.stderr, result.stdout + result.stderr
    assert 'for the conversion to ' in result.stderr, result.stderr


# A 64-bit target is a narrowing too: a closed row that excludes failure rejects it.
def test_int64_target_is_a_possible_failure(compiler, tmp_path):
    result = run(compiler, tmp_path, '$runtime_checks\nf = (n:int):>int64 & allocates => int64(n)\nmain = () => printl(f(3))\n')
    assert result.returncode != 0 and 'possible failure exceeds' in result.stderr, result.stdout + result.stderr


ACCEPT = '''$bulletproof
narrow = (n:int):>int32 => {
    if n <? -1000 or n >? 1000 return 0
    int32(n)
}
store = (n:int):>int64 => {
    if n >=? 0 and n <? 1000000 {
        let y:int64 = n
        return y
    }
    0
}
cast = (n:int):>uint8 => if n >=? 0 and n <=? 255 n as uint8 else 0
wrap = (n:int):>uint8<overflow='wrap'> => uint8<overflow='wrap'>(n)
sat = (n:int):>int16<overflow='saturate'> => int16<overflow='saturate'>(n)
''' + MAIN + '''    printl"{narrow(x)} {narrow(7)} {store(x)} {store(5)} {cast(200)} {wrap(x + 1)} {wrap(257)} {sat(x)} {sat(-x)}"
}
'''


@pytest.mark.core_quick
def test_guarded_wrap_saturate_accepted(compiler, tmp_path):
    result = run(compiler, tmp_path, ACCEPT, 'run')
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == '0 7 0 5 200 1 1 32767 -32768\n', result.stdout
