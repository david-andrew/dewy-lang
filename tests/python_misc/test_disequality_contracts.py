"""Dependent contracts retain disequality without selecting either order."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from dewy.semantic.check import typecheck_and_resolve
from test_scalar_projection import execute

CHECK = '''different=(a:int64 b:int64<v=>v not=?a>):>int64=>{
    $assert a not=?b
    return 42
}
probe=(a:int64 b:int64):>int64=>{
    if a=?b return 0
    return different(a b)
}
main=():>int64=>probe(12 4)
'''
CASES = [CHECK,
    CHECK.replace('return different(a b)', 'return different(b a)'),
    '''$proof
different=(a:int64 b:int64<v=>v not=?a>):> <a not=?b>=>{}
probe=(a:int64 b:int64):>int64=>{
    if a=?b return 0
    different(a b)
    $assert a not=?b
    return 42
}
main=():>int64=>probe(12 4)''',
    '''pick=(a:int64 b:int64<v=>v not=?a>):>int64<v=>v not=?a>=>b
probe=(a:int64 b:int64):>int64=>{
    if a=?b return 0
    let value=pick(a b)
    $assert value not=?a
    return 42
}
main=():>int64=>probe(12 4)''',
    '''check=(xs:array<int64> n:int64<v=>v not=?xs.length>):>int64=>{
    $assert n not=?xs.length
    return 42
}
probe=(xs:array<int64> n:int64):>int64=>{
    if xs.length=?n return 0
    return check(xs n)
}
main=():>int64=>probe([1 2 3] 4)''',
    '''different=(a:int64 b:int64):>true & <a not=?b> | false=>a not=?b
probe=(a:int64 b:int64):>int64=>{
    if different(a b) {$assert a not=?b return 42}
    return 0
}
main=():>int64=>probe(12 4)''',
    '''Pair:type=const [a:int64 b:int64<v=>v not=?a>]
probe=(pair:Pair):>int64=>{$assert pair.a not=?pair.b return 42}
main=():>int64=>probe(Pair[12 4])''',
]
CASES += [CHECK.replace('return different(a b)', 'let copied=b\n    return different(a copied)'),
    CHECK.replace('return different(a b)', 'let copied=b\n    b=a\n    $assert a not=?copied\n    return different(a copied)'),
    CHECK.replace('probe(12 4)', 'probe(12 0)'),
    """check=(xs:array<int64> ys:array<int64 length not=?xs.length>):>int64=>{
    $assert xs.length not=?ys.length
    return 42
}
probe=(xs:array<int64> ys:array<int64>):>int64=>{
    if xs.length=?ys.length return 0
    return check(xs ys)
}
main=():>int64=>probe([1 2 3] [4])""",
]
CASES.append(CASES[4].replace('    $assert n not=?xs.length', '    let size=xs.length\n    $assert n not=?size'))
CASES.append("""Pair:type=const [a:array<int64> b:array<int64 length not=?a.length>]
probe=(pair:Pair):>int64=>{$assert pair.a.length not=?pair.b.length return 42}
main=():>int64=>probe(Pair[[12 4] [8]])""")
ERRORS = [CHECK.replace('    if a=?b return 0\n', ''),
    CHECK.replace('return different(a b)', 'return different(a a)'),
    CHECK.replace('    $assert a not=?b', '    a=b\n    $assert a not=?b'),
    CASES[3].replace('=>b\nprobe', '=>a\nprobe'),
    CASES[3].replace('    $assert value not=?a', '    a=value\n    $assert value not=?a'),
    CASES[4].replace('    $assert n not=?xs.length', '    xs.push(0)\n    $assert n not=?xs.length'),
    CHECK.replace('    $assert a not=?b', '    $assert b not=?0'),
    CASES[6].replace('Pair[12 4]', 'Pair[12 12]'),
]

ERRORS.append("""pick=(a:int64 @b:int64):>int64<v=>v not=?a>=>{
    if a=?0 {b=1 return 1}
    b=0
    return 0
}
probe=(a:int64):>int64=>{
    let value=pick(a @a)
    $assert value not=?a
    return 42
}
main=():>int64=>probe(12)""")

# Expression bounds use the same checked strict-order rules as <=/>= contracts.
LENGTH_EXPRESSION = """next=(src:string):>uint64<n=>n not=?src.length>=>src.length+1
main=():>int64=>if next('hello')=?6 42 else 0"""
CASES.append(LENGTH_EXPRESSION)
CASES.append(LENGTH_EXPRESSION.replace('src.length+1', 'src.length+2').replace("=?6", "=?7"))
ERRORS.append(LENGTH_EXPRESSION.replace('src.length+1', 'src.length+0'))
ERRORS.append(LENGTH_EXPRESSION.replace('src.length+1', 'if src.length=?0 1 else src.length'))

@pytest.mark.parametrize('source', CASES)
def test_dependent_disequality(tmp_path, source):
    execute(tmp_path, 'disequality-contract', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_unproven_disequality_rejected(source):
    with pytest.raises(ReportException):
        typecheck_and_resolve(SrcFile(None, source))


def test_native_disequality_contracts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
