"""Deferred bodies preserve eager parse precedence and ordered diagnostics."""
import os
import subprocess

import pytest

from tests.support import ROOT, compiler
from tests.test_core_fused_determinism import build, check, pytestmark
from tools.compiler.speed import generate_dewy


def compile_result(compiler, source, output, workers, *options):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(DEWY_CORE_LIB=str(ROOT / 'lib'), SLOPPY_EMIT_WORKERS=str(workers),
               SLOPPY_EMIT_FORCE='1')
    run = subprocess.run([compiler, *options, 'build', source, '-o', output],
                         env=env, capture_output=True, timeout=120)
    return run.returncode, run.stdout, run.stderr


@pytest.mark.parametrize('early', [0, 20, 200])
def test_lazy_parse_before_type_error(compiler, tmp_path, early):
    source = tmp_path / 'precedence.dewy'
    source.write_text(generate_dewy(600)
                      .replace(f'let s="item {early}"', 'let s=missing_name')
                      .replace('let s="item 590"', 'let s=)'))
    results = [compile_result(compiler, source, tmp_path / f'w{w}', w) for w in (1, 2, 4)]
    assert results[0] == results[1] == results[2]
    assert results[0][0] == 1
    assert b"error: expected an expression, found ')'" in results[0][2]
    assert b"unknown name" not in results[0][2]


def test_lazy_parse_errors_in_two_partitions(compiler, tmp_path):
    source = tmp_path / 'two-errors.dewy'
    source.write_text(generate_dewy(600)
                      .replace('let s="item 20"', 'let s=)')
                      .replace('let s="item 590"', 'let s=]'))
    results = [compile_result(compiler, source, tmp_path / f'w{w}', w) for w in (1, 2, 4)]
    assert results[0] == results[1] == results[2]
    assert results[0][0] == 1
    assert b"error: expected an expression, found ')'" in results[0][2]
    assert b"found ']'" not in results[0][2]


def test_lazy_warning_order_and_bytes(compiler, tmp_path):
    source = tmp_path / 'warnings.dewy'
    text = generate_dewy(600)
    for i in (0, 20, 200, 400, 590):
        text = text.replace(f'let s="item {i}"', f'let unused_{i}=1\n    let s="item {i}"')
    source.write_text(text)
    check(compiler, source, tmp_path, SLOPPY_EMIT_FORCE='1')
    _, err = build(compiler, source, tmp_path / 'warnings', 4, SLOPPY_EMIT_FORCE='1')
    lines = [line for line in err.splitlines() if 'unused_' in line]
    assert len(lines) == 5
    assert [next(i for i in (0, 20, 200, 400, 590) if f"'unused_{i}'" in line)
            for line in lines] == [0, 20, 200, 400, 590]
    _, timed = build(compiler, source, tmp_path / 'timed-lazy', 4,
                     SLOPPY_EMIT_FORCE='1', SLOPPY_PAR_TIME='1')
    assert 'pcheck: parsed deferred bodies before checking' in timed


@pytest.mark.parametrize('change', [
    ('let total:float64=0.0', 'let total:float64=(if a >? 0 {0.0} else {1.0})'),
    ('let total:float64=0.0', 'let total:float64=0.0\n    let callback=(x:int64):>int64=>x+1\n    total+=float64(callback(a))'),
    ('let total:float64=0.0', 'let total:float64=0.0\n    $assert(a >=? 0)'),
])
def test_lazy_contextual_body_identity(compiler, tmp_path, change):
    source = tmp_path / 'contextual.dewy'
    source.write_text(generate_dewy(160).replace(*change))
    base = compile_result(compiler, source, tmp_path / 'one', 1)
    for workers in (2, 4):
        got = compile_result(compiler, source, tmp_path / f'w{workers}', workers)
        assert got == base
        if got[0] == 0:
            assert (tmp_path / f'w{workers}').read_bytes() == (tmp_path / 'one').read_bytes()


def test_lazy_loop_else_identity(compiler, tmp_path):
    source = tmp_path / 'loop-else.dewy'
    source.write_text(generate_dewy(160).replace('let total:float64=0.0',
        'let total:float64=0.0\n    loop k in [0..2) {total+=float64(k)} else {total+=3.0}'))
    base = compile_result(compiler, source, tmp_path / 'one', 1)
    assert base[0] == 0, base[2]
    for workers in (2, 4):
        assert compile_result(compiler, source, tmp_path / f'w{workers}', workers) == base
        assert (tmp_path / f'w{workers}').read_bytes() == (tmp_path / 'one').read_bytes()


def test_lazy_parse_warnings_before_check_warnings(compiler, tmp_path):
    source = tmp_path / 'parse-warnings.dewy'
    text = generate_dewy(160).replace('let s="item 0"', 'let unused_early=1\n    let s="item 0"')
    text = text.replace('let s="item 150"',
                        'let maybe:int64?=none\n    let chosen=maybe ?? 0 + 1\n    total+=float64(chosen)\n    let s="item 150"')
    source.write_text(text)
    baseline = compile_result(compiler, source, tmp_path / 'one', 1)
    assert baseline[0] == 0, baseline[2]
    assert baseline[2].index(b'arithmetic binds') < baseline[2].index(b'unused_early')
    for workers in (2, 4):
        assert compile_result(compiler, source, tmp_path / f'w{workers}', workers) == baseline
        assert (tmp_path / f'w{workers}').read_bytes() == (tmp_path / 'one').read_bytes()


def test_lazy_replay_does_not_repeat_parse_warning(compiler, tmp_path):
    source = tmp_path / 'warning-then-error.dewy'
    source.write_text('notice=(x:int64?):>int64=>{return x ?? 0 + 1}\n' +
                      generate_dewy(160).replace('let s="item 150"', 'let s=)'))
    results = [compile_result(compiler, source, tmp_path / f'w{w}', w) for w in (1, 2, 4)]
    assert results[0] == results[1] == results[2]
    assert results[0][0] == 1
    assert results[0][2].count(b'warning:') == 1


def test_lazy_unused_generic_stays_eager(compiler, tmp_path):
    source = tmp_path / 'unused-generic.dewy'
    source.write_text(generate_dewy(160) + '\nunused=(x):>int64=>{let broken=)}\n')
    results = [compile_result(compiler, source, tmp_path / f'w{w}', w) for w in (1, 2, 4)]
    assert results[0] == results[1] == results[2]
    assert results[0][0] == 1
    assert b"error: expected an expression, found ')'" in results[0][2]
