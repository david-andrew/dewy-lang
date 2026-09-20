"""Finite transfer composition must check all reachable loop iterations."""
import subprocess
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError
from udewy.cache import cache_artifact
from udewy.frontend import entry_point, EntryPointOptions
from test_bootstrap_lowering import ROOT


ERRORS = [(ROOT / 'tests/fixtures' / f'{name}.dewy').read_text() for name in (
    'finite_loop_late_index', 'finite_loop_early_break', 'finite_loop_late_narrowing',
    'parallel_array_missing_push', 'loop_length_early_break',
)]


@pytest.mark.parametrize('name', ['finite_loop_facts', 'nonzero_field_bounds', 'parallel_array_invariant', 'loop_length_counter_invariant'])
def test_finite_loop_facts(tmp_path, name):
    source = ROOT / 'tests/fixtures' / f'{name}.dewy'
    output = tmp_path / 'finite-loops.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    assert subprocess.run([cache_artifact(output).resolve()], timeout=5).returncode == 42


@pytest.mark.parametrize('source', ERRORS)
def test_later_iteration_or_early_exit_is_not_assumed_safe(source):
    with pytest.raises(UserError):
        codegen(SrcFile(None, source), debug_locations=False)
