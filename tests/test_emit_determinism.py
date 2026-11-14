"""Parallel emit output follows queue order, including fallback and frozen twins."""
import os
import re
import subprocess

import pytest

from tests.support import compiler, ROOT  # noqa: F401
from tests.selfhost_lsp_double import leaf_compilers
from tools.compiler.speed import generate_dewy


def outputs(binary, source, target, flags=(), extra=None, command='build'):
    env = dict(os.environ, DEWY_CORE_LIB=str(ROOT / 'lib'), DISPLAY='', WAYLAND_DISPLAY='',
               DEWY_NO_AUDIO='1', **(extra or {}))
    args = [str(binary), command, str(source), *flags]
    if command == 'build':
        args += ['-o', str(target)]
    run = subprocess.run(args, env=env, capture_output=True, timeout=120)
    assert run.returncode == 0, run.stderr
    return run.stdout, run.stderr, target.read_bytes() if command == 'build' else b''


@pytest.mark.parametrize('flags,extra,command', [
    (('--ir',), {'DEWY_FUSED': '0'}, 'build'),
    (('--ir', '--release'), {}, 'build'),
    (('-g',), {}, 'build'),
    ((), {}, 'build'),
    (('--release',), {'DEWY_RADUMP': 'work0'}, 'build'),
    ((), {'DEWY_RASTAT': 'v'}, 'build'),
    (('--obligations',), {}, 'check'),
])
def test_parallel_outputs_repeat(compiler, tmp_path, flags, extra, command):
    source = tmp_path / 'program.dewy'
    source.write_text(generate_dewy(240))
    env = dict(DEWY_EMIT_WORKERS='2', DEWY_EMIT_FORCE='1', **extra)
    if 'DEWY_RADUMP' in extra:
        ir = outputs(compiler, source, tmp_path / 'program', (*flags, '--ir'),
                     dict(DEWY_EMIT_WORKERS='1', DEWY_FUSED='0'))[0]
        env['DEWY_RADUMP'] = re.search(rb'^fn (f_work0_\d+) ', ir, re.M)[1].decode()
    first = outputs(compiler, source, tmp_path / 'program', flags, env, command)
    if 'DEWY_RADUMP' in extra:
        assert b' -> ' in first[1]
    assert outputs(compiler, source, tmp_path / 'program', flags, env, command) == first


def test_par_drive_ir_builders_fused_drive_pcheck_drive_match_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source = tmp_path / 'program.dewy'
    source.write_text(generate_dewy(120))
    pair = leaf_compilers(compiler, tmp_path, ('par_drive', 'ir_builders', 'fused_drive', 'pcheck_drive'))
    expected = None
    for binary in pair:
        for workers, fail in [('1', ''), ('2', ''), ('4', ''), ('2', '1')]:
            got = outputs(binary, source, tmp_path / 'program', ('--ir',),
                          dict(DEWY_FUSED='0', DEWY_EMIT_FORCE='1',
                               DEWY_EMIT_WORKERS=workers, DEWY_EMIT_FAIL_WORKER=fail))
            if expected is None:
                expected = got
            assert got == expected


    # Exercise fused_drive's trace trailer through both implementations too.
    import re
    fused_expected = None
    for binary in pair:
        stdout, stderr, binary_bytes = outputs(
            binary, source, tmp_path / 'program', extra=dict(
                DEWY_EMIT_WORKERS='2', DEWY_EMIT_FORCE='1', DEWY_FUSED_TRACE='1'))
        result = stdout, re.sub(rb'\d+(?:\.\d+)?', b'N', stderr), binary_bytes
        if fused_expected is None:
            fused_expected = result
        assert result == fused_expected


def test_parallel_diagnostics_repeat(compiler, tmp_path):
    source = tmp_path / 'bad.dewy'
    source.write_text('\n'.join(f'bad{i}=():>int64=>"wrong"' for i in range(80)) +
                      '\nmain=():>void=>{printl(bad0())}\n')
    env = dict(os.environ, DEWY_CORE_LIB=str(ROOT / 'lib'), DEWY_EMIT_WORKERS='2',
               DEWY_EMIT_FORCE='1', DISPLAY='', WAYLAND_DISPLAY='', DEWY_NO_AUDIO='1')
    runs = [subprocess.run([compiler, 'build', source, '-o', tmp_path / 'bad'],
                           capture_output=True, env=env, timeout=60) for _ in range(2)]
    assert runs[0].returncode != 0
    assert (runs[0].returncode, runs[0].stdout, runs[0].stderr) == (
        runs[1].returncode, runs[1].stdout, runs[1].stderr)


@pytest.mark.parametrize("fused", [False, True])
def test_parallel_timing_order(compiler, tmp_path, fused):
    import re
    source = tmp_path / 'program.dewy'
    source.write_text(generate_dewy(240))
    env = dict(DEWY_FUSED='1' if fused else '0', DEWY_EMIT_WORKERS='2', DEWY_EMIT_FORCE='1', DEWY_PAR_TIME='1')
    if fused:
        env['DEWY_FUSED_TRACE'] = '1'
    reports = [outputs(compiler, source, tmp_path / 'program', ('--time',), env)[1]
               for _ in range(2)]
    if fused:
        assert b'fused worker:' in reports[0]  # Preserve detailed speculative traces too.
    # Durations measure each run; compare labels and worker/source order.
    normalized = [re.sub(rb'\d+(?:\.\d+)?', b'N', report) for report in reports]
    assert normalized[0] == normalized[1]
    workers = re.findall(rb'worker (\d+)\.\.(\d+):', reports[0])
    assert len(workers) == 2 and workers == sorted(workers, key=lambda w: int(w[0]))


def test_parallel_warnings_repeat(compiler, tmp_path):
    source = tmp_path / 'warnings.dewy'
    source.write_text('\n'.join(f'work{i}=(unused:int64):>int64=>{i}' for i in range(80)) +
                      '\nmain=():>void=>{printl(' + '+'.join(f'work{i}(1)' for i in range(80)) + ')}\n')
    env = dict(DEWY_EMIT_WORKERS='2', DEWY_EMIT_FORCE='1')
    first = outputs(compiler, source, tmp_path / 'warnings', extra=env)
    assert b'warning:' in first[1]
    assert outputs(compiler, source, tmp_path / 'warnings', extra=env) == first
