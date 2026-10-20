"""Expected user behavior for the experimental source-level core."""
import base64
import ctypes
import json
import math
import os
import platform
import random
import re
import shutil
import struct
import subprocess
import zlib
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from tests.core_glsl_driver import DriverUnavailable, ShaderDriver
from tests import support
from tests.support import build_case_batch, build_exit_batch, case_source, run_value_batch, Scripts
from tests.support import compiler  # noqa: F401 (fixture)
from tools.compiler.bench import CHECKSUMS_1000, prepare_source



@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('integer, storage', [('int64', 'local'), ('int64', 'array'),
                                               ('int64', 'fixed'), ('int8', 'array'),
                                               ('uint8', 'array'), ('uint32', 'array'),
                                               ('uint8', 'local')])
def test_core_integer_interval_comparisons(compiler, tmp_path, target, release, integer, storage):
    bits = int(re.search(r'\d+', integer)[0])
    minimum = 0 if integer.startswith('u') else -(2**(bits-1))
    maximum = 2**bits-1 if integer.startswith('u') else 2**(bits-1)-1
    bounds = [(minimum, maximum), (minimum, minimum), (maximum, maximum),
              (-10, 10), (0, 256), (48, 57), (-5, -1), (5, 5), (5, -5),
              (-1, 0), (minimum, 0), (0, maximum), (minimum + 1, maximum - 1),
              (maximum, minimum)]
    bounds = [(lo, hi) for lo, hi in bounds if minimum <= lo <= maximum and minimum <= hi <= maximum]
    rng = random.Random(731)
    values = [minimum, minimum + 1, maximum - 1, maximum, *range(-12, 13),
              47, 48, 49, 56, 57, 58, 255, 256, 257,
              *(rng.randint(minimum, maximum) for _ in range(12))]
    values = [v for v in values if minimum <= v <= maximum]
    read = 'x' if storage == 'local' else 'xs[index]'
    parameter = f'x:{integer}' if storage == 'local' else f'xs:array<{integer}{" length=1" if storage == "fixed" else ""}> index:int64'
    argument = 'x' if storage == 'local' else '[x] 0'
    functions, body, expected = [], [], []
    for low, high in bounds:
        for lower_closed, upper_closed in [(True, True), (False, False),
                                           (True, False), (False, True)]:
            number = len(functions)
            lower = f'x {">=?" if lower_closed else ">?"} ({low})'
            upper = f'x {"<=?" if upper_closed else "<?"} ({high})'
            below = f'x {"<?" if lower_closed else "<=?"} ({low})'
            above = f'x {">?" if upper_closed else ">=?"} ({high})'
            # Reverse operands and conjunction order to cover equivalent source forms.
            if number % 2:
                lower = f'({low}) {"<=?" if lower_closed else "<?"} x'
                upper = f'({high}) {">=?" if upper_closed else ">?"} x'
                below = f'({low}) {">?" if lower_closed else ">=?"} x'
                above = f'({high}) {"<?" if upper_closed else "<=?"} x'
            inside = f'{lower} and {upper}' if number % 3 else f'{upper} and {lower}'
            outside = f'{below} or {above}' if number % 3 else f'{above} or {below}'
            inside, outside = inside.replace('x', read), outside.replace('x', read)
            functions.append(f'''probe_{number}=({parameter}):>int64=>{{
let a={inside} let b={outside} let result:int64=0
if a result+=1
if b result+=2
if {inside} result+=4
if {outside} result+=8
if not ({inside}) result+=16
if not ({outside}) result+=32
return result
}}''')
            body.append(f'printl(to_json([loop x in values probe_{number}({argument})]))')
            expected.append([37 if (x >= low if lower_closed else x > low)
                             and (x <= high if upper_closed else x < high) else 26
                             for x in values])
    literal = ' '.join(f'({x})' for x in values)
    program = '\n'.join(functions) + f'\nmain=()=>{{let values:array<{integer}>=[{literal}]\n'
    program += '\n'.join(body) + '\nreturn 42\n}'
    command, error = build_case_batch(compiler, tmp_path, {'intervals': program},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    assert [json.loads(line) for line in ran.stdout.splitlines()] == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('ordering', ['key', 'comparison'])
def test_core_sort_order(compiler, tmp_path, target, release, ordering):
    (tmp_path / 'keys.jo').write_text('''key = (i: int) -> (int, int): (i % 7, -i)
less = (a: int, b: int) -> bool: key(a) < key(b)
more = (a: int, b: int) -> bool: key(b) < key(a)
''')
    statements = ['from p"keys.jo" import key, less, more', 'main=()=>{']
    expected = []
    for size in [0, 1, 2, 15, 16, 17, 31, 32, 33, 129]:
        values = [(i * 79) % 137 for i in range(size)]
        literal = ' '.join(map(str, values))
        statements += [f'let values_{size}:array<int64>=[{literal}]']
        if ordering == 'key':
            statements += [f'printl(to_json(values_{size}.sorted_by(@key)))',
                           f'printl(to_json(values_{size}.sorted_by(@key true)))']
        else:
            statements += [f'let ascending_{size}=values_{size}',
                           f'let descending_{size}=values_{size}',
                           f'ascending_{size}.sort_with(@less)',
                           f'descending_{size}.sort_with(@more)',
                           f'printl(to_json(ascending_{size}))',
                           f'printl(to_json(descending_{size}))']
        statements += [f'printl(to_json(values_{size}))']
        expected += [sorted(values, key=lambda i: (i % 7, -i)),
                     sorted(values, key=lambda i: (i % 7, -i), reverse=True), values]
    statements += ['return 42', '}']
    command, error = build_case_batch(compiler, tmp_path, {'order': '\n'.join(statements)},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    assert [json.loads(line) for line in ran.stdout.splitlines()] == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_json_aggregates(compiler, tmp_path, target, release):
    # Core providers expose aggregate types whose Dewy declaration syntax is
    # still developing. Serialization must use their actual storage and tags.
    (tmp_path / 'types.jo').write_text('''enum Choice: idle, number(value: u64), text(value: str), list(values: int[])
struct Aggregate:
    pair: (u64, str)
    fixed: u64[3]
    nested: str[2][2]
    point: vec3
    mode: Choice
    choice: int | str
make = () -> Aggregate:
    fixed: u64[3] = [1, 2, u64(18446744073709551615)]
    nested: str[2][2] = [["a", "b"], ["c", "d"]]
    Aggregate((u64(18446744073709551615), "tuple"), fixed, nested, vec3(1.0, 2.0, 3.0), Choice.number(u64(18446744073709551615)), "union")
matrix = () -> mat4: mat4()
''')
    program = '''from p"types.jo" import make, Choice, Aggregate, matrix
main=()=>{
    let original=make()
    let text=to_json(original 2)
    printl(text)
    let copy=from_json<Aggregate>(text)
    if copy is? TextError {printl(copy.message) return 1}
    if to_json(copy) not=? to_json(original) return 2
    let variants=[Choice.idle Choice.number(uint64.max) Choice.text("hello") Choice.list([1 2 3])]
    loop variant in variants {
        printl(to_json(variant))
        let loaded=from_json<Choice>(to_json(variant))
        if loaded is? TextError {printl(loaded.message) return 3}
        if loaded not=? variant return 4
        let text_loaded=from_text<Choice>(to_text(variant))
        if text_loaded is? TextError return 5
        if text_loaded not=? variant return 6
    }
    printl(to_json(matrix()))
    printl(to_json(json_value(Choice.text("hello"))))
    let bad=[r'{"missing":[1]}' r'{"number":[]}' r'{"number":[1],"text":["extra"]}' r'{"idle":}']
    loop input in bad {
        let result=from_json<Choice>(input)
        if not (result is? TextError) return 7
    }
    return 42
}
'''
    command, error = build_case_batch(compiler, tmp_path, {'aggregates': program},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    decoder = json.JSONDecoder()
    output = ran.stdout.strip()
    values = []
    while output:
        value, end = decoder.raw_decode(output)
        values.append(value)
        output = output[end:].lstrip()
    maximum = 2**64 - 1
    assert values == [
        {'pair': [maximum, 'tuple'], 'fixed': [1, 2, maximum],
         'nested': [['a', 'b'], ['c', 'd']], 'point': [1, 2, 3],
         'mode': {'number': [maximum]}, 'choice': 'union'},
        'idle', {'number': [maximum]}, {'text': ['hello']}, {'list': [[1, 2, 3]]},
        [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], {'text': ['hello']},
    ]


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_json_scanning(compiler, tmp_path, target, release):
    # Exercise literal tokens and escaped strings with an independent JSON
    # oracle, including empty strings, UTF-8, controls and allocation boundaries.
    rng = random.Random(2917)
    values = ['', 'ordinary object key', 'é日本🙂', '"\\\n\t\r\b\f\0',
              None, True, False, 42, -3.125, -0.0, float('inf'), -float('inf'),
              *['a' * n for n in (1, 7, 8, 15, 16, 31, 32, 127, 1024)]]
    alphabet = 'abcXYZé日🙂"\\\n\t'
    for _ in range(48):
        text = ''.join(rng.choice(alphabet) for _ in range(rng.randrange(80)))
        values.extend([text, {'name': text, 'enabled': True, 'missing': None}])
    inputs, expected = [], []
    for value in values:
        for ascii_only in (False, True):
            inputs.append(json.dumps(value, ensure_ascii=ascii_only))
            expected.append(value)
    # Existing permissive unknown escapes and raw controls still use the same
    # decoder after a plain prefix. Do not silently tighten parsing in a speedup.
    inputs += ['"plain\\qtail"', '"raw\tcontrol"', '"prefix\\uD83D\\uDE42"']
    expected += ['plainqtail', 'raw\tcontrol', 'prefix🙂']

    def quote(text):
        return json.dumps(text, ensure_ascii=False).replace('{', r'\{').replace('}', r'\}')

    body = ['main=()=>{', 'let inputs=[' + ' '.join(map(quote, inputs)) + ']',
            'loop input in inputs {', 'let result=parse_json(input)',
            'if result is? JsonError {printl(result.message) return 1}',
            'printl(to_json(result))', '}']
    errors = [('', 'a value was expected, found the end', 1, 1),
              ('tru', 'a value was expected', 1, 1),
              ('nul', 'a value was expected', 1, 1),
              ('Infinit', 'a value was expected', 1, 1),
              ('falsex', 'more after the end of the value', 1, 6),
              ('"', 'the text has no closing \'"\'', 1, 2),
              ('"plain', 'the text has no closing \'"\'', 1, 7),
              ('"plain\\', 'the text has no closing \'"\'', 1, 8),
              ('"prefix\\u12x4"', '\\u needs four hex digits', 1, 12),
              ('\n  "abc', 'the text has no closing \'"\'', 2, 7)]
    body += ['let bad=[' + ' '.join(quote(x[0]) for x in errors) + ']',
             'loop input in bad {let result=parse_json(input)',
             'if not (result is? JsonError) return 2',
             'printl(to_json(result))', '}', 'return 42', '}']
    command, error = build_case_batch(compiler, tmp_path, {'scanning': '\n'.join(body)},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    assert [json.loads(line) for line in ran.stdout.splitlines()] == [
        *expected, *[dict(message=message, line=line, column=column)
                     for _, message, line, column in errors]]


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('unused', [False, True], ids=['generated-only', 'user-binding'])
def test_core_generated_binding_warnings(compiler, tmp_path, release, unused):
    source = tmp_path / 'warnings.dewy'
    binding = 'let forgotten=23' if unused else ''
    source.write_text('Point:type=[x:int64 y:int64]\nmain=()=>{\n'
                      'let base=Point[1 2]\nlet result=[base... x=20 x=40 y=2]\n'
                      + binding + '\nreturn result.x+result.y}\n')
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'program', *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    warnings = [line for line in built.stderr.splitlines() if 'warning:' in line]
    assert len(warnings) == int(unused), built.stderr
    if unused:
        assert "'forgotten' is given a value here but never used" in warnings[0]


@pytest.mark.parametrize('scope', ['unrelated', 'visible', 'alias', 'shadowed'])
def test_core_unused_global_hint_scope(compiler, tmp_path, scope):
    (tmp_path / 'other.dewy').write_text('let score=0\nkeep=()=>42\n')
    programs = {
        'unrelated': ('from p"other.dewy" import keep\n'
                      'main=()=>{let score=1 let scroe=2 return keep()}'),
        'visible': 'let score=0\nmain=()=>{let scroe=1 return 42}',
        'shadowed': ('let score=0\nprobe=(score:int64)=>{let scroe=1 return 42}\n'
                     'main=()=>probe(9)'),
        'alias': ('from p"other.dewy" import (score as points), keep\n'
                  'main=()=>{let poitns=1 return keep()}'),
    }
    source = tmp_path / 'main.dewy'
    source.write_text(programs[scope])
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True,
                             timeout=30, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert 'never used' in checked.stderr
    assert 'not seen from this file' not in checked.stderr
    assert "use '" not in checked.stderr
    if scope in ('unrelated', 'shadowed'):
        assert 'did you mean' not in checked.stderr
    else:
        name = 'points' if scope == 'alias' else 'score'
        assert f"did you mean the visible variable '{name}'" in checked.stderr


@pytest.mark.parametrize('scope', ['local', 'global'])
def test_core_copy_warning_dewy_syntax(compiler, tmp_path, scope):
    bindings = 'let xs=[Item[42]] let item=xs[0]\n'
    body = 'item.hp-=5 return xs[0].hp'
    source = tmp_path / 'copy.dewy'
    source.write_text('Item:type=[hp:int64]\n' +
                      (bindings + f'main=()=>{{{body}}}' if scope == 'global'
                       else f'main=()=>{{{bindings}{body}}}'))
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True,
                             timeout=30, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert 'holds a copy' in checked.stderr
    assert 'loop @e in xs' in checked.stderr
    assert 'loop mut' not in checked.stderr


def test_core_debug_local_values(compiler, tmp_path):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or not shutil.which('gdb'):
        pytest.skip('native Linux x86-64 with GDB required')
    source = tmp_path / 'main.dewy'
    source.write_text('''Pair:type=[left:int64 right:int64]
probe=():>int64=>{
let result=Pair[20 21]
result.right+=1
let total=result.left+result.right
printl"{total}"
return total
}
main=()=>probe()
''')
    binary = tmp_path / 'program'
    built = subprocess.run([compiler, 'build', source, '-g', '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    debugged = subprocess.run([
        'gdb', '--batch', '-nx', '-ex', f'break {source}:6', '-ex', 'run',
        '-ex', 'printf "scalar=%ld\\n", total',
        '-ex', 'printf "field=%ld\\n", result.right', str(binary),
    ], capture_output=True, text=True, timeout=30, check=False)
    assert debugged.returncode == 0, debugged.stdout + debugged.stderr
    assert 'scalar=42' in debugged.stdout, debugged.stdout
    assert 'field=22' in debugged.stdout, debugged.stdout


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_exit_batch_results(compiler, tmp_path, target):
    cases = {'first': 'main=()=>panic("first case panic")',
             'normal': 'main=()=>printl"normal return"',
             'last': 'main=()=>panic("last case panic")'}
    command, failure = build_exit_batch(compiler, tmp_path, cases, False, target)
    assert failure is None, failure
    for index, message in enumerate(['first case panic', 'normal return', 'last case panic']):
        ran = subprocess.run([*command, str(index)], capture_output=True, text=True,
                             timeout=10, check=False)
        assert (ran.returncode == 0) == (index == 1), ran.stdout + ran.stderr
        assert message in ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_value_batch_results(compiler, tmp_path, target, monkeypatch):
    calls = []
    original = support.build_case_batch

    def counted(*args, **kwargs):
        calls.append(tuple(args[2]))
        return original(*args, **kwargs)

    monkeypatch.setattr('tests.support.build_case_batch', counted)
    cases = {
        'first': 'value=1\nmain=()=>{value+=1 printl"first 🙂" return 42}',
        'wrong': 'value=40\nmain=()=>{printl"wrong result" return 17}',
        'last': 'value=40\nmain=()=>if value =? 40 42 else 1',
    }
    outcomes = support.run_value_batch(compiler, tmp_path, cases, False, target)
    assert outcomes == {'first': ('42', 'first 🙂\n'), 'wrong': ('17', 'wrong result\n'),
                        'last': ('42', '')}
    assert calls == [('first', 'wrong', 'last')], 'successful batches should compile once'


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('failure', ['compile', 'runtime', 'exit-zero'])
def test_core_value_batch_failures(compiler, tmp_path, target, failure):
    bad = {'compile': 'main=()=>missing_batch_name',
           'runtime': 'main=()=>{panic("intentional batch stop") return 42}',
           'exit-zero': 'main=()=>{exit(0) return 42}'}[failure]
    outcomes = support.run_value_batch(compiler, tmp_path,
                                       {'first': 'main=()=>42', 'bad': bad, 'last': 'main=()=>42'}, False, target)
    assert outcomes['first'] == outcomes['last'] == ('42', '')
    code, diagnostic = outcomes['bad']
    assert code is None and str(tmp_path) in diagnostic
    assert {'compile': 'bad.dewy', 'runtime': 'intentional batch stop',
            'exit-zero': 'Missing result for bad'}[failure] in diagnostic


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_value_batch_combined_failure(compiler, tmp_path, target, monkeypatch):
    original = support.build_case_batch

    def combined_only(*args, **kwargs):
        if len(args[2]) > 1:
            return None, 'injected failure requiring the combined program'
        return original(*args, **kwargs)

    monkeypatch.setattr('tests.support.build_case_batch', combined_only)
    outcomes = support.run_value_batch(compiler, tmp_path,
                                       {'first': 'main=()=>42', 'last': 'main=()=>42'}, False, target)
    assert outcomes == {name: (None, 'injected failure requiring the combined program')
                        for name in ('first', 'last')}


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
@pytest.mark.parametrize('both', [False, True], ids=['fallback', 'preferred'])
def test_core_named_module_languages(compiler, tmp_path, extension, both):
    other = 'jo' if extension == 'dewy' else 'dewy'
    (tmp_path / f'helper.{other}').write_text('answer=()=>41' if other == 'dewy' else 'answer = (): 41')
    expected = 41
    if both:
        expected = 42
        (tmp_path / f'helper.{extension}').write_text('answer=()=>42' if extension == 'dewy' else 'answer = (): 42')
    source = tmp_path / f'main.{extension}'
    if extension == 'dewy':
        source.write_text(f'from helper import answer\nmain=()=>if answer() =? {expected} 42 else 1')
    else:
        source.write_text(f'from helper import answer\nmain = (): if answer() == {expected}: 42 else: 1')
    binary = tmp_path / 'imports'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
def test_core_bundled_module_path(compiler, tmp_path, extension):
    (tmp_path / 'bigint.dewy').write_text('bigint=(value)=>0')
    (tmp_path / 'bigint.jo').write_text('bigint = (value): 0')
    source = tmp_path / f'main.{extension}'
    if extension == 'dewy':
        source.write_text('from p"@lib/bigint.dewy" import bigint\nmain=()=>if bigint(42).to_int64() =? 42 42 else 1')
    else:
        source.write_text('from "@lib/bigint.dewy" import bigint\nmain = (): if bigint(42).to_int64() == 42: 42 else: 1')
    binary = tmp_path / 'bundled'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('notation', ['constructor', 'division'])
def test_core_rational_arithmetic(compiler, tmp_path, target, release, notation):
    values = [(0, 1), (0, -13), (1, 1), (-1, 1), (1, 2), (-1, 2), (2, -3),
              (-2, -3), (4, 6), (10**50, 10**25), (2**127-1, 2**96+1), (-2**63, 2**64-1)]
    pairs = [(a, b) for a in values for b in values if b[0]]
    rng = random.Random(42027)
    for _ in range(96):
        parts = [rng.getrandbits(rng.choice([32, 64, 128, 256])) * rng.choice([-1, 1]) or 1
                 for _ in range(4)]
        pairs.append((tuple(parts[:2]), tuple(parts[2:])))
    (tmp_path / 'cases.txt').write_text('\n'.join(f'{a} {b} {c} {d}' for (a, b), (c, d) in pairs))
    source = tmp_path / 'fractions.dewy'
    body = '''from rational import rational
main=():>void=>{
let input=$include_bytes(p"cases.txt") as string|none
if input is? none panic("invalid test data")
loop line in input.split("\n") {
    let fields=line.split(" ")
    let a=rational(fields[0] fields[1]) let b=rational(fields[2] fields[3])
    let parts=a.divmod(b)
    if a//b not=? parts.quotient or a%b not=? parts.remainder panic("division operators disagree")
    if b*parts.quotient+parts.remainder not=? a panic("division reconstruction")
    printl"{a+b}|{a-b}|{a*b}|{a/b}|{parts.quotient}|{parts.remainder}|{a <? b}|{a =? b}|{a.floor()}|{a.ceil()}|{a.pow(3)}"
}
}
'''
    if notation == 'division':
        body = body.replace('from rational import rational', 'from bigint import bigint')
        body = body.replace('rational(fields[0] fields[1])', 'bigint(fields[0])/bigint(fields[1])')
        body = body.replace('rational(fields[2] fields[3])', 'bigint(fields[2])/bigint(fields[3])')
    source.write_text(body)
    expected = []
    for left, right in pairs:
        a, b = Fraction(*left), Fraction(*right)
        expected.append('|'.join(map(str, [a+b, a-b, a*b, a/b, a//b, a%b]))
                        + f'|{str(a < b).lower()}|{str(a == b).lower()}'
                        + f'|{math.floor(a)}|{math.ceil(a)}|{a**3}')
    binary = tmp_path / 'fractions'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web rational checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'fractions.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_exact_float_conversions(compiler, tmp_path, target, release):
    values = {Fraction(0), Fraction(1, 3), Fraction(2, 3), Fraction(2**4096+1, 2**4096-1)}
    for fraction_bits, bias in [(23, 127), (52, 1023)]:
        minimum = 1-bias-fraction_bits
        exponents = [minimum-1, minimum, minimum+1, -bias, 1-bias, 2-bias,
                     -fraction_bits-1, -1, 0, 1, fraction_bits, fraction_bits+1, bias-1, bias, bias+1]
        for exponent in exponents:
            base = Fraction(2)**exponent
            unit = Fraction(2)**max(exponent-fraction_bits, minimum)
            half = base+unit/2
            values.update([base, base+unit, half, half-unit/2**200,
                           half+unit/2**200, base+3*unit/2])
        largest = (2-Fraction(2)**(-fraction_bits))*Fraction(2)**bias
        half = largest+Fraction(2)**(bias-fraction_bits-1)
        values.update([largest, half, half-Fraction(2)**(bias-fraction_bits-200),
                       half+Fraction(2)**(bias-fraction_bits-200)])
        # These perturbations disappear if the conversion rounds to float64
        # before float32, or rounds either part before dividing.
        half = 1+Fraction(2)**(-fraction_bits-1)
        values.update([half-Fraction(2)**-2000, half+Fraction(2)**-2000])
    rng = random.Random(42029)
    for _ in range(96):
        numerator = rng.getrandbits(rng.choice([32, 64, 256, 1024, 2048, 4096])) or 1
        denominator = rng.getrandbits(rng.choice([32, 64, 256, 1024, 2048, 4096])) or 1
        values.add(Fraction(numerator, denominator))
    values |= {-value for value in values}
    values = sorted(values)
    (tmp_path / 'cases.txt').write_text('\n'.join(f'{v.numerator} {v.denominator}' for v in values))
    # CPython converts Fraction directly to a correctly rounded double. libc's
    # decimal-to-float parser supplies an independent single-precision oracle;
    # 5,000 digits resolve these <=4,096-bit inputs around every rounding tie.
    libc = ctypes.CDLL(None)
    libc.strtof.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p)]
    libc.strtof.restype = ctypes.c_float

    def bits(value):
        try:
            double = float(value)
        except OverflowError:
            double = -math.inf if value < 0 else math.inf
        with localcontext() as context:
            context.prec = 5000
            text = str(Decimal(value.numerator)/Decimal(value.denominator))
        single = libc.strtof(text.encode(), None)
        return [struct.unpack('>Q', struct.pack('>d', double))[0],
                struct.unpack('>I', struct.pack('>f', single))[0]]

    expected = ['|'.join(map(str, bits(Fraction(v.numerator))+bits(v))) for v in values]
    source = tmp_path / 'conversions.dewy'
    source.write_text('''from bigint import bigint
from rational import rational
main=():>void=>{
let input=$include_bytes(p"cases.txt") as string|none
if input is? none panic("invalid test data")
loop line in input.split("\n") {
    let fields=line.split(" ")
    let numerator=bigint(fields[0])
    let value=rational(numerator bigint(fields[1]))
    printl"{f64_bits(numerator.to_float64())}|{f32_bits(numerator.to_float32())}|{f64_bits(value.to_float64())}|{f32_bits(value.to_float32())}"
}
}
''')
    binary = tmp_path / 'conversions'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web floating conversion checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'conversions.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_magnitude_reference(compiler, tmp_path, target, release):
    # Python's independently implemented hypot is the numerical reference.
    smallest = math.ulp(0.0)
    largest = float.fromhex('0x1.fffffffffffffp+1023')
    boundary = largest / math.sqrt(2.0)
    cases = [[], [0.0, -0.0], [3.0, 4.0], [3e200, 4e200], [3e-200, 4e-200],
             [smallest], [smallest, smallest], [largest], [largest, smallest],
             [largest, largest], [math.inf, math.nan], [math.nan, -math.inf],
             [math.nan, 1.0], [-math.inf, 0.0]]
    for direction in [0.0, math.inf]:
        value = boundary
        for _ in range(4):
            cases.append([value, value])
            value = math.nextafter(value, direction)
    rng = random.Random(73021)
    for exponent in [-1074, -1060, -1022, -540, -512, -500, -1, 0, 500, 512, 1000, 1022]:
        for count in [1, 2, 3, 9, 64, 257]:
            cases.append([math.ldexp(rng.uniform(-1.0, 1.0), exponent) for _ in range(count)])
    for _ in range(40):
        cases.append([math.ldexp(rng.uniform(-1.0, 1.0), rng.randrange(-1074, 1023))
                      for _ in range(rng.choice([2, 3, 9, 64]))])

    def bits(value):
        return struct.unpack('>Q', struct.pack('>d', value))[0]

    rows = '\n'.join('[' + ' '.join(str(bits(v)) for v in values) + ']' for values in cases)
    source = tmp_path / 'magnitudes.dewy'
    source.write_text('let rows:array<array<uint64>>=[\n' + rows + '''\n]
main=()=>{
loop words in rows {
let values=[loop word in words f64_from_bits(word)]
let pair=if values.length =? 2 hypot(values[0] values[1]) else 0.0
printl"{f64_bits(norm(values))}|{f64_bits(pair)}"
}
return 0
}
''')
    binary = tmp_path / 'magnitudes'
    flags = (['--release'] if release else []) + (['--target', 'wasm'] if target == 'wasm' else [])
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web magnitude checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'magnitudes.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    outputs = ran.stdout.splitlines()
    assert len(outputs) == len(cases), ran.stdout
    for values, output in zip(cases, outputs, strict=True):
        actual = [struct.unpack('>d', struct.pack('>Q', int(v)))[0] for v in output.split('|')]
        expected = [math.nan if any(math.isnan(v) for v in values) else math.hypot(*values),
                    math.hypot(*values) if len(values) == 2 else 0.0]
        for got, want in zip(actual, expected, strict=True):
            if math.isnan(want):
                assert math.isnan(got), (values, got, want)
            elif not math.isfinite(want) or want == 0.0:
                assert bits(got) == bits(want), (values, got, want)
            else:
                assert math.isfinite(got) and abs(got-want) <= 8*math.ulp(want), (values, got, want)


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('example', ['exact_integers', 'exact_rationals'])
def test_core_exact_example(compiler, tmp_path, target, release, example):
    source = Path(__file__).resolve().parents[1] / f'examples/{example}.dewy'
    binary = tmp_path / 'exact'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web bigint checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'exact.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    if example == 'exact_rationals':
        harmonic = sum(Fraction(1, n) for n in range(1, 11))
        chance = 45 * Fraction(1, 6)**2 * Fraction(5, 6)**8
        quotient, remainder = divmod(Fraction(-7, 3), Fraction(2, 5))
        assert ran.stdout.splitlines() == [f'First ten harmonic terms: {harmonic}',
                                          f'Exactly two sixes in ten rolls: {chance}',
                                          'Reciprocal cube of 2/3: 27/8', 'Sixty exact time steps: 1',
                                          f'Floor quotient: {quotient}; remainder: {remainder}']
        return
    quotient, remainder = divmod(-123456789012345678901234567890, 9876543210987654321)
    assert ran.stdout.splitlines() == [f'100! = {math.factorial(100)}',
                                      f'Ways to choose 50 of 100: {math.comb(100, 50)}',
                                      f'Floor quotient: {quotient}; remainder: {remainder}',
                                      'Reconstruction: true', f'2^256 = {2**256}']


def integer_literal(value, prefix, alphabet):
    digits = ''
    while value:
        value, digit = divmod(value, len(alphabet))
        digits = alphabet[digit] + digits
    digits = digits or '0'
    return prefix + '_'.join(digits[i:i+4] for i in range(0, len(digits), 4))


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_bigint_literal_bases(compiler, tmp_path, target, release):
    alphabets = [('0b', '01'), ('0t', '012'), ('0q', '0123'), ('0s', '012345'),
                 ('0o', '01234567'), ('0d', '0123456789'), ('0z', '0123456789xe'),
                 ('0x', '0123456789ABCDEF')]
    values = [2**63+1, 2**64, 2**64+1, 2**127-1, 2**128+17, 2**255+43, 2**1023+7]
    rng = random.Random(42028)
    values += [rng.getrandbits(257) for _ in range(8)]
    statements, expected = [], []
    for prefix, alphabet in alphabets:
        for value in values:
            literal = integer_literal(value, prefix, alphabet)
            for sign in ['', '-']:
                statements.append(f'printl"{{bigint({sign}{literal})}}"')
                expected.append(str(-value if sign else value))
    # A local module cannot replace the implementation of a numeric literal.
    (tmp_path / 'bigint.dewy').write_text('BigInt:type=[wrong:bool]\n')
    source = tmp_path / 'literals.dewy'
    source.write_text('from p"@lib/bigint.dewy" import bigint\nmain=():>void=>{\n' + '\n'.join(statements) + '\n}\n')
    binary = tmp_path / 'literals'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web literal checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'literals.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_bigint_literal_modules(compiler, tmp_path, target, release):
    (tmp_path / 'rational.dewy').write_text('rational=()=>"wrong library"\n')
    (tmp_path / 'constants.dewy').write_text('''from bigint import BigInt
const amount:BigInt=123456789012345678901234567890
const fraction=amount/7
read=(value=amount)=>value+1
fractional=(value=fraction)=>value*7
''')
    source = tmp_path / 'main.dewy'
    source.write_text('''from bigint import bigint
from constants import amount, read, fractional
main=()=>if amount+1 =? read() and read(bigint(18446744073709551616)) =? bigint(18446744073709551617)
and fractional() =? amount 42 else 1
''')
    binary = tmp_path / 'modules'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web literal checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'modules.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_bigint_arithmetic(compiler, tmp_path, target, release):
    boundary = [0, 1, -1, 2, -2]
    for bits in [31, 32, 63, 64, 96, 128]:
        boundary.extend([2**bits-1, 2**bits, 2**bits+1, -(2**bits-1), -(2**bits+1)])
    divisors = [1, -1, 3, -3, 2**32-1, -(2**32-1), 2**32+1, -(2**32+1), 2**96-1, -(2**96+1)]
    pairs = [(a, b) for a in boundary for b in divisors]
    # Algorithm D: a low divisor limb forces the final add-back; a quotient
    # estimate at the limb base forces the estimate correction before subtract.
    base = 2**32
    for divisor in [base**2 * (base//2) + 1, base**2 - 1, base**2 + base - 1]:
        for multiplier in [2, base - 1, base, base + 1]:
            for offset in [-1, 0, 1]:
                numerator = divisor * multiplier + offset
                pairs.extend((a, b) for a in [numerator, -numerator] for b in [divisor, -divisor])
    rng = random.Random(42026)
    for _ in range(128):
        a = rng.getrandbits(rng.choice([32, 64, 128, 256, 512]))
        b = rng.getrandbits(rng.choice([32, 64, 128, 256])) or 1
        pairs.append((a * rng.choice([-1, 1]), b * rng.choice([-1, 1])))
    (tmp_path / 'cases.txt').write_text('\n'.join(f'{a} {b}' for a, b in pairs))
    source = tmp_path / 'bigint.dewy'
    source.write_text('''from bigint import BigInt, bigint
main=():>void=>{
let input=$include_bytes(p"cases.txt") as string|none
if input is? none panic("invalid test data")
loop line in input.split("\n") {
    let fields=line.split(" ")
    let a=bigint(fields[0]) let b=bigint(fields[1])
    let parts=a.divmod(b)
    if a//b not=? parts.quotient or a%b not=? parts.remainder panic("division operators disagree")
    printl"{a+b}|{a-b}|{a*b}|{parts.quotient}|{parts.remainder}|{a.gcd(b)}|{a <? b}|{a =? b}"
}
}
''')
    expected = ['|'.join(map(str, [a+b, a-b, a*b, a//b, a%b, math.gcd(a, b)]))
                + f'|{str(a < b).lower()}|{str(a == b).lower()}' for a, b in pairs]
    binary = tmp_path / 'bigint'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web bigint checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'bigint.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('form', ['unit', 'stepped', 'stored-unit', 'stored-stepped',
                                  'stored-open-unit', 'stored-open-stepped'])
def test_core_integer_ranges(compiler, tmp_path, target, release, form):
    cases, expected = [], []

    def add(kind, start, second, end, inclusive):
        if form.startswith('stored-') and kind != 's':
            return
        step = second - start if form.endswith('stepped') else 1
        if not step:
            return
        stop = end + (1 if step > 0 else -1) if inclusive else end
        values = range(start, stop, step)
        if form.startswith('stored-open-'):
            values = values[1:]
        try:
            if len(values) > 32:
                return
        except OverflowError:
            return
        cases.append(f'{kind}|{start}|{second}|{end}|{int(inclusive)}')
        expected.extend(str(value) for value in values)
        if form.startswith('stored-'):
            expected.extend(str(needle in values).lower() for needle in [start, second, end, 0])
        expected.append('end')

    for kind, edges in [('s', [-2**63, -2**63+1, -4, 0, 4, 2**63-2, 2**63-1]),
                        ('u', [0, 1, 2, 2**63-1, 2**63, 2**64-2, 2**64-1])]:
        for start in edges:
            for second in (edges if form.endswith('stepped') else [start]):
                for end in edges:
                    for inclusive in [False, True]:
                        add(kind, start, second, end, inclusive)
    rng = random.Random(42028)
    for _ in range(128):
        start = rng.randrange(-100, 101)
        step = rng.choice([n for n in range(-17, 18) if n])
        add('s', start, start + step, start + rng.randrange(-50, 51), rng.choice([False, True]))
    (tmp_path / 'cases.txt').write_text('\n'.join(cases))
    source = tmp_path / 'ranges.dewy'
    source.write_text('''from bigint import bigint
emit=<T>(a:T b:T end:T inclusive:bool):>void=>{
let count:int64=0
if inclusive {
    loop i in [a,b..end] {if count >=? 32 panic("loop did not terminate") printl(i) count+=1}
} else {
    loop i in [a,b..end) {if count >=? 32 panic("loop did not terminate") printl(i) count+=1}
}
printl"end"
}
main=():>void=>{
let input=$include_bytes(p"cases.txt") as string|none
if input is? none panic("invalid test data")
loop line in input.split("\\n") {
    let fields=line.split("|") let inclusive=fields[4] =? "1"
    if fields[0] =? "s" {
        let a=bigint(fields[1]).to_int64() let b=bigint(fields[2]).to_int64() let end=bigint(fields[3]).to_int64()
        if a is? none or b is? none or end is? none panic("invalid signed bounds")
        emit<int64>(a b end inclusive)
    } else {
        let a=bigint(fields[1]).to_uint64() let b=bigint(fields[2]).to_uint64() let end=bigint(fields[3]).to_uint64()
        if a is? none or b is? none or end is? none panic("invalid unsigned bounds")
        emit<uint64>(a b end inclusive)
    }
}
}
''')
    if form.startswith('stored-'):
        source.write_text(source.read_text()
                          .replace('loop i in [a,b..end] {', 'let r=[a,b..end] loop i in r {')
                          .replace('loop i in [a,b..end) {', 'let r=[a,b..end) loop i in r {')
                          .replace('count+=1}', 'count+=1} printl(a in? r) printl(b in? r) printl(end in? r) printl(0 in? r)')
                          .replace('emit<uint64>(a b end inclusive)', 'panic("stored inputs must be signed")'))
    if form.endswith('unit'):
        source.write_text(source.read_text().replace('a,b..', 'a..'))
    if form.startswith('stored-open-'):
        source.write_text(source.read_text().replace('let r=[', 'let r=('))
    binary = tmp_path / 'ranges'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web range checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'ranges.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_bigint_bits(compiler, tmp_path, target, release):
    rng = random.Random(42027)
    values = [0, 1, -1]
    for bits in [31, 32, 33, 63, 64, 65, 127, 128, 256]:
        for delta in [-1, 0, 1]:
            value = 2**bits + delta
            values.extend([value, -value])
    counts = [0, 1, 31, 32, 33, 63, 64, 65, 127, 256, 4096]
    cases = [(a, b, counts[i % len(counts)]) for i, a in enumerate(values)
             for b in [0, 1, -1, 2**32-1, -(2**32+1), 2**128]]
    for _ in range(128):
        a = rng.getrandbits(rng.choice([32, 64, 256, 512, 1024, 4096])) * rng.choice([-1, 1])
        b = rng.getrandbits(rng.choice([32, 64, 256, 512, 1024, 4096])) * rng.choice([-1, 1])
        cases.append((a, b, rng.choice(counts)))
    (tmp_path / 'cases.txt').write_text('\n'.join(f'{a} {b} {count}' for a, b, count in cases))
    source = tmp_path / 'bits.dewy'
    source.write_text('''from bigint import bigint
main=():>void=>{
let input=$include_bytes(p"cases.txt") as string|none
if input is? none panic("invalid test data")
loop line in input.split("\\n") {
    let fields=line.split(" ")
    let a=bigint(fields[0]) let b=bigint(fields[1]) let count=to_int(fields[2])
    if count is? none panic("invalid shift count")
    printl"{a and b}|{a or b}|{a xor b}|{not a}|{a << count}|{a >> count}"
}
}
''')
    expected = ['|'.join(map(str, [a & b, a | b, a ^ b, ~a, a << count, a >> count]))
                for a, b, count in cases]
    binary = tmp_path / 'bits'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web bigint checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'bits.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_word_power_arithmetic(compiler, tmp_path, target, release):
    signed = [-2**63, -2**63+1, -65537, -3, -2, -1, 0, 1, 2, 3, 65537, 2**63-1]
    unsigned = [0, 1, 2, 3, 2**32-1, 2**32, 2**63, 2**64-2, 2**64-1]
    exponents = [0, 1, 2, 3, 7, 16, 31, 32, 63, 64, 127, 255]
    source = tmp_path / 'powers.dewy'
    source.write_text(f'''main=():>void=>{{
let signed:array<int64>=[{' '.join(map(str, signed))}]
let unsigned:array<uint64>=[{' '.join(map(str, unsigned))}]
let exponents:array<int64>=[{' '.join(map(str, exponents))}]
loop a in signed {{loop n in exponents {{printl"{{a^n}}"}}}}
loop a in unsigned {{loop n in exponents {{printl"{{a^n}}"}}}}
}}
''')
    expected = []
    for a in signed:
        for n in exponents:
            value = pow(a, n, 2**64)
            expected.append(str(value if value < 2**63 else value - 2**64))
    expected.extend(str(pow(a, n, 2**64)) for a in unsigned for n in exponents)
    binary = tmp_path / 'powers'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web power checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'powers.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_set_algebra(compiler, tmp_path, target, release):
    keys = [-2, 0, 3, 5]
    members = [[key for i, key in enumerate(keys) if mask & (1 << i)] for mask in range(16)]
    literals = ' '.join('set['+' '.join(map(str, values))+']' for values in members)
    source = tmp_path / 'sets.dewy'
    source.write_text('''digest=(values:set<int64>):>int64=>{
let result:int64=7 loop value in values {result=result*11+value+5} return result}
main=():>void=>{
let values:array<set<int64>>=['''+literals+''']
loop a in values {loop b in values {
printl(digest(a & b)) printl(digest(a | b))
printl(digest(a-b)) printl(digest(a xor b)) printl(a =? b)
}}
}''')
    expected = []
    for left in members:
        for right in members:
            a, b = set(left), set(right)
            results = ([v for v in left if v in b], list(dict.fromkeys(left+right)),
                       [v for v in left if v not in b],
                       [v for v in left if v not in b]+[v for v in right if v not in a])
            for values in results:
                checksum = 7
                for value in values:
                    checksum = checksum*11+value+5
                expected.append(str(checksum))
            expected.append(str(a == b).lower())
    binary = tmp_path / 'sets'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web set checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'sets.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_bounded_remainder_ir(compiler, tmp_path, target, release):
    source = tmp_path / 'bounded.dewy'
    source.write_text(case_source('numeric/bounded_remainder'))
    flags = ['--ir', *(['--release'] if release else []), *(['--target', 'wasm'] if target == 'wasm' else [])]
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'bounded', *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    # The recurrence may now live entirely in main after inlining.
    output = built.stdout + built.stderr
    probe = (re.search(r'^fn f_probe_.*?(?=^fn |\Z)', output, re.M | re.S)
             or re.search(r'^fn f_main_.*?(?=^fn |\Z)', output, re.M | re.S))
    assert probe, 'bounded recurrence was not emitted'
    assert re.search(r' = (mulhu|remu) ', probe[0]), 'bounded recurrence still uses signed remainder'
    assert ' = mulhs ' not in probe[0]


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_constant_floor_ir(compiler, tmp_path, target):
    source = tmp_path / 'constant.dewy'
    source.write_text('''probe=(a:int64):>int64=>a%3+a//3+a%8+a//8
main=()=>probe(-7)
''')
    built = subprocess.run([compiler, 'build', source, '--ir', '--target', target,
                            '-o', tmp_path / 'constant'],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_probe_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    assert probe, 'constant arithmetic probe was not emitted'
    assert 'call' not in probe[0], 'literal floor arithmetic still calls a helper in default builds'


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_constant_match_lookup(compiler, tmp_path, target, release):
    # The value batches cover widths, holes, unsigned/extreme keys and effects.
    # Keep this probe out of callers so the lookup itself stays inspectable.
    source = tmp_path / 'lookup.jo'
    source.write_text("""@noinline
lookup_probe = (key: int) -> int:
    match key:
        -2: 17
        0: 3
        3: 42
        _: 5
main = () -> int: lookup_probe(3)
""")
    flags = ['--ir', '--target', target, *(['--release'] if release else [])]
    binary = tmp_path / 'lookup'
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_lookup_probe_.*?(?=^fn |\Z)',
                      built.stdout + built.stderr, re.M | re.S)
    assert probe, 'constant match probe was not emitted'
    assert 'brtable' not in probe[0], probe[0]
    assert ' = daddr ' in probe[0] and ' = load ' in probe[0], probe[0]


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('subject', ['integer', 'enum', 'grouped-int'])
def test_core_grouped_match_lookup(compiler, tmp_path, target, release, subject):
    selected = [0, 58, 64, 66, 68, 71, 81, 83, 91, 93]
    result_type = 'bool'
    if subject == 'enum':
        declaration = 'enum Tag: ' + ', '.join(f'v{i}' for i in range(96)) + '\n'
        parameter = 'Tag'
        patterns = ', '.join(f'v{i}' for i in selected)
        values = '[' + ', '.join(f'Tag.v{i}' for i in range(96)) + ']'
        yes, no = 'false', 'true'
    else:
        declaration, parameter = '', 'int'
        patterns = ', '.join(map(str, selected))
        values = '[loop i in [-2..258): i] + [int.min, int.max]'
        yes, no = 'true', 'false'
        if subject == 'grouped-int':
            selected = [-2, 0, 3]
            patterns = ', '.join(map(str, selected))
            result_type, yes, no = 'int', '32767', '-127'
    reference = ' or '.join(f'int(key) == {i}' for i in selected)
    membership = reference
    if subject == 'enum':
        reference = f'not ({reference})'
    elif subject == 'grouped-int':
        reference = f'if {reference}: {yes} else: {no}'
    source = tmp_path / 'grouped.jo'
    effect_patterns = ', '.join(map(str, selected))
    source.write_text(declaration + f'''calls = 0
evaluated = (key: int) -> int:
    calls += 1
    key
effectful = (key: int) -> bool:
    match evaluated(key):
        {effect_patterns}:
            calls += 10
            true
        _: false
@noinline
lookup_probe = (key: {parameter}) -> {result_type}:
    match key:
        {patterns}: {yes}
        _: {no}
main = () -> int:
    loop key in {values}:
        if lookup_probe(key) != ({reference}): return 1
        before = calls
        hit = {membership}
        if effectful(int(key)) != hit: return 2
        if calls != before + 1 + (if hit: 10 else: 0): return 3
    42
''')
    binary = tmp_path / 'grouped'
    flags = ['--ir', '--target', target, *(['--release'] if release else [])]
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_lookup_probe_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    assert probe and ' = daddr ' in probe[0] and ' = load ' in probe[0], built.stdout
    assert probe[0].count(' = eq ') < 3, 'grouped alternatives still form a comparison chain'
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web lookup checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'grouped.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('kind,values', [
    ('bool', ['false', 'true']),
    ('i8', ['-128', '-1', '0', '1', '127']),
    ('u8', ['0', '1', '127', '128', '255']),
    ('i16', ['-32768', '-1', '0', '1', '32767']),
    ('u16', ['0', '1', '32767', '32768', '65535']),
])
def test_core_narrow_slot_promotion(compiler, tmp_path, target, release, kind, values):
    # Branch-result slots must preserve sign/zero extension. Record copies also
    # exercise promotion next to an escaping mutable argument and loop resets.
    source = tmp_path / 'narrow.jo'
    source.write_text(f'''struct Box:
    value: {kind}
@noinline
narrow_probe = (flag: bool, a: {kind}, b: {kind}) -> {kind}:
    if flag: a else: b
@noinline
replace = (box: mut Box, value: {kind}): box.value = value
@noinline
copy_probe = (flag: bool, a: {kind}, b: {kind}) -> {kind}:
    original = Box(a)
    private = original
    replace(original, b)
    if flag: private.value else: original.value
@noinline
reset_probe = (a: {kind}) -> {kind}:
    answer: {kind}
    loop i in [0..3):
        fresh: Box
        if i == 0: fresh.value = a
        answer = fresh.value
    answer
main = () -> int:
    values: {kind}[] = [{', '.join(values)}]
    loop a in values:
        loop b in values:
            if narrow_probe(true, a, b) != a or narrow_probe(false, a, b) != b: return 1
            if copy_probe(true, a, b) != a or copy_probe(false, a, b) != b: return 2
        if reset_probe(a) != {('false' if kind == 'bool' else '0')}: return 3
    42
''')
    binary = tmp_path / 'narrow'
    flags = ['--ir', '--target', target, *(['--release'] if release else [])]
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_narrow_probe_.*?(?=^fn |\Z)',
                      built.stdout + built.stderr, re.M | re.S)
    assert probe, 'narrow scalar probe was not emitted'
    assert ' = load ' not in probe[0] and 'store ' not in probe[0], probe[0]
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web narrow scalar checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'narrow.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_recursive_branch_returns(compiler, tmp_path, target, release):
    source = tmp_path / 'returns.dewy'
    source.write_text('''let calls:int64=0
fib=(n:int64):>int64=>if n<?2 n else fib(n-1)+fib(n-2)
fib_float=(n:int64):>float64=>if n<?2 (n as float64) else fib_float(n-1)+fib_float(n-2)
# Returning a narrow value must retain its conversion before leaving the branch.
narrow=(n:int64):>int8=>if n=?0 (-128 as int8) else if n=?1 (127 as int8) else narrow(n-2)
marked=(n:int64):>int64=>{calls+=1 return if n<?2 n else marked(n-1)+marked(n-2)}
# A loop back-edge must stay a loop; exits with intervening work cannot return early.
walk=(n:int64):>int64=>{
    let total=0
    loop i in [0..n) {if i<?2 {total+=i; continue} total+=walk(i-2)}
    total+1
}
main=()=>{
    let a=0 let b=1
    loop n in [0..15) {
        if fib(n) not=?a or fib_float(n) not=?(a as float64) return 1
        let next=a+b a=b b=next
    }
    if narrow(8) not=?-128 or narrow(9) not=?127 return 2
    if marked(10) not=?55 or calls not=?177 return 3
    if walk(0) not=?1 or walk(1) not=?1 or walk(2) not=?2 or walk(5) not=?6 return 4
    return 42
}
''')
    binary = tmp_path / 'returns'
    flags = ['--ir', '--target', target, *(['--release'] if release else [])]
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    if release:
        probe = re.search(r'^fn f_fib_.*?(?=^fn |\Z)',
                          built.stdout + built.stderr, re.M | re.S)
        assert probe and probe[0].count('ret a=') >= 2, built.stdout
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web recursive return checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'returns.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_fast_inline(compiler, tmp_path, target):
    source = tmp_path / 'leaf.jo'
    source.write_text('''counter = 0
next = () -> int:
    counter += 1
    counter
small = (x: int) -> int:
    if x < 0: return -x
    x + 2
wrapped = (x: int) -> int: small(x) + 1
outer = (x: int) -> int: wrapped(x) + 2
@noinline
kept = (x: int) -> int: x * 2
bump = (value: mut int) -> int:
    value += 2
    value
main = () -> int:
    x = 10
    a = small(next())
    b = small(-3)
    c = kept(4)
    d = bump(x)
    e = wrapped(next())
    f = outer(-3)
    if a + b + c + d + e + f + x + counter == 51: return 42
    1
''')
    binary = tmp_path / 'leaf'
    built = subprocess.run([compiler, 'build', source, '--ir', '--target', target, '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    main = re.search(r'^fn f_main_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    assert main, 'main was not emitted'
    assert main[0].count(' = call ') == 2, 'only the @noinline call and the deeper wrapper should remain'
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web inlining checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'leaf.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


def record_source(count: int) -> str:
    parts = ['struct Box[T]:\n    value: T\n']
    for i in range(count):
        parts.append(f'struct Record{i}:\n    value: int\n'
                     f'make{i} = (x: int) -> Box[Record{i}]: Box(Record{i}(x))\n')
    parts.append('main = ():\n    total = 0\n')
    for i in range(count):
        parts.append(f'    total += make{i}({i}).value.value\n')
    parts.append('    print(total)\n')
    return ''.join(parts)


def test_core_many_record_types(compiler, tmp_path):
    # Record instances bypass the ordinary type interner. Enough of them can
    # outgrow even its next doubled table before it is asked to intern again.
    source = tmp_path / 'records.jo'
    source.write_text(record_source(5000))
    checked = subprocess.run([compiler, 'check', source], capture_output=True,
                             text=True, timeout=10, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_type_instance_inference(compiler, tmp_path, release):
    source = Path(__file__).resolve().parents[1] / 'tests/fixtures/programs/type_instances.jo'
    binary = tmp_path / 'type_instances'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'ok\n'


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_function_reachability(compiler, tmp_path, target):
    source = Path(__file__).resolve().parents[1] / 'tests/fixtures/programs/function_reachability.jo'
    binary = tmp_path / 'reachable'
    built = subprocess.run([compiler, 'build', source, '--target', target,
                            '--release', '--ir', '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    functions = re.findall(r'^fn (\S+)', built.stdout + built.stderr, re.M)
    assert any(name.startswith('f_api_step_') for name in functions), functions
    assert any(name.startswith('f_recursive_sum_') for name in functions), functions
    assert not any(name.startswith(('f_tiny_step_', 'f_obsolete_branch_')) for name in functions), functions
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web reachability checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'reachable.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    assert not ran.stdout


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_dictionary_presence_ir(compiler, tmp_path, target):
    source = tmp_path / 'presence.dewy'
    source.write_text('''probe=(values:dict<int64 array<int64>> key:int64):>bool=>values.get(key) is? none
main=()=>if probe([1->[42]] 1) 1 else 42
''')
    flags = ['--ir', *(['--target', 'wasm'] if target == 'wasm' else [])]
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'presence', *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_probe_.*?(?=^fn |\Z)',
                      built.stdout + built.stderr, re.M | re.S)
    assert probe, 'presence probe was not emitted'
    assert ' = load ' not in probe[0], 'presence query still loads an optional tag'


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_return_condition_facts(compiler, tmp_path, target, release):
    # Execution and rejoining exits are covered by the optimizer-return-facts value cases.
    source = tmp_path / 'return_facts.jo'
    source.write_text("""@noinline
probe = (value: int) -> int:
    if value == 0: return 11
    if value == 0: return 12
    return 13
main = () -> int: probe(1)
""")
    flags = ['--ir', '--target', target, *(['--release'] if release else [])]
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'return_facts', *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_probe_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    assert probe, 'guarded-return function was not emitted'
    assert len(re.findall(r'^\s+(?:if_|brif) ', probe[0], re.M)) == 1, probe[0]


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_nested_exit_cleanup(compiler, tmp_path, target, release):
    # Keep a separate body for the IR assertion. Dewy execution of the same
    # control flow is covered by optimizer-nested-exits in the value batches.
    source = tmp_path / 'nested_exit.jo'
    source.write_text('''@noinline
reachability_probe = (first: bool, second: bool) -> int:
    if first:
        if second: return 20
        else: return 21
    else: return 22
    print("unreachable tail")
    return 99
main = () -> int: reachability_probe(true, false)
''')
    flags = ['--ir', *(['--release'] if release else [])]
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'nested_exit', *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_reachability_probe_.*?(?=^fn |\Z)',
                      built.stdout + built.stderr, re.M | re.S)
    assert probe, 'nested-return function was not emitted'
    assert ' = call ' not in probe[0], 'unreachable printing remained after nested returns'


@pytest.mark.parametrize('target', ['native', 'wasm', 'linux-arm64'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_integer_select(compiler, tmp_path, target, release):
    runner = shutil.which('qemu-aarch64' if target == 'linux-arm64' else 'node')
    if target != 'native' and not runner:
        pytest.skip(f'Runner unavailable for {target}')
    values = [-(1 << 63), -(1 << 63)+1, -129, -1, 0, 1, 127, (1 << 63)-1]
    rng = random.Random(42031)
    values += [rng.randrange(-(1 << 63), 1 << 63) for _ in range(128)]
    source = tmp_path / 'select.dewy'
    source.write_text(f"""pick=(x:int64 y:int64 flag:bool):>int64=>
if flag (x xor y)+1 else (x-y)*3
main=():>void=>{{
let values:array<int64>=[{' '.join(map(str, values))}]
loop i in [0..values.length) {{
let x=values[i] let y=values[values.length-1-i]
loop flag in [true false] {{printl(pick(x y flag))}}
}}
}}
""")
    expected = []
    for x, y in zip(values, reversed(values), strict=True):
        for result in [(x ^ y)+1, (x-y)*3]:
            expected.append(str((result+(1 << 63)) % (1 << 64)-(1 << 63)))
    binary = tmp_path / 'select'
    flags = ['--ir', *(['--release'] if release else [])]
    if target != 'native':
        flags += ['--target', target]
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    pick_ir = re.search(r'^fn f_(?:pick|main)_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    if release:
        assert pick_ir and ' = select ' in pick_ir[0], 'conditional selection was not emitted'
    command = [binary]
    if target == 'linux-arm64':
        command = [runner, binary]
    elif target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        script = tmp_path / 'select.cjs'
        script.write_text('\n'.join(scripts.parts))
        command = [runner, script]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('host', ['windows', 'macos', 'linux-arm64'])
def test_core_compiler_hosts(compiler, tmp_path, host):
    # A selected immutable host must rebuild its matching compiler/runtime pair.
    source = compiler.parent.parent / 'compiler/main.jo'
    binary = tmp_path / ('compiler.exe' if host == 'windows' else 'compiler')
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(DEWY_CORE_LIB=str(compiler.parent.parent / 'lib'), SLOPPY_EMIT_WORKERS='1')
    built = subprocess.run([compiler, 'build', source, '--target', host,
                            '-o', binary], env=env, capture_output=True, text=True,
                           timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    header = binary.read_bytes()[:20]
    if host == 'windows':
        assert header[:2] == b'MZ'
    elif host == 'macos':
        assert header[:8] == bytes.fromhex('cffaedfe0c000001')
    else:
        assert header[:4] == b'\x7fELF' and int.from_bytes(header[18:20], 'little') == 183
        if runner := shutil.which('qemu-aarch64'):
            source = tmp_path / 'values.dewy'
            source.write_text('''from bigint import BigInt
main=()=>{
let original=[20 21] let changed=original
loop @item in changed {item+=1}
assert(original =? [20 21] and changed =? [21 22])
let huge:BigInt=18446744073709551616
printl"{changed[1]} {1/3+1/6} {huge+1}"
return 0
}''')
            for flags in [[], ['--release']]:
                program = tmp_path / 'values'
                built = subprocess.run([runner, binary, 'build', source, '-o', program, *flags],
                                       env=env, capture_output=True, text=True, timeout=30, check=False)
                assert built.returncode == 0, built.stdout + built.stderr
                ran = subprocess.run([runner, program], env=env, capture_output=True, text=True,
                                     timeout=10, check=False)
                assert ran.returncode == 0, ran.stdout + ran.stderr
                assert ran.stdout == '22 1/2 18446744073709551617\n'


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_unsigned_floor_arithmetic(compiler, tmp_path, target, release):
    maximum = (1 << 64) - 1
    numerators = [0, 1, 2, 127, 255, 65535, (1 << 32) - 1, 1 << 32,
                  (1 << 63) - 1, 1 << 63, maximum - 1, maximum]
    denominators = [1, 2, 3, 255, 1000000007, (1 << 32) - 1, 1 << 32, 1 << 63, maximum]
    literal_divisors = [*[1 << shift for shift in range(64)], 3, 5, 7, 31, 255, 1000, 1000000007]
    constants = '\n'.join(f'printl"{{a//{b}}} {{a%{b}}}"' for b in literal_divisors)
    source = tmp_path / 'unsigned.dewy'
    source.write_text(f'''main=():>void=>{{
let values:array<uint64>=[{' '.join(map(str, numerators))}]
let divisors:array<uint64>=[{' '.join(map(str, denominators))}]
loop a in values {{
    loop b in divisors {{
        let quotient:uint64=a//b
        let remainder:uint64=a%b
        printl"{{quotient}} {{remainder}}"
    }}
    {constants}
}}
}}
''')
    expected = [f'{a // b} {a % b}' for a in numerators for b in denominators + literal_divisors]
    binary = tmp_path / 'unsigned'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web unsigned arithmetic checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'unsigned.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_signed_floor_arithmetic(compiler, tmp_path, target, release):
    minimum, maximum = -(1 << 63), (1 << 63) - 1
    numerators = [minimum, minimum + 1, -1000000007, -129, -7, -1, 0, 1, 7, 129, 1000000007, maximum - 1, maximum]
    denominators = [minimum, minimum + 1, -1000000007, -129, -3, -1, 1, 2, 3, 129, 1000000007, maximum]
    powers = [1 << shift for shift in range(63)]
    constants = powers + [-3, 3, 5, 7, 9, 10, 31, 63, 1000, 2147483647,
                          -129, 129, -1000000007, 1000000007, minimum, maximum]
    constant_cases = '\n'.join(f'printl"{{a%{b}}} {{a//{b}}}"' for b in constants)
    source = tmp_path / 'floor.dewy'
    source.write_text(f'''main=():>void=>{{
let numerators:array<int64>=[{' '.join(map(str, numerators))}]
let denominators:array<int64>=[{' '.join(map(str, denominators))}]
loop a in numerators {{
    loop b in denominators {{
        let remainder=a%b
        let quotient=a//b
        printl"{{remainder}} {{quotient}}"
    }}
    {constant_cases}
}}
}}
''')
    expected = [f'{a % b} {minimum if a == minimum and b == -1 else a // b}'
                for a in numerators for b in denominators + constants]
    binary = tmp_path / 'floor'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web arithmetic checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'floor.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_scalar_conditional_results(compiler, tmp_path, target, release):
    source = tmp_path / 'conditional.dewy'
    source.write_text('''let calls:int64=0
pick=(yes:bool x:int8 y:int8):>int8=>if yes {calls+=1 x} else {calls+=10 y}
floating=(yes:bool x:float32 y:float32):>float32=>if yes x else y
early=(x:int64):>int64=>if x <? 0 {return -x} else if x =? 0 7 else {let values=[x 2] values[0]+values[1]}
main=():>void=>{
    let total:int64=0
    loop i in [0..100) {
        let value:int8=pick(i%2 =? 0 (-128) 127)
        total+=value as int64
    }
    let real=floating(true 1.25 8.5)+floating(false 1.25 8.5)
    let wide:uint64=if total <? 0 18446744073709551615 as uint64 else 0 as uint64
    let truth=if calls =? 550 total =? -50 else false
    let jumped:int64=0
    loop i in [0..10) {
        jumped+=if i =? 2 {continue} else if i =? 5 {break} else i
    }
    printl"{total} {calls} {real} {wide} {truth} {jumped} {early(-3)+early(0)+early(30)}"
}
''')
    binary = tmp_path / 'conditional'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web conditional checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'conditional.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.split() == ['-50', '550', '9.75', '18446744073709551615', 'true', '8', '42']


@pytest.mark.parametrize(('name', 'expression', 'expected'), [
    ('constant-interpolation', '"answer {42}"', 'answer 42'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_string_literals(compiler, tmp_path, name, expression, expected, target, release):
    # Other string literals are golden cases in tests/cases/string.
    source = tmp_path / f'{name}.dewy'
    source.write_text(f'main=():>void=>{{printl({expression})}}')
    binary = tmp_path / name
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert 'warning:' not in built.stderr, built.stderr

    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web string checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / f'{name}.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == (expected + '\n').encode('utf-8')


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_imported_generics(compiler, tmp_path, target, release):
    (tmp_path / 'support.dewy').write_text('''Box:type=<T>[value:T]
wrap=<T>(value:T):>Box<T>=>[value=value]
identity=<T>(value:T):>T=>value
''')
    (tmp_path / 'other.jo').write_text('''struct Box[T]:
    value: T
    extra = 2
type Nested[T] = Box[T[]]
identity[T] = (value: T) -> T: value
''')
    source = tmp_path / 'main.dewy'
    source.write_text('''import p"support.dewy" as a
import p"other.jo" as b
from p"support.dewy" import (Box as Package), wrap
main=()=>{
    let one:a.Box<int64>=a.Box<int64>[20]
    let two=b.Box<int64>(22)
    let nested:b.Nested<string>=[value=["one"]]
    let words=Package<array<string>>[["yes"]]
    let item=wrap<string>("wrapped")
    let dewy_identity=@a.identity<int64>
    let core_identity=@b.identity<string>
    let make_package=@wrap<int64>
    return if one.value+b.identity<int64>(two.value) =? 42 and two.extra =? 2
        and nested.value[0] =? "one" and item.value =? "wrapped"
        and dewy_identity(42) =? 42 and core_identity("ok") =? "ok"
        and make_package(42).value =? 42
        and a.identity<array<string>>(words.value)[0] =? "yes" 42 else 1
}
''')
    binary = tmp_path / 'imports'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web generic checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'imports.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('language', ['dewy', 'jo'])
@pytest.mark.parametrize('provider', ['dewy', 'jo'])
def test_core_indexed_update_order(compiler, tmp_path, target, release, language, provider):
    (tmp_path / 'store.jo').write_text('''struct Store[T]:
    values: T[]
trace = ""
at = (label: str, value: int) -> int:
    trace += label
    value
([])[T] = (s: Store[T], i: int) -> T:
    trace += "g"
    s.values[i]
([]=)[T] = (s: mut Store[T], i: int, value: T):
    trace += "s"
    s.values[i] = value
reset = (): trace = ""
events = () -> str: trace
''')
    source = tmp_path / 'main.dewy'
    source.write_text('''from p"store.jo" import Store, at, events, reset
main=()=>{
    let root=[Store<array<int64>>[values=[[1 2]]]]
    let original=root
    root[at("a" 0)][at("b" 0)][at("c" 1)]+=at("r" 40)
    if events() not=? "abgcrs" return 1
    if root[0].values[0][1] not=? 42 or original[0].values[0][1] not=? 2 return 2
    reset()
    let store=Store<array<int64>>[values=[[1] [2]]]
    let index:int64=0
    store[index][at("c" 0)]={index=1 at("r" 42)}
    if events() not=? "grcs" or store.values[0][0] not=? 42 or store.values[1][0] not=? 2 return 3
    reset()
    let scalars=Store<int64>[values=[2 3]]
    index=0
    scalars[index]+={index=1 at("r" 40)}
    if events() not=? "grs" or scalars.values not=? [42 3] return 4
    return 42
}
''')
    if language == 'jo':
        source = tmp_path / 'main.jo'
        source.write_text('''from "store.jo" import Store, at, events, reset
change = (index: mut int, value: int) -> int:
    index = 1
    at("r", value)
main = () -> int:
    let root = [Store[int[]](values = [[1, 2]])]
    let original = root
    root[at("a", 0)][at("b", 0)][at("c", 1)] += at("r", 40)
    if events() != "abgcrs": return 1
    if root[0].values[0][1] != 42 or original[0].values[0][1] != 2: return 2
    reset()
    let store = Store[int[]](values = [[1], [2]])
    let index = 0
    store[index][at("c", 0)] = change(index, 42)
    if events() != "grcs" or store.values[0][0] != 42 or store.values[1][0] != 2: return 3
    reset()
    let scalars = Store[int](values = [2, 3])
    index = 0
    scalars[index] += change(index, 40)
    if events() != "grs" or scalars.values != [42, 3]: return 4
    42
''')
    if provider == 'dewy':
        (tmp_path / 'store.dewy').write_text('''Store:type=<T>[values:array<T>]
trace=""
at=(label:string value:int64):>int64=>{trace+=label return value}
__index__=<T>(s:Store<T> i:int64):>T=>{trace+="g" return s.values[i]}
__setindex__=<T>(@s:Store<T> i:int64 value:T):>void=>{trace+="s" s.values[i]=value}
reset=():>void=>{trace=""}
events=():>string=>trace
''')
        source.write_text(source.read_text().replace('store.jo', 'store.dewy'))
    binary = tmp_path / 'order'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web indexed update checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'order.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('name, imports', [
    ('generic/operator_arithmetic', 'Vec, __add__'),
    ('generic/operator_comparison', 'Score'),
    ('generic/operator_specialization', 'Box'),
    ('overload/group_callable', 'step, apply'),
    ('overload/group_defaults', 'choose'),
    ('overload/group_operators', 'Point'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_operator_imports(compiler, tmp_path, name, imports, target, release):
    declarations, body = case_source(name).split('main=', 1)
    (tmp_path / 'operators.dewy').write_text(declarations)
    source = tmp_path / 'main.dewy'
    source.write_text(f'from p"operators.dewy" import {imports}\nmain={body}')
    binary = tmp_path / 'operators'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web operator checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'operators.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('case', ['history', 'managed-values', 'iteration', 'capacity', 'negative-index', 'past-end'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_ring_example(compiler, tmp_path, case, target, release):
    examples = Path(__file__).resolve().parents[1] / 'examples'
    shutil.copy2(examples / 'ring.dewy', tmp_path / 'ring.dewy')
    source = tmp_path / 'main.dewy'
    if case == 'history':
        source.write_text((examples / 'history.dewy').read_text())
    elif case == 'iteration':
        source.write_text('''from p"ring.dewy" import new_ring
main=()=>{
let ring=new_ring<int64>(4) loop i in [0..6) ring.push(i)
let saved=ring let sum=0 let both=0 let either=0
loop x in ring and y in [20 22] both+=x+y
loop x in ring or y in [20 22] either+=(x??0)+(y??0)
let tripled=[loop x in ring 3x]
loop x in ring {sum+=x ring.push(99)}
return if sum =? 14 and both =? 47 and either =? 56
and tripled =? [6 9 12 15] and saved[0] =? 2 and ring[0] =? 99 42 else 1
}
''')
    elif case == 'managed-values':
        source.write_text('''from p"ring.dewy" import new_ring
main=()=>{
let ring=new_ring<array<string>>(2)
loop i in [0..7) {ring.push(["{i}"])}
let snapshot=ring
ring[0][0]="changed"
ring[1]=["replacement"]
if ring[0][0] not=? "changed" or ring[1][0] not=? "replacement" return 1
if snapshot[0][0] not=? "5" or snapshot[1][0] not=? "6" return 2
let empty=new_ring<int64>(1)
if empty.len() not=? 0 return 3
empty.push(1) empty.push(42)
return if empty.len() =? 1 and empty[0] =? 42 42 else 4
}
''')
    else:
        action = {'capacity': 'new_ring<int64>(0)',
                  'negative-index': 'ring[-1]', 'past-end': 'ring[1]'}[case]
        source.write_text(f'from p"ring.dewy" import new_ring\n'
                          f'main=()=>{{let ring=new_ring<int64>(2) ring.push(42) {action} return 0}}')
    binary = tmp_path / 'ring'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web ring checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'ring.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    if case == 'history':
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == ('History length: 4\nOldest position: 6, 3\n'
                              'Newest position: 112, 6\nRewind position: 12, 6\nRecorded total: 54\n')
    elif case in ('managed-values', 'iteration'):
        assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    else:
        assert ran.returncode != 0
        message = 'ring capacity must be positive' if case == 'capacity' else 'ring index out of bounds'
        assert message in ran.stdout + ran.stderr


@pytest.mark.parametrize('case', ['stale', 'missing', 'storage-bounds', 'rhs-removes-item'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_pool_update_errors(compiler, tmp_path, case, target, release):
    declarations = ''
    setup = 'let pool:Pool<array<int64>>=[] let h=pool.add([20])'
    update = 'pool[h][0]=42'
    if case == 'stale':
        setup += ' pool.remove(h) pool.add([1])'
    elif case == 'missing':
        setup += ' h=Handle[]'
    elif case == 'storage-bounds':
        setup += ' pool.items.clear()'
    else:
        declarations = '''let pool:Pool<array<int64>>=[] let h:Handle=[]
erase=():>int64=>{pool.remove(h) return 22}
'''
        setup = 'h=pool.add([20])'
        update = 'pool[h][0]+=erase()'
    source = tmp_path / 'invalid.dewy'
    source.write_text(declarations + f'main=()=>{{{setup} {update} return 0}}')
    binary = tmp_path / 'invalid'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web pool update checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'invalid.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode != 0, 'invalid pool update unexpectedly succeeded'
    expected = 'out of bounds' if case == 'storage-bounds' else 'gone from the pool'
    assert expected in ran.stdout + ran.stderr


@pytest.mark.parametrize('setter', [False, True], ids=['missing-setter', 'readonly-receiver'])
def test_core_indexed_update_rejects(compiler, tmp_path, setter):
    source = tmp_path / 'readonly.jo'
    source.write_text('''struct Store:
    values: int[][]
([]) = (s: Store, i: int) -> int[]: s.values[i]
''' + ('([]=) = (s: mut Store, i: int, value: int[]): s.values[i] = value\n' if setter else '') + '''edit = (s: Store):
    s[0][0] = 42
main = ():
    edit(Store(values = [[1]]))
''')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'readonly'],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode != 0, 'a getter copy must not silently discard the update'
    expected = 'read-only' if setter else '[]='
    assert expected in built.stderr, built.stdout + built.stderr


@pytest.mark.parametrize('name', CHECKSUMS_1000)
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_applications(compiler, tmp_path, name, target, release):
    source = prepare_source(name, tmp_path)
    binary = tmp_path / name
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary, '1000']
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web application checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / f'{name}.cjs'
        runner.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [node, runner, '1000']
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    checksum, elapsed = map(int, ran.stdout.split())
    assert checksum == CHECKSUMS_1000[name]
    assert elapsed >= 0


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_numeric_example(compiler, tmp_path, target, release):
    source = Path(__file__).resolve().parents[1] / 'examples/trajectory_fit.dewy'
    command, error = build_case_batch(compiler, tmp_path, {'trajectory': source.read_text()},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == ('height = 1.501 + 8.008*t + -4.909*t*t\n'
                          'height at 0.6 seconds: 4.538\n')


@pytest.mark.parametrize('target, backend', [
    ('native', 'fallback'), ('wasm', 'fallback'),
    ('native', 'gles'), ('native', 'vulkan'),
])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_gpu_arrays(compiler, tmp_path, target, backend, release, request):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(SLOPPY_THREADS='2', LP_NUM_THREADS='2', SLOPPY_VK_PIPELINE_CACHE='0')
    if backend == 'fallback':
        env['SLOPPY_SOFTWARE'] = '1'
    else:
        if platform.system() != 'Linux':
            pytest.skip('offscreen Mesa driver checks currently target Linux')
        env.update(LIBGL_ALWAYS_SOFTWARE='1', EGL_PLATFORM='surfaceless')
        if backend == 'gles':
            request.getfixturevalue('shader_driver')
            env['SLOPPY_VULKAN'] = '0'
        else:
            drivers = list(Path('/usr/share/vulkan/icd.d').glob('lvp_icd*.json'))
            drivers = [path for path in drivers if 'i686' not in path.name]
            if not drivers:
                pytest.skip('Mesa lavapipe Vulkan driver is needed')
            env.update(SLOPPY_VULKAN='1', VK_DRIVER_FILES=str(drivers[0]),
                       VK_ICD_FILENAMES=str(drivers[0]))
    program = '''import p"@lib/game/gpuarray.jo" as engine
half=(x:float32):>float32=>x*0.5+0.25
main=()=>{
printl"{gpu_available()} {engine.__gpu_vk}"
let original=[1.0 2.0 3.0 4.0] let g=gpu(original) let saved=g
original[0]=99.0
let h=half.(g) .* 2.0 .+ 1.0
assert(cpu(h).data =? [2.5 3.5 4.5 5.5])
assert(cpu(.-(half.(g) .* 2.0 .+ 1.0)).data =? [-2.5 -3.5 -4.5 -5.5])
assert(cpu(.+g).data =? [1.0 2.0 3.0 4.0])
assert(cpu(hypot.(gpu([3.0 5.0]) gpu([4.0 12.0]))).data =? [5.0 13.0])
let magnitudes=cpu(hypot.(gpu([3e30 3e-30 0.0 -3e30 INF NAN NAN])
                         gpu([4e30 4e-30 -0.0 4e30 NAN INF 1.0]))).data
assert(abs(magnitudes[0]/5e30-1.0) <? 1e-6)
assert(abs(magnitudes[1]/5e-30-1.0) <? 1e-6)
assert(magnitudes[2] =? 0.0 and 1.0/magnitudes[2] >? 0.0)
assert(abs(magnitudes[3]/5e30-1.0) <? 1e-6)
assert(magnitudes[4] =? INF and magnitudes[5] =? INF and is_nan(magnitudes[6]))
let zeros=cpu(.-gpu([0.0 -0.0])).data
assert(1.0/zeros[0] <? 0.0 and 1.0/zeros[1] >? 0.0)
assert(sum(h) =? 16.0 and min(h) =? 2.5 and max(h) =? 5.5)
assert(cpu(g .>? 2.0).data =? [0.0 0.0 1.0 1.0])
let m=gpu(reshape([1.0 2.0 3.0 4.0 5.0 6.0] 2 3))
let row=gpu([10.0 20.0 30.0]) let col=gpu(reshape([100.0 200.0] 2 1))
let result=cpu(m .+ row .+ col)
assert(result.shape =? [2 3] and result.data =? [111.0 122.0 133.0 214.0 225.0 236.0])
assert(cpu(m ./ 2.0).data =? [0.5 1.0 1.5 2.0 2.5 3.0])
let ints=gpu([-7 0 9])
assert(cpu(ints .* 2 .+ 1).data =? [-13 1 19])
assert(cpu(.-ints).data =? [7 0 -9])
assert(cpu(.+ints).data =? [-7 0 9])
assert(sum(ints) =? 2 and min(ints) =? -7 and max(ints) =? 9)
let empty=gpu(zeros(0 3)) .+ row
assert(cpu(empty).shape =? [0 3] and size(cpu(empty)) =? 0 and sum(empty) =? 0.0)
let many=gpu(fill(1.0 4097)) .* 3.0
assert(sum(many) =? 12291.0 and min(many) =? 3.0 and max(many) =? 3.0)
loop i in [0..24) {g .+= 0.5}
assert(cpu(g).data =? [13.0 14.0 15.0 16.0])
assert(cpu(saved).data =? [1.0 2.0 3.0 4.0])
let downloaded=cpu(saved) downloaded[0]=123.0
assert(cpu(saved).data =? [1.0 2.0 3.0 4.0])
return 0
}'''
    example = Path(__file__).resolve().parents[1] / 'examples/terrain_array.dewy'
    command, error = build_case_batch(compiler, tmp_path, {'gpu': program, 'terrain': example.read_text()},
                                      ['exit(case_0()+case_1())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, env=env, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    expected = {'fallback': 'false false\n', 'gles': 'true false\n', 'vulkan': 'true true\n'}
    available = 'false' if backend == 'fallback' else 'true'
    assert ran.stdout.startswith(expected[backend] +
                                f'Generated 33x33 height field (GPU available: {available}).\n'), ran.stdout + ran.stderr
    assert ran.stdout.splitlines()[2].startswith('Maximum CPU difference: '), ran.stdout


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_metal_magnitude(compiler, tmp_path, release):
    # Source cross-compilation only: execution requires Apple hardware.
    source = tmp_path / 'magnitude.dewy'
    source.write_text('main=()=>{printl(cpu(hypot.(gpu([3.0]) gpu([4.0]))).data) return 0}')
    shaders = tmp_path / 'shaders'
    shaders.mkdir()
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_MSL_DUMP'] = str(shaders)
    built = subprocess.run([compiler, 'build', source, '--target', 'macos', '-o', tmp_path / 'magnitude',
                            *(['--release'] if release else [])], env=env,
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    kernels = list(shaders.glob('*.kernel.metal'))
    assert len(kernels) == 1
    text = kernels[0].read_text()
    assert 'float sl_hypot(float x, float y)' in text
    assert 'as_type<uint>(x)' in text and 'as_type<float>(max(hi &' in text
    assert 'f64_bits' not in text and 'floatBitsToUint' not in text


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_metal_unary_plus(compiler, tmp_path, release):
    # Cross-compilation checks generated source; executing Metal needs macOS.
    source = tmp_path / 'plus.dewy'
    source.write_text('''main=()=>{
let floats=.+gpu([1.0 2.0]) let ints=.+gpu([1 -2])
printl(cpu(floats).data) printl(cpu(ints).data)
return 0
}''')
    shaders = tmp_path / 'shaders'
    shaders.mkdir()
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_MSL_DUMP'] = str(shaders)
    built = subprocess.run([compiler, 'build', source, '--target', 'macos', '-o', tmp_path / 'plus',
                            *(['--release'] if release else [])], env=env,
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    kernels = sorted(shaders.glob('*.kernel.metal'))
    assert len(kernels) == 2
    for kernel in kernels:
        text = kernel.read_text()
        bodies = re.findall(r'(?:float|int) f_\w+\([^)]*\)\s*\{([^}]+)\}', text)
        assert len(bodies) == 1, text
        assert '~' not in bodies[0], text
        assert re.search(r'\breturn l_\w+;', bodies[0]), text


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_numeric_pointer_loop_aliases(compiler, tmp_path, target, release):
    (tmp_path / 'loops.jo').write_text('''axpy[T] = (left: mut T[], right: T[], scale: T):
    assert(left.len() == right.len())
    p = data(left)
    q = data(right)
    loop i in [0..left.len()): p[i] += scale * q[i]
overlap[T] = (values: mut T[]):
    p = data(values)
    q = p + 1
    loop i in [0..max(values.len() - 1, 0)): q[i] += p[i]
same[T] = (values: mut T[]):
    p = data(values)
    q = p
    loop i in [0..values.len()): q[i] += p[i]
ordered = (values: f64[]) -> f64:
    p = data(values)
    total = 0.0
    loop i in [0..values.len()): total += p[i]
    total
''')
    program = '''from p"loops.jo" import axpy, overlap, same, ordered
exercise=<T>(one:T):>void=>{
loop count in [0..20) {
    let a=fill(one count) let b=fill(one+one count) let saved=a
    axpy(@a b one+one)
    loop v in a {assert(v =? one+one+one+one+one)}
    loop v in saved {assert(v =? one)}
    let ascending=fill(one count)
    overlap(@ascending)
    loop i in [0..count) {assert(ascending[i] =? ((i+1) as T))}
    same(@ascending)
    loop i in [0..count) {assert(ascending[i] =? ((2*(i+1)) as T))}
}
}
main=()=>{
exercise<float64>(1.0) exercise<float32>(1.0)
assert(ordered([1e16 1.0 -1e16 2.0]) =? 2.0)
return 42
}'''
    command, error = build_case_batch(compiler, tmp_path, {'loops': program},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    modes = [False, True] if target == 'native' else [False]
    for no_avx in modes:
        env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
        if no_avx:
            env['SLOPPY_NO_AVX'] = '1'
        ran = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10, check=False)
        assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('flags', [[], ['--release']], ids=['default', 'release'])
def test_core_numeric_cpu_feature_initializer(compiler, tmp_path, flags):
    if platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('the vectorizer currently targets native x86-64')
    source = tmp_path / 'matrix.dewy'
    source.write_text('main=()=>{let a=ones(2 2) return sum(a*a) as int64}')
    binary = tmp_path / 'matrix'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    # Merely reserving the vectorizer's global leaves it zero: its runtime
    # initializer must stay reachable without an explicit reference in user code.
    assert 'fn f___cpu_detect_' in built.stdout
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 8, ran.stdout + ran.stderr


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_numeric_array_vectors(compiler, tmp_path, release):
    if platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('AVX2/SSE2 code generation targets native x86-64')
    source = tmp_path / 'vectors.dewy'
    source.write_text('''looped=<T>(a:array<T> b:array<T>):>array<T>=>[loop i in [0..a.length) a[i]*2.0+b[i]*0.5+1.0]
valued=<T>(a:array<T> b:array<T>):>array<T>=>[loop i in 0.. and x in a x*2.0+b[i]*0.5+1.0]
mapped=<T>(a:array<T>):>array<T>=>[loop x in a x*2.5+1.0]
fused=<T>(a:array<T> b:array<T>):>array<T>=>a .* 2.0 .+ b .* 0.5 .+ 1.0
negated=<T>(a:array<T>):>array<T>=>.-a
negloop=<T>(a:array<T>):>array<T>=>[loop x in a -x]
main=(argv:array<string>)=>{
let words64:array<uint64>=[0 0x8000000000000000 0x7ff0000000000000 0xfff0000000000000 0x7ff8000000000042 0xfff8000000000017 1 0x3ff4000000000000]
let words32:array<uint32>=[0 0x80000000 0x7f800000 0xff800000 0x7fc00042 0xffc00017 1 0x3fa00000]
loop n in [0..20) {
let a=[loop i in [0..n) (i as float64)*0.5]
let b=[loop i in [0..n) (i as float64)*0.25]
let expected=[loop i in [0..n) (i as float64)*1.125+1.0]
assert(looped(a b) =? expected and fused(a b) =? expected)
assert(valued(a b) =? expected)
let same=[loop i in [0..n) (i as float64)*1.25+1.0]
assert(looped(a a) =? same and fused(a a) =? same)
assert(valued(a a) =? same and mapped(a) =? same)
let single_a=float32.(a) let single_b=float32.(b)
let single_expected=float32.(expected)
assert(looped(single_a single_b) =? single_expected and fused(single_a single_b) =? single_expected)
assert(valued(single_a single_b) =? single_expected and mapped(single_a) =? float32.(same))
let special64=[loop i in [0..n) f64_from_bits(words64[i%8])]
let special32=[loop i in [0..n) f32_from_bits(words32[i%8])]
let negative64=negated(special64) let loop64=negloop(special64)
let negative32=negated(special32) let loop32=negloop(special32)
loop i in [0..n) {
assert(f64_bits(negative64[i]) =? (words64[i%8] xor 0x8000000000000000))
assert(f64_bits(loop64[i]) =? f64_bits(negative64[i]))
assert(f32_bits(negative32[i]) =? (words32[i%8] xor 0x80000000))
assert(f32_bits(loop32[i]) =? f32_bits(negative32[i]))
}
}
if argv.length >? 1 {
if argv[1] =? "values" printl(valued(fill(1.0 20) fill(2.0 19)))
else printl(looped(fill(1.0 20) fill(2.0 19)))
}
return 42
}''')
    binary = tmp_path / 'vectors'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    bodies = [body for body in re.split(r'(?=^fn )', built.stdout, flags=re.M)
              if re.match(r'fn f_(?:looped|fused|valued|mapped|negated|negloop)_', body)]
    assert len(bodies) == 12, built.stdout
    assert all('vld ' in body and 'vst ' in body for body in bodies), '\n'.join(bodies)
    for sse2 in [False, True]:
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('DEWY_', 'SLOPPY_'))}
        if sse2:
            env['SLOPPY_NO_AVX'] = '1'
        ran = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=10, check=False)
        assert ran.returncode == 42, ran.stdout + ran.stderr
        for form in ['short', 'values']:
            short = subprocess.run([binary, form], env=env, capture_output=True, text=True,
                                   timeout=10, check=False)
            assert short.returncode != 0 and 'out of bounds' in short.stderr, short.stdout + short.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_numeric_ranges_custom_index(compiler, tmp_path, target, release):
    (tmp_path / 'lookup.jo').write_text('''struct Lookup:
    value: int
calls = 0
len = (x: Lookup) -> int:
    calls += 1
    x.value
count = () -> int: calls
([]) = (x: Lookup, a: int, b: int) -> int: a + b
([]=) = (x: mut Lookup, a: int, b: int, value: int): x.value = value + a + b
([]) = (x: Lookup, a: IntRange, b: IntRange) -> int: x.value + a._first + b._first
([]=) = (x: mut Lookup, a: IntRange, b: IntRange, value: int): x.value = value + a._first + b._first
''')
    program = '''from p"lookup.jo" import Lookup, count
main=()=>{
let x=Lookup[10]
assert(x[[1..3] (1..3]] =? 13)
x[[1,3..5] [4,2..0]]=37
let other=Lookup[22]
assert(other[end end] =? 42 and count() =? 1)
other[end end]=0
assert(other.value =? 42 and count() =? 2)
return x.value
}'''
    command, error = build_case_batch(compiler, tmp_path, {'custom_index': program},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
@pytest.mark.parametrize('style', ['selected', 'namespace', 'module-alias', 'name-alias'])
@pytest.mark.core_quick
def test_core_imports(compiler, tmp_path, extension, style):
    dependency = tmp_path / f'helper.{extension}'
    dependency.write_text('twice=(x:int64):>int64=>x*2' if extension == 'dewy'
                          else 'twice = (x: int) -> int: x * 2')
    source = tmp_path / 'main.dewy'
    forms = {
        'selected': (f'from p"helper.{extension}" import twice', 'twice(21)'),
        'namespace': (f'import p"helper.{extension}"', 'helper.twice(21)'),
        'module-alias': (f'import p"helper.{extension}" as other', 'other.twice(21)'),
        'name-alias': (f'from p"helper.{extension}" import twice as double', 'double(21)'),
    }
    declaration, expression = forms[style]
    source.write_text(f'{declaration}\nmain=():>int64=>{expression}')
    binary = tmp_path / 'main'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert subprocess.run([binary], timeout=10, check=False).returncode == 42


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
def test_core_imported_dependent_default(compiler, tmp_path, extension):
    dependency = tmp_path / f'helper.{extension}'
    dependency.write_text('let offset:int64=2\ncombine=(a:int64 b:int64=a+offset)=>a+b'
                          if extension == 'dewy' else
                          'offset: int = 2\ncombine = (a: int, b: int = a + offset) -> int: a + b\n')
    source = tmp_path / 'main.dewy'
    source.write_text(f'''from p"helper.{extension}" import combine
let offset:int64=99
main=()=>{{let value:int64=20 return combine(value)}}''')
    binary = tmp_path / 'main'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert subprocess.run([binary], timeout=10, check=False).returncode == 42


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_inline_record_across_modules(compiler, tmp_path, release):
    (tmp_path / 'helper.dewy').write_text('''Count:type=int64
make=():>[y:Count x:Count]=>[x=20 y=22]
sum=(point:[x:Count y:Count])=>point.x+point.y
''')
    source = tmp_path / 'main.dewy'
    source.write_text('''from p"helper.dewy" import make, sum
Count:type=string
main=()=>{let point:[x:int64 y:int64]=make()
return if sum([y=22 x=20]) =? 42 point.x+point.y else 1}
''')
    binary = tmp_path / 'main'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert subprocess.run([binary], timeout=10, check=False).returncode == 42


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
def test_core_imported_record_brackets(compiler, tmp_path, extension):
    dependency = tmp_path / f'helper.{extension}'
    dependency.write_text('Point:type=[x:int64=20 y:int64=22]' if extension == 'dewy'
                          else 'struct Point:\n    x: int = 20\n    y: int = 22\n')
    source = tmp_path / 'main.dewy'
    source.write_text(f'''import p"helper.{extension}" as geometry
from p"helper.{extension}" import Point
main=()=>{{let p=geometry.Point[20 22] let q=Point[y=22 x=20] return p.x+q.y}}''')
    binary = tmp_path / 'main'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert subprocess.run([binary], timeout=10, check=False).returncode == 42


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_rollback_model(compiler, tmp_path, target, release):
    source = Path(__file__).resolve().parents[1] / 'tests/fixtures/programs/rollback.dewy'
    binary = tmp_path / 'rollback'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web rollback checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'rollback.cjs'
        runner.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [node, runner]
    for scenario in ['direct', 'delayed']:
        ran = subprocess.run([*command, scenario], capture_output=True, text=True,
                             timeout=15, check=False)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert not ran.stderr, ran.stderr
        lines = ran.stdout.splitlines()
        assert len(lines) == 8, ran.stdout
        tick = int(lines[0])
        assert 700 < tick < 900
        positions, scores = [0, 0], [0, 0]
        for t in range(2, tick):
            for player in range(2):
                positions[player] += (t//12 + player) % 3 - 1
                if (t + player*3) % 11 == 0 and abs(positions[player] - positions[1-player]) < 5:
                    scores[player] += 1
        expected = {'positions': positions, 'scores': scores, 'hits': sum(scores)}
        assert json.loads(lines[1]) == json.loads(lines[2]) == expected
        rollbacks = list(map(int, lines[3:5]))
        if scenario == 'delayed':
            assert all(n > 30 for n in rollbacks)
        else:
            assert rollbacks == [0, 0]
        assert lines[5:7] == ['-1', '-1']
        assert json.loads(lines[7]) == {'positions': [0, 0], 'scores': [0, 0], 'hits': 0}


@pytest.mark.parametrize(('setup', 'callback', 'start', 'diagnostic'), [
    ('tick=(state:int64 _inputs:array<int64>)=>state+int64(time())', '@tick', 'int64(0)', 'reads the clock'),
    ('clock=()=>time()\ntick=(state:int64 _inputs:array<int64>)=>state+int64(clock())', '@tick', 'int64(0)', 'reads the clock'),
    ('', '((state:int64 _inputs:array<int64>)=>state+int64(random()))', 'int64(0)', 'takes random numbers'),
    ('let count:int64=0\nhelper=()=>{count+=1 return count}\ntick=(state:int64 _inputs:array<int64>)=>state+helper()', '@tick', 'int64(0)', "changes the global 'count'"),
    ('input=():>int64=>if key_down(Key.space) 1 else 0\ntick=(state:int64 _inputs:array<int64>)=>state+input()', '@tick', 'int64(0)', 'reads the input'),
    ('helper=(n:int64):>int64=>if n>?0 helper(n-1) else int64(time())\ntick=(state:int64 _inputs:array<int64>)=>state+helper(1)', '@tick', 'int64(0)', 'reads the clock'),
    ('tick=(state:Rng _inputs:array<int64>)=>{state.next_int(0 10) return state}', '@tick', 'rng(7)', None),
    ('tick=(state:Rng _inputs:array<int64>)=>{let xs=[1 2 3] shuffle(@state @xs) return state}', '@tick', 'rng(7)', None),
    ('tick=(state:int64 _inputs:array<int64>)=>state+int64(unix_time(date(0.0 utc=true)))', '@tick', 'int64(0)', None),
    ('let random_state=rng(7)\ntick=(state:int64 _inputs:array<int64>)=>state+random_state.next_int(0 10)', '@tick', 'int64(0)', "changes the global 'random_state'"),
    ('random=(value:int64)=>value\ntick=(state:int64 _inputs:array<int64>)=>state+random(1)', '@tick', 'int64(0)', None),
    ('tick=(state:int64 inputs:array<int64>)=>state+inputs[0]+inputs[1]', '@tick', 'int64(0)', None),
], ids=['clock', 'helper-clock', 'lambda-random', 'helper-global', 'helper-input', 'recursive-clock', 'seeded-rng', 'seeded-shuffle', 'date-conversion', 'global-rng', 'user-random', 'pure'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('at_top', [False, True], ids=['main', 'global'])
def test_core_netplay_tick_warnings(compiler, tmp_path, setup, callback, start, diagnostic, target, release, at_top):
    source = tmp_path / 'tick.dewy'
    session = f'let game=netplay.session({start} {callback} players=2 me=0)'
    program = f'{session}\nmain=()=>game.tick+42' if at_top else f'main=()=>{{{session} return game.tick+42}}'
    source.write_text(f'import netplay\n{setup}\n{program}')
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', tmp_path / 'tick', *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    outputs = [built.stderr]
    if target == 'native' and not release:
        checked = subprocess.run([compiler, 'check', source], capture_output=True,
                                 text=True, timeout=30, check=False)
        assert checked.returncode == 0, checked.stdout + checked.stderr
        outputs.append(checked.stderr)
    for output in outputs:
        warnings = [line for line in output.splitlines() if "'s tick" in line and 'warning:' in line]
        if diagnostic:
            assert len(warnings) == 1 and diagnostic in warnings[0], output
        else:
            assert not warnings, output


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_netplay_restart(compiler, tmp_path, target, release):
    source = Path(__file__).resolve().parents[1] / 'tests/fixtures/programs/netplay_restart.dewy'
    binary = tmp_path / 'restart'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web rollback checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'restart.cjs'
        runner.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [node, runner]
    for scenario in ['clean', 'late']:
        ran = subprocess.run([*command, scenario], capture_output=True, text=True,
                             timeout=15, check=False)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert not ran.stderr, ran.stderr
        values = list(map(int, ran.stdout.splitlines()))
        assert len(values) == 18, ran.stdout
        for start in range(0, 18, 6):
            left, right, left_state, right_state, left_desync, right_desync = values[start:start+6]
            assert 220 < left <= 240 and 220 < right <= 240, (scenario, start, values)
            assert left_state == 3 * (left - 2)
            assert right_state == 3 * (right - 2)
            assert left_desync == right_desync == -1


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.core_quick
def test_core_game_model(compiler, tmp_path, target, release):
    node = shutil.which('node')
    if target == 'wasm' and node is None:
        pytest.skip('Node is needed to execute the generated web runner')
    model = Path(__file__).resolve().parents[1] / 'examples/paddle_model.dewy'
    shutil.copy2(model, tmp_path)
    source = tmp_path / 'model_test.dewy'
    source.write_text('''from p"paddle_model.dewy" import fresh, advance, Point
main=():>int64=>{
    let world=fresh()
    let original=world
    advance(@world 0.5 730.0)
    if world.position.x not=? 730.0 or world.position.y not=? 340.0 return 1
    if original.position.x not=? 640.0 or original.position.y not=? 220.0 return 2
    world.position=Point(730.0 610.0)
    world.velocity=Point(0.0 240.0)
    advance(@world 0.1 730.0)
    if world.score not=? 1 or world.velocity.y >=? 0.0 return 3
    world.position=Point(100.0 750.0)
    world.velocity=Point(0.0 240.0)
    advance(@world 0.1 730.0)
    if world.misses not=? 1 or world.position.y not=? 220.0 return 4
    advance(@world 0.0 0.0)
    if world.paddle not=? 80.0 return 5
    advance(@world 0.0 1280.0)
    if world.paddle not=? 1200.0 return 6
    return 42
}''')
    binary = tmp_path / 'model_test'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_numeric_matrix_range_reference(compiler, tmp_path, target, release):
    rng = random.Random(4187)
    cases = {}

    def array(values):
        return '[' + ' '.join(map(str, values)) + ']'

    for case in range(48):
        shape = [rng.randrange(5) for _ in range(1 + case % 4)]
        offsets, result_shape, declarations, selectors = [0], [], [], []
        for axis, size in enumerate(shape):
            if axis and size and rng.randrange(2):
                index = rng.randrange(size)
                selected = [index]
                selectors.append(str(index))
            else:
                first = rng.randrange(size) if size else 0
                step = rng.choice([-3, -2, -1, 1, 2, 3])
                available = len(range(first, size if step > 0 else -1, step)) if size else 0
                count = rng.randrange(available + 1)
                selected = [first + step * i for i in range(count)]
                expression = (f'[{first},{first + step}..{selected[-1]}]' if count else '[0..0)')
                declarations.append(f'let r{axis}={expression}')
                selectors.append(f'r{axis}')
                result_shape.append(count)
            offsets = [base * size + index for base in offsets for index in selected]
        original = [i * 7 - 3 for i in range(math.prod(shape))]
        picked = [original[i] for i in offsets]
        updated = original.copy()
        replacement = [1000 + i for i in range(len(offsets))]
        for index, value in zip(offsets, replacement, strict=True):
            updated[index] = value + 5
        selection = ' '.join(selectors)
        cases[f'matrix_{case}'] = (
            'main=()=>{\n'
            f'let values:array<int64>={array(original)}\n'
            f'let m=reshape(values {array(shape)}) let saved=m\n'
            + '\n'.join(declarations) + '\n'
            + f'let picked=m[{selection}]\n'
            + f'assert(picked.shape =? {array(result_shape)} and picked.data =? {array(picked)})\n'
            + f'm[{selection}]={array(replacement)}\nm[{selection}] .+= 5\n'
            + f'assert(m.data =? {array(updated)} and saved.data =? values)\nreturn 42\n}}')
    body = [f'assert(case_{i}() =? 42)' for i in range(len(cases))] + ['exit(42)']
    command, error = build_case_batch(compiler, tmp_path, cases, body, release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_reaction_model(compiler, tmp_path, target, release):
    node = shutil.which('node')
    if target == 'wasm' and node is None:
        pytest.skip('Node is needed to execute the web simulation')
    model = Path(__file__).resolve().parents[1] / 'examples/reaction_model.dewy'
    shutil.copy2(model, tmp_path)
    source = tmp_path / 'reaction_test.dewy'
    source.write_text('''from p"reaction_model.dewy" import fresh, paint, advance
simulate=()=>{
let field=fresh(8 6) let saved=field
paint(@field 4 3 1)
loop i in [0..8) advance(@field 0.035 0.062)
assert(saved.a.data =? fill(1.0 as float32 48) and saved.b.data =? fill(0.0 as float32 48))
assert(saved.steps =? 0)
let before=field paint(@field -100 -100 2) assert(field =? before)
return field
}
main=()=>{
let result=simulate() let before=alloc_count()
loop i in [0..20) {let trial=simulate() assert(trial.steps =? 8)}
assert(alloc_count() =? before)
printl(to_json(result))
return 42
}''')
    binary = tmp_path / 'reaction_test'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr
    actual = json.loads(ran.stdout)
    width, height = 8, 6
    a, b = [1.0] * (width * height), [0.0] * (width * height)
    for y in range(2, 5):
        for x in range(3, 6):
            a[y * width + x], b[y * width + x] = 0.5, 0.25
    for _ in range(8):
        next_a, next_b = a.copy(), b.copy()
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                i = y * width + x
                reaction = a[i] * b[i] * b[i]
                lap_a = a[i - width] + a[i + width] + a[i - 1] + a[i + 1] - 4 * a[i]
                lap_b = b[i - width] + b[i + width] + b[i - 1] + b[i + 1] - 4 * b[i]
                next_a[i] += 0.16 * lap_a - reaction + (1 - a[i]) * 0.035
                next_b[i] += 0.08 * lap_b + reaction - b[i] * (0.035 + 0.062)
        a, b = next_a, next_b
    assert actual['steps'] == 8
    assert actual['a']['shape'] == actual['b']['shape'] == [height, width]
    assert actual['a']['data'] == pytest.approx(a, rel=2e-6, abs=2e-6)
    assert actual['b']['data'] == pytest.approx(b, rel=2e-6, abs=2e-6)


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_forest_model(compiler, tmp_path, target, release):
    model = Path(__file__).resolve().parents[1] / 'examples/forest_model.dewy'
    shutil.copy2(model, tmp_path)
    source = tmp_path / 'forest_test.dewy'
    source.write_text('''from p"forest_model.dewy" import fresh_forest, hill, ground_color
main=()=>{
    let forest=fresh_forest()
    if forest.trunks.length not=? 300 or forest.crowns.length not=? 300 return 1
    let original=forest
    forest.crowns[0].color.x=0.9
    if abs(original.crowns[0].color.x-0.2) >? 0.0001 return 2
    let repeated=fresh_forest()
    if abs(repeated.trunks[0].model[3].x-original.trunks[0].model[3].x) >? 0.0001 return 3
    loop tree in original.trunks {
        let position=tree.model[3]
        if abs(position.x) >? 55.0 or abs(position.z) >? 55.0 return 4
        if abs((position.y as float64)-hill(position.x as float64 position.z as float64)) >? 0.001 return 5
    }
    let empty=fresh_forest(0)
    if empty.trunks.length not=? 0 or hill(0.0 0.0) not=? 0.0 return 6
    let low=ground_color(0.0 (-10.0) 0.0)
    let high=ground_color(0.0 10.0 0.0)
    if abs(low.x-0.35) >? 0.0001 or abs(high.x-0.75) >? 0.0001 return 7
    return 42
}
''')
    binary = tmp_path / 'forest-model'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web forest checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'forest-model.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.fixture(scope='module')
def shader_driver():
    try:
        driver = ShaderDriver()
    except DriverUnavailable as error:
        pytest.skip(str(error))
    try:
        yield driver
    finally:
        driver.close()


@pytest.mark.parametrize('case', ['dunes', 'lit', 'parameter-copies'])
def test_core_shader_driver(compiler, shader_driver, tmp_path, case):
    if case == 'dunes':
        model = Path(__file__).resolve().parents[1] / 'examples/dunes_model.dewy'
        shutil.copy2(model, tmp_path / model.name)
        body = 'from p"dunes_model.dewy" import sand_vs, sand_fs\n'
        pair = '@sand_vs @sand_fs'
    elif case == 'lit':
        body = ''
        pair = '@lit_vs @lit_fs'
    else:
        body = """Vertex:type=[pos:vec4 uv:vec2]
Surface:type=[tex:Texture tint:vec4]
Uniform:type=[surface:Surface]
Output:type=[pos:vec4 uv:vec2]
shift=(@p:vec2):>void=>{p.x+=1.0}
vertex=(v:Vertex u:Uniform):>Output=>{
let before=v.uv.x shift(@v.uv)
return Output(v.pos vec2(before v.uv.x))
}
fetch=(tex:Texture uv:vec2):>vec4=>sample(tex uv)
fragment=(i:Output u:Uniform):>vec4=>fetch(u.surface.tex i.uv)*u.surface.tint
"""
        pair = '@vertex @fragment'
    body += f"""main=()=>{{let source=shader({pair})
write_file("shader.vert" source.vs); write_file("shader.frag" source.fs); return 0}}
"""
    source = tmp_path / 'shaders.dewy'
    source.write_text(body)
    binary = tmp_path / 'shaders'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], cwd=tmp_path, capture_output=True, text=True,
                         timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    shader_driver.validate((tmp_path / 'shader.vert').read_text(),
                           (tmp_path / 'shader.frag').read_text())


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_dunes_model(compiler, tmp_path, target, release):
    model = Path(__file__).resolve().parents[1] / 'examples/dunes_model.dewy'
    shutil.copy2(model, tmp_path / model.name)
    source = tmp_path / 'dunes-model.dewy'
    source.write_text("""from p"dunes_model.dewy" import dune_height, robe_vertices, robe_indices, ribbon_vertices, ribbon_indices
main=()=>{
let cloth=robe_vertices(0.0 0.0) let indices=robe_indices()
if cloth.length not=? 175 or indices.length not=? 864 return 1
loop index in indices {if (index as int64) >=? cloth.length return 2}
loop v in cloth {if not is_finite(v.pos.x as float64) or abs(length(v.normal)-1.0) >? 0.0001 return 3}
let original=cloth cloth[0].pos.x+=10.0
if abs(cloth[0].pos.x-original[0].pos.x-10.0) >? 0.0001 return 4
let moving=robe_vertices(1.0 4.0)
if moving.length not=? cloth.length or moving[174].pos =? original[174].pos return 5
let points=[vec3(0 0 0) vec3(1 0 0) vec3(2 1 0) vec3(3 1 1)]
let ribbon=ribbon_vertices(points 0.2 0.0) let ribbon_ids=ribbon_indices(points.length)
if ribbon.length not=? 8 or ribbon_ids.length not=? 36 return 6
loop index in ribbon_ids {if (index as int64) >=? ribbon.length return 7}
if ribbon_vertices([] 0.2 0.0).length not=? 0 or ribbon_indices(0).length not=? 0 return 8
if dune_height(0.0 (-150.0)) <? 60.0 or dune_height(150.0 150.0) >? 60.0 return 9
return 42
}
""")
    binary = tmp_path / 'dunes-model'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web geometry checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'dunes.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('game', ['paddle', 'physics', 'forest', 'dunes', 'netpong', 'camera_roll', 'rollback_lab', 'outlines', 'controls', 'charts', 'reaction_field'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_game_web_build(compiler, tmp_path, game, release):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed to validate the web module')
    source = Path(__file__).resolve().parents[1] / f'examples/{game}.dewy'
    output = tmp_path / game
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', 'wasm', '-o', output, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    html = output.with_suffix('.html').read_text()
    embedded = re.search(r'SLOPPY_WASM = "([A-Za-z0-9+/=]+)"', html)
    assert embedded, 'web host must include its compiled program'
    module = tmp_path / f'{game}.wasm'
    module.write_bytes(base64.b64decode(embedded[1], validate=True))
    validation = subprocess.run([node, '-e',
        "new WebAssembly.Module(require('fs').readFileSync(process.argv[1]));", module],
        capture_output=True, text=True, timeout=10, check=False)
    assert validation.returncode == 0, validation.stdout + validation.stderr


@pytest.mark.parametrize('game', ['paddle', 'physics', 'forest', 'dunes', 'netpong', 'camera_roll', 'rollback_lab', 'outlines', 'controls', 'charts', 'reaction_field'])
def test_core_game_renderer(compiler, tmp_path, game):
    source = Path(__file__).resolve().parents[1] / f'examples/{game}.dewy'
    binary = tmp_path / game
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    screenshot = tmp_path / 'frame.png'
    env = {k: v for k, v in os.environ.items() if not k.startswith('SLOPPY_')}
    env.update(SLOPPY_SOFTWARE='1', SLOPPY_SCREENSHOT=str(screenshot), SLOPPY_FRAMES='3',
               SLOPPY_WINDOW='1280x720', SLOPPY_INPUT='1:mouse=800x620,2:mouse_right+,3:b+')
    ran = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=15, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    data = screenshot.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('>II', data[16:24]) == (1280, 720)
    if game == 'reaction_field':
        from PIL import Image
        with Image.open(screenshot) as frame:
            pixels = frame.crop((40, 152, 790, 646)).convert('RGB').tobytes()
        warm = sum(red > 100 and red > green > blue
                   for red, green, blue in zip(pixels[0::3], pixels[1::3], pixels[2::3]))
        assert warm > 1000, 'the field must contain visible reaction patterns'


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_software_raster_chunks(compiler, tmp_path, release):
    source = Path(__file__).resolve().parents[1] / 'tests/fixtures/programs/software_raster.jo'
    binary = tmp_path / 'raster'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    for threads in [1, 2]:
        env = {k: v for k, v in os.environ.items() if not k.startswith('SLOPPY_')}
        env.update(SLOPPY_THREADS=str(threads), SLOPPY_SOFT_SCALE='0.5')
        ran = subprocess.run([binary], env=env, capture_output=True, text=True,
                             timeout=10, check=False)
        assert ran.returncode == 42, (threads, ran.stdout, ran.stderr)


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_chart_render(compiler, tmp_path, release):
    source = Path(__file__).resolve().parents[1] / 'tests/fixtures/programs/chart_render.dewy'
    binary = tmp_path / 'chart'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    env = {k: v for k, v in os.environ.items() if not k.startswith('SLOPPY_')}
    env['SLOPPY_SOFTWARE'] = '1'
    ran = subprocess.run([binary], cwd=tmp_path, env=env, capture_output=True,
                         text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    data = (tmp_path / 'chart.png').read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('>II', data[16:24]) == (320, 240)


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_slider_controls(compiler, tmp_path, release):
    source = Path(__file__).resolve().parents[1] / 'tests/fixtures/programs/slider_controls.dewy'
    binary = tmp_path / 'sliders'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    scripts = {
        'drag': ('1:mouse=405x80,1:mouse_left+,2:mouse=600x350,3:mouse=200x210,4:mouse_left-,'
                 '5:mouse=40x220,5:mouse_left+,6:mouse=600x80,7:mouse_left-,'
                 '8:mouse=180x220,8:mouse_left+,9:mouse=210x450,10:mouse_left-'),
        'keys': '1:right+,2:right-,3:right+,4:right-',
        'touch': '1:touch1=405x80,2:touch1=600x350,3:touch1-',
        'click': ('1:mouse=405x80,1:mouse_left+,1:mouse_left-,'
                  '2:mouse=320x220,2:mouse_left+,2:mouse_left-,3:mouse=40x220,'
                  '4:mouse=330x80,4:mouse_left+,4:mouse_left-'),
        'descending': '1:mouse=360x220,1:mouse_left+,2:mouse=700x450,3:mouse_left-',
    }
    for scenario, script in scripts.items():
        env = {k: v for k, v in os.environ.items() if not k.startswith('SLOPPY_')}
        env.update(SLOPPY_SOFTWARE='1', SLOPPY_SCREENSHOT=str(tmp_path / f'{scenario}.png'),
                   SLOPPY_FRAMES='10', SLOPPY_WINDOW='640x480', SLOPPY_INPUT=script)
        ran = subprocess.run([binary], env=env, capture_output=True, text=True,
                             timeout=15, check=False)
        assert ran.returncode == 0, (scenario, ran.stdout, ran.stderr)
        values = [list(map(float, line.split())) for line in ran.stdout.splitlines()]
        assert [row[0] for row in values] == list(range(11)), ran.stdout
        if scenario == 'drag':
            assert [row[1] for row in values] == [10, 20, 30, 10, 10, 10, 10, 10, 10, 10, 10]
            assert [row[2] for row in values] == [0, 0, 0, 0, 0, -5, 5, 5, 0, 1, 1]
            assert all(row[3] == 0 for row in values)
        elif scenario == 'keys':
            assert [row[1] for row in values] == [10, 12.5, 12.5, 15, 15, 15, 15, 15, 15, 15, 15]
            assert all(row[2:] == [0, 0] for row in values)
        elif scenario == 'touch':
            assert [row[1] for row in values] == [10, 20, 30, 30, 30, 30, 30, 30, 30, 30, 30]
            assert all(row[2:] == [0, 0] for row in values)
        elif scenario == 'click':
            assert [row[1] for row in values] == [10, 20, 20, 20, 10, 10, 10, 10, 10, 10, 10]
            assert [row[2] for row in values] == [0, 0, 5, 5, 5, 5, 5, 5, 5, 5, 5]
            assert all(row[3] == 0 for row in values)
        else:
            assert [row[3] for row in values] == [0, 10, -10, -10, -10, -10, -10, -10, -10, -10, -10]
            assert all(row[1:3] == [10, 0] for row in values)


@pytest.mark.core_quick
def test_core_check_and_format_boundary(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    text = 'unused=()=>missing\nmain=()=>42'
    source.write_text(text)
    checked = subprocess.run([compiler, 'check', source], capture_output=True,
                             text=True, timeout=10, check=False)
    assert checked.returncode != 0 and 'unknown' in checked.stderr, checked.stdout + checked.stderr
    formatted = subprocess.run([compiler, 'fmt', source], capture_output=True,
                               text=True, timeout=10, check=False)
    assert formatted.returncode == 0, formatted.stdout + formatted.stderr
    assert source.read_text() == 'unused = () => missing\nmain = () => 42\n'


@pytest.mark.parametrize(('text', 'expected', 'errors'), [
    (('1+2\nlet xs=[20 22]\nlet saved=xs\nxs[0]=99\nsaved[0]+saved[1]\n'
     'Point:type=[x:int64 y:int64]\nlet point=Point[20 22]\npoint.x=40\npoint.x+point.y\n'
     '1/2+1/3\n:type 1/2\n'), ['3', '42', '62', '5/6', 'Rational'], []),
    (('let score=20\nread=()=>score\nscore=40\nread()+2\nlet score=99\nread()\nscore\n'
     'identity=<T>(value:T):>T=>value\nidentity(42)\n'), ['42', '40', '99', '42'], []),
    ('repl_add=(x:int64 y:int64):>int64=>x+y\n:type repl_add\n:type [1 2]\n:type 40+2\n',
     ['repl_add = (x: int64 y: int64):>int64', 'array<int>', 'int'], []),
    (('{\n# A comment inside the final expression.\nlet x=20\nx+22\n}\n'
     'f=(x)=>{\nx+2\n}\nf(40)\n[loop i in [0..3) i*2]\n'
     'let text="""first\nan unmatched " inside triple quotes\nlast"""\ntext.length >? 10\n'
     'let raw=r"\\hello"\nraw.length\n'), ['42', '42', '[0, 2, 4]', 'true', '6'], []),
    (('let xs=[20 22]\n{xs[0]=99 panic("restore values")}\nxs[0]\n'
     'missing_repl_name\nxs[1]\nbroken=()=>missing_repl_name\n'
     'explode=():>int64=>{panic("restore declarations") return 42}\n'
     'let transient_repl=explode()\ntransient_repl\nlet transient_repl=42\ntransient_repl\n'),
     ['20', '22', '42'], ['panic: restore values', "unknown name 'missing_repl_name'",
                         'panic: restore declarations', "unknown name 'transient_repl'"]),
    ('let calls=0\nnext=()=>{calls+=1 return 42}\n:type next()\ncalls\nnext()\ncalls\n',
     ['int', '0', '42', '1'], []),
    (('let calls=0\nnext=()=>{calls+=1 return [20 22]}\nconst saved=next()\n'
     'saved\nsaved\ncalls\nsaved[0]=99\nsaved\nlet saved=[42]\nsaved\n'),
     ['[20, 22]', '[20, 22]', '1', '[20, 22]', '[42]'], ['cannot modify const']),
], ids=['values', 'bindings', 'types', 'multiline', 'recovery', 'query-effects', 'constant-values'])
def test_core_repl_inputs(compiler, tmp_path, text, expected, errors):
    env = {**os.environ, 'TMPDIR': str(tmp_path)}
    ran = subprocess.run([compiler, 'repl'], input=text + ':quit\n', cwd=tmp_path,
                         env=env, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected, ran.stdout + ran.stderr
    if errors:
        for message in errors:
            assert message in ran.stderr, ran.stderr
    else:
        assert not ran.stderr, ran.stderr
    assert not list((tmp_path / 'dewy-repl').glob('*.bin'))


def test_core_repl_imports(compiler, tmp_path):
    (tmp_path / 'seed.dewy').write_text('printl"seed"\nlet offset=2\n')
    (tmp_path / 'helper.dewy').write_text('from seed import offset\nprintl"helper"\n'
                                         'twice=(x)=>x*2+offset\n')
    (tmp_path / 'helper.jo').write_text('twice = (x: int) -> int: 0\n')
    text = ('import helper as h\nh.twice(20)\nfrom helper import twice\ntwice(20)\n'
            'import p"helper.dewy" as again\nagain.twice(20)\n:quit\n')
    ran = subprocess.run([compiler, 'repl'], input=text, cwd=tmp_path,
                         env={**os.environ, 'TMPDIR': str(tmp_path)}, capture_output=True,
                         text=True, timeout=20, check=False)
    assert ran.returncode == 0 and not ran.stderr, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['seed', 'helper', '42', '42', '42']


def test_core_repl_failed_import(compiler, tmp_path):
    (tmp_path / 'gate.dewy').write_text('if not file_exists("ready") panic("retry import")\n'
                                       'let answer=42\n')
    text = ('import gate as g\ng.answer\nwrite_file("ready" "yes")\n'
            'import gate as g\ng.answer\n:quit\n')
    ran = subprocess.run([compiler, 'repl'], input=text, cwd=tmp_path,
                         env={**os.environ, 'TMPDIR': str(tmp_path)}, capture_output=True,
                         text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['true', '42'], ran.stdout + ran.stderr
    assert 'panic: retry import' in ran.stderr
    assert "unknown name 'g'" in ran.stderr


def test_core_repl_help_and_eof(compiler, tmp_path):
    ran = subprocess.run([compiler, 'repl'], input=':help\n40+2\n', cwd=tmp_path,
                         env={**os.environ, 'TMPDIR': str(tmp_path)}, capture_output=True,
                         text=True, timeout=20, check=False)
    assert ran.returncode == 0 and not ran.stderr, ran.stdout + ran.stderr
    assert 'Type Dewy' in ran.stdout and 'Sloppy' not in ran.stdout
    assert ran.stdout.endswith('42\n')


def test_core_repl_terminal(compiler, tmp_path):
    import pty
    import select
    import signal
    import time

    master, slave = pty.openpty()
    env = {**os.environ, 'TMPDIR': str(tmp_path),
           'DEWY_REPL_HISTORY': str(tmp_path / 'history')}
    process = subprocess.Popen([compiler, 'repl'], cwd=tmp_path, env=env,
                               stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    output = bytearray()
    position = 0

    def expect(needle):
        nonlocal position
        deadline = time.monotonic() + 10
        while True:
            found = output.find(needle, position)
            if found >= 0:
                position = found + len(needle)
                return
            remaining = deadline - time.monotonic()
            assert remaining > 0, bytes(output)
            ready, _, _ = select.select([master], [], [], remaining)
            assert ready, bytes(output)
            output.extend(os.read(master, 16384))

    try:
        expect(b'Dewy (:help')
        expect(b'>>> ')
        os.write(master, b'let repl_unique=40\nrepl_uni\t+2\n')
        expect(b'\r\n42\r\n')
        # Cancel an unfinished input, then recall the preceding complete line.
        os.write(master, b'bad_partial\x03\x1b[A\n')
        expect(b'\r\n42\r\n')
        os.write(master, b'{repl_unique=99 printl"running" loop true {}}\n')
        expect(b'\r\nrunning\r\n')
        os.killpg(process.pid, signal.SIGINT)
        expect(b'interrupted; the session is as it was before this input')
        os.write(master, b'repl_unique+2\n')
        expect(b'\r\n42\r\n')
        expect(b'>>> ')
        os.write(master, b'\x04')
        assert process.wait(timeout=5) == 0, bytes(output)
        assert 'repl_unique+2' in (tmp_path / 'history').read_text()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        os.close(master)


@pytest.mark.parametrize('command', ['update', 'upgrade', 'add'])
def test_core_unavailable_cli(compiler, tmp_path, command):
    result = subprocess.run([compiler, command], cwd=tmp_path, capture_output=True,
                            text=True, timeout=5, check=False)
    assert result.returncode == 2
    assert 'dewy-core:' in result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.core_quick
def test_core_cli_identity(compiler):
    result = subprocess.run([compiler, '--version'], capture_output=True, text=True,
                            timeout=5, check=False)
    assert result.returncode == 0 and result.stdout.startswith('dewy-core ')
    result = subprocess.run([compiler, '--help'], capture_output=True, text=True,
                            timeout=5, check=False)
    assert result.returncode == 0 and 'file.dewy' in result.stderr


def test_core_build_source_counts(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    helper = tmp_path / 'helper.dewy'
    body = 'import p"helper.dewy" as h\n# 🙂\n\nmain=()=>h.answer()'
    imported = 'answer=()=>42\n'
    source.write_text(body)
    helper.write_text(imported)
    built = subprocess.run([compiler, 'build', source, '--time', '-o', tmp_path / 'program'],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    expected_bytes = len((body + imported).encode())
    assert f'5 Dewy lines ({expected_bytes} bytes)' in built.stderr, built.stderr
    assert 'implementation lines' in built.stderr and 'lower+codegen' in built.stderr


@pytest.mark.parametrize('kind', ['game', 'arcade', 'platformer', '3d', 'story', 'online', 'program'])
def test_core_new_project(compiler, tmp_path, kind):
    project = tmp_path / 'project with spaces'
    made = subprocess.run([compiler, 'new', project, kind], capture_output=True,
                          text=True, timeout=5, check=False)
    assert made.returncode == 0, made.stdout + made.stderr
    source = project / ('project-with-spaces.dewy' if kind in {'online', 'arcade', 'story'} else 'main.dewy')
    assert source.is_file() and (project / 'README.md').is_file()
    assert not list(project.glob('*.jo'))
    binary = project / 'main'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(SLOPPY_SOFTWARE='1', SLOPPY_THREADS='2', SLOPPY_FRAMES='3',
               SLOPPY_SCREENSHOT=str(project / 'frame.png'), SLOPPY_SAVE_DIR=str(project / 'saves'))
    ran = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    if kind == 'program':
        assert ran.stdout == 'Hello, Dewy!\n'
    else:
        assert (project / 'frame.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
        built = subprocess.run([compiler, 'build', source, '--target', 'wasm', '-o', binary],
                               capture_output=True, text=True, timeout=30, check=False)
        assert built.returncode == 0, built.stdout + built.stderr
        assert (project / 'main.html').is_file()
        if kind == 'online':
            assert 'distinct .dewy source filename' in built.stderr
            assert '`build:`' not in built.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_platformer_starter_model(compiler, tmp_path, target, release):
    template = Path(__file__).resolve().parents[1] / 'lib/new/dewy/platformer.dewy'
    model = template.read_text().split('# Presentation and live game state.', 1)[0]
    body = model + r'''
main=()=>{
    let map=make_level("........\n........\n........\n........\n########")
    let at=vec2(72 168)
    let p=spawn(at)
    loop i in [0..60) p=tick(p map at Pad[] 1.0/120.0).player
    if not p.on_ground or abs(p.box.y-152.0)>?0.001 or p.vel.y not=?0.0 return 1
    let saved=p
    let jumping=tick(p map at Pad[pressed=true held=true] 1.0/120.0)
    if not jumping.jumped or jumping.player.box.y>=?p.box.y or p not=?saved return 2
    p=jumping.player
    loop i in [0..14) p=tick(p map at Pad[held=true] 1.0/120.0).player
    if tick(p map at Pad[pressed=true held=true] 1.0/120.0).jumped return 3
    let held=tick(p map at Pad[held=true] 1.0/120.0).player
    let released=tick(p map at Pad[] 1.0/120.0).player
    if released.vel.y<=?held.vel.y or released.box.y<=?held.box.y return 4

    # A recent ledge departure permits one jump; an expired window does not.
    let ledge=spawn(vec2(500 100))
    ledge.coyote=0.05
    if not tick(ledge map at Pad[pressed=true held=true] 0.01).jumped return 5
    ledge.coyote=0.0
    if tick(ledge map at Pad[pressed=true held=true] 0.01).jumped return 6

    # Press just before landing: consume the buffered jump on the next step.
    let falling=spawn(vec2(72 170))
    falling.vel.y=600.0
    let landed=tick(falling map at Pad[pressed=true held=true] 0.01)
    if not landed.player.on_ground or landed.jumped or landed.impact<?600.0 return 7
    if not tick(landed.player map at Pad[held=true] 0.01).jumped return 8

    let platforms=make_level("........\n........\n========\n........\n########")
    let standing=spawn(vec2(72 76))
    standing.on_ground=true
    let stay=tick(standing platforms at Pad[] 0.01).player
    let drop=tick(standing platforms at Pad[drop=true] 0.01).player
    if not stay.on_ground or drop.on_ground or drop.box.y<=?stay.box.y return 9
    let rising=spawn(vec2(72 120))
    rising.vel.y=-600.0
    let through=tick(rising platforms at Pad[held=true] 0.01).player
    if through.box.y>=?96.0 or through.vel.y>=?0.0 return 10

    let slopes=make_level(r"/\")
    let up=tilemap_move(slopes 0 Rect(10 -60 28 40) vec2(0 100))
    let down=tilemap_move(slopes 0 Rect(58 -60 28 40) vec2(0 100))
    if not up.hit_y or not down.hit_y or abs(up.rect.y+16.0)>?0.001 or abs(down.rect.y+16.0)>?0.001 return 11
    let wall=make_level("..#\n..#\n..#")
    let stopped=tilemap_move(wall 0 Rect(20 20 28 40) vec2(100 0))
    if not stopped.hit_x or stopped.rect.x not=?68.0 return 12

    let lost=spawn(vec2(500 900))
    lost.vel=vec2(50 600)
    if tick(lost map at Pad[] 0.01).player not=?spawn(at) return 13
    let moving=tick(saved map at Pad[move=-1.0] 0.01).player
    if moving.facing not=?-1.0 or moving.vel.x>=?0.0 return 14

    let coins=[Coin[pos=vec2(72 100)] Coin[pos=vec2(150 100)]]
    let original=coins
    if collect(@coins vec2(72 100) 0.01) not=?1 return 15
    if collect(@coins vec2(72 100) 0.01) not=?0 return 16
    if not coins[0].taken or coins[1].taken or original[0].taken return 17
    if coins[0].pop.t<=?0.0 or original[0].pop.t not=?0.0 return 18
    if markers("o").length not=?16 or markers("@")[0] not=?vec2(72 600) return 19
    return 42
}
'''
    result, output = run_value_batch(compiler, tmp_path, {'platformer-model': body}, release, target)['platformer-model']
    assert result == '42', output


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_3d_starter_model(compiler, tmp_path, target, release):
    template = Path(__file__).resolve().parents[1] / 'lib/new/dewy/3d.dewy'
    model = template.read_text().split('# Presentation and live game state.', 1)[0]
    body = model + r'''
main=()=>{
    let forward=view_direction(0.0 0.0)
    if length(forward-vec3(0 0 -1))>?0.00001 return 1
    if length(view_direction(PI/2.0 0.0)-vec3(-1 0 0))>?0.00001 return 2
    if abs(length(view_direction(0.7 0.4))-1.0)>?0.00001 return 3
    let origin=vec3(0 0 0)
    let targets=[Orb[pos=vec3(0 0 -8)] Orb[pos=vec3(0 0 -4)] Orb[pos=vec3(0 0 4)]]
    let saved=targets
    if shot_target(targets origin forward 0.0 100.0) not=?1 return 4
    if shot_target(targets origin forward 0.0 3.0) not=?-1 return 5
    if shot_target(targets origin forward 0.0 3.75) not=?1 return 6
    targets[1].pop=0.1
    if shot_target(targets origin forward 0.0 100.0) not=?0 or saved[1].pop not=?0.0 return 7
    if shot_target([Orb[pos=vec3(1 0 -4)]] origin forward 0.0 100.0) not=?-1 return 8
    if shot_target([Orb[pos=vec3(0 0 4)]] origin forward 0.0 100.0) not=?-1 return 9
    if shot_target([Orb[pos=origin]] origin forward 0.0 100.0) not=?0 return 10
    if shot_target([] origin forward 0.0 100.0) not=?-1 return 11
    if abs(orb_at(Orb[pos=origin] PI/4.0).y-0.25)>?0.00001 return 12

    # The same World/Character calls used by the game, with an independent saved world.
    let w=physics3d.World[gravity=vec3(0 -GRAVITY 0)]
    w.add_box(vec3(0 -0.5 0) vec3(40 1 40) kind=physics3d.BodyKind.fixed)
    let wall=w.add_box(vec3(0 2 -4) vec3(10 4 1) kind=physics3d.BodyKind.fixed)
    let body=w.add_box(vec3(5 1 0) vec3(2 2 2) density=150)
    let before=w
    let actor=w.character(vec3(0 0 0) radius=0.35)
    loop i in [0..10) w.walk(@actor vec3(0 0 0) 1.0/120.0)
    if not actor.on_ground or abs(actor.feet.y)>?0.01 return 13
    w.walk(@actor vec3(0 0 0) 1.0/120.0 jump=JUMP)
    if actor.feet.y<=?0.0 or actor.on_ground return 14
    loop i in [0..180) w.walk(@actor vec3(0 0 -WALK) 1.0/120.0)
    if actor.feet.z<?-3.2 or actor.feet.z>?-3.0 or not actor.on_ground return 15
    let hit=w.raycast(vec3(0 1 0) vec3(0 1 -10))
    let distance=match hit {h:physics3d.Hit=>float64(h.fraction)*10.0 <none>=>100.0}
    if abs(distance-3.5)>?0.001 return 16
    if shot_target(targets vec3(0 1 0) forward 0.0 distance) not=?-1 return 17
    w.push(body vec3(400 0 0) vec3(5 1 0))
    w.step(1.0/60.0)
    if w.pos(body).x<=?5.0 or before.pos(body).x not=?5.0 or before.velocity(body) not=?vec3(0 0 0) return 18
    w.remove(body)
    if w.alive(body) or not before.alive(body) return 19
    if not w.alive(wall) return 20
    return 42
}
'''
    result, output = run_value_batch(compiler, tmp_path, {'3d-model': body}, release, target)['3d-model']
    assert result == '42', output


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_arcade_starter_model(compiler, tmp_path, target, release):
    template = Path(__file__).resolve().parents[1] / 'lib/new/dewy/arcade.dewy'
    model = template.read_text().split('# Presentation and live game state.', 1)[0]
    body = model + r'''
main=()=>{
    let game=fresh(42)
    let saved=game
    if length(game.gold-game.player)<=?260.0 return 1
    game.rock_wait=0.0
    let replay=game
    advance(@game vec2(1 0) 1.0/60.0)
    advance(@replay vec2(1 0) 1.0/60.0)
    if game not=?replay or game.rocks.length not=?1 return 2
    if saved.rocks.length not=?0 or saved.elapsed not=?0.0 return 3
    if game.player.x<=?640.0 or game.vel.x<=?0.0 return 4
    game.player=vec2(1263 703)
    game.vel=vec2(420 420)
    advance(@game vec2(1 1) 0.1)
    if game.player not=?vec2(1264 704) return 5

    let collecting=fresh(7)
    collecting.player=collecting.gold
    let before=collecting
    advance(@collecting vec2(0 0) 0.01)
    if collecting.score not=?1 or before.score not=?0 return 6
    if length(collecting.gold-collecting.player)<=?260.0 return 7

    let moving=fresh(19)
    moving.rocks=[Rock[pos=vec2(200 200) vel=vec2(30 -20) r=20 spin=2.0]
                  Rock[pos=vec2(1500 200) vel=vec2(30 0) r=20]]
    let old=moving
    advance(@moving vec2(0 0) 0.1)
    if moving.rocks.length not=?1 or moving.rocks[0].pos not=?vec2(203 198) return 8
    if abs(moving.rocks[0].angle-0.2)>?0.00001 or old.rocks[0].angle not=?0.0 or old.rocks.length not=?2 return 9
    moving.rocks=[Rock[pos=moving.player vel=vec2(0 0) r=20]]
    advance(@moving vec2(0 0) 0.01)
    if not moving.over return 10
    let crashed=moving
    advance(@moving vec2(1 1) 1.0)
    if moving not=?crashed return 11

    let late=fresh(23)
    late.elapsed=1000.0
    late.rock_wait=0.0
    advance(@late vec2(0 0) 0.01)
    if late.rock_wait not=?ROCK_GAP_MIN or length(late.rocks[0].vel)>?ROCK_SPEED_MAX*1.2+0.001 return 12
    loop seed in [0..64) {
        let trial=fresh(seed)
        if trial.gold.x<?80 or trial.gold.x>=?1200 or trial.gold.y<?100 or trial.gold.y>=?660 return 13
        let same=trial
        loop frame in [0..180) {
            let input=vec2(sin(float64(frame)*0.1) cos(float64(frame)*0.1))
            advance(@trial input 1.0/60.0)
            advance(@same input 1.0/60.0)
        }
        if trial not=?same return 14
    }
    return 42
}
'''
    result, output = run_value_batch(compiler, tmp_path, {'arcade-model': body}, release, target)['arcade-model']
    assert result == '42', output


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_story_starter_model(compiler, tmp_path, target, release):
    template = Path(__file__).resolve().parents[1] / 'lib/new/dewy/story.dewy'
    model = template.read_text().split('# Presentation and live game state.', 1)[0]
    body = model + r'''
main=()=>{
    loop option in [0..2) {
        let reading=fresh()
        if reading.step.text not=?"The bell rang twice across the empty square." return 1
        let menus=0
        let ending=false
        loop i in [0..20) {
            let restored=resume(reading.bookmark)
            if restored.step not=?reading.step or restored.background not=?reading.background or restored.shown not=?reading.shown return 2
            if restored.script.vars not=?reading.script.vars return 3
            let saved=to_text(reading.bookmark)
            let decoded=from_text<Bookmark>(saved)
            match decoded {
                bookmark:Bookmark=>{
                    let loaded=resume(bookmark)
                    if loaded.step not=?reading.step or loaded.shown not=?reading.shown or loaded.background not=?reading.background return 4
                }
                error:TextError=>{printl(error.message); return 5}
            }
            if reading.step.kind=?StoryKind.end {ending=true; break}
            if reading.step.kind=?StoryKind.choice {
                menus+=1
                if reading.shown.length not=?2 or reading.step.choices.length not=?2 return 6
                let snapshot=reading
                choose(@reading -1)
                choose(@reading 99)
                if reading not=?snapshot return 7
                choose(@reading option)
                if snapshot.script.vars.length not=?0 return 8
                if option=?0 and reading.step.speaker not=?"Mira" return 9
                if option=?1 and reading.step.speaker not=?"Ren" return 10
            } else advance(@reading)
        }
        if not ending or menus not=?1 or reading.shown.length not=?0 return 11
        if reading.background not=?SCENES["tower"] return 12
        if option=?0 and reading.script.vars.get("mira")??0 not=?1 return 13
        if option=?1 and reading.script.vars.get("ren")??0 not=?1 return 14
        let restarted=fresh()
        if restarted.step.text not=?"The bell rang twice across the empty square." or restarted.script.vars.length not=?0 return 15
    }
    return 42
}
'''
    result, output = run_value_batch(compiler, tmp_path, {'story-model': body}, release, target)['story-model']
    assert result == '42', output


@pytest.mark.parametrize('flags', [[], ['--release']])
@pytest.mark.parametrize(('kind', 'count'), [('platformer', 2), ('3d', 1), ('arcade', 2), ('story', 2)])
def test_core_game_starter_tests(compiler, tmp_path, flags, kind, count):
    template = Path(__file__).resolve().parents[1] / f'lib/new/dewy/{kind}.dewy'
    env = {**os.environ, 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'SLOPPY_THREADS': '2',
           'SLOPPY_SAVE_DIR': str(tmp_path / 'saves')}
    result = subprocess.run([compiler, 'test', *flags, template], env=env, capture_output=True,
                            text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'{count} test' in result.stdout


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_online_starter_model(compiler, tmp_path, target, release):
    template = Path(__file__).resolve().parents[1] / 'lib/new/dewy/online.dewy'
    model = template.read_text().split('# Connection and presentation state', 1)[0]
    body = model + """
main=()=>{
    let original=Game[]
    let moving=tick(original [Pad[x=1 y=-1] Pad[x=-1 y=1]])
    if moving.players[0].pos not=?vec2(406 354) or moving.players[1].pos not=?vec2(874 366) return 1
    if original.players[0].pos not=?vec2(400 360) return 2
    let edge=Game[]
    edge.players[0].pos=vec2(1259 21)
    let clamped=tick(edge [Pad[x=1 y=-1] Pad[]])
    if clamped.players[0].pos not=?vec2(1260 20) return 3
    let state=Game[]
    loop i in [0..WIN) {
        state.players[0].pos=state.coin
        let saved=state
        let next=tick(state [Pad[] Pad[]])
        if next not=?tick(state [Pad[] Pad[]]) return 4
        if state not=?saved or next.players[0].score not=?i+1 return 5
        state=next
    }
    if state.winner not=?0 or state.taken not=?WIN return 6
    if tick(state [Pad[x=1] Pad[y=1]]) not=?state return 7
    return 42
}
"""
    result, output = run_value_batch(compiler, tmp_path, {'online-model': body}, release, target)['online-model']
    assert result == '42', output


@pytest.mark.parametrize('directory, entry', [('Coin Race!', 'coin-race.dewy'),
                                             ('___', '___.dewy'), ('!!!', 'online.dewy')])
@pytest.mark.parametrize('kind', ['online', 'arcade', 'story'])
def test_core_named_starter_filename(compiler, tmp_path, directory, entry, kind):
    if directory == '!!!':
        entry = f'{kind}.dewy'
    project = tmp_path / directory
    made = subprocess.run([compiler, 'new', str(project) + '/', kind],
                          capture_output=True, text=True, timeout=5, check=False)
    assert made.returncode == 0, made.stdout + made.stderr
    assert (project / entry).is_file()
    assert f'dewy-core watch {entry}' in (project / 'README.md').read_text()


@pytest.mark.parametrize('flags', [[], ['--release']])
def test_core_arcade_starter_saved_score(compiler, tmp_path, flags):
    template = Path(__file__).resolve().parents[1] / 'lib/new/dewy/arcade.dewy'
    source = tmp_path / 'score-test.dewy'
    source.write_text(template.read_text() + '''
test "save round" {
    best=0
    game.score=7
    crash()
    assert(best=?7 and screen=?Screen.over and load_data("best")??""=?"7")
    game.score=3
    crash()
    assert(best=?7 and load_data("best")??""=?"7")
    start()
    assert(screen=?Screen.playing and game.score=?0 and not game.over and best=?7)
}
test "load round" {assert(best=?7)}
''')
    env = {**os.environ, 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'SLOPPY_THREADS': '2',
           'SLOPPY_SAVE_DIR': str(tmp_path / 'saves')}
    for name in ['save round', 'load round']:
        result = subprocess.run([compiler, 'test', *flags, source, name], env=env,
                                capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        assert '1 test passed' in result.stdout


@pytest.mark.parametrize('flags', [[], ['--release']])
def test_core_story_starter_saved_reading(compiler, tmp_path, flags):
    template = Path(__file__).resolve().parents[1] / 'lib/new/dewy/story.dewy'
    source = tmp_path / 'reading-test.dewy'
    source.write_text(template.read_text() + '''
test "save reading" {
    reading=fresh()
    advance(@reading)
    assert(reading.step.speaker=?"Mira" and reading.shown["mira"]=?"left")
    on_quit()
}
test "load reading" {
    assert(reading.step.speaker=?"Mira" and reading.step.text=?"You came! I wasn't sure you would.")
    assert(reading.shown["mira"]=?"left" and reading.background=?SCENES["square"])
}
''')
    env = {**os.environ, 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'SLOPPY_THREADS': '2',
           'SLOPPY_SAVE_DIR': str(tmp_path / 'saves')}
    for name in ['save reading', 'load reading']:
        result = subprocess.run([compiler, 'test', *flags, source, name], env=env,
                                capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        assert '1 test passed' in result.stdout


def test_core_new_existing_directory(compiler, tmp_path):
    marker = tmp_path / 'main.dewy'
    marker.write_text('existing work')
    made = subprocess.run([compiler, 'new', tmp_path], capture_output=True,
                          text=True, timeout=5, check=False)
    assert made.returncode != 0 and 'already exists' in made.stderr
    assert marker.read_text() == 'existing work'
    assert list(tmp_path.iterdir()) == [marker]


def test_core_new_unknown_template(compiler, tmp_path):
    project = tmp_path / 'project'
    made = subprocess.run([compiler, 'new', project, 'unknown'], capture_output=True,
                          text=True, timeout=5, check=False)
    assert made.returncode != 0 and 'no template' in made.stderr
    assert not project.exists()


def assert_x64_compare_branch_layout(objdump, binary, symbol):
    dumped = subprocess.run([objdump, '-d', f'--disassemble={symbol}', binary],
                            capture_output=True, text=True, timeout=10, check=True)
    instructions = []
    for line in dumped.stdout.splitlines():
        match = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)\s*(\S+)', line)
        if match:
            instructions.append((int(match[1], 16), len(match[2].split()), match[3]))
    pairs = [(left, right) for left, right in zip(instructions, instructions[1:])
             if left[2].startswith('cmp') and right[2].startswith('j') and right[2] != 'jmp']
    assert len(pairs) >= 8, dumped.stdout
    for compare, branch in pairs:
        # The fused pair must neither cross nor end on the 32-byte boundary.
        assert compare[0] // 32 == (branch[0] + branch[1]) // 32, dumped.stdout
    return dumped.stdout


def test_core_x64_compare_branch_layout(compiler, tmp_path):
    objdump = shutil.which('objdump')
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64') or not objdump:
        pytest.skip('requires an x86-64 Linux host and objdump')
    cutoffs = [-129, -128, 0, 1, 127, 128, 65536, *[i * 13 + 3 for i in range(24)]]
    body = '\n'.join(f'if x <? {cutoff} printl({i})' for i, cutoff in enumerate(cutoffs))
    source = tmp_path / 'branches.dewy'
    source.write_text('branch_probe=(x:int64 y:int64):>void=>{\n'
                      'if x <? y printl(777)\n' + body +
                      '\n}\nmain=()=>{branch_probe(100 200) return 42}\n')
    binary = tmp_path / 'branches'
    built = subprocess.run([compiler, 'build', source, '--release', '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['777', *[str(i) for i, cutoff in enumerate(cutoffs) if 100 < cutoff]]
    assert_x64_compare_branch_layout(objdump, binary, 'branch_probe')


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('name', ['optional_values', 'include_bytes', 'array_moves', 'object_fields', 'object_nested', 'array_elements', 'dict_runtime'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_existing_program(compiler, tmp_path, release, name, target):
    source = Path(__file__).resolve().parents[1] / f'tests/fixtures/programs/{name}.dewy'
    binary = tmp_path / 'optional'
    flags = ['--release'] if release else []
    node = shutil.which('node')
    if target == 'wasm':
        if node is None: pytest.skip('Node is needed for web execution')
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True,
                           text=True, timeout=30, cwd=tmp_path, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_grapheme_conformance(compiler, tmp_path, release, target):
    """Independent Unicode expectations, with one compiler process per mode/target."""
    root = Path(__file__).resolve().parents[1]
    cases = [(b'', [0])]
    for line in (root / 'tests/data/GraphemeBreakTest-16.0.0.txt').read_text().splitlines():
        tokens = line.split('#')[0].split()
        if not tokens:
            continue
        data = bytearray()
        boundaries = []
        for token in tokens:
            if token == '÷':
                boundaries.append(len(data))
            elif token != '×':
                data.extend(chr(int(token, 16)).encode())
        cases.append((bytes(data), boundaries))
    # Exhaust the ASCII shortcut, including the CR/LF exception.
    cases.extend((bytes([a, b]), [0, 2] if (a, b) == (13, 10) else [0, 1, 2])
                 for a in range(128) for b in range(128))
    cases.extend((data, None) for data in [b'\x80', b'\xc0\xaf', b'\xc1\xbf', b'\xc2',
                 b'\xe0\x80\x80', b'\xed\xa0\x80', b'\xf0\x80\x80\x80', b'\xf4\x90\x80\x80',
                 b'\xf5\x80\x80\x80', b'\xe2\x82', b'\xc2A', b'\xff'])
    cases.extend((prefix + invalid, None)
                 for prefix in [b'A', b'AB', b'\r', b'\r\n', b'\r\nA']
                 for invalid in [b'\x80', b'\xc2', b'\xed\xa0\x80', b'\xf4\x90\x80\x80'])
    (tmp_path / 'cases.bin').write_bytes(b''.join(struct.pack('<I', len(data)) + data for data, _ in cases))
    expected = ['invalid' if boundaries is None else ','.join(map(str, boundaries)) for _, boundaries in cases]
    (tmp_path / 'iteration.dewy').write_text('''stream_clusters=(text:string):>array<string>=>[loop c in text c]
''')
    source = tmp_path / 'conformance.jo'
    source.write_text('''use 'iteration.dewy'
main = ():
    data_ = embed("cases.bin")
    offset = 0
    loop offset < data_.len():
        size = __grapheme_word(data_, offset)
        offset += 4
        text = str_from_bytes(data_[offset..offset + size))
        offset += size
        decoded = __dewy_decode_utf8(bytes(text))
        if let bounds = grapheme_boundaries(text):
            assert(decoded != none and decoded! == text)
            assert(__dewy_string_length(text) == bounds.len() - 1)
            clusters = graphemes(text)
            assert(clusters.len() == bounds.len() - 1)
            assert(join(clusters, "") == text)
            assert(stream_clusters(text) == clusters)
            loop i in [0..clusters.len()):
                assert(__dewy_string_index(text, i) == clusters[i])
                assert(__dewy_string_slice(text, i, i + 1, false, true) == clusters[i])
                assert(__dewy_string_slice(text, i, i, true, true) == clusters[i])
            parts: str[]
            loop boundary in bounds: parts.push("{boundary}")
            print(join(parts, ","))
        else:
            assert(decoded == none)
            print("invalid")
''')
    binary = tmp_path / 'conformance'
    flags = ['--release'] if release else []
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web conformance')
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_streaming_graphemes(compiler, tmp_path, target, release):
    source = tmp_path / 'stream.dewy'
    source.write_text('''let calls:int64=0
let shared="abc"
input=()=>{calls+=1 return shared}
replace=()=>{shared="changed" return "12"}
first=(text:string):>string=>{loop c in text return c return ""}
main=()=>{
    let before=alloc_count()
    {
        let large=repeat("a" 20000)
        let ready=alloc_count()
        loop c in large {
            # A loop keeps one cluster, not an array of 20,000 cluster strings.
            if alloc_count()-ready >? 12 return 1
            if c not=? "a" return 2
            break
        }
        let sum:int64=0
        loop i in 0.. and c in large {if i =? 3 break if i =? 1 continue sum+=i+bytes(c).length}
        if sum not=? 4 return 3
        let saved:array<string>=[]
        loop c in "é👩‍👩‍👧‍👦🇺🇸" {saved.push(c) c="changed"}
        if saved not=? ["é" "👩‍👩‍👧‍👦" "🇺🇸"] return 4
        let seen=""
        loop c in input() {shared="replacement" seen+=c}
        if calls not=? 1 or seen not=? "abc" return 5
        shared="abc"
        seen=""
        loop a in input() and b in replace() {seen+=a+b}
        if calls not=? 2 or seen not=? "a1b2" return 6
        let zipped=[loop a in "abc" and b in [1 2] a]
        if zipped not=? ["a" "b"] return 7
        let count:int64=0
        loop a in "" and b in "abc" {count+=1}
        loop a in "ab" and b in "cd" {loop c in "12" {if c =? "1" continue count+=1}}
        if count not=? 2 return 8
        if first("") not=? "" or first("🙂x") not=? "🙂" return 9
        # Foreign bytes are checked as visited; an untouched tail is not scanned.
        let bad_tail=str_from_bytes([97 98 99 255] as array<uint8>)
        if first(bad_tail) not=? "a" return 10
        loop i in [0..100) {if first(large) not=? "a" return 11}
        if alloc_count()-ready >? 25 return 12
    }
    if alloc_count() not=? before return 13
    return 42
}
''')
    binary = tmp_path / 'stream'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web streaming checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'stream.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_embedded_png(compiler, tmp_path, release, target):
    """A Dewy asset declaration feeds the inherited image decoder on both targets."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

    asset = tmp_path / 'pixel.png'
    asset.write_bytes(b'\x89PNG\r\n\x1a\n'
                      + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
                      + chunk(b'IDAT', zlib.compress(bytes([0, 42, 0, 0, 255])))
                      + chunk(b'IEND', b''))
    source = tmp_path / 'image.dewy'
    source.write_text('''$include_bytes(p"pixel.png") as pixel
main=()=>{let image=load_image(pixel)
return if image.width =? 1 and image.height =? 1 and image.pixels.length =? 4 image.pixels[0] as int64 else 1}
''')
    binary = tmp_path / 'image'
    flags = ['--release'] if release else []
    node = shutil.which('node')
    if target == 'wasm':
        if node is None:
            pytest.skip('Node is needed for web execution')
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    # The emitted program is self-contained; decoding must not read the source asset.
    asset.unlink()
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_physics_scene(compiler, tmp_path, target, release):
    node = shutil.which('node')
    if target == 'wasm' and node is None:
        pytest.skip('Node is needed to execute the generated web runner')
    model = Path(__file__).resolve().parents[1] / 'examples/physics_scene.dewy'
    shutil.copy2(model, tmp_path)
    source = tmp_path / 'physics_test.dewy'
    source.write_text('''import physics as dynamics
from p"physics_scene.dewy" import fresh, advance, add_ball
main=()=>{
    let scene=fresh()
    if scene.world.bodies().length not=? 57 return 1
    let original=scene
    let ball=add_ball(@scene vec2(50 100) 12)
    loop i in [0..120) {advance(@scene 1.0/120.0)}
    if scene.world.bodies().length not=? 58 or original.world.bodies().length not=? 57 return 2
    let fallen=scene.world.pos(ball)
    if fallen.y <? 400.0 or fallen.y >? 680.0 return 3
    if original.rope is? dynamics.Joint {
        let ends=original.world.ends(original.rope)
        if ends[1].x not=? 640.0 or ends[1].y not=? 160.0 return 4
    } else return 5
    let joint=scene.world.drag(ball fallen)
    scene.world.drag_to(joint vec2(200 200))
    loop i in [0..120) {advance(@scene 1.0/120.0)}
    let moved=scene.world.pos(ball)
    if moved.x <? 100.0 or moved.y >? 400.0 return 6
    scene.world.remove(joint)
    scene.world.remove(ball)
    if scene.world.bodies().length not=? 57 return 7
    return 42
}''')
    binary = tmp_path / 'physics_test'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('style', ['namespace', 'selected'])
def test_core_library_import(compiler, tmp_path, style):
    source = tmp_path / 'import_test.dewy'
    declaration, name = ('import physics as dynamics', 'dynamics.World') if style == 'namespace' else (
        'from physics import World as Space', 'Space')
    source.write_text(f'{declaration}\nmain=()=>{{let world={name}[] return world.iterations+34}}')
    binary = tmp_path / 'import_test'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert subprocess.run([binary], timeout=10, check=False).returncode == 42


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('indent', ['    ', '\t'], ids=['spaces', 'tabs'])
@pytest.mark.parametrize('use_invalid', [False, True], ids=['deferred', 'called'])
def test_core_conditional_library_bodies(compiler, tmp_path, target, release, indent, use_invalid):
    library = tmp_path / 'lib'
    library.mkdir()
    for item in (compiler.parent.parent / 'lib').iterdir():
        if item.name != 'std':
            (library / item.name).symlink_to(item, target_is_directory=item.is_dir())
    (library / 'std').mkdir()
    for item in (compiler.parent.parent / 'lib/std').iterdir():
        (library / 'std' / item.name).symlink_to(item)
    # Declaration branches, sibling bodies, multiline strings, comments and local
    # closures must keep their boundaries when library bodies are parsed on demand.
    text = '''when true:
    when false:
        conditional_pick = () -> int:
            return )
    else when TARGET == "wasm":
        conditional_pick = () -> int:
            text = """first
unindented text
last"""
            return if len(text) > 0: 40 else: 0
    else:
        conditional_pick = () -> int:
            return 40
# A comment outside the function does not end the declaration branch.
    conditional_tail = () -> int:
        f = (x: int) -> int:
            when true:
                return x + 1
        return f(1)
    conditional_invalid = () -> int:
        return )
conditional_runtime = () -> int:
    if true:
        local = (x: int) -> int:
            return x + 1
        return local(1) - 2
    else:
        local = (x: int) -> int:
            return x + 2
        return local(1) - 3
'''
    if indent == '\t':
        text = '\n'.join(indent * ((len(line) - len(line.lstrip(' '))) // 4)
                         + line.lstrip(' ') for line in text.split('\n'))
    fixture = library / 'std/conditional_bodies.jo'
    fixture.write_text(text)
    source = tmp_path / 'main.dewy'
    expression = 'conditional_invalid()' if use_invalid else (
        'conditional_pick()+conditional_tail()+conditional_runtime()')
    source.write_text(f'main=()=>{expression}\n')
    binary = tmp_path / 'program'
    flags = ['--release'] if release else []
    env = {**os.environ, 'DEWY_CORE_LIB': str(library)}
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary, *flags],
                           env=env, capture_output=True, text=True, timeout=30, check=False)
    if use_invalid:
        line = text.splitlines().index('        return )'.replace('    ', indent), 5) + 1
        assert built.returncode != 0
        assert f'{fixture}:{line}:' in built.stderr, built.stderr
        return
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web library parsing checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'conditional.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('source_text', [
    'divide=(a b)=>a/b\nmain=()=>if divide(3.0 2.0) =? 1.5 42 else 1',
    'BigInt:type=[value:int64]\n__truediv__=(a:BigInt b:BigInt)=>a.value//b.value\nmain=()=>BigInt[84]/BigInt[2]',
], ids=['float', 'custom'])
def test_core_division_without_exact_libraries(compiler, tmp_path, source_text):
    library = tmp_path / 'lib'
    library.mkdir()
    for item in (compiler.parent.parent / 'lib').iterdir():
        if item.name not in ('bigint.dewy', 'rational.dewy'):
            (library / item.name).symlink_to(item, target_is_directory=item.is_dir())
    source = tmp_path / 'main.dewy'
    source.write_text(source_text)
    binary = tmp_path / 'program'
    env = {**os.environ, 'DEWY_CORE_LIB': str(library)}
    built = subprocess.run([compiler, 'build', source, '-o', binary, '--release'], env=env,
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('entry', ['body', 'global', 'unused-constant'])
def test_core_exact_division_module_initialization(compiler, tmp_path, target, release, entry):
    library = tmp_path / 'lib'
    library.mkdir()
    for item in (compiler.parent.parent / 'lib').iterdir():
        if item.name != 'rational.dewy':
            (library / item.name).symlink_to(item, target_is_directory=item.is_dir())
    # An observable library initializer checks dependency order when a language
    # operation first discovers a module during function/global checking.
    (library / 'seed.dewy').write_text('let seed:int64=39\nprintl"seed"\n')
    (library / 'rational.dewy').write_text('''from seed import seed
let base=seed+1
printl"rational"
rational=(a b):>int64=>a+b+base
''')
    (tmp_path / 'helper.dewy').write_text('const offset=1\n')
    bodies = {
        'body': 'main=()=>1/2-offset',
        'global': 'let ratio=1/2\nmain=()=>ratio-offset',
        'unused-constant': 'const unused=1/2\nmain=()=>42',
    }
    source = tmp_path / 'main.dewy'
    source.write_text('from helper import offset\nprintl"main"\n' + bodies[entry] + '\n')
    binary = tmp_path / 'program'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    env = {**os.environ, 'DEWY_CORE_LIB': str(library)}
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], env=env,
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web module initialization checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'modules.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['seed', 'rational', 'main']


@pytest.mark.parametrize(('expression', 'diagnostic'), [
    ('pair[0]+pair[1].length', None),
    ('pair[-1]', 'tuple index out of range'),
    ('pair[2]', 'tuple index out of range'),
    ('pair[i]', 'tuple index must be an integer literal'),
])
def test_core_tuple_interop(compiler, tmp_path, expression, diagnostic):
    (tmp_path / 'helper.jo').write_text('pair = () -> (int, str): (39, "abc")')
    source = tmp_path / 'tuple.dewy'
    source.write_text(f'import p"helper.jo"\nmain=()=>{{let pair=helper.pair() let i:int64=0 return {expression}}}')
    binary = tmp_path / 'tuple'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    if diagnostic:
        assert built.returncode != 0 and diagnostic in built.stderr, built.stdout + built.stderr
    else:
        assert built.returncode == 0, built.stdout + built.stderr
        assert subprocess.run([binary], timeout=10, check=False).returncode == 42


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('mismatch', [False, True])
@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('parameter', [False, True], ids=['binding', 'parameter'])
def test_core_unpack_tuple_and_length_guard(compiler, tmp_path, target, release, mismatch, nested, parameter):
    (tmp_path / 'helper.jo').write_text('''pair = () -> (int, str): (39, "abc")
nested = () -> ((int, str), int[]): ((39, "abc"), [0])
pairs = () -> (str, int[])[]: [("a", [20, 1]), ("b", [2, 19])]''')
    source = tmp_path / 'unpack.dewy'
    if mismatch:
        program = ('main=()=>{let [[first second] [_]]=[[42] [0]] return first+second}' if nested else
                   'main=()=>{let [first second]=[42] return first+second}')
    else:
        program = ('''main=()=>{let [[count text] [extra]]=helper.nested()
let total:int64=0
loop [key [x y]] in helper.pairs() {total+=x+y}
loop i in [0..2) and [key [x y]] in helper.pairs() {total+=x+y}
if total not=? 84 return 1
return count+text.length+extra}''' if nested else
                   'main=()=>{let [count:float64 text:string]=helper.pair() return if count is?float64 (count as int64)+text.length else 1}')
    if parameter:
        if mismatch:
            program = ('sum=([[first second] [_]]:array<array<int64>>):>int64=>first+second\nmain=()=>sum([[42] [0]])' if nested else
                       'sum=([first second]:array<int64>):>int64=>first+second\nmain=()=>sum([42])')
        else:
            program = ('sum=([[count text] [extra]])=>count+text.length+extra\nmain=()=>sum(helper.nested())' if nested else
                       'sum=([count:float64 text:string])=>if count is?float64 (count as int64)+text.length else 1\nmain=()=>sum(helper.pair())')
    source.write_text('import p"helper.jo"\n' + program)
    binary = tmp_path / 'unpack'
    node = shutil.which('node')
    if target == 'wasm' and node is None:
        pytest.skip('Node is needed for web execution')
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    if mismatch:
        assert ran.returncode != 0 and 'unpacking requires exactly 2 elements' in ran.stderr, ran.stdout + ran.stderr
    else:
        assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


def test_core_web_pointer_lock_events():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is required for the web input event check')
    script = Path(__file__).with_name('core_web_input.cjs')
    result = subprocess.run([node, script], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_memory_equality_guard_pages(compiler, tmp_path, release):
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('guard-page syscalls require x86-64 Linux')
    source = tmp_path / 'guard.jo'
    # Each source ends at an inaccessible page; test every mismatch position,
    # vector boundary, and relative alignment, including zero readable bytes.
    source.write_text('''main = () -> int:
    aa = syscall(9, 0, 8192, 3, 0x22, -1, 0)
    bb = syscall(9, 0, 8192, 3, 0x22, -1, 0)
    if aa < 0 or bb < 0: return 3
    if syscall(10, aa + 4096, 4096, 0) != 0: return 4
    if syscall(10, bb + 4096, 4096, 0) != 0: return 5
    loop n in [0..257):
        loop offset in [0..16):
            a = (aa + 4096 - n) as *u8
            b = (bb + 4096 - n - offset) as *u8
            loop i in [0..n):
                a[i] = u8((i * 13 + n) % 256)
                b[i] = a[i]
            if not __mem_eq(a, b, n): return 6
            loop i in [0..n):
                b[i] = b[i] xor u8(128)
                if __mem_eq(a, b, n): return 7
                b[i] = b[i] xor u8(128)
    if syscall(11, aa, 8192) != 0: return 8
    if syscall(11, bb, 8192) != 0: return 9
    42
''')
    binary = tmp_path / 'guard'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_memory_equality_live_results(compiler, tmp_path, release):
    # More live comparison results than available integer registers: retaining
    # earlier results must work when a later comparison spills its destination.
    statements = '\n'.join(f'        r{i} = __mem_eq(a, b, n + {i})' for i in range(24))
    combine = '\n'.join(f'        if r{i}: result += {1 << i}' for i in range(24))
    source = tmp_path / 'live.jo'
    source.write_text('probe = (a: *u8, b: *u8, n: int, rounds: int) -> int:\n'
                      '    total = 0\n    loop _ in [0..rounds):\n' + statements +
                      '\n        result = 0\n' + combine + '\n        total += result\n    total\n' +
                      'main = () -> int:\n    a = fill(u8(7), 64)\n    b = fill(u8(7), 64)\n'
                      '    if probe(data(a), data(b), 1, 2) != 33554430: return 1\n'
                      '    b[17] = 8\n    if probe(data(a), data(b), 1, 2) != 262142: return 2\n'
                      '    b[17] = 7\n    if probe(data(a), data(b), 1, 2) != 33554430: return 3\n'
                      '    42\n')
    binary = tmp_path / 'live'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr
    objdump = shutil.which('objdump')
    if platform.system() == 'Linux' and platform.machine().lower() in ('x86_64', 'amd64') and objdump:
        assembly = assert_x64_compare_branch_layout(objdump, binary, 'probe')
        assert 'pcmpeqb' in assembly, assembly
        assert any('push' in line and '%r11' in line for line in assembly.splitlines()), assembly


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_memory_equality_branches(compiler, tmp_path, release):
    source = tmp_path / 'branches.jo'
    source.write_text("""@noinline
identity = (x: int) -> int: x
@noinline
positive = (a: *u8, b: *u8, n: int) -> int:
    result = 0
    loop _ in [0..2):
        if __mem_eq(a, b, n): result += identity(17)
        else: result += identity(42)
    result / 2
@noinline
negative = (a: *u8, b: *u8, n: int) -> int:
    result = 0
    loop _ in [0..2):
        if not __mem_eq(a, b, n): result += identity(29)
        else: result += identity(31)
    result / 2
main = () -> int:
    a = fill(u8(7), 64)
    b = fill(u8(7), 64)
    loop n in [-3, 0, 1, 2, 4, 8, 16, 31, 32, 63, 64]:
        if positive(data(a), data(b), n) != 17: return 1
        if negative(data(a), data(b), n) != 31: return 2
    b[17] = 8
    loop n in [18, 31, 32, 63, 64]:
        if positive(data(a), data(b), n) != 42: return 3
        if negative(data(a), data(b), n) != 29: return 4
    if positive(data(a), data(b), 17) != 17: return 5
    42
""")
    binary = tmp_path / 'branches'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr
    objdump = shutil.which('objdump')
    if platform.system() == 'Linux' and platform.machine().lower() in ('x86_64', 'amd64') and objdump:
        for symbol in ['positive', 'negative']:
            assembly = assert_x64_compare_branch_layout(objdump, binary, symbol)
            assert 'pcmpeqb' in assembly, assembly
            assert not re.search(r'\bset(?:e|ne)\b', assembly), assembly


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_string_equality_guard_pages(compiler, tmp_path, release):
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('guard-page syscalls require x86-64 Linux')
    source = tmp_path / 'string-guard.jo'
    # Immortal headers keep the test's mappings outside refcount ownership.
    # An unequal length must return before touching an inaccessible payload.
    source.write_text('''main = () -> int:
    aa = syscall(9, 0, 8192, 3, 0x22, -1, 0)
    bb = syscall(9, 0, 8192, 3, 0x22, -1, 0)
    if aa < 0 or bb < 0: return 3
    if syscall(10, aa + 4096, 4096, 0) != 0: return 4
    if syscall(10, bb + 4096, 4096, 0) != 0: return 5
    nil_: str
    loop n in [0..129):
        loop offset in [0..8):
            a = (aa + 4096 - n - 24) as *u8
            b = (bb + 4096 - n - 24 - offset) as *u8
            (a as *int)[0] = 0
            (b as *int)[0] = 0
            (a as *int)[1] = n
            (b as *int)[1] = n
            (a as *int)[2] = n
            (b as *int)[2] = n
            loop i in [0..n):
                a[24 + i] = u8((i * 13 + n) % 256)
                b[24 + i] = a[24 + i]
            if not __str_eq(a as str, b as str): return 6
            if not __str_eq(a as str, a as str): return 7
            if __str_eq(a as str, nil_) != (n == 0): return 8
            if __str_eq(nil_, b as str) != (n == 0): return 9
            (b as *int)[1] = n + 1
            if __str_eq(a as str, b as str): return 10
            (b as *int)[1] = n
            loop i in [0..n):
                b[24 + i] = b[24 + i] xor u8(128)
                if __str_eq(a as str, b as str): return 11
                b[24 + i] = b[24 + i] xor u8(128)
    if syscall(11, aa, 8192) != 0: return 12
    if syscall(11, bb, 8192) != 0: return 13
    42
''')
    binary = tmp_path / 'string-guard'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


def emission_word_helpers(compiler):
    source = compiler.parent.parent / 'compiler/x64.jo'
    if not source.exists():
        # Packaged host-smoke compilers omit implementation sources. Those jobs
        # test the checkout's helpers with the packaged compiler instead.
        source = Path(__file__).resolve().parents[1] / 'compiler/x64.jo'
    implementation = source.read_text(encoding='utf-8')
    return 'code: u8[]\n' + implementation[implementation.index('b = (x: int):'):
                                            implementation.index('\nrip_kind =')]


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'linux-arm64'])
def test_core_emission_words(compiler, tmp_path, release, target):
    runner = shutil.which('qemu-aarch64') if target == 'linux-arm64' else None
    if target == 'linux-arm64' and runner is None:
        pytest.skip('QEMU is needed to exercise word emission on ARM64')
    # Exercise the actual emitter helpers against independently encoded words,
    # with unaligned offsets, signed boundaries, growth and retained snapshots.
    rng = random.Random(138)
    values = [-(1 << 63), -(1 << 31), -1, 0, 1, (1 << 31)-1, (1 << 32)-1, (1 << 63)-1]
    values += [rng.randrange(-(1 << 63), 1 << 63) for _ in range(24)]
    initial = bytearray([0xA5])
    for value in values:
        initial += (value & 0xffffffff).to_bytes(4, 'little') + b'\x5a'
        initial += (value & 0xffffffffffffffff).to_bytes(8, 'little') + b'\xa5'
    changes = [(0, -1), (17, -(1 << 31)), (len(initial)-4, 0x12345678)]
    expected = initial.copy()
    for offset, value in changes:
        expected[offset:offset+4] = (value & 0xffffffff).to_bytes(4, 'little')
    statements = '\n'.join(f'    b32({value}); b(90); b64({value}); b(165)' for value in values)
    patches = '\n'.join(f'    patch32({offset}, {value})' for offset, value in changes)
    source = tmp_path / 'emission-words.jo'
    source.write_text(emission_word_helpers(compiler) + f'''\nmain = () -> int:
    b(165)
    first = code
{statements}
    saved = code
{patches}
    assert(first == [u8(165)])
    loop byte in saved: print(int(byte))
    print("patched")
    loop byte in code: print(int(byte))
    0
''')
    binary = tmp_path / 'words'
    flags = ['--release'] if release else []
    if target != 'native':
        flags += ['--target', target]
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [runner, binary] if runner else [binary]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == [*map(str, initial), 'patched', *map(str, expected)]


@pytest.mark.core_quick
@pytest.mark.parametrize('offset', [-1, 5], ids=['before-buffer', 'past-buffer'])
def test_core_emission_fixup_bounds(compiler, tmp_path, offset):
    source = tmp_path / 'bad-fixup.jo'
    source.write_text(emission_word_helpers(compiler) + f'''\nmain = () -> int:
    b64(0)
    patch32({offset}, 42)
    0
''')
    binary = tmp_path / 'bad-fixup'
    built = subprocess.run([compiler, 'build', source, '--release', '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode != 0, ran.stdout + ran.stderr
    assert 'panic:' in ran.stderr, ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_scaled_multiply(compiler, tmp_path, release):
    rng = random.Random(3549)
    values = [-(1 << 63), -(1 << 63)+1, -(1 << 31), -1, 0, 1,
              (1 << 31)-1, (1 << 63)-2, (1 << 63)-1]
    values += [rng.randrange(-(1 << 63), 1 << 63) for _ in range(24)]
    coefficients = [3, 5, 9] * 4
    params = ', '.join(f'a{i}: int' for i in range(12))
    products = '\n'.join(f'    v{i} = a{i} * {c}' for i, c in enumerate(coefficients))
    arguments = ', '.join(f'v{i}' for i in range(12))
    total = ' + '.join(f'a{i}' for i in range(12))
    calls = '\n'.join(f'    print(mul3({v})); print(mul5({v})); print(mul9({v}))' for v in values)
    pressure_values = values[:12]
    source = tmp_path / 'scaled-multiply.jo'
    source.write_text(f'''@noinline
mul3 = (x: int) -> int: x * 3
@noinline
mul5 = (x: int) -> int: x * 5
@noinline
mul9 = (x: int) -> int: x * 9
@noinline
sink = ({params}) -> int: {total}
@noinline
pressure = ({params}) -> int:
{products}
    sink({arguments})
main = () -> int:
{calls}
    print(pressure({', '.join(map(str, pressure_values))}))
    0
''')
    binary = tmp_path / 'scaled-multiply'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    def signed_word(value):
        return (value + (1 << 63)) % (1 << 64) - (1 << 63)
    expected = [signed_word(v*c) for v in values for c in (3, 5, 9)]
    expected.append(signed_word(sum(v*c for v, c in zip(pressure_values, coefficients))))
    assert [int(line) for line in ran.stdout.splitlines()] == expected
    objdump = shutil.which('objdump')
    if platform.system() == 'Linux' and platform.machine().lower() in ('x86_64', 'amd64') and objdump:
        for name in ('mul3', 'mul5', 'mul9'):
            assembly = subprocess.check_output([objdump, '-d', f'--disassemble={name}', binary], text=True)
            assert re.search(r'\blea\b', assembly), assembly
            assert not re.search(r'\bimul\b', assembly), assembly


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_integer_select_flags(compiler, tmp_path, release):
    # Dynamic comparisons prevent constant folding. Zero/large arms check that
    # operand materialization preserves comparison flags; live results exercise
    # overlapping registers and spills.
    rng = random.Random(1906)
    signed = [-(1 << 63), -(1 << 31), -1, 0, 1, (1 << 31)-1, (1 << 63)-1]
    unsigned = [0, 1, (1 << 31)-1, 1 << 31, (1 << 63)-1, 1 << 63, (1 << 64)-1]
    functions, calls, expected = [], [], []
    operations = [('eq', '==', lambda a, b: a == b), ('ne', '!=', lambda a, b: a != b),
                  ('lt', '<', lambda a, b: a < b), ('le', '<=', lambda a, b: a <= b),
                  ('gt', '>', lambda a, b: a > b), ('ge', '>=', lambda a, b: a >= b)]
    for kind, ty, values in [('signed', 'int', signed), ('unsigned', 'u64', unsigned)]:
        pairs = [(a, b) for a in values for b in values]
        for op, symbol, predicate in operations:
            name = f'{kind}_{op}'
            functions.append(f'@noinline\n{name} = (a: {ty}, b: {ty}, yes: int, no: int) -> int: if a {symbol} b: yes else: no')
            for a, b in pairs:
                yes, no = rng.choice([0, -1, 0x123456789abcdef]), rng.choice([0, 1, -0x123456789abcdef])
                calls.append(f'    print({name}({a}, {b}, {yes}, {no}))')
                expected.append(yes if predicate(a, b) else no)
    functions.append('@noinline\nconstant_arms = (a: int, b: int) -> int: if a < b: 0 else: 0x123456789abcdef')
    for a, b in [(-1, 0), (0, -1), (0, 0)]:
        calls.append(f'    print(constant_arms({a}, {b}))')
        expected.append(0 if a < b else 0x123456789abcdef)
    params = ', '.join(f'a{i}: int' for i in range(12))
    total = ' + '.join(f'a{i}' for i in range(12))
    functions.append(f'@noinline\nsink_selects = ({params}) -> int: {total}')
    choices = '\n'.join(f'    v{i} = if a{i} < limit: a{(i+1)%12} else: a{(i+2)%12}' for i in range(12))
    functions.append(f"@noinline\npressure_selects = ({params}, limit: int) -> int:\n{choices}\n    sink_selects({', '.join(f'v{i}' for i in range(12))})")
    for limit in (-1, 6, 12):
        calls.append(f"    print(pressure_selects({', '.join(map(str, range(12)))}, {limit}))")
        expected.append(sum((i+1)%12 if i < limit else (i+2)%12 for i in range(12)))
    source = tmp_path / 'integer-select.jo'
    source.write_text('\n'.join(functions) + '\nmain = () -> int:\n' + '\n'.join(calls) + '\n    0\n')
    binary = tmp_path / 'integer-select'
    built = subprocess.run([compiler, 'build', source, *(['--release'] if release else []), '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert [int(line) for line in ran.stdout.splitlines()] == expected
    objdump = shutil.which('objdump')
    if platform.system() == 'Linux' and platform.machine().lower() in ('x86_64', 'amd64') and objdump:
        for name in ('signed_lt', 'unsigned_gt', 'constant_arms'):
            assembly = subprocess.check_output([objdump, '-d', f'--disassemble={name}', binary], text=True)
            assert re.search(r'\bcmov\w*\b', assembly), assembly
            if name != 'constant_arms':  # constant definitions separate compare/select
                assert not re.search(r'\bset\w+\b', assembly), assembly


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_allocator_boundaries(compiler, tmp_path, release, target):
    sizes = {0, 1, 15, 16, 17, 262127, 262128, 262129, 300000}
    for power in range(5, 19):
        for block_size in (1 << power, 3 * (1 << (power - 1))):
            sizes.update(block_size + delta for delta in (-17, -16, -15))
    boundary_sizes = ', '.join(map(str, sorted(sizes)))
    source = tmp_path / 'allocator.jo'
    source.write_text(f"""@noinline
check_size = (n: int):
    p = __alloc(n)
    assert((p as int) & 15 == 0)
    assert(__alloc_size(p) >= n)
    loop i in [0..n):
        assert(p[i] == 0)
        p[i] = u8(i % 251 + 1)
    q = __grow_alloc(p, n, n + 17)
    assert((q as int) & 15 == 0 and __alloc_size(q) >= n + 17)
    loop i in [0..n): assert(q[i] == u8(i % 251 + 1))
    mem_set(q, 255, n + 17)
    __free(q)
    # A block reused from a free list must be zeroed just like fresh pages.
    z = __alloc(n + 17)
    loop i in [0..n + 17): assert(z[i] == 0)
    __free(z)
@cabi
ffi_alloc = (n: int) -> int:
    check_size(n)
    7
check_chunks = ():
    # Cross several fresh 4 MiB chunks while keeping previous buffers live.
    buffers: *u8[]
    loop k in [0..40):
        p = __alloc(200000)
        assert(p[0] == 0 and p[199999] == 0)
        p[0] = u8(k)
        p[199999] = u8(k + 1)
        buffers.push(p)
    loop k in [0..40):
        assert(buffers[k][0] == u8(k) and buffers[k][199999] == u8(k + 1))
        __free(buffers[k])
main = () -> int:
    warm = __alloc(1)
    __free(warm)
    before = alloc_count()
    loop n in [{boundary_sizes}]: check_size(n)
    assert(alloc_count() == before)
    check_chunks()
    assert(alloc_count() == before)
    # Calling a C-ABI entry switches allocator lookup to the stack-aware path.
    assert(ffi_alloc(33) == 7 and ffi_alloc(262129) == 7)
    assert(alloc_count() == before)
    0
""")
    binary = tmp_path / 'allocator'
    built = subprocess.run([compiler, 'build', source, '--target', target,
                            *(['--release'] if release else []), '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for allocator checks under WebAssembly')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'allocator.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stdout + ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_short_copy_bounds_and_live_values(compiler, tmp_path, release):
    guarded = platform.system() == 'Linux' and platform.machine().lower() in ('x86_64', 'amd64')
    setup = """    aa = syscall(9, 0, 12288, 3, 0x22, -1, 0)
    bb = syscall(9, 0, 12288, 3, 0x22, -1, 0)
    assert(aa > 0 and bb > 0)
    assert(syscall(10, aa, 4096, 0) == 0 and syscall(10, aa + 8192, 4096, 0) == 0)
    assert(syscall(10, bb, 4096, 0) == 0 and syscall(10, bb + 8192, 4096, 0) == 0)
    a = (aa + 4096) as *u8
    b = (bb + 4096) as *u8
""" if guarded else """    a = __alloc(4096)
    b = __alloc(4096)
"""
    cleanup = """    assert(syscall(11, aa, 12288) == 0 and syscall(11, bb, 12288) == 0)
""" if guarded else """    __free(a)
    __free(b)
"""
    params = ', '.join(f'x{i}: int' for i in range(12))
    total = ' + '.join(f'x{i}' for i in range(12))
    source = tmp_path / 'short-copy.jo'
    source.write_text(f"""@noinline
transfer = (to: *u8, from: *u8, n: int, {params}) -> int:
    mem_copy(to, from, n)
    {total}
main = () -> int:
{setup}    loop n in [0..129):
        loop side_a in [0..2):
            loop side_b in [0..2):
                ai = if side_a == 0: 0 else: 4096 - n
                bi = if side_b == 0: 0 else: 4096 - n
                mem_set(a, 60, 4096)
                mem_set(b, 165, 4096)
                loop i in [0..n): a[ai + i] = u8(i * 11 + 7)
                assert(transfer(b + bi, a + ai, n, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12) == 78)
                loop i in [0..4096):
                    expected = if i >= bi and i < bi + n: u8((i - bi) * 11 + 7) else: u8(165)
                    assert(b[i] == expected)
                    original = if i >= ai and i < ai + n: u8((i - ai) * 11 + 7) else: u8(60)
                    assert(a[i] == original)
{cleanup}    42
""")
    binary = tmp_path / 'short-copy'
    built = subprocess.run([compiler, 'build', source, *(['--release'] if release else []), '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=15)
    assert ran.returncode == 42, ran.stdout + ran.stderr


def lexer_span_helpers(compiler):
    directory = compiler.parent.parent / 'compiler'
    if not directory.exists():
        directory = Path(__file__).resolve().parents[1] / 'compiler'
    # Compile the actual lexer and its intern/token helpers in a small probe.
    # Diagnostics are stubbed; malformed-source integration tests use the compiler.
    fast = (directory / 'dewy_fast.jo').read_text(encoding='utf-8')
    util = (directory / 'util.jo').read_text(encoding='utf-8')
    parse = (directory / 'dewy_parse.jo').read_text(encoding='utf-8')
    tokens = (directory / 'dewy_tokens.jo').read_text(encoding='utf-8')
    lex = (directory / 'lex.jo').read_text(encoding='utf-8')
    return '\n'.join([
        lex[lex.index('lx_cls:'):lex.index('is_ident_start =')],
        util[util.index('struct SrcFile:'):util.index("# a file's name")],
        parse[parse.index('enum DewyKind:'):parse.index('dw_kind_name =')],
        tokens[tokens.index('enum DewyToken:'):],
        'mkpos = (file: int, off: int) -> int: (file << 40) | off\n'
        'fatal = (pos: int, message: str): panic(message)',
        fast[fast.index('struct DewyLexeme:'):fast.index('dn_peek =')],
    ])


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_lexer_bounded_spans(compiler, tmp_path, release):
    # Expected payloads and byte spans are independent of the lexer implementation.
    cases = [
        ('', 'ignored', []),
        ('>>=>', 'tail', [('op', '>>', 0, 2), ('op', '=>', 2, 4)]),
        ('>>=', '>tail', [('op', '>>=', 0, 3)]),
        ('notin', '?tail', [('identifier', 'notin', 0, 5)]),
        ('notin?', 'tail', [('op', 'notin?', 0, 6)]),
        ('isnt', '?tail', [('identifier', 'isnt', 0, 4)]),
        ('is?', 'tail', [('op', 'is?', 0, 3)]),
        ('0', 'xAF', [('source_integer', '0', 0, 1)]),
        ('0x2F', 'AB', [('integer', '0x:2F', 0, 4)]),
        ('0d12.5e+2', '34', [('source_real', '12.5e+2', 0, 9)]),
        ('12.', '3', [('source_integer', '12', 0, 2), ('op', '.', 2, 3)]),
        ('12e', '+3', [('source_integer', '12', 0, 2), ('identifier', 'e', 2, 3)]),
        ('r', '"tail"', [('identifier', 'r', 0, 1)]),
        ("r'a{b}'", 'tail', [('rawquoted', "r'a{b}'", 0, 7)]),
        ('"{x + 1}"', 'tail', [('quoted', '"{x + 1}"', 0, 9)]),
        ('λ2', 'π', [('identifier', 'λ2', 0, 3)]),
        ('$capture', 'name', [('metatag', 'capture', 0, 8)]),
        ('true false if', 'fy', [('boolean', 'true', 0, 4), ('boolean', 'false', 5, 10), ('identifier', 'if', 11, 13)]),
        ('a # trailing', '\nb', [('identifier', 'a', 0, 1)]),
        ('a # comment\nλ', 'x', [('identifier', 'a', 0, 1), ('identifier', 'λ', 12, 14)]),
    ]

    def quote(text):
        return json.dumps(text.replace('{', '{{').replace('}', '}}'), ensure_ascii=False)

    symbols = {'>>': 'shr', '=>': 'function', '>>=': 'shr_assign',
               'notin?': 'not_contains', 'is?': 'is_type', '.': 'dot', 'if': 'kw_if'}
    body = ['main = () -> int:', '    loop intern_names in [false, true]:']
    for text, suffix, expected in cases:
        raw = text.encode('utf-8')
        expected = [*expected, ('eof', '', len(raw), len(raw))]
        for prefix in ('', 'excluded:'):
            start = len(prefix.encode('utf-8'))
            stop = start + len(raw)
            full_text = quote(prefix + text + suffix)
            # Each case is scoped to avoid lexical binding interference.
            body += [
                '        if true:',
                f'            files = [SrcFile(path = "span.dewy", src = {full_text}, is_dewy = true)]',
                '            dn_file = 0',
                f'            ts = dn_lex(0, {start}, {stop}, intern_names)',
                f'            assert(ts.len() == {len(expected)})',
            ]
            previous_stop = 0
            for i, (kind, payload, begin, end) in enumerate(expected):
                gap = raw[previous_stop:begin]
                symbol = symbols.get(payload, 'none')
                spaced = str(bool(gap)).lower()
                newline = str(10 in gap).lower()
                body += [
                    f'            assert(ts[{i}].kind == DewyKind.{kind})',
                    f'            assert(ts[{i}].start == {start + begin} and ts[{i}].stop == {start + end})',
                    f'            assert(dn_payload(ts[{i}]) == {quote(payload)})',
                    f'            assert(ts[{i}].space == {spaced} and ts[{i}].newline == {newline})',
                    f'            assert(ts[{i}].symbol == DewyToken.{symbol})',
                ]
                previous_stop = end
    body += ['    42']
    source = tmp_path / 'lexer-spans.jo'
    source.write_text(lexer_span_helpers(compiler) + '\n' + '\n'.join(body) + '\n', encoding='utf-8')
    binary = tmp_path / 'lexer-spans'
    built = subprocess.run([compiler, 'build', source, *(['--release'] if release else []), '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('debug', [False, True], ids=['default', 'debug'])
@pytest.mark.parametrize('method', [False, True], ids=['fields', 'method'])
def test_core_parameter_view_frame(compiler, tmp_path, debug, method):
    source = tmp_path / 'parameter-frame.dewy'
    expression = 'row.read_score()' if method else 'row.values[0]+row.bias'
    source.write_text('''Row:type=[values:array<int64> bias:int64]
read_score=(row:Row):>int64=>row.values[0]+row.bias
parameter_frame_probe=(row:Row):>int64=>EXPRESSION
let callback=@parameter_frame_probe
main=()=>callback(Row[[20] 22])
'''.replace('EXPRESSION', expression))
    binary = tmp_path / 'parameter-frame'
    built = subprocess.run([compiler, 'build', source, '--ir', *(['-g'] if debug else []), '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_parameter_frame_probe_.*?(?=^fn |\Z)',
                      built.stdout + built.stderr, re.M | re.S)
    assert probe, 'parameter-view probe was not emitted'
    slots = re.findall(r'^  slot\d+:', probe[0], re.M)
    if debug:
        assert slots, 'debugger-visible parameter local lost its owned storage'
    else:
        assert not slots, f'read-only parameter still reserves dead frame storage:\n{probe[0]}'
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.core_quick
def test_core_repl_parameter_views(compiler, tmp_path):
    # Subsequent submissions lower checked functions again. A borrowed local
    # must bind to this lowering's parameter storage, while writes stay private.
    text = '''Row:type=[values:array<int64> bias:int64]
score=(row:Row):>int64=>row.values[0]+row.bias
let row=Row[[20] 22]
score(row)
let saved=row
row.values[0]=99
score(row)
score(saved)
copy=(row:Row):>Row=>{row.values[0]+=1 return row}
let next=copy(saved)
score(next)
score(saved)
:quit
'''
    # macOS commonly supplies a trailing slash; virtual-source lookup must
    # use the same normalized key as insertion. Exercise it on every host.
    env = {**os.environ, 'TMPDIR': str(tmp_path) + os.sep,
           'TMP': str(tmp_path) + os.sep, 'TEMP': str(tmp_path) + os.sep}
    ran = subprocess.run([compiler, 'repl'], input=text, cwd=tmp_path,
                         env=env, capture_output=True, text=True, timeout=20)
    assert ran.returncode == 0 and not ran.stderr, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['42', '121', '42', '43', '42']


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_fast_inline_failure_path(compiler, tmp_path, target):
    runner = shutil.which('node') if target == 'wasm' else None
    if target == 'wasm' and runner is None:
        pytest.skip('Node is needed to exercise the web failure path')
    source = tmp_path / 'checked-leaf.jo'
    source.write_text('''read = (values: int[], at: int) -> int: values[at]
wrapped_read = (values: int[], at: int, live: int) -> int: read(values, at) + live
@noinline
checked_leaf_probe = (values: int[], at: int, live: int) -> int: wrapped_read(values, at, live)
main = () -> int:
    at = if args().len() > 1: 1 else: 0
    checked_leaf_probe([20], at, 22)
''')
    binary = tmp_path / 'checked-leaf'
    built = subprocess.run([compiler, 'build', source, '--ir', '--target', target, '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_checked_leaf_probe_.*?(?=^fn |\Z)',
                      built.stdout + built.stderr, re.M | re.S)
    assert probe, 'bounds-checking caller was not emitted'
    assert ' = call ' not in probe[0], 'small checked helper was not inlined'
    assert re.search(r'\bcall .* c=1 ', probe[0]), 'inlining removed the failure path'
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        script = tmp_path / 'checked-leaf.cjs'
        script.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [runner, script]
    good = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert good.returncode == 42, good.stdout + good.stderr
    bad = subprocess.run([*command, 'outside'], capture_output=True, text=True, timeout=10)
    assert bad.returncode not in (0, 42), bad.stdout + bad.stderr
    assert 'out of bounds' in bad.stdout + bad.stderr, bad.stdout + bad.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_loop_endpoint_overflow(compiler, tmp_path, release, target):
    runner = shutil.which('node') if target == 'wasm' else None
    if target == 'wasm' and runner is None:
        pytest.skip('Node is needed to exercise web loop checks')
    source = tmp_path / 'loop-endpoints.jo'
    source.write_text('''@noinline
unsigned_limit = (a: int[], b: int[], stop: u64) -> int:
    total = 0
    loop i in [u64(0)..stop):
        total += a[int(i)] + b[int(i)]
        if i == 5: return total
    total
@noinline
positive_offset = (a: int[], b: int[], start: int, stop: int) -> int:
    total = 0
    loop i in [start..stop):
        total += a[i + 2] + b[i + 2]
        if i == start + 3: return total
    total
@noinline
negative_offset = (a: int[], b: int[], start: int, stop: int) -> int:
    total = 0
    loop i in [start..stop):
        total += a[i + (-1)] + b[i + (-1)]
        if i == start + 3: return total
    total
@noinline
unsigned_wrap = (a: int[], b: int[], start: u64, stop: u64) -> int:
    total = 0
    loop i in [start..stop): total += a[int(i + 3)] + b[int(i + 3)]
    total
@noinline
do_first = (a: int[], b: int[], start: int, stop: int) -> int:
    i = start
    total = 0
    loop true:
        total += a[i] + b[i]
        i += 1
        if i < stop: continue
        break
    total
@noinline
ordered_failure = (a: int[], b: int[], stop: u64) -> int:
    total = 0
    loop i in [u64(0)..stop):
        print("{i}:")
        total += a[int(i)]
        print("a:")
        total += b[int(i)]
        if i == 3: return total
    total
main = () -> int:
    case = args()[1]
    if case == "unsigned": return unsigned_limit([1], [2], u64(0xffffffffffffffff))
    if case == "high": return positive_offset([1, 2, 3], [4, 5, 6], 0, 9223372036854775807)
    if case == "low": return negative_offset([1], [2], -9223372036854775808, -9223372036854775804)
    if case == "negative-start": return positive_offset([10, 11], [10, 11], -2, 0)
    if case == "wrap": return unsigned_wrap([10, 11], [10, 11], u64(0xfffffffffffffffd), u64(0xffffffffffffffff))
    if case == "do-first": return do_first([1], [2], 1, 0)
    if case == "empty":
        a: int[]
        return 42 + unsigned_limit(a, a, u64(0)) + positive_offset(a, a, 5, 2)
    if case == "order": return ordered_failure([1, 2], [3], u64(0xffffffffffffffff))
    99
''')
    binary = tmp_path / 'loop-endpoints'
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        script = tmp_path / 'loop-endpoints.cjs'
        script.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [runner, script]
    for case in ('negative-start', 'wrap', 'empty'):
        ran = subprocess.run([*command, case], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 42, (case, ran.stdout, ran.stderr)
    for case, index in [('unsigned', '1'), ('high', '3'), ('low', '9223372036854775807'), ('do-first', '1'),
                        ('order', '1')]:
        ran = subprocess.run([*command, case], capture_output=True, text=True, timeout=10)
        assert ran.returncode not in (0, 42), (case, ran.stdout, ran.stderr)
        assert f'index {index} out of bounds' in ran.stdout + ran.stderr, (case, ran.stdout, ran.stderr)
        if case == 'order':
            assert (ran.stdout + ran.stderr).startswith('0:\na:\n1:\na:\n'), (ran.stdout, ran.stderr)


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_affine_loop_checks(compiler, tmp_path, release, target):
    runner = shutil.which('node') if target == 'wasm' else None
    if target == 'wasm' and runner is None:
        pytest.skip('Node is needed to exercise web loop checks')
    source = tmp_path / 'affine-checks.jo'
    source.write_text('''@noinline
shifted = (a: int[], b: int[], start: int, stop: int, offset: int) -> int:
    total = 0
    loop i in [start..stop):
        total += a[i + offset] + b[i + offset]
        if i == start + 3: return total
    total
@noinline
unsigned_shift = (a: int[], b: int[], start: u64, stop: u64, offset: u64) -> int:
    total = 0
    loop i in [start..stop):
        total += a[int(i + offset)] + b[int(i + offset)]
        if i == start + 3: return total
    total
@noinline
sum_offset = (a: int[], b: int[], start: int, stop: int, x: int, y: int) -> int:
    total = 0
    loop i in [start..stop): total += a[i + x + y] + b[i + x + y]
    total
@noinline
row_offset = (a: int[], b: int[], row: int, width: int, count: int) -> int:
    total = 0
    loop j in [0..count): total += a[(row - 1) * width + j] + b[(row - 1) * width + j]
    total
@noinline
invariant = (a: int[], b: int[], row: int, width: int, count: int) -> int:
    total = 0
    loop j in [0..count): total += a[row * width] + b[row * width] + j
    total
@noinline
ordered = (a: int[], b: int[], stop: int, offset: int) -> int:
    total = 0
    loop i in [0..stop):
        print("{i}:")
        total += a[i + offset]
        print("a:")
        total += b[i + offset]
    total
main = () -> int:
    case = args()[1]
    if case == "negative-start": return shifted([10, 11], [10, 11], -2, 0, 2)
    if case == "near-max": return shifted([10, 11], [10, 11], 9223372036854775805, 9223372036854775807, -9223372036854775805)
    if case == "sum-wrap": return sum_offset([10, 11], [10, 11], -9223372036854775808, -9223372036854775806, 9223372036854775807, 1)
    if case == "unsigned-wrap": return unsigned_shift([10, 11], [10, 11], u64(0xfffffffffffffffd), u64(0xffffffffffffffff), u64(3))
    if case == "row": return row_offset([0, 0, 0, 10, 11], [0, 0, 0, 10, 11], 2, 3, 2)
    if case == "invariant": return invariant([0, 21], [0, 21], 1, 1, 1)
    if case == "empty":
        a: int[]
        return 42 + shifted(a, a, 5, 2, 9) + unsigned_shift(a, a, u64(5), u64(2), u64(9))
    if case == "high": return shifted([1, 2, 3], [4, 5, 6], 0, 9223372036854775807, 2)
    if case == "low": return shifted([1], [2], -9223372036854775808, -9223372036854775804, -1)
    if case == "wide": return shifted([10, 11], [10, 11], -9223372036854775808, 9223372036854775807, -9223372036854775808)
    if case == "unsigned-gap": return unsigned_shift([1, 2, 3], [4, 5, 6], u64(0), u64(0xffffffffffffffff), u64(2))
    if case == "row-overflow": return row_offset([1], [2], 9223372036854775807, 2, 1)
    if case == "invariant-bad": return invariant([1], [2], 1, 1, 1)
    if case == "order": return ordered([1, 2], [3], 2, 0)
    99
''')
    binary = tmp_path / 'affine-checks'
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        script = tmp_path / 'affine-checks.cjs'
        script.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [runner, script]
    for case in ('negative-start', 'near-max', 'sum-wrap', 'unsigned-wrap', 'row', 'invariant', 'empty'):
        ran = subprocess.run([*command, case], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 42, (case, ran.stdout, ran.stderr)
    for case, index in [('high', '3'), ('low', '9223372036854775807'), ('wide', '2'),
                        ('unsigned-gap', '3'), ('row-overflow', '-4'), ('invariant-bad', '1'), ('order', '1')]:
        ran = subprocess.run([*command, case], capture_output=True, text=True, timeout=10)
        assert ran.returncode not in (0, 42), (case, ran.stdout, ran.stderr)
        assert f'index {index} out of bounds' in ran.stdout + ran.stderr, (case, ran.stdout, ran.stderr)
        if case == 'order':
            assert (ran.stdout + ran.stderr).startswith('0:\na:\n1:\na:\n'), (ran.stdout, ran.stderr)


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('float_type', ['f32', 'f64'])
def test_core_shifted_vector_loops(compiler, tmp_path, release, target, float_type):
    runner = shutil.which('node') if target == 'wasm' else None
    if target == 'wasm' and runner is None:
        pytest.skip('Node is needed to exercise web loop checks')
    source = tmp_path / 'shifted-vectors.jo'
    source.write_text('''@noinline
shifted_sum = (a: int[], b: int[], start: int, stop: int, offset: int) -> int:
    total = 0
    loop i in [start..stop): total += a[i + offset] + b[i + offset]
    total
@noinline
reverse_offset_sum = (a: int[], b: int[], start: int, stop: int, offset: int) -> int:
    total = 0
    loop i in [start..stop): total += a[i - offset] + b[i - offset]
    total
@noinline
commuted_sum = (a: int[], b: int[], start: int, stop: int, offset: int) -> int:
    total = 0
    loop i in [start..stop): total += a[offset + i] + b[offset + i]
    total
@noinline
unsigned_sum = (a: int[], b: int[], start: u64, stop: u64, offset: u64) -> int:
    total = 0
    loop i in [start..stop): total += a[int(i + offset)] + b[int(i + offset)]
    total
@noinline
shifted_copy = (dst: *f64, src: *f64, proof: f64[], start: int, stop: int, offset: int):
    loop i in [start..stop): dst[i + offset] = src[i + offset] + proof[i + offset]
@noinline
index_as_value = (a: int[], b: int[], stop: int, offset: int) -> int:
    total = 0
    loop i in [0..stop):
        index = i + offset
        total += a[index] + b[index] + index
    total
main = () -> int:
    if args().len() > 1:
        return shifted_sum([1, 2], [3, 4], 0, 8, 0)
    integers = [loop i in [0..24): i + 1]
    zeros = fill(0.0, 24)
    saved_avx = __cpu_avx2
    loop mode in [0..2):
        if mode == 1: __cpu_avx2 = false
        loop n in [0..18):
            assert(shifted_sum(integers, integers, -3, n - 3, 3) == n * (n + 1))
            assert(shifted_sum(integers, integers, 0, n, 3) == n * (n + 7))
            start = 9223372036854775807 - n
            assert(shifted_sum(integers, integers, start, 9223372036854775807, -start) == n * (n + 1))
            assert(reverse_offset_sum(integers, integers, start, 9223372036854775807, start) == n * (n + 1))
            assert(commuted_sum(integers, integers, -3, n - 3, 3) == n * (n + 1))
            ustop = u64(0xffffffffffffffff)
            assert(unsigned_sum(integers, integers, ustop - u64(n), ustop, u64(n + 1)) == n * (n + 1))
            assert(index_as_value(integers, integers, n, 3) == n * (n + 7) + n * (n + 5) / 2)
            values = [loop i in [0..24): f64(i + 1)]
            shifted_copy(&values[1], &values[0], zeros, 0, n, 3)
            loop i in [0..24):
                expected = if i >= 4 and i < n + 4: 4.0 else: f64(i + 1)
                assert(values[i] == expected)
            src = [loop i in [0..24): f64(i + 1)]
            dst = fill(-7.0, 24)
            shifted_copy(&dst[0], &src[0], zeros, start, 9223372036854775807, -start)
            loop i in [0..24): assert(dst[i] == (if i < n: f64(i + 1) else: -7.0))
    __cpu_avx2 = saved_avx
    42
'''.replace('f64', float_type)
        .replace('fill(0.0, 24)', f'fill({float_type}(0.0), 24)')
        .replace('fill(-7.0, 24)', f'fill({float_type}(-7.0), 24)'))
    binary = tmp_path / 'shifted-vectors'
    built = subprocess.run([compiler, 'build', source, '--ir', '--target', target, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    if target == 'native' and platform.machine().lower() in ('x86_64', 'amd64'):
        names = ['shifted_copy']
        if release:
            names += ['shifted_sum', 'unsigned_sum', 'reverse_offset_sum', 'commuted_sum']
        for name in names:
            probe = re.search(rf'^fn f_{name}_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
            assert probe and ' = vld ' in probe[0], f'{name}: shifted loop did not vectorize'
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        script = tmp_path / 'shifted-vectors.cjs'
        script.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [runner, script]
    good = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert good.returncode == 42, good.stdout + good.stderr
    bad = subprocess.run([*command, 'outside'], capture_output=True, text=True, timeout=10)
    assert bad.returncode not in (0, 42), bad.stdout + bad.stderr
    assert 'index 2 out of bounds' in bad.stdout + bad.stderr, bad.stdout + bad.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_masked_loop_bounds(compiler, tmp_path, release, target):
    runner = shutil.which('node') if target == 'wasm' else None
    if target == 'wasm' and runner is None:
        pytest.skip('Node is needed to exercise web loop checks')
    source = tmp_path / 'masked-bounds.jo'
    source.write_text('''@noinline
masked_bound_probe = (values: int[], start: int, stop: int) -> int:
    total = 0
    loop i in [start..stop): total += values[(i * 17 ^ 42) & 7]
    total
@noinline
unsigned_mask = (values: int[], start: u64, stop: u64) -> int:
    total = 0
    loop i in [start..stop): total += values[int(i & u64(5))]
    total
@noinline
negative_mask = (values: int[], start: int, stop: int) -> int:
    total = 0
    loop i in [start..stop): total += values[i & (-2)]
    total
@noinline
conditional_mask = (values: int[], seed: int, stop: int) -> int:
    total = 0
    at = seed
    loop i in [0..stop):
        if i > 0: at = i & 7
        total += values[at]
    total
@noinline
ordered_mask = (values: int[], stop: int) -> int:
    total = 0
    loop i in [0..stop):
        print("{i}:")
        total += values[i & 7]
    total
@noinline
shrinking_mask = (values: mut int[], stop: int) -> int:
    total = 0
    loop i in [0..stop):
        if i == 1: values.clear()
        total += values[i & 7]
    total
main = () -> int:
    mode = if args().len() > 1: args()[1] else: "ok"
    values = [3, 5, 7, 11, 13, 17, 19, 23]
    if mode == "negative": return negative_mask(values, -1, 2)
    if mode == "conditional": return conditional_mask(values, 8, 2)
    if mode == "ordered": return ordered_mask([20, 22], 4)
    if mode == "shrink": return shrinking_mask(values, 3)
    loop start in [-17, -9, -1, 0, 9, 9223372036854775780]:
        loop count in [0..18):
            expected = 0
            loop j in [0..count): expected += values[((start + j) * 17 ^ 42) & 7]
            assert(masked_bound_probe(values, start, start + count) == expected)
    loop count in [0..18):
        start = u64(18446744073709551590)
        expected = 0
        loop j in [0..count): expected += values[int((start + u64(j)) & u64(5))]
        assert(unsigned_mask(values, start, start + u64(count)) == expected)
    assert(masked_bound_probe([], 0, 0) == 0)
    assert(negative_mask([], 0, 0) == 0)
    assert(negative_mask(values, 1, 2) == 3)
    assert(conditional_mask(values, 7, 2) == 28)
    42
''')
    binary = tmp_path / 'masked-bounds'
    built = subprocess.run([compiler, 'build', source, '--ir', '--target', target, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_masked_bound_probe_.*?(?=^fn |\Z)',
                      built.stdout + built.stderr, re.M | re.S)
    assert probe, 'masked index probe was not emitted'
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        script = tmp_path / 'masked-bounds.cjs'
        script.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [runner, script]
    good = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert good.returncode == 42, good.stdout + good.stderr
    for case in ('negative', 'conditional', 'ordered', 'shrink'):
        bad = subprocess.run([*command, case], capture_output=True, text=True, timeout=10)
        assert bad.returncode not in (0, 42), (case, bad.stdout, bad.stderr)
        assert 'out of bounds' in bad.stdout + bad.stderr, (case, bad.stdout, bad.stderr)
        if case == 'ordered':
            assert bad.stdout.splitlines()[:3] == ['0:', '1:', '2:'], bad.stdout + bad.stderr
            assert '3:' not in bad.stdout.splitlines(), bad.stdout + bad.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_encoded_word_buffers(compiler, tmp_path, release):
    directory = compiler.parent.parent / 'compiler'
    if not directory.exists():
        directory = Path(__file__).resolve().parents[1] / 'compiler'
    writer = (directory / 'elf.jo').read_text()
    helpers = writer[writer.index('put16 ='):writer.index('# the machine')]
    source = tmp_path / 'encoded-words.jo'
    source.write_text(helpers + '''
main = () -> int:
    words = [0, 1, -1, 0x0123456789ABCDEF, 9223372036854775807, -9223372036854775807 - 1]
    loop prefix in [0..33):
        loop value in words:
            bytes = fill(u8(170), prefix)
            expected = bytes
            loop width in [2, 4, 8]:
                saved = bytes
                old = bytes.len()
                if width == 2: put16(bytes, value)
                else if width == 4: put32(bytes, value)
                else: put64(bytes, value)
                assert(saved.len() == old and saved == expected)
                loop i in [0..width): expected.push(u8((value >> (8 * i)) & 255))
                assert(bytes == expected)
            # Repeated growth with no retained snapshots, and an independent
            # byte-at-a-time oracle. Prefixes exercise every word alignment.
            loop i in [0..257):
                word = i * 7919 xor value
                put64(bytes, word)
                loop j in [0..8): expected.push(u8((word >> (8 * j)) & 255))
            assert(bytes == expected)
    42
''')
    binary = tmp_path / 'encoded-words'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('mode', ['default', 'release', 'debug'])
def test_core_branch_table_control_flow(compiler, tmp_path, mode):
    keys = [-(1 << 63), -100, *range(-5, 11), (1 << 63)-1]
    source = tmp_path / 'branch-tables.jo'
    source.write_text('''@noinline
dispatch_probe = (key: int, salt: int) -> int:
    total = 17
    loop round in [0..3):
        match key:
            -3: total += salt + round
            -2, 0: total = total xor (salt * 3 + round)
            1: total -= salt - round
            4, 5: total *= 2
            7:
                if round == 1: continue
                total += 7
            8: break
            _: total += 11
        total += 1
    match key:
        -3: total += salt
        -2: total -= salt
        0, 1: total = total xor salt
        4, 5, 7: total += salt * 2
        8: total *= salt
        _: total -= salt * 2
    total
main = ():
    loop key in [''' + ', '.join(map(str, keys)) + ''']:
        print(dispatch_probe(key, 7))
''')
    expected = []
    for key in keys:
        total = 17
        for iteration in range(3):
            if key == -3:
                total += 7 + iteration
            elif key in (-2, 0):
                total ^= 21 + iteration
            elif key == 1:
                total -= 7 - iteration
            elif key in (4, 5):
                total *= 2
            elif key == 7:
                if iteration == 1:
                    continue
                total += 7
            elif key == 8:
                break
            else:
                total += 11
            total += 1
        if key == -3:
            total += 7
        elif key == -2:
            total -= 7
        elif key in (0, 1):
            total ^= 7
        elif key in (4, 5, 7):
            total += 14
        elif key == 8:
            total *= 7
        else:
            total -= 14
        expected.append(str(total))
    binary = tmp_path / 'branch-tables'
    flags = {'default': [], 'release': ['--release'], 'debug': ['-g']}[mode]
    built = subprocess.run([compiler, 'build', source, '--ir', *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_dispatch_probe_.*?(?=^fn |\Z)',
                      built.stdout + built.stderr, re.M | re.S)
    assert probe and probe[0].count('brtable') >= 2, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_integer_extension_boundaries(compiler, tmp_path, release, target):
    runner = shutil.which('node') if target == 'wasm' else None
    if target == 'wasm' and runner is None:
        pytest.skip('Node is needed to exercise web integer conversions')
    values = [-(1 << 63), -4294967297, -2147483649, -65537, -32769,
              -257, -129, -1, 0, 1, 127, 128, 255, 256, 32767, 32768,
              65535, 65536, 2147483647, 2147483648, 4294967295, (1 << 63)-1]
    types = [(sign + str(bits), bits, sign == 'i')
             for bits in (8, 16, 32, 64) for sign in ('i', 'u')]

    def converted(value, bits, signed):
        value %= 1 << bits
        return value - (1 << bits) if signed and value >= 1 << (bits-1) else value

    definitions, calls, expected = [], [], []
    for src, src_bits, src_signed in types:
        for dst, dst_bits, dst_signed in types:
            # A loaded narrow value, a repeated cast, and a changing local all
            # exercise normalization; unsigned-to-signed at equal width must
            # still truncate/sign-extend, even when the load was unsigned.
            name = f'convert_{src}_{dst}'
            definitions.append(f'@noinline\n{name} = (p: *{src}) -> int:\n'
                               f'    x = p[0]\n    int({dst}({src}(x)))\n')
            calls.append(f'        print({name}((&value) as *{src}))')
    # Runtime order is value, source type, destination type.
    for value in values:
        for _, src_bits, src_signed in types:
            for _, dst_bits, dst_signed in types:
                x = converted(value, src_bits, src_signed)
                x = converted(x, dst_bits, dst_signed)
                expected.append(str(converted(x, 64, True)))
    source = tmp_path / 'integer-extensions.jo'
    source.write_text('\n'.join(definitions) +
                      'main = ():\n    loop value in [' + ', '.join(map(str, values)) + ']:\n' +
                      '\n'.join(calls) + '\n')
    binary = tmp_path / 'integer-extensions'
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        script = tmp_path / 'integer-extensions.cjs'
        script.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [runner, script]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.core_quick
@pytest.mark.parametrize('mode', ['default', 'release', 'debug'])
def test_core_immediate_store_widths(compiler, tmp_path, mode):
    source = tmp_path / 'immediate-stores.jo'
    source.write_text('''g_before: int = 123456789
g8: u8 = 17
g16: u16 = 18
g32: u32 = 19
g64: int = 20
g_bool: bool = false
g_after: int = 987654321
@noinline
write_globals = ():
    g8 = u8(255)
    g16 = u16(48879)
    g32 = u32(305419896)
    g64 = -2147483648
    g_bool = true
@noinline
write_bytes = (p: *u8, at: int):
    p[at] = u8(255)
    ((p + at + 1) as *u16)[0] = u16(48879)
    ((p + at + 3) as *u32)[0] = u32(305419896)
    ((p + at + 7) as *int)[0] = -2147483648
    ((p + at + 15) as *int)[0] = 2147483647
    ((p + at + 23) as *u64)[0] = u64(4294967295)
main = ():
    write_globals()
    print("{g_before} {g8} {g16} {g32} {g64} {g_bool} {g_after}")
    loop at in [0, 1, 7]:
        bytes = fill(u8(165), 40)
        write_bytes(bytes.data(), at)
        loop x in bytes: print(int(x))
''')
    binary = tmp_path / 'immediate-stores'
    flags = {'default': [], 'release': ['--release'], 'debug': ['-g']}[mode]
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    expected = ['123456789 255 48879 305419896 -2147483648 true 987654321']
    payload = (bytes([255]) + (48879).to_bytes(2, 'little') +
               (305419896).to_bytes(4, 'little') +
               (-2147483648).to_bytes(8, 'little', signed=True) +
               (2147483647).to_bytes(8, 'little') +
               (4294967295).to_bytes(8, 'little'))
    for at in (0, 1, 7):
        expected.extend(map(str, bytes([165])*at + payload + bytes([165])*(40-at-len(payload))))
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.core_quick
@pytest.mark.parametrize('mode', ['default', 'release', 'debug'])
def test_core_mixed_parameter_prologues(compiler, tmp_path, mode):
    definitions = ['@noinline\ntouch = (x: int) -> int: x * 3 + 1\n']
    calls, probes = [], []
    for ni, nf in [(0, 0), (1, 0), (0, 1), (6, 0), (7, 0), (0, 8),
                   (0, 9), (6, 8), (7, 9), (10, 12)]:
        for sparse in (False, True):
            name = f'probe_{ni}_{nf}_{int(sparse)}'
            params, values, arguments = [], [], []
            for i in range(max(ni, nf)):
                if i < ni:
                    params.append((f'i{i}', 'int'))
                    values.append(('int', (i + 1) * 13))
                    arguments.append(f'seed + {(i + 1) * 13}')
                if i < nf:
                    params.append((f'f{i}', 'f64'))
                    values.append(('float', (i + 1) / 2))
                    arguments.append(f'f64(seed) + {(i + 1) / 2}')
            used = [i for i in range(len(params)) if not sparse or i % 3 == 0]
            terms = [f'{2 * (i + 1)} * f64({params[i][0]})' for i in used]
            left = ' + '.join(reversed(terms)) or '0.0'
            right = ' + '.join(terms) or '0.0'
            first = f'int({params[used[0]][0]})' if used else '7'
            signature = ', '.join(f'{name}: {kind}' for name, kind in params)
            # Keep parameters live across a call, with both dense and sparse
            # uses. This exercises incoming register moves, spills, stack
            # arguments and restoration before the function body is emitted.
            definitions.append(f'@noinline\n{name} = ({signature}) -> int:\n'
                               f'    before = {left}\n    middle = touch({first})\n'
                               f'    after = {right}\n    int(before + after) + middle\n')
            calls.append(f'    print({name}({", ".join(arguments)}))')
            probes.append((values, used))
    source = tmp_path / 'parameter-prologues.jo'
    source.write_text('\n'.join(definitions) + 'main = ():\n    seed = args().len()\n' +
                      '\n'.join(calls) + '\n')
    binary = tmp_path / 'parameter-prologues'
    flags = {'default': [], 'release': ['--release'], 'debug': ['-g']}[mode]
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    for extra in ([], ['one', 'two']):
        seed = 1 + len(extra)
        expected = []
        for values, used in probes:
            total = sum(2 * (i + 1) * (seed + values[i][1]) for i in used)
            first = int(seed + values[used[0]][1]) if used else 7
            expected.append(str(int(2 * total) + 3 * first + 1))
        ran = subprocess.run([binary, *extra], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_text_case_bytes(compiler, tmp_path, release, target):
    # Python supplies the expected text for the existing simple-case repertoire.
    # Include every ASCII byte, word-load/tail boundaries, and retained aliases.
    pairs = []
    for size in [*range(34), 63, 64, 65, 255, 256, 257, 4095, 4096, 4097]:
        text = (''.join(map(chr, range(128))) * 33)[:size]
        pairs.append((text.encode(), text.upper().encode(), text.lower().encode()))
    for offset in range(16):
        for tail in ('é', 'ÿ', 'Ÿ', 'Ω', 'Я', 'Ё', '漢', '🙂', 'é'):
            text = 'aZ_ ' * offset + tail + ' azAZ09'
            pairs.append((text.encode(), text.upper().encode(), text.lower().encode()))
    text = 'café déjà vu ÄÖÜ ÿŸ Ąą Ćć Ωω Яя Ёё 漢字🙂'
    pairs.append((text.encode(), text.upper().encode(), text.lower().encode()))
    # Malformed UTF-8 is a byte-preserving transformation, not an implicit repair.
    # These sequences contain no valid two-byte letters to map.
    for raw in [bytes(range(256)), bytes(reversed(range(256))),
                b'a\xc2', b'Z\xdf', b'\xc0\x80a', b'\xc1\xbfZ',
                b'\xe0\x80\x80Az', b'\xffa\x80Z', b'\xf0\x80A\x80']:
        pairs.append((raw, raw.upper(), raw.lower()))
    arrays = [f'[{" ".join("0x\"" + row[k].hex() + "\"" for row in pairs)}]'
              for k in range(3)]
    source = tmp_path / 'case-bytes.dewy'
    source.write_text('''main=()=>{
let inputs:array<array<uint8>>=INPUTS
let uppers:array<array<uint8>>=UPPERS
let lowers:array<array<uint8>>=LOWERS
loop i in [0..inputs.length) {
    let text=str_from_bytes(inputs[i])
    let saved=text
    let hi=upper(text)
    let lo=lower(text)
    if bytes(hi) not=? uppers[i] return 1
    if bytes(lo) not=? lowers[i] return 2
    if bytes(text) not=? inputs[i] or saved not=? text return 3
}
return 42
}
'''.replace('INPUTS', arrays[0]).replace('UPPERS', arrays[1]).replace('LOWERS', arrays[2]))
    binary = tmp_path / 'case-bytes'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', target]
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'case-bytes.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = ['node', runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_text_case_guard_page(compiler, tmp_path, release):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        pytest.skip('guard-page probe uses Linux x86-64 memory syscalls')
    source = tmp_path / 'case-guard.jo'
    source.write_text('''main = () -> int:
    page = __os_raw_pages(8192)
    assert(syscall(10, page + 4096, 4096, 0) == 0)
    loop n in [0..65):
        p = page + 4096 - n - 24
        h = p as *int
        h[0] = -1
        h[1] = n
        h[2] = n
        loop tail in [0..4):
            loop i in [0..n): p[24 + i] = u8(97 + i % 26)
            if n > 0 and tail == 1: p[24 + n - 1] = u8(0xC2)
            if n > 0 and tail == 2: p[24 + n - 1] = u8(0xDF)
            if n > 1 and tail == 3:
                p[24 + n - 2] = u8(0xC3)
                p[24 + n - 1] = u8(0xA9)
            text = p as str
            hi = upper(text)
            lo = lower(text)
            assert(len(hi) == n and len(lo) == n)
            loop i in [0..n):
                c = p[24 + i]
                expected = c
                if c >= 'a' and c <= 'z': expected = c - 32
                if tail == 3 and n > 1 and i == n - 1: expected = u8(0x89)
                assert(hi[i] == expected and lo[i] == c and text[i] == c)
    __os_raw_free(page, 8192)
    42
''')
    binary = tmp_path / 'case-guard'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_swap_checked_helper_inlines(compiler, tmp_path, target):
    source = tmp_path / 'swap-inline.jo'
    source.write_text('''@noinline
swap_probe = (values: mut int[], count: int):
    loop i in [0..count): values.swap(i & 1, (i + 1) & 1)
main = () -> int:
    values = [20, 22]
    saved = values
    swap_probe(values, 3)
    if values != [22, 20] or saved != [20, 22]: return 1
    42
''')
    binary = tmp_path / 'swap-inline'
    built = subprocess.run([compiler, 'build', source, '--release', '--ir', '--target', target,
                            '-o', binary], capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_swap_probe_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    assert probe, 'swap loop was not emitted'
    calls = [line for line in probe[0].splitlines() if 'call a=' in line]
    assert calls and all(' c=0 ' not in line for line in calls), probe[0]
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web checked-helper checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'swap-inline.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_integer_parse_boundaries(compiler, tmp_path, target, release):
    rng = random.Random(9217)
    texts = ['', '+', '-', '_', '__', '+_', '-_', '0', '-0', '+0',
             '999999999999999999', '-999999999999999999',
             '9223372036854775807', '-9223372036854775808',
             '9223372036854775808', '-9223372036854775809',
             '0x7fffffffffffffff', '-0X8000000000000000', '0x8000000000000000',
             '0x', '-0x', '0x_', '0b10', '0o10', '1.0', '1e3', '1 2', '1\x002',
             '  \t-42\r\n', '\v42', '42\f', '\u00a042', '１２', '🙂',
             '_1_', '0_x10', '0x_f_f_', '+0x2a', '--1', '+-1', '1-',
             '0' * 80, '0' * 80 + '42', '9' * 80]
    for _ in range(160):
        value = rng.randrange(-(1 << 66), 1 << 66)
        token = str(value) if rng.randrange(2) else ('-' if value < 0 else '+') + hex(abs(value))
        texts.append(token)
        texts.append(' \t' + token + '\r\n')
    def expected(text):
        token = text.strip(' \t\r\n')
        negative = token.startswith('-')
        if token[:1] in ('+', '-'):
            token = token[1:]
        base = 16 if token[:2].lower() == '0x' else 10
        if base == 16:
            token = token[2:]
        token = token.replace('_', '')
        pattern = '[0-9a-fA-F]+' if base == 16 else '[0-9]+'
        if not re.fullmatch(pattern, token):
            return None
        value = int(token, base) * (-1 if negative else 1)
        return value if -(1 << 63) <= value < (1 << 63) else None
    answers = [expected(text) for text in texts]
    literals = ' '.join(json.dumps(text, ensure_ascii=False) for text in texts)
    results = ' '.join('none' if value is None else str(value) for value in answers)
    source = tmp_path / 'integers.dewy'
    source.write_text(f'''main=()=>{{
let texts=[{literals}]
let expected:array<int64?>=[{results}]
loop i in [0..texts.length) {{
    if to_int(texts[i]) not=?expected[i] {{printl"case {{i}}" return 1}}
}}
return 42
}}
''')
    binary = tmp_path / 'integers'
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web integer parsing checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'integers.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.core_quick
@pytest.mark.parametrize('target,flags', [
    ('native', []), ('native', ['--release']), ('native', ['-g']),
    ('wasm', []), ('wasm', ['--release']),
])
@pytest.mark.parametrize('failure', ['none', 'direct', 'callback', 'multiple', 'assert'])
def test_core_terminal_message_calls(compiler, tmp_path, target, flags, failure):
    terminal = {
        'none': 'panic(message(a))',
        'direct': 'panic(message(a))',
        'callback': 'panic(callback(a))',
        'multiple': 'panic("{message(a)}:{message(x)}")',
        'assert': 'assert(x >= 0, message(a))',
    }[failure]
    argument = 10 if failure == 'none' else -10
    source = tmp_path / 'terminal.jo'
    source.write_text('''@noinline
message = (x: int) -> str:
    print("message {x}")
    "value={x}"
@noinline
probe = (x: int, callback: (int) -> str) -> int:
    a = x * 3 + 7
    b = f64(x) * 2.5
    if x < 0:
        ''' + terminal + '''
    a + x + int(b)
main = () -> int:
    if probe(10, message) != 72: return 1
    if probe(20, message) != 137: return 2
    if probe(''' + str(argument) + ''', message) != 72: return 3
    42
''')
    binary = tmp_path / 'terminal'
    built = subprocess.run([compiler, 'build', source, '-o', binary, '--target', target, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web terminal-call checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'terminal.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    if failure == 'none':
        assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
        assert ran.stdout == ''
    else:
        assert ran.returncode not in (0, 1, 2, 3, 42), (ran.returncode, ran.stdout, ran.stderr)
        messages = [line for line in ran.stdout.splitlines() if line.startswith('message ')]
        assert messages == (['message -23', 'message -10'] if failure == 'multiple' else ['message -23'])
        assert ('value=-23:value=-10' if failure == 'multiple' else 'value=-23') in ran.stdout + ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_grapheme_length_blocks(compiler, tmp_path, release, target):
    # Independent counts exercise each possible ASCII byte around word edges,
    # CR/LF, and Unicode that can extend the last cluster of an ASCII prefix.
    cases = []
    sizes = [*range(34), 63, 64, 65, 127, 128, 129]
    for n in sizes:
        prefix = b'a' * n
        for byte in range(128):
            data = prefix + bytes([byte]) + b'\nend'
            cases.append((data, len(data) - data.count(b'\r\n')))
        for suffix, extra in [('é', 1), ('👩‍👩‍👧‍👦', 1), ('🇺🇸🇨', 2),
                              ('क्ष', 1), ('\r\n', 1), ('\r\n\u0301', 2),
                              ('\u0301', int(n == 0)), ('\u0301\u0308', int(n == 0)),
                              ('\u200d', int(n == 0))]:
            cases.append((prefix + suffix.encode(), n + extra))
        cases.append((b'a\r\n' * n + '\u0301'.encode(), 2*n + 1))
        cases.append((prefix, n))
    (tmp_path / 'counts.bin').write_bytes(b''.join(struct.pack('<II', len(s), count) + s
                                                 for s, count in cases))
    source = tmp_path / 'counts.jo'
    source.write_text('''main = () -> int:
    cases = embed("counts.bin")
    at = 0
    loop at < cases.len():
        size = __grapheme_word(cases, at)
        expected = __grapheme_word(cases, at + 4)
        at += 8
        text = str_from_bytes(cases[at..at + size))
        assert(__dewy_string_length(text) == expected)
        at += size
    42
''')
    binary = tmp_path / 'counts'
    flags = ['--release'] if release else []
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web conformance')
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('prefix', [0, 7, 8, 15, 16, 31, 32, 65])
def test_core_grapheme_length_invalid_tail(compiler, tmp_path, prefix):
    source = tmp_path / 'invalid.dewy'
    source.write_text('main=()=>{let text=str_from_bytes([' + '97 '*prefix +
                      '226 130]) return text.length}\n')
    binary = tmp_path / 'invalid'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode != 0 and 'invalid UTF-8 in grapheme operation' in ran.stderr, ran.stdout + ran.stderr


@pytest.mark.core_quick
def test_core_grapheme_pages_reproducible():
    from tools.compiler.unicode_pages import DIRECTORY, pack
    assert pack() == (DIRECTORY / 'grapheme_pages.bin').read_bytes()


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_grapheme_property_pages(compiler, tmp_path, release, target):
    from bisect import bisect_right
    directory = Path(__file__).resolve().parents[1] / 'lib/std/unicode'
    tables = [list(struct.iter_unpack('<IIB', (directory / name).read_bytes()))
              for name in ('grapheme_break.bin', 'indic_conjunct_break.bin',
                           'extended_pictographic.bin')]
    starts = [[row[0] for row in table] for table in tables]
    points = {-1, 0x110000}
    for page in range(0, 0x110001, 256):
        points.update((page-1, page, page+1))
    for table in tables:
        for start, end, _ in table:
            points.update((start-1, start, end, end+1))
    rng = random.Random(1600)
    points.update(rng.randrange(0x110000) for _ in range(4096))

    def expected(scalar):
        properties = []
        for table, keys in zip(tables, starts):
            index = bisect_right(keys, scalar) - 1
            properties.append(table[index][2] if index >= 0 and scalar <= table[index][1] else 0)
        return properties[0] | properties[1] << 4 | properties[2] << 6

    (tmp_path / 'properties.bin').write_bytes(b''.join(struct.pack('<iI', p, expected(p))
                                                     for p in sorted(points)))
    source = tmp_path / 'properties.jo'
    source.write_text('''main = () -> int:
    cases = embed("properties.bin")
    loop row in [0..cases.len() / 8):
        at = row * 8
        scalar = int(__grapheme_word(cases, at) as i32)
        expected = __grapheme_word(cases, at + 4)
        assert(__grapheme_property_bits(scalar) == expected)
    42
''')
    binary = tmp_path / 'properties'
    flags = ['--release'] if release else []
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web conformance')
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.core_quick
def test_core_grapheme_lookup_borrows_table(compiler, tmp_path):
    source = tmp_path / 'lookup.jo'
    source.write_text('main = () -> int: __grapheme_property_bits(0x301)\n')
    binary = tmp_path / 'lookup'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    functions = re.findall(r'^fn f___grapheme_(?:property_bits|page_lookup)_[^\n]*\n.*?(?=^fn |\Z)',
                           built.stdout + built.stderr, re.M | re.S)
    assert functions, 'grapheme table lookup was not emitted'
    # CALL_IF_SHARED would clone the embedded table for data() on a mutable
    # local. The lookup must borrow its bytes regardless of table size.
    assert not any(re.search(r'\bcall .*\bc=3\b', fn) for fn in functions), '\n'.join(functions)


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_fixed_index_unsigned_domain(compiler, tmp_path, release, target):
    source = tmp_path / 'domains.dewy'
    source.write_text('''read8=(table:array<uint8 length=256> index:uint8)=>(table[index] as int64)
read16=(table:array<uint8 length=65536> index:uint16)=>(table[index] as int64)
read_widen=(table:array<uint8 length=256> index:uint8)=>(table[(index as int16) as int64] as int64)
read_wrap=(table:array<uint8 length=256> index:int16)=>(table[index as uint8] as int64)
main=()=>{
 let small:array<uint8 length=256>=[]
 loop i in [0..256) {small[i]=i as uint8}
 let large:array<uint8 length=65536>=[]
 loop i in [int64(0)..65536) {large[i]=i as uint8}
 loop i in [0..256) {if read8(small i as uint8) not=? i return 1
 if read_widen(small i as uint8) not=? i return 2}
 loop i in [int64(0)..65536) {if read16(large i as uint16) not=? ((i as uint8) as int64) return 3}
 if read_wrap(small -1) not=? 255 return 4
 return 42
}
''')
    binary = tmp_path / 'domains'
    flags = ['--release'] if release else []
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web fixed-index checks')
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('size,ty,index,value', [
    (255, 'uint8', 'index', '255'),
    (65535, 'uint16', 'index', '65535'),
    (256, 'uint16', '(index as int8) as int64', '255'),
    (256, 'int8', '(index as int16) as int64', '-1'),
])
def test_core_fixed_index_domain_keeps_checks(compiler, tmp_path, release, size, ty, index, value):
    source = tmp_path / 'bounds.dewy'
    source.write_text(f'''read=(table:array<uint8 length={size}> index:{ty})=>(table[{index}] as int64)
main=()=>{{let table:array<uint8 length={size}>=[] return read(table {value})}}
''')
    binary = tmp_path / 'bounds'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode != 0 and 'out of bounds' in ran.stderr, ran.stdout + ran.stderr


@pytest.mark.core_quick
def test_core_fixed_index_domain_ir(compiler, tmp_path):
    source = tmp_path / 'lookup.jo'
    source.write_text('''@noinline
read = (table: u8[65536], index: u16) -> int: int(table[index])
main = () -> int:
    table: u8[65536]
    read(table, 65535)
''')
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', tmp_path / 'lookup'],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    functions = re.findall(r'^fn f_read_[0-9]+[^\n]*\n.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    assert len(functions) == 1, built.stdout + built.stderr
    assert ' = load ' in functions[0] and 'call ' not in functions[0], functions[0]


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']], ids=['default', 'release', 'debug'])
def test_core_cold_array_calls_preserve_live_values(compiler, tmp_path, flags):
    # Growth and shared-array detachment must preserve both integer and floating
    # values assigned to caller-saved registers, including on repeated slow paths.
    import math
    inputs = [-9, 0, 1, 2, 7, 31, 127, 257, 65535]
    expected = []
    for n in inputs:
        integer = (n + 11) + (n * 3 + 7) * 3 + (n ^ 19) * 5 + (n - 5) * 7 + (n * 17 + 3) * 11 + (n * n + 1) * 13
        floating = (n + .25) * 3 + (n * .5 + .5) * 5 + (n * .25 + .75) * 7 + (n * 1.5 + .125) * 11
        expected.append(integer + math.trunc(floating))
    source = tmp_path / 'cold-values.jo'
    source.write_text('''@noinline
push_probe = (xs: mut int[], n: int) -> int:
    a = n + 11
    b = n * 3 + 7
    c = n xor 19
    d = n - 5
    e = n * 17 + 3
    f = n * n + 1
    p = f64(n) + 0.25
    q = f64(n) * 0.5 + 0.5
    r = f64(n) * 0.25 + 0.75
    s = f64(n) * 1.5 + 0.125
    xs.push(n)
    a + b * 3 + c * 5 + d * 7 + e * 11 + f * 13 + int(p * 3 + q * 5 + r * 7 + s * 11)
main = () -> int:
    inputs: int[] = INPUTS
    expected: int[] = EXPECTED
    xs: int[]
    loop i in [0..inputs.len()):
        snapshot = xs
        if push_probe(xs, inputs[i]) != expected[i]: return 1
        if snapshot.len() != i or xs.len() != i + 1: return 2
        if xs[i] != inputs[i]: return 3
        loop j in [0..i):
            if snapshot[j] != inputs[j]: return 4
    42
'''.replace('INPUTS', repr(inputs)).replace('EXPECTED', repr(expected)))
    binary = tmp_path / 'cold-values'
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']], ids=['default', 'release', 'debug'])
def test_core_entry_guard_argument_and_return_conventions(compiler, tmp_path, flags):
    source = tmp_path / 'entry-guard.jo'
    source.write_text('''ticks = 0
@noinline
void_probe = (n: int):
    if n == 0: return
    ticks += n
    void_probe(n - 1)
@noinline
constant_probe = (n: int) -> int:
    if n == 0: return 4294967297
    100 + n
@noinline
nonzero_probe = (n: int) -> int:
    if n != 0: return -73
    n + 9
@noinline
mixed_probe = (a: f64, b: int, c: f32, d: int, e: int, f: int, g: int, h: int) -> int:
    if h == 0: return -91
    int(a) + b + int(c) + d + e + f + g + h
@noinline
stack_probe = (a: int, b: int, c: int, d: int, e: int, f: int, g: int) -> int:
    if g == 0: return -19
    a + b + c + d + e + f + g
@noinline
float_probe = (n: int) -> f64:
    if n == 0: return 1.5
    f64(n) + 0.25
main = () -> int:
    void_probe(0)
    if ticks != 0: return 1
    void_probe(3)
    if ticks != 6: return 2
    if constant_probe(0) != 4294967297 or constant_probe(2) != 102: return 3
    if nonzero_probe(-3) != -73 or nonzero_probe(0) != 9: return 4
    if mixed_probe(1.25, 2, 3.5, 4, 5, 6, 7, 0) != -91: return 5
    if mixed_probe(1.25, 2, 3.5, 4, 5, 6, 7, 8) != 36: return 6
    if stack_probe(1, 2, 3, 4, 5, 6, 0) != -19: return 7
    if stack_probe(1, 2, 3, 4, 5, 6, 7) != 28: return 8
    if float_probe(0) != 1.5 or float_probe(3) != 3.25: return 9
    42
''')
    binary = tmp_path / 'entry-guard'
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.core_quick
@pytest.mark.parametrize('target,flags,threads', [
    ('native', [], 1), ('native', ['--release'], 1), ('native', ['-g'], 1),
    ('native', ['--release'], 2), ('wasm', [], 1), ('wasm', ['--release'], 1),
])
def test_core_matrix_product_tiles(compiler, tmp_path, target, flags, threads):
    source = tmp_path / 'products.dewy'
    source.write_text('''main=()=>{
loop dims in [[0 3 2] [2 0 3] [3 7 5] [9 65 513] [3 64 512] [2 66 515]] {
    let r=dims[0] let m=dims[1] let p=dims[2]
    let a=reshape([loop i in [0..r*m) ((i%17)-8) as float64] r m)
    let b=reshape([loop i in [0..m*p) ((i%13)-6) as float64] m p)
    let saved_a=a let saved_b=b
    let c=a*b
    assert(c.shape =? [r p])
    loop i in [0..r) {loop j in [0..p) {
        let want=0.0
        loop k in [0..m) {want+=a[i k]*b[k j]}
        assert(c[i j] =? want)
    }}
    assert(a.data =? saved_a.data and b.data =? saved_b.data)
}
let ints=reshape([loop i in [0..2*65) (i%19)-9] 2 65)
let ones=reshape([loop i in [0..65*3) 1] 65 3)
let product=ints*ones
loop i in [0..2) {loop j in [0..3) {assert(product[i j] =? sum(row(ints i)))}}
let cancellation=reshape([1e16 1.0 (-1e16) 1.0 3.0] 1 5)*reshape([1.0 1.0 1.0 1.0 1.0] 5 1)
assert(cancellation[0 0] =? 4.0)
let zero=reshape([0.0 (-0.0) 0.0 0.0 0.0] 1 5)
let nonfinite=reshape([INF NAN INF NAN INF] 5 1)
assert((zero*nonfinite)[0 0] =? 0.0)
return 42
}
''')
    binary = tmp_path / 'products'
    built = subprocess.run([compiler, 'build', source, '--target', target,
                            '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web matrix checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'products.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, env={**os.environ, 'SLOPPY_THREADS': str(threads)},
                         capture_output=True, text=True, timeout=15)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_array_byte_count_boundaries(compiler, tmp_path, target, release):
    limit = ((1 << 32) - 1 if target == 'wasm' else (1 << 63) - 1) - 65535 - 16 - 24
    pairs = [(0, 0), ((1 << 63) - 1, 0), (0, (1 << 63) - 1)]
    for size in [1, 2, 3, 8, 40, 65535, 65536, (1 << 31) - 1, 1 << 31]:
        pairs.extend((cap, size) for cap in {0, 1, limit // size, max(0, limit // size - 1)})
    rng = random.Random(30417)
    for _ in range(80):
        size = rng.randrange(1, 1 << 20)
        pairs.append((rng.randrange(limit // size + 1), size))
    rows = ','.join(f'({cap}, {size}, {24 + cap * size})' for cap, size in pairs)
    source = tmp_path / 'byte-count.jo'
    source.write_text(f'''@noinline
checked = (cap: int, size: int) -> int: __arr_bytes(cap, size)
main = () -> int:
    cases = [{rows}]
    loop item in cases: assert(checked(item.0, item.1) == item.2)
    42
''')
    binary = tmp_path / 'byte-count'
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web byte-count checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'byte-count.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.core_quick
def test_core_element_view_call_ir(compiler, tmp_path):
    source = tmp_path / 'element-view.jo'
    source.write_text('''struct Row:
    values: int[]
    bias: int
@noinline
read_row = (r: Row) -> int: r.values[0] + r.bias
@noinline
view_probe = (rows: Row[]) -> int:
    total = 0
    loop i in [0..rows.len()):
        r = rows[i]
        total += read_row(r)
    total
main = () -> int: view_probe([Row([20], 22)])
''')
    binary = tmp_path / 'element-view'
    built = subprocess.run([compiler, 'build', source, '--release', '--ir', '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_view_probe_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    assert probe, 'element-view probe was not emitted'
    # Keep read_row, without retain/drop calls or copying the stable element.
    assert len(re.findall(r'\bcall a=', probe[0])) == 1, probe[0]
    assert not re.search(r'\b(?:store|copy) a=', probe[0]), probe[0]
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('target,flags', [('native', []), ('native', ['--release']), ('native', ['-g']),
                                         ('wasm', []), ('wasm', ['--release'])])
def test_core_nonreturning_helper_calls(compiler, tmp_path, target, flags):
    source = tmp_path / 'nonreturning.jo'
    source.write_text('''fail_limit = (value: int): panic("custom limit {value}")
@noinline
checked_probe = (value: int, limit: int) -> int:
    if value >= limit: fail_limit(value)
    value * 2
# A nonreturning call with mutable arguments must leave lowering's copy-back
# bookkeeping balanced when compiling the other branch and following calls.
values = [20]
fail_mut = (xs: mut int[], marker: int):
    xs.push(marker)
    fail_limit(xs[1])
@noinline
change_values = (xs: mut int[]): xs[0] += 1
main = () -> int:
    if args().len() > 1: fail_mut(values, checked_probe(21, 22))
    change_values(values)
    checked_probe(values[0], 22)
''')
    binary = tmp_path / 'nonreturning'
    built = subprocess.run([compiler, 'build', source, '--ir', '--target', target, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_checked_probe_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    assert probe, 'checked helper was not emitted'
    if not flags:
        assert re.search(r'call a=\d+ b=1 c=1 ', probe[0]), probe[0]
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web nonreturning-call checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'nonreturning.cjs'
        runner.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, ran.stdout + ran.stderr
    failed = subprocess.run([*command, 'fail'], capture_output=True, text=True, timeout=10)
    assert failed.returncode != 0 and 'custom limit 42' in failed.stderr, failed.stdout + failed.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_mask_comparison_boundaries(compiler, tmp_path, target, release):
    import operator
    masks = [-1, -(1 << 63), 1, 15, 255, 65535, (1 << 63) - 1]
    inputs = [-(1 << 63), -(1 << 31), -256, -1, 0, 1, 2, 14, 15, 16,
              254, 255, 256, (1 << 31) - 1, 1 << 31, (1 << 63) - 1]
    ops = [('<', operator.lt), ('<=', operator.le), ('>', operator.gt),
           ('>=', operator.ge), ('==', operator.eq), ('!=', operator.ne)]
    definitions, checks = [], []
    for mask in masks:
        for bound in sorted({-1, 0, 1, mask, min(mask + 1, (1 << 63) - 1)}):
            name = f'check{len(definitions)}'
            expressions = []
            for unsigned in [False, True]:
                for op, _ in ops:
                    left = '(m as u64)' if unsigned else 'm'
                    right = f'({bound & ((1 << 64) - 1)} as u64)' if unsigned else str(bound)
                    expressions.append(f'(int({left} {op} {right}) << {len(expressions)})')
            definitions.append(f'@noinline\n{name} = (v: int) -> int:\n    m = v & {mask}\n    '
                               + ' | '.join(expressions))
            for value in inputs:
                masked, expected, bit = value & mask, 0, 0
                for unsigned in [False, True]:
                    left = masked & ((1 << 64) - 1) if unsigned else masked
                    right = bound & ((1 << 64) - 1) if unsigned else bound
                    for _, compare in ops:
                        expected |= int(compare(left, right)) << bit
                        bit += 1
                checks.append(f'    assert({name}({value}) == {expected})')
    definitions.append('''@noinline
changed_mask = (change: bool) -> int:
    m = 99 & 255
    if change: m = 4096
    int(m >= 256)
@noinline
mask_probe = (x: int) -> int:
    m = x & 1023
    if m < 0 or m >= 1024: panic("impossible mask bounds")
    m
''')
    source = tmp_path / 'mask-comparisons.jo'
    source.write_text('\n'.join(definitions) + '\nmain = () -> int:\n'
                      + '\n'.join(checks)
                      + '\n    assert(changed_mask(false) == 0 and changed_mask(true) == 1)\n    mask_probe(42)\n')
    binary = tmp_path / 'mask-comparisons'
    built = subprocess.run([compiler, 'build', source, '--ir', '--target', target,
                            *(['--release'] if release else []), '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_mask_probe_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    assert probe and 'call a=' not in probe[0], probe[0] if probe else 'missing probe'
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web mask checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'mask-comparisons.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, ran.stdout + ran.stderr
