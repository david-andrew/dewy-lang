"""A partitioned check decides the no-traps default's obligations in each
process for its own roots; a failure anywhere is decided again serially, so
every worker count reports the same errors and builds the same program."""
import os
import subprocess

from tests.support import ROOT, compiler  # noqa: F401
from tools.compiler.speed import generate_dewy

# A root another root calls: proven only knowing its result length.
CALLEE = '''make=(n:int64):>array<int64>=>fill(int64(1) n)
pick=():>int64=>{
    let xs=make(4)
    return xs[3]
}
'''
UNPROVEN = 'bad=(xs:array<int64> i:int64):>int64=>xs[i]\n'


def build(compiler, source, out, workers, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    env.update(DEWY_CORE_LIB=str(ROOT / 'lib'), DEWY_EMIT_WORKERS=str(workers), DEWY_PAR_TIME='1', **extra)
    return subprocess.run([compiler, 'build', source, '-o', out], env=env, capture_output=True, text=True, timeout=120)


def program(extra):
    workload = generate_dewy(600)
    return workload.replace('work300=', extra + 'work300=') + 'printl"{pick()}"\n'


def test_partitioned_roots_prove(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'proved.dewy'
    source.write_text(program(CALLEE))
    serial = build(compiler, source, tmp_path / 'one', 1)
    assert serial.returncode == 0, serial.stderr
    parallel = build(compiler, source, tmp_path / 'four', 4)
    assert parallel.returncode == 0, parallel.stderr
    assert 'workers checked' in parallel.stderr
    assert (tmp_path / 'one').read_bytes() == (tmp_path / 'four').read_bytes()


def test_partitioned_root_unproven(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'unproven.dewy'
    source.write_text(program(CALLEE + UNPROVEN))
    results = []
    for workers, extra in ((1, {}), (2, {}), (4, {}), (4, {'DEWY_FUSED_FAIL_WORKER': '1'})):
        run = build(compiler, source, tmp_path / 'bad', workers, **extra)
        assert run.returncode != 0
        results.append([line for line in run.stderr.splitlines() if 'error' in line])
    assert results[0] and 'cannot prove index is in bounds' in results[0][0]
    assert all(r == results[0] for r in results)
