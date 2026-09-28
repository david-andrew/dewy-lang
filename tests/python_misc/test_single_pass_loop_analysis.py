"""An iteration without an advancing edge needs no invariant search."""
import pytest
from dewy.reporting import ReportException, SrcFile
from dewy.semantic.check import typecheck_and_resolve
from dewy.semantic.analyze.bounds import _BoundsValidator
from dewy.backend.udewy import codegen
from test_scalar_projection import execute


def nested(depth, *, broken=False):
    body = ('$assert false ' if broken else '') + 'break'
    for index in range(depth):
        body = 'loop flag { ' + body + ' } break'
    return 'probe=(flag:bool):>int64=>{loop flag {'+body+'} return 42}\nmain=():>int64=>if probe(false)=?42 probe(true) else 0'


CASES = [nested(18),
    '''probe=(flag:bool):>int64=>{
        let value:int64=0
        loop true {if flag {value=42 break} else {value=42 break}}
        $assert value=?42
        return value
    }
    main=():>int64=>probe(true)''',
    '''advance=(@value:int64):>bool=>{value+=1 return true}
    main=():>int64=>{
        let value:int64=0
        loop advance(@value) {break}
        return value+41
    }''',
    '''main=():>int64=>{
        let value:int64=0
        loop true {
            loop value<?3 {value+=1 continue}
            break
        }
        $assert value=?3
        return value+39
    }''',
]
ERRORS = [nested(12, broken=True), CASES[2].replace('        return value+41', '        $assert value=?0\n        return value+41'),
    '''main=():>int64=>{
        let value:int64=0
        loop value<?3 {value+=1 if value<?3 continue break}
        $assert value=?1
        return 42
    }''',
]


OUTER_CONTINUE = """main=():>int64=>{
    let value:int64=0
    $outer
    loop value<?3 {
        value+=1
        loop true {continue $outer}
        break
    }
    $assert value>=?1
    return value+39
}"""
OUTER_BREAK = """main=():>int64=>{
    let value:int64=0
    $outer
    loop true {
        loop true {value=42 break $outer}
        value=0
    }
    $assert value=?42
    return value
}"""
for loop in ('loop true', 'loop i in [0..3)', 'loop i in [0..10)', 'loop i in [0..3) and j in [0..3)'):
    continue_case=OUTER_CONTINUE.replace('loop true', loop)
    break_case=OUTER_BREAK.replace('        loop true', '        '+loop)
    CASES += [continue_case, break_case]
    ERRORS += [continue_case.replace('value>=?1', 'value=?0'), break_case.replace('$assert value=?42', '$assert value=?0')]


def test_nested_single_pass_loops_have_linear_transfer_count(monkeypatch):
    count = 0
    original = _BoundsValidator._loop_transfer
    def counted(self, *args, **kwargs):
        nonlocal count
        if self.srcfile.body.startswith('probe='):
            count += 1
        return original(self, *args, **kwargs)
    monkeypatch.setattr(_BoundsValidator, '_loop_transfer', counted)
    typecheck_and_resolve(SrcFile(None, nested(18)))
    assert count < 200, count  # 10 levels previously triggered 620,010 visits.


@pytest.mark.parametrize('source', CASES)
def test_single_pass_loop_still_validates_and_executes(tmp_path, source):
    execute(tmp_path, 'single-pass', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_advancing_or_broken_loop_cannot_gain_proofs(source):
    with pytest.raises(ReportException):
        typecheck_and_resolve(SrcFile(None, source))


def test_native_single_pass_loop_analysis(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
