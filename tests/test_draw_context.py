"""Draw reachability is a caller obligation, independent of GPU resource limits."""
import os
from pathlib import Path
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


CASES = Path(__file__).parent / 'cases/draw_context'


def invoke(compiler, path, *arguments, flags=(), **extra):
    env = {**os.environ, 'DEWY_EMIT_WORKERS': '1', 'DEWY_THREADS': '2', **extra}
    return subprocess.run([compiler, *arguments, path, *flags], capture_output=True,
                          text=True, env=env, timeout=60)


@pytest.mark.parametrize('name', ['direct', 'helpers', 'recursion'])
def test_draw_context_proved_and_runs(compiler, tmp_path, name):
    source = (CASES / f'{name}.dewy').read_text().replace('main=()=>exit(0)\n', '')
    path = tmp_path / 'game.dewy'
    path.write_text(source)
    checked = invoke(compiler, path, 'check', '--obligations')
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert 'drawing runs only' not in checked.stdout
    assert 'drawing works only' not in checked.stdout + checked.stderr
    # Without the opt-in, the draw precondition is discharged, and GPU capacity
    # is an environment failure, not a panic (resource_exhaustion.md).
    path.write_text(source.replace('$runtime_checks\n', ''))
    strict = invoke(compiler, path, 'check')
    assert strict.returncode == 0, strict.stdout + strict.stderr
    assert 'drawing' not in strict.stderr
    path.write_text(source)
    screenshot = tmp_path / 'frame.png'
    ran = invoke(compiler, path, 'run', DEWY_SOFTWARE='1', DEWY_FRAMES='2',
                 DEWY_SCREENSHOT=str(screenshot), DISPLAY='', WAYLAND_DISPLAY='')
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert screenshot.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')


@pytest.mark.parametrize('name', [
    'mixed_callers', 'function_value', 'user_called_draw', 'recursion_update', 'draw_value',
    'library_caller',
])
def test_draw_context_rejects_outside_paths(compiler, name):
    result = invoke(compiler, CASES / f'{name}.dewy', 'check')
    assert result.returncode == 1, result.stdout + result.stderr
    for expected in (CASES / f'{name}.err').read_text().splitlines():
        assert expected in result.stderr, result.stderr


def test_draw_context_deferred_check_still_traps(compiler, tmp_path):
    path = tmp_path / 'outside.dewy'
    path.write_text('$runtime_checks\ncircle(vec2(100 100) 20 RED)\n')
    checked = invoke(compiler, path, 'check', '--obligations')
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert 'drawing runs only inside runtime-invoked draw' in checked.stdout
    ran = invoke(compiler, path, 'run', DEWY_SOFTWARE='1', DISPLAY='', WAYLAND_DISPLAY='')
    assert ran.returncode == 101, ran.stdout + ran.stderr
    assert 'drawing works only inside' in ran.stderr


def test_draw_context_without_opt_in(compiler, tmp_path):
    path = tmp_path / 'game.dewy'
    path.write_text('draw=():>void=>{circle(vec2(100 100) 20 RED)}\n')
    checked = invoke(compiler, path, 'check')
    assert checked.returncode == 0, checked.stdout + checked.stderr


@pytest.mark.parametrize('target', ['native', 'wasm32'])
def test_draw_context_does_not_instantiate_unused_field_defaults(compiler, tmp_path, target):
    # These modules combine a draw obligation with generic value equality.
    # Inspecting the equality helper's layout during graph collection used to
    # append an unchecked field-default instance and overrun the graph arrays.
    modules = ['game/polyline_joins', 'generic/constructor_empty_inference', 'generic/function']
    imports = [f'from p"{CASES.parent / name}.dewy" import (run as run_{i})'
               for i, name in enumerate(modules)]
    path = tmp_path / 'batch.dewy'
    path.write_text('$runtime_checks\n' + '\n'.join(imports) + '\nmain=():>void=>{\n'
                    'printl"{run_0()} {run_1()} {run_2()}"\n}\n')
    flags = [] if target == 'native' else ['--target', target]
    checked = invoke(compiler, path, 'check', flags=flags)
    assert checked.returncode == 0, checked.stdout + checked.stderr
