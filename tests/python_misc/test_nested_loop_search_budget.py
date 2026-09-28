"""A per-loop cap must also bound the multiplication through nested loops."""
import pytest

from dewy.reporting import ReportException, SrcFile
from dewy.semantic.check import typecheck_and_resolve
from dewy.semantic.analyze.bounds import _BoundsValidator
from dewy.backend.udewy import codegen
from test_scalar_projection import execute


def nested(depth=18, *, body='value=42', tail='return value', kind='while'):
    for index in range(depth):
        if kind == 'while':
            body = f'let step{index}:int64=0 loop step{index}<?1 {{ {body} step{index}+=1 }}'
        else:
            # More than the finite-unrolling threshold, but execution exits
            # after one iteration. Iterator analysis still searches a head.
            body = f'loop step{index} in [0..10) {{ {body} break }}'
    return 'probe=():>int64=>{let value:int64=0 '+body+' '+tail+'}\nmain=():>int64=>probe()'


CASES = [nested(), nested(kind='iterator'), nested(tail='''
    let fresh:int64=0
    loop fresh<?42 {fresh+=1}
    $assert fresh=?42
    return fresh''')]
ERRORS = [nested(body='$assert false'), nested(tail='$assert value=?0 return 42'),
          nested(kind='iterator', body='$assert false')]


@pytest.mark.parametrize('depth', [8, 18])
def test_nested_search_work_is_bounded(monkeypatch, depth):
    count = 0
    original = _BoundsValidator._loop_transfer
    def counted(self, *args, **kwargs):
        nonlocal count
        if self.srcfile.body.startswith('probe='):
            count += 1
        return original(self, *args, **kwargs)
    monkeypatch.setattr(_BoundsValidator, '_loop_transfer', counted)
    typecheck_and_resolve(SrcFile(None, nested(depth)))
    assert count < 25_000, count


@pytest.mark.parametrize('source', CASES)
def test_exhaustion_preserves_execution_and_independent_loop_proofs(tmp_path, source):
    execute(tmp_path, 'nested-search', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_exhaustion_never_skips_validation_or_proves_an_unstable_head(source):
    with pytest.raises(ReportException):
        typecheck_and_resolve(SrcFile(None, source))


def test_native_nested_loop_budget(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
