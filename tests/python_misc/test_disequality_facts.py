"""A finite disequality fact needs neither an ordering nor a guessed interval."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from dewy.semantic.check import typecheck_and_resolve
from test_scalar_projection import execute

PAIR = '''probe=(a:int64 b:int64):>int64=>{
    if a=?b return 0
    $assert a not=?b
    $assert b not=?a
    return 42
}
main=():>int64=>probe(12 4)
'''
CASES = [PAIR,
    PAIR.replace('if a=?b return 0', 'if not (a not=?b) return 0'),
    PAIR.replace('    return 42', '    let unused:int64=0\n    unused+=1\n    return 42'),
    '''probe=(n:int64 xs:array<int64>):>int64=>{
        if n=?xs.length return 0
        $assert n not=?xs.length
        $assert xs.length not=?n
        return 42
    }
    main=():>int64=>probe(1 [2 3])''',
    '''Pair:type=[a:int64 b:int64]
    probe=(pair:Pair):>int64=>{
        if pair.a=?pair.b return 0
        $assert pair.a not=?pair.b
        return 42
    }
    main=():>int64=>probe(Pair[12 4])''',
    '''probe=(xs:array<int64> index:int64 value:int64):>int64=>{
        if index<?0 or index>=?xs.length return 0
        if xs[index]=?value return 0
        $assert value not=?xs[index]
        return 42
    }
    main=():>int64=>probe([12 4] 0 4)''',
    '''probe=(a:int64 b:int64 flag:bool):>int64=>{
        if flag {if a=?b return 0} else {if b=?a return 0}
        $assert a not=?b
        return 42
    }
    main=():>int64=>probe(12 4 true)''',
]
CASES.append('probe=(a:int64 b:int64):>int64=>{\n    if a=?b return 0\n    if a>?b return 1\n    $assert a<?b\n    return 42\n}\nmain=():>int64=>probe(4 12)')
CASES.append(PAIR.replace('    return 42', '    loop i in [0..20) {$assert a not=?b}\n    return 42'))
JOIN = """probe=(a:int64 b:int64 flag:bool):>int64=>{
    if flag {if a>=?b return 0} else {if a=?b return 0}
    $assert a not=?b
    return 42
}
main=():>int64=>if probe(4 12 true)=?42 probe(12 4 false) else 0"""
CASES += [JOIN, JOIN.replace('if a>=?b', 'if a<=?b').replace('probe(4 12 true)', 'probe(12 4 true)'),
    JOIN.replace('if a>=?b return 0', 'a=1 b=2')]
ERRORS = [JOIN.replace('if a>=?b return 0', 'if a>?b return 0'),
    JOIN.replace('if a>=?b return 0', 'a=1 b=1'),
    PAIR.replace('    $assert a not=?b', '    $unsafe_assume a=?b'), PAIR.replace('    if a=?b return 0', ''), PAIR.replace('    $assert a not=?b', '    a=b\n    $assert a not=?b'),
    PAIR.replace('    $assert a not=?b', '    a+=1\n    $assert a not=?b'),
    PAIR.replace('    $assert a not=?b', '    $assert a<?b'),
    CASES[3].replace('        $assert n not=?xs.length', '        xs.push(0)\n        $assert n not=?xs.length'),
    CASES[4].replace('        $assert pair.a not=?pair.b', '        pair.a=pair.b\n        $assert pair.a not=?pair.b'),
    CASES[5].replace('        $assert value not=?xs[index]', '        index+=1\n        if index>=?xs.length return 0\n        $assert value not=?xs[index]'),
    'change=(@a:int64 b:int64):>void=>{a=b}\n' + PAIR.replace('    $assert a not=?b', '    change(@a b)\n    $assert a not=?b'),
    PAIR.replace('    $assert a not=?b', '    loop i in [0..20) {$assert a not=?b a=b}\n    $assert a not=?b'),
]


@pytest.mark.parametrize('source', CASES)
def test_disequality_is_retained(tmp_path, source):
    execute(tmp_path, 'disequality', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_disequality_does_not_survive_changed_values(source):
    with pytest.raises(ReportException):
        typecheck_and_resolve(SrcFile(None, source))


def test_native_disequality_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
