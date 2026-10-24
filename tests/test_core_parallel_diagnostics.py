"""Diagnostic transactions must follow reachable serial order, including fallback."""
import os
import subprocess

import pytest

from tests.support import ROOT, compiler
from tests.test_core_fused_determinism import build, check, pytestmark
from tools.compiler.speed import generate_dewy

LOST = '''import netplay
World:type=[n:int64=0]
bad=(n:int64):>int64=>{return n+int64(random()*10.0)}
stepA=(s:World inputs:array<int64>):>World=>{return World[n=bad(s.n)+inputs.length]}
stepB=(s:World inputs:array<int64>):>World=>{return World[n=bad(s.n)+inputs.length]}
first=():>void=>{let game=netplay.session(World[] @stepA players=2 me=0); printl"{game.state.n}"}
second=():>void=>{let game=netplay.session(World[] @stepB players=2 me=0); printl"{game.state.n}"}
second()
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('automatic', [False, True])
@pytest.mark.parametrize('shared', [False, True])
def test_rollback_warning_order(compiler, tmp_path, automatic, shared):
    source = tmp_path / 'rollback.dewy'
    text = LOST
    if shared:
        # Spread the factories through root work so their journals come from
        # different partitions; serial reachability still visits second first.
        lines = text.splitlines()
        workload = generate_dewy(600)
        workload = workload.replace('work150=', lines[5] + '\nwork150=')
        workload = workload.replace('work450=', lines[6] + '\nwork450=')
        text = '\n'.join(lines[:5]) + '\n' + workload + 'second()\nfirst()\n'
    elif automatic:
        text += generate_dewy(600)
    source.write_text((text) + "\n$runtime_checks\n")
    options = {} if automatic else {'DEWY_EMIT_FORCE': '1'}
    check(compiler, source, tmp_path, **options)
    base, err = build(compiler, source, tmp_path / 'serial', 1, **options)
    assert err.count('takes random numbers') == 1
    assert "stepB is netplay.session's tick" in err
    assert "stepA is netplay.session's tick" not in err
    for disabled in ({'DEWY_FUSED': '0'}, {'DEWY_FUSED_FAIL': '1'}, {'DEWY_FUSED_FAIL_WORKER': '1'}):
        got, errors = build(compiler, source, tmp_path / 'fallback', 4, **options, **disabled)
        assert (got, errors) == (base, err)


@pytest.mark.core_quick
@pytest.mark.parametrize('forced', [False, True])
def test_library_root_error_order(compiler, tmp_path, forced):
    source = tmp_path / 'errors.dewy'
    source.write_text('f0=():>float64=>path_length([1 2])\nf1=():>int64=>1\n'
                      'f2=():>int64=>missing_name\n' +
                      '\n'.join(f'f{i}=(x:int64):>int64=>x+{i}' for i in range(3, 130)) +
                      '\nprintl"{f0()}"\n')
    results = []
    for workers, disabled in ((1, False), (2, False), (4, False), (4, True)):
        env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
        env.update(DEWY_CORE_LIB=str(ROOT / 'lib'), DEWY_EMIT_WORKERS=str(workers))
        if forced:
            env['DEWY_EMIT_FORCE'] = '1'
        if disabled:
            env['DEWY_PCHECK'] = '0'
        run = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'bad'],
                             env=env, capture_output=True, timeout=120)
        assert run.returncode == 1
        results.append((run.returncode, run.stdout, run.stderr))
    assert all(result == results[0] for result in results)
    assert results[0][2].index(b"unknown name 'missing_name'") < results[0][2].index(b'in this call to path_length')


@pytest.mark.parametrize('mode', ['partitioned', 'fused', 'emission'])
@pytest.mark.parametrize('failed', ['0', '1'])
def test_partial_worker_failure(compiler, tmp_path, mode, failed):
    source = tmp_path / 'partial.dewy'
    source.write_text(generate_dewy(600))
    options = {'DEWY_EMIT_FORCE': '1'}
    if mode == 'fused':
        options['DEWY_PCHECK'] = '0'
    if mode == 'emission':
        options['DEWY_FUSED'] = '0'
    base = build(compiler, source, tmp_path / 'one', 1, **options)
    failure = 'DEWY_EMIT_FAIL_WORKER' if mode == 'emission' else 'DEWY_FUSED_FAIL_WORKER'
    for workers in (2, 4):
        got = build(compiler, source, tmp_path / 'partial', workers, **options, **{failure: failed})
        assert got == base
        _, trace = build(compiler, source, tmp_path / 'trace', workers, DEWY_PAR_TIME='1', **options, **{failure: failed})
        assert f'{"emit" if mode == "emission" else "fused"}: {workers} workers,' in trace
