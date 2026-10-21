"""Fused partition workers (compiler/fused.jo) make the same bytes and diagnostics as one process.

A cross-function cache in lowering that a worker neither journals nor bypasses
changes the order in which functions, strings or globals get their places, and
so the binary. Each program here is built with 1, 2 and 4 workers; a separate
timed build checks that the fused path really ran.
"""
import os
import platform
import re
import subprocess
import sys

import pytest

from tests.support import ROOT, compiler
from tools.compiler.bench import prepare_source
from tools.compiler.speed import generate_dewy

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'amd64'),
    reason='fused workers are x86-64 Linux only')

KERNELS = ['records', 'text', 'callbacks', 'callbacks_literal']
# (examples whose functions share cached lowering state: the guard's real catches)
EXAMPLES = ['ring', 'rollback_model', 'reaction_model']


def build(compiler, source, output, workers, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(SLOPPY_EMIT_WORKERS=str(workers), DEWY_CORE_LIB=str(ROOT / 'lib'), **extra)
    run = subprocess.run([compiler, 'build', source, '-o', output], cwd=output.parent, env=env,
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout == "", run.stdout
    return output.read_bytes(), run.stderr


def check(compiler, source, directory, **extra):
    base, base_err = build(compiler, source, directory / 'one', 1, **extra)
    for workers in (2, 4):
        got, err = build(compiler, source, directory / f'w{workers}', workers, **extra)
        assert err == base_err, f'{workers} workers: diagnostics differ'
        assert got == base, f'{workers} workers: binary differs from one process'
    # (not vacuous: the fused workers made most functions)
    for workers in (2, 4):
        _, timed = build(compiler, source, directory / 'timed', workers, SLOPPY_PAR_TIME='1', **extra)
        fused = re.search(rf'fused: {workers} workers, \d+ functions, .*, (\d+) records, (\d+) valid', timed)
        assert fused, 'the fused path did not run:\n' + timed
        assert int(fused.group(2)) * 2 > int(fused.group(1)), fused.group(0)


def test_fused_root_heavy_program(compiler, tmp_path):
    source = tmp_path / 'synthetic.dewy'
    source.write_text(generate_dewy(600))
    check(compiler, source, tmp_path)


@pytest.mark.parametrize('name', KERNELS)
def test_fused_bench_kernel(compiler, tmp_path, name):
    # (below the root-weight gate: forced)
    check(compiler, prepare_source(name, tmp_path), tmp_path, SLOPPY_EMIT_FORCE='1')


@pytest.mark.parametrize('name', EXAMPLES)
def test_fused_example(compiler, tmp_path, name):
    check(compiler, ROOT / 'examples' / f'{name}.dewy', tmp_path, SLOPPY_EMIT_FORCE='1')


# Known-callback versions (callback_specialize.jo) share their instance with the ordinary
# function: workers must leave them, and what calls them, to the compiler.
CALLBACK_VERSIONS = '''Callback:type=(x:int64):>int64
visit=(callback:Callback):>int64=>callback(3)+callback(4)
forward=(callback:Callback):>int64=>visit(@callback)
main=()=>{
 let n:int64=5
 let named=(x:int64):>int64=>x+n
 let a=visit(@named)
 let b=visit((x:int64):>int64=>x*n)
 let c=forward((x:int64):>int64=>x-n)
 printl"{a} {b} {c} {visit((x:int64):>int64=>x)}"
 return 0
}
'''


@pytest.mark.core_quick
def test_fused_callback_versions(compiler, tmp_path):
    source = tmp_path / 'versions.dewy'
    source.write_text(CALLBACK_VERSIONS)
    check(compiler, source, tmp_path, SLOPPY_EMIT_FORCE='1')
    ir = subprocess.run([compiler, 'build', source, '--ir', '-o', tmp_path / 'ir'], capture_output=True, text=True)
    assert '_callback_' in ir.stdout, 'no callback versions: the case does not exercise them'
    assert subprocess.run([tmp_path / 'w4'], capture_output=True, text=True).stdout.split() == ['17', '35', '-3', '7']
