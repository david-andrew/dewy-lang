"""Explicit bigint operators route through the visible prelude identities."""
import test_bootstrap_check as source_values

# Small signatures isolate dispatch from the arithmetic library's algorithms.
# Execution of the real BigInt library belongs to the full native graph tests.
PREFIX = '''
BigInt:type=0|[sign:-1|1 limbs:array<uint64 length >? 0>]
let _bigint_from_int=(value:int64):>BigInt=>[sign=1 limbs=[1]]
let _bigint_from_uint=(value:uint64):>BigInt=>[sign=1 limbs=[1]]
let _bigint_from_int_nonzero=(value:int64 & ~0):>BigInt & ~0=>[sign=1 limbs=[1]]
let _bigint_from_uint_nonzero=(value:uint64 & ~0):>BigInt & ~0=>[sign=1 limbs=[1]]
let _bigint_neg=(value:BigInt):>BigInt=>value
let _bigint_to_int=(value:BigInt):>int64=>0
let _bigint_to_uint=(value:BigInt):>uint64=>0
'''
for suffix in ['add', 'sub', 'mul', 'floordiv', 'mod']:
    divisor = 'BigInt & ~0' if suffix in ('floordiv', 'mod') else 'BigInt'
    PREFIX += f'let _bigint_{suffix}=(a:BigInt b:{divisor}):>BigInt=>a\n'
for suffix in ['eq', 'ne', 'lt', 'le', 'gt', 'ge']:
    PREFIX += f'let _bigint_{suffix}=(a:BigInt b:BigInt):>bool=>false\n'

CASES = [PREFIX + f'let operation=(a:BigInt b:{other}):>{result}=>{left} {op} {right}'
         for op in ['+', '-', '*', '=?', 'not=?', '<?', '<=?', '>?', '>=?']
         for other, left, right in [('int64', 'a', 'b'), ('uint64', 'b', 'a'), ('int8', 'a', 'b'), ('uint8', 'b', 'a')]
         for result in ['bool' if '?' in op else 'BigInt']]
CASES += [PREFIX + body for body in [
    'let operation=(value:BigInt):>BigInt=>{let result=value result //= 4294967296 return result}',
    'let operation=(value:BigInt):>BigInt=>{let result=value result %= 4294967296 return result}',
    'let operation=(value:BigInt):>BigInt=>{let values:dict<string BigInt>=["value"->value] values["value"] //= 4294967296 return values["value"]}',
    'let operation=(a:int8):>BigInt=>a',
    'let operation=(a:uint8):>BigInt=>a',
    'let operation=(a:BigInt b:uint8 & ~0):>BigInt=>a // b',
    'let operation=(a:BigInt b:int8 & ~0):>BigInt=>a % b',
    'let operation=(a:BigInt):>int64=>a as int64',
    'let operation=(a:BigInt):>uint8=>a as uint8',
    'let operation=(a:int64):>BigInt=>{let value:BigInt=a return value}',

    'let operation=(a:BigInt):>BigInt=>-a',
    'let operation=(a:BigInt):>BigInt=>a+18446744073709551616',
    'let operation=(a:BigInt):>BigInt=>a // 2',
    'let operation=(a:BigInt b:int64 & ~0):>BigInt=>a % b',
    # An unknown word divisor leaves a proof obligation for bounds validation.
    'let operation=(a:BigInt b:int64):>BigInt=>a % b',
    'let operation=(a:BigInt b:BigInt):>BigInt=>if b not=? 0 a // b else 0',
]]
ERRORS = [PREFIX + body for body in [
    'let operation=(value:BigInt):>BigInt=>{let result=value result //= 0 return result}',
    'let operation=(value:BigInt divisor:BigInt):>BigInt=>{let result=value result //= divisor return result}',
    'let operation=(a:BigInt):>BigInt=>a // 0',
    'let operation=(a:BigInt b:BigInt):>BigInt=>a // b',
    'let operation=(a:BigInt):>BigInt=>a and 1',
]]


def test_native_bigint_operator_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)


def test_native_bigint_word_boundaries_require_proofs(tmp_path, monkeypatch):
    import test_bootstrap_bounds as native_bounds

    bodies = [
        'let convert=(x:BigInt):>int64=>{if x <? -9223372036854775808 or x >? 9223372036854775807 return 0 return x as int64}',
        'let convert=(x:BigInt):>uint64=>{if x <? 0 or x >? 18446744073709551615 return 0 return x}',
        'let convert=(x:BigInt):>int8=>if x >=? -128 and x <=? 127 x as int8 else 0',
        'let convert=(x:BigInt):>int64=>x as int64',
        'let convert=(x:BigInt):>uint64=>if x >=? 0 x as uint64 else 0',
        'let convert=(x:BigInt):>int8=>if x <=? 127 x as int8 else 0',
    ]
    monkeypatch.setattr(native_bounds, 'CASES', [PREFIX + body for body in bodies])
    native_bounds.test_native_bounds_visitor_matches_hosted(tmp_path)
