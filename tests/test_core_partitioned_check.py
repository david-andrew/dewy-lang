"""Root checking shares the lifetime and failure handling of fused workers."""
import os
import subprocess

import pytest

from tests.test_core_fused_determinism import build, check, pytestmark
from tests.support import ROOT, compiler
from tools.compiler.speed import generate_dewy


def test_partitioned_roots(compiler, tmp_path):
    source = tmp_path / 'roots.dewy'
    # Diagnostics from different partitions must retain serial source order.
    text = generate_dewy(600)
    for i in (10, 200, 400, 590):
        text = text.replace(f'let s="item {i}"', f'let unused_{i}=1\n    let s="item {i}"')
    source.write_text(text)
    check(compiler, source, tmp_path)
    _, timed = build(compiler, source, tmp_path / 'checked', 4, SLOPPY_PAR_TIME='1')
    assert 'pcheck: 4 workers checked 598 roots' in timed, timed
    serial, err = build(compiler, source, tmp_path / 'serial', 4, DEWY_PCHECK='0')
    assert serial == (tmp_path / 'one').read_bytes()
    assert 'unused_10' in err and 'unused_590' in err


@pytest.mark.parametrize('failure', ['check', 'barrier', 'emit'])
def test_partitioned_worker_failure(compiler, tmp_path, failure):
    source = tmp_path / 'failure.dewy'
    source.write_text(generate_dewy(600))
    base, errors = build(compiler, source, tmp_path / 'one', 1)
    option = {'DEWY_FUSED_FAIL': '1'} if failure == 'emit' else {'DEWY_PCHECK_FAIL': failure}
    got, err = build(compiler, source, tmp_path / 'four', 4, **option)
    assert (got, err) == (base, errors)


def test_partitioned_new_instance_falls_back(compiler, tmp_path):
    source = tmp_path / 'new-instance.dewy'
    source.write_text(generate_dewy(600).replace('let s="item 590"', 'printl"late {a}"\n    let s="item 590"'))
    base, errors = build(compiler, source, tmp_path / 'one', 1)
    got, err = build(compiler, source, tmp_path / 'four', 4)
    assert (got, err) == (base, errors)
    _, timed = build(compiler, source, tmp_path / 'timed', 4, SLOPPY_PAR_TIME='1')
    assert 'pcheck: closed-state check rejected' in timed


def test_partitioned_error_order(compiler, tmp_path):
    source = tmp_path / 'errors.dewy'
    source.write_text(generate_dewy(600).replace('let s="item 20"', 'let s=not_a_name').replace('let s="item 590"', 'let s=another_missing_name'))
    results = []
    for workers in (1, 2, 4):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
        env.update(DEWY_CORE_LIB=str(ROOT / 'lib'), SLOPPY_EMIT_WORKERS=str(workers))
        r = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'bad'], env=env,
                           capture_output=True, timeout=120)
        assert r.returncode != 0
        results.append((r.returncode, r.stdout, r.stderr))
    assert results[0] == results[1] == results[2]


@pytest.mark.core_quick
def test_partitioned_below_fused_gate(compiler, tmp_path):
    source = tmp_path / 'small.dewy'
    source.write_text('\n'.join(f'f{i}=(x:int64):>int64=>x+{i}' for i in range(140)) +
                      '\nlet sum:int64=0\n' + '\n'.join(f'sum+=f{i}({i})' for i in range(140)) +
                      '\nprintl"{sum}"\n')
    base, errors = build(compiler, source, tmp_path / 'one', 1)
    got, err = build(compiler, source, tmp_path / 'four', 4)
    assert (got, err) == (base, errors)
    _, timed = build(compiler, source, tmp_path / 'timed', 4, SLOPPY_PAR_TIME='1')
    assert 'pcheck: 4 workers checked 138 roots' in timed
    assert 'fused: 4 workers,' not in timed


@pytest.mark.parametrize('addition', [
    '\nextra=():>void=>{let named=(x:int64):>int64=>x+1; printl"{named(2)}"}\n',
    '\nlate=():>void=>{let new_type:array<string>=[]; printl"{new_type}"}\n',
])
def test_partitioned_unsupported_program(compiler, tmp_path, addition):
    source = tmp_path / 'unsupported.dewy'
    source.write_text(generate_dewy(600) + addition)
    base, errors = build(compiler, source, tmp_path / 'one', 1)
    got, err = build(compiler, source, tmp_path / 'four', 4)
    assert (got, err) == (base, errors)
    _, timed = build(compiler, source, tmp_path / 'timed', 4, SLOPPY_PAR_TIME='1')
    assert 'pcheck: 4 workers checked' not in timed


@pytest.mark.core_quick
def test_partitioned_cross_worker_inline(compiler, tmp_path):
    source = tmp_path / 'chain.dewy'
    source.write_text('f0=(x:int64):>int64=>x\n' +
                      '\n'.join(f'f{i}=(x:int64):>int64=>f{i-1}(x)+{i}' for i in range(1, 180)) +
                      '\nprintl"{f179(1)}"\n')
    base, errors = build(compiler, source, tmp_path / 'one', 1, SLOPPY_EMIT_FORCE='1')
    for workers in (2, 4):
        got, err = build(compiler, source, tmp_path / f'w{workers}', workers, SLOPPY_EMIT_FORCE='1')
        assert (got, err) == (base, errors)
    _, timed = build(compiler, source, tmp_path / 'timed', 4,
                     SLOPPY_EMIT_FORCE='1', SLOPPY_PAR_TIME='1')
    assert 'pcheck: 4 workers checked 178 roots' in timed
    assert subprocess.run([tmp_path / 'w4'], capture_output=True, text=True).stdout == '16111\n'


def test_partitioned_static_policy_stays_serial(compiler, tmp_path):
    source = tmp_path / 'static.dewy'
    source.write_text('\n'.join(f'f{i}=(x:int64):>int64=>x+{i}' for i in range(140)) +
                      '\nlet sum:int64=0\n' + '\n'.join(f'sum+=f{i}({i})' for i in range(140)) +
                      '\nprintl"{sum}"\n')
    policy = {'DEWY_INTERNAL_FACT_POLICY': 'require-static', 'SLOPPY_EMIT_FORCE': '1'}
    base, errors = build(compiler, source, tmp_path / 'one', 1, **policy)
    got, err = build(compiler, source, tmp_path / 'four', 4, **policy)
    assert (got, err) == (base, errors)
    _, timed = build(compiler, source, tmp_path / 'timed', 4, SLOPPY_PAR_TIME='1', **policy)
    assert 'pcheck:' not in timed
