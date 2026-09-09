"""Mathematical integer facts survive library lowering and word boundaries."""

import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_proven_bigint_conversions_run_with_signed_and_unsigned_limits(tmp_path):
    text = '''
let signed = (x:bigint):>int64 => {
    if x <? -9223372036854775808 or x >? 9223372036854775807 return 42
    return x as int64
}
let unsigned = (x:bigint):>uint64 => {
    if x <? 0 or x >? 18446744073709551615 return 42
    return x
}
let small = (x:bigint):>int8 => {
    if x >=? -128 and x <=? 127 return x as int8
    return 42
}
let shifted = (x:bigint):>int64 => {
    if x <? 0 or x >? 100 return 42
    return (x + 1) as int64
}
let main = ():>int64 => {
    printl(signed(-9223372036854775808))
    printl(signed(9223372036854775807))
    printl(signed(9223372036854775808))
    if unsigned(18446744073709551615) =? 18446744073709551615 printl('unsigned maximum')
    else printl('bad unsigned value')
    printl(unsigned(-1))
    printl(small(-128))
    printl(small(127))
    printl(small(128))
    printl(shifted(12))
    let wide:uint64 = 18446744073709551615
    let big:bigint = wide
    if unsigned(big) =? wide printl('unsigned round trip')
    else printl('bad round trip')
    return 0
}
'''
    output = tmp_path / 'bigint_words.udewy'
    output.write_text(codegen(SrcFile(None, text)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        '-9223372036854775808', '9223372036854775807', '42',
        'unsigned maximum', '42', '-128', '127', '42', '13',
        'unsigned round trip',
    ]


@pytest.mark.parametrize('body', [
    'return x as int64',
    'if x >=? 0 return x as int64\nreturn 0',
    'if x <=? 127 return x as int8\nreturn 0',
    'if x >=? 0 and x <=? 127 { x = 999999999999999999999 return x as int8 }\nreturn 0',
    'if x >=? -385 and x <=? -384 return (x // 3) as int8\nreturn 0',
])
def test_unproven_bigint_word_boundaries_are_rejected(body):
    with pytest.raises(UserError, match='integer.*fit'):
        codegen(SrcFile(None, f'let f = (x:bigint):>int64 => {{ {body} }}'))


@pytest.mark.parametrize('write', ['x.sign = -1', 'x.limbs[0] = 256', 'x.limbs.push(1)'])
def test_component_writes_invalidate_the_containing_integer(write):
    with pytest.raises(UserError, match='integer.*fit'):
        codegen(SrcFile(None, f'''let f = (x:bigint):>uint8 => {{
    if x =? 0 return 0
    if x <? 1 or x >? 127 return 0
    {write}
    return x as uint8
}}'''))


def test_helper_spelling_does_not_grant_a_numeric_fact():
    with pytest.raises(UserError, match='integer.*fit'):
        codegen(SrcFile(None, '''
let _bigint_ge = (a:bigint b:bigint):>bool => true
let _bigint_le = (a:bigint b:bigint):>bool => true
let f = (x:bigint):>int64 => {
    if _bigint_ge(x 0) and _bigint_le(x 127) return x as int64
    return 0
}
'''))
