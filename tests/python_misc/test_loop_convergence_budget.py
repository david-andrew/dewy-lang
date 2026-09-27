"""A bounded analysis must not mistake an unfinished iteration for induction."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from dewy.semantic import check
from tests.python_misc.test_scalar_projection import execute


def delayed_change(kind, depth=24, *, assertion=True):
    lines = ['main=():>int64=>{']
    lines += [f'let x{i}:int64=0' for i in range(depth)]
    if kind == 'while':
        lines += ['let step:int64=0', f'loop step <? {depth+8} {{']
    elif kind == 'iterator':
        lines += [f'loop step in [0..{depth+8}) {{']
    else:
        lines += [f'loop step in [0..{depth+8}) and other in [0..{depth+8}) {{']
    if assertion:
        lines += ['$assert x0 =? 0']
    # Every loop transfer advances the information by one variable. The
    # assertion eventually becomes false, even though early transfers agree.
    lines += [f'x{i}=x{i+1}' for i in range(depth-1)]
    lines += [f'x{depth-1}=1']
    if kind == 'while':
        lines += ['step+=1']
    lines += ['}', 'return if x0 =? 1 42 else 1', '}']
    return '\n'.join(lines)


@pytest.mark.parametrize('kind', ['while', 'iterator', 'multi'])
@pytest.mark.parametrize('depth', [8, 12, 24])
def test_unstable_loop_candidate_cannot_prove_assertion(kind, depth):
    with pytest.raises(ReportException, match='cannot prove assertion'):
        check.typecheck_and_resolve(SrcFile(None, delayed_change(kind, depth)))


@pytest.mark.parametrize('kind', ['while', 'iterator', 'multi'])
def test_budget_fallback_preserves_runtime_behavior(tmp_path, kind):
    execute(tmp_path, f'loop-budget-{kind}', codegen(SrcFile(None, delayed_change(kind, assertion=False))))


def test_native_loop_convergence_budget(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[delayed_change(kind, assertion=False) for kind in ('while', 'iterator', 'multi')],
                          errors=[*(delayed_change(kind) for kind in ('while', 'iterator', 'multi')), CONDITION_EFFECTS])


CONDITION_EFFECTS = (
    'advance=(@value:int64):>bool=>{value=1 return true}\n'
    + delayed_change('while', 3)
      .replace('loop step <? 11 {', 'loop step <? 11 and advance(@x2) {')
      .replace('x2=1\n', '')
)


def test_condition_writes_participate_in_each_loop_transfer():
    # A short dependency chain converges within budget. The condition, not
    # the body, changes its final link on every iteration.
    with pytest.raises(ReportException, match='cannot prove assertion'):
        check.typecheck_and_resolve(SrcFile(None, CONDITION_EFFECTS))
