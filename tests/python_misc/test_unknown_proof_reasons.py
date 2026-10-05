"""An unknown proof says why it stayed unknown (closure row P4).

Both checkers add one `why unknown:` note to a report they cannot decide,
in the same priority: an exhausted search budget, a value other code
changes (a module-level or captured variable), a call whose result carries
no refinement, an operation the checker does not track between two unknown
values, or simply no fact on the path. A name is followed to its
initializer when it is never reassigned. A refuted fact gets no such note.
"""
import subprocess

import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile

import test_bootstrap_lowering as native_lowering

CASES = [
    ('''weight=(x:int64):>int64=>x*2
main=():>int64=>{
    let xs:array<int64>=[1 2 3 4]
    let a=weight(1)
    return xs[a]
}''', 'why unknown: `weight` returns a value with no refinement the checker could use'),
    ('''let shared:int64=3
bump=():>void=>{shared+=1}
main=():>int64=>{
    let xs:array<int64>=[1 2 3 4]
    bump()
    let b:int64=shared
    return xs[b]
}''', 'why unknown: `shared` is changed by other code (a module-level or captured variable), so facts about it do not survive calls'),
    ('''main=():>int64=>{
    let xs:array<int64>=[1 2 3 4 5 6 7 8 9]
    let a:int64=xs[0]
    let b:int64=xs[1]
    return xs[a*b]
}''', 'why unknown: the checker does not track `*` between two unknown values'),
    ('''main=():>int64=>{
    let xs:array<int64>=[1 2 3]
    let total:int64=0
    loop x in xs {total+=x}
    $assert total <? 2
    return 42
}''', None),
]


def report(source):
    with pytest.raises(ReportException) as raised:
        codegen(SrcFile(None, source), debug_locations=False)
    return str(raised.value)


@pytest.mark.parametrize('source, reason', CASES)
def test_hosted_unknown_proof_reason(source, reason):
    text = report(source)
    if reason is None:
        assert 'why unknown' not in text
    else:
        assert reason in text


def test_native_unknown_proof_reasons(tmp_path):
    from test_bootstrap_structural_text import build_program_driver
    binary = build_program_driver(tmp_path)
    cache = tmp_path / 'prelude-cache'
    for index, (source, reason) in enumerate(CASES):
        path = tmp_path / f'case-{index}.dewy'
        path.write_text(source)
        result = subprocess.run([binary, path, native_lowering.ROOT / 'library', cache],
                                capture_output=True, text=True, timeout=300)
        assert result.returncode == 1 and 'Error' in result.stderr, (source, result.stderr)
        if reason is None:
            assert 'why unknown' not in result.stderr, result.stderr
        else:
            assert reason in result.stderr, result.stderr
