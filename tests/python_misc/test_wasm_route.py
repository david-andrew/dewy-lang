"""Programs on wasm32, with the full prelude, run under node.

Two routes build each program: µDewy's wasm32 backend from the native
compiler's µDewy text, and the native compiler's own wasm32 emitter
(dewy/bootstrap/backend/native/wasm32.dewy). Both must give the result the
program expects. `tools/run_wasm.mjs` provides the host imports a command
line can give (`host_log` to standard output, `host_exit`).
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

import test_bootstrap_lowering as native_lowering
from test_bootstrap_structural_text import build_program_driver
from test_ssa_form import CASES as FORM_CASES
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

NODE = shutil.which('node')
RUNNER = native_lowering.ROOT / 'tools/run_wasm.mjs'

pytestmark = pytest.mark.skipif(NODE is None, reason='node runs the wasm32 modules')

# Programs whose output is checked as well as their status.
PRINTED = [
    ('''main=():>int64=>{
    let words:array<string>=["wasm" "and" "dewy"]
    printl(words.join(" "))
    let total:int64=0
    loop i in 0..10 {total+=i*i}
    printl"{total} {total//7} {total%7} {0-total}"
    return 42
}''', 'wasm and dewy\n385 55 0 -385\n'),
    ('''Point:type=[x:int64 y:int64]
main=():>int64=>{
    let seen:dict<string int64>=[]
    let points:array<Point>=[]
    loop i in 0..5 {
        points.push(Point[i i*i])
        seen["p{i}"]=i*3
    }
    let sum:int64=0
    loop point in points {sum+=point.x*10+point.y}
    let keys:array<string>=[]
    loop [key value] in seen {keys.push("{key}={value}")}
    printl"{sum} {keys.join(",")}"
    return 42
}''', '205 p0=0,p1=3,p2=6,p3=9,p4=12,p5=15\n'),
]

# A browser host calls `main` once per animation frame: module startup runs
# on the first call only, so the state top-level code set up persists.
FRAMES = '''let calls:int64 = 0
printl"setup"
main = ():>int64 => {
    calls += 1
    return calls + 39
}'''


def _run(module, calls=1):
    return subprocess.run([NODE, RUNNER, module, str(calls)], capture_output=True, timeout=60)


def test_wasm_routes(tmp_path):
    binary = build_program_driver(tmp_path)
    cache = tmp_path / 'prelude-wasm32'
    environment = {**os.environ, 'DEWY_TEST_TARGET': 'wasm32'}
    cases = [(text, None, 1) for text in FORM_CASES] + [(text, printed, 1) for text, printed in PRINTED]
    cases.append((FRAMES, 'setup\n', 3))
    for index, (text, printed, calls) in enumerate(cases):
        source = tmp_path / f'case-{index}.dewy'
        source.write_text(text)
        arguments = [binary, source, native_lowering.ROOT / 'library', cache]
        compiled = subprocess.run(arguments, env=environment, capture_output=True, text=True, timeout=300)
        assert compiled.returncode == 0, text + '\n' + compiled.stdout + compiled.stderr
        listing = tmp_path / f'udewy-{index}.udewy'
        listing.write_text(compiled.stdout)
        assert entry_point(listing, [], EntryPointOptions(compile_only=True, target='wasm32')) == 0
        module = tmp_path / f'native-{index}.wasm'
        built = subprocess.run(arguments, env={**environment, 'DEWY_TEST_NATIVE': str(module)},
                               capture_output=True, text=True, timeout=300)
        assert built.returncode == 0, text + '\n' + built.stdout + built.stderr
        for route, path in [('µDewy', cache_artifact(listing, '.wasm')), ('native', module)]:
            result = _run(path, calls)
            assert result.returncode == 42, (route, text, result.stdout, result.stderr)
            if printed is not None:
                assert result.stdout.decode() == printed, (route, text, result.stdout)


def test_hosted_wasm_frames(tmp_path):
    from dewy.backend.udewy.emit import codegen
    from dewy.reporting import SrcFile
    source = tmp_path / 'frames.dewy'
    source.write_text(FRAMES)
    listing = tmp_path / 'frames.udewy'
    listing.write_text(codegen(SrcFile(str(source), FRAMES), target='wasm32'))
    assert entry_point(listing, [], EntryPointOptions(compile_only=True, target='wasm32')) == 0
    result = _run(cache_artifact(listing, '.wasm'), 3)
    assert result.returncode == 42, (result.stdout, result.stderr)
    assert result.stdout.decode() == 'setup\n'
