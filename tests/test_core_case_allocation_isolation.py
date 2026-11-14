"""Unrelated dynamic settings must not change an allocation golden's program."""
from dataclasses import replace

import pytest

from tests.support import compiler  # noqa: F401
from tools import cases


def test_allocation_counter_spellings_run_alone(tmp_path):
    for name, expression in [('called', 'alloc_count()'), ('bare', 'alloc_count')]:
        (tmp_path / f'{name}.dewy').write_text(f'main=()=>{{printl({expression})}}\n')
    (tmp_path / 'ordinary.dewy').write_text('main=()=>{printl(42)}\n')
    units = cases.plan(cases.discover(tmp_path), node=False)
    assert {(kind, mode, tuple(c.name for c in batch)) for kind, mode, batch in units} == {
        (kind, mode, (name,))
        for mode in ('native', 'native-release')
        for kind, name in [('single', 'called'), ('single', 'bare'), ('value', 'ordinary')]
    }


@pytest.mark.parametrize('mode', ['native', 'native-release'])
def test_allocation_cases_ignore_other_program_policy(compiler, tmp_path, monkeypatch, mode):  # noqa: F811
    # The time-rules module makes callable values capture policy throughout a
    # combined executable. Those wrappers legitimately allocate; these three
    # separate programs are measuring callbacks without that unrelated policy.
    names = ['closure/stack_local_noheap', 'closure/stack_pinned_call',
             'sequence/minmax_by_no_tail_allocation', 'settingsplace_rules/pinned']
    chosen = [replace(cases.parse(cases.CASES / f'{name}.dewy'), modes=(mode,)) for name in names]
    monkeypatch.setattr(cases.tempfile, 'tempdir', str(tmp_path))
    assert cases.run(compiler, chosen, workers=1) == 0
