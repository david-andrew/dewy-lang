"""GPU capacity is an environment failure (docs/design/resource_exhaustion.md):
running out of texture slots or buffer room ends the program with a report, as
running out of memory does, so draw calls are not `panics` at the call site."""
import os
import subprocess
import sys

import pytest

from tests.support import compiler  # noqa: F401

DRAWS = '''main=():>void=>{ window("x" 320 200) }
draw=():>void=>{
    let ink=rgb(0.1 0.2 0.3)
    clear(rgb(0.9 0.9 0.9))
    text("Score" vec2(10 10) 20 ink)
    text_centered("Paused" vec2(160 100) 24 ink)
    circle(vec2(40 30) 7 ink)
    ring(vec2(40 30) 7 9 ink)
    rect(1 2 30 40 ink)
    rect_outline(1 2 30 40 2 ink)
    rect_rounded(1 2 30 40 4 ink)
    line(vec2(1 2) vec2(30 40) 1 ink)
    polyline([vec2(1 2) vec2(30 40) vec2(50 10)] 2 ink)
    polygon([vec2(1 2) vec2(30 40) vec2(50 10)] ink)
    circle_gradient(vec2(80 80) 12 ink rgb(1 1 1))
    let cube=cube_mesh(0.5)
    let ball=sphere_mesh(0.5)
    let custom=custom_mesh([])
    let tex=texture(image(1 1))
}
'''


def invoke(compiler, cwd, *arguments, **extra):
    env = {**os.environ, 'DEWY_EMIT_WORKERS': '1', 'DEWY_THREADS': '1', **extra}
    return subprocess.run([compiler, *arguments], capture_output=True, text=True, env=env, timeout=120, cwd=cwd)


@pytest.mark.parametrize('target', ['native', 'wasm32'])
def test_draw_calls_need_no_opt_in(compiler, tmp_path, target):
    (tmp_path / 'game.dewy').write_text(DRAWS)
    checked = invoke(compiler, tmp_path, 'check', 'game.dewy', '--target', target)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert 'may panic' not in checked.stderr, checked.stderr


def test_draw_calls_run_headless(compiler, tmp_path):
    (tmp_path / 'game.dewy').write_text('\n'.join(line for line in DRAWS.splitlines() if not line.startswith(('    let cube=', '    let ball=', '    let custom=', '    let tex='))))
    screenshot = tmp_path / 'frame.png'
    ran = invoke(compiler, tmp_path, 'run', 'game.dewy', DEWY_SOFTWARE='1', DEWY_FRAMES='2',
                 DEWY_SCREENSHOT=str(screenshot), DISPLAY='', WAYLAND_DISPLAY='')
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert screenshot.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')


def test_exhaustion_reports_and_exits(compiler, tmp_path):
    # The hook the GPU limits end in (lib/core/rt.jo): a report and exit status 1, as
    # for running out of memory, never a panic (101).
    (tmp_path / 'main.dewy').write_text('main=():>void=>{\n    printl"before"\n    __environment_failure("too many textures (at most 16384)")\n    printl"after"\n}\n')
    ran = invoke(compiler, tmp_path, 'run', 'main.dewy')
    assert ran.returncode == 1, ran.stdout + ran.stderr
    assert ran.stdout == 'before\n', ran.stdout
    assert ran.stderr == 'fatal: too many textures (at most 16384)\n', ran.stderr


def test_input_end_reports_and_exits(compiler, tmp_path):
    # The same path, reached from a public call at run time.
    (tmp_path / 'main.dewy').write_text('main=():>void=>printl(input_int())\n')
    ran = subprocess.run([compiler, 'run', 'main.dewy'], capture_output=True, text=True, timeout=120, cwd=tmp_path, stdin=subprocess.DEVNULL)
    assert ran.returncode == 1, ran.stdout + ran.stderr
    assert ran.stderr == 'fatal: the input ended before a whole number came\n', ran.stderr


@pytest.mark.skipif(sys.platform != 'linux', reason='Vulkan slot allocator is native Linux')
def test_texture_slots_exhaust_before_driver_call(compiler, tmp_path):
    (tmp_path / 'main.dewy').write_text('main=()=>{\n__vk_slot_next=__VK_MAX_TEXTURES\nprintl(__vk_slot_new())\n}\n')
    ran = invoke(compiler, tmp_path, 'run', 'main.dewy', DEWY_NO_GPU='1', DISPLAY='', WAYLAND_DISPLAY='')
    assert ran.returncode == 1, ran.stdout + ran.stderr
    assert ran.stdout == '' and ran.stderr == 'fatal: too many textures (at most 16384)\n', ran.stdout + ran.stderr


@pytest.mark.parametrize('source, message', [
    ('let g=gpu(reshape([float32(1)] [1 1 1 1 1]))', 'GPU arrays have at most 4 dimensions'),
    ('let b=gpu_buffer<int64>(-1)', 'a GPU buffer cannot have'),
    ('let b=gpu_buffer([1 2]); printl(b[2])', 'out of bounds for a GPU buffer'),
    ('let b=gpu_buffer([1 2]); upload(b [3] 2)', 'do not fit in a GPU buffer'),
    ('let w=physics.World[]; let b=w.add_circle(vec2(0 0) 1); w.remove(b); printl(w.pos(b))', 'this body was removed'),
])
def test_api_misuse_is_still_a_panic(compiler, tmp_path, source, message):
    (tmp_path / 'main.dewy').write_text('import p"@lib/physics.jo" as physics\nmain=()=>{' + source + '}\n')
    checked = invoke(compiler, tmp_path, 'check', 'main.dewy')
    assert checked.returncode == 1 and 'may panic' in checked.stderr, checked.stdout + checked.stderr
    (tmp_path / 'main.dewy').write_text('import p"@lib/physics.jo" as physics\n$runtime_checks\nmain=()=>{' + source + '}\n')
    ran = invoke(compiler, tmp_path, 'run', 'main.dewy', DEWY_NO_GPU='1')
    assert ran.returncode == 101 and message in ran.stderr, ran.stdout + ran.stderr
