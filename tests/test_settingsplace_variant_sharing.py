"""Inherited checks reuse a body already required to prove its obligations."""
import re
import subprocess

from tests.selfhost_lsp_double import leaf_compilers
from tests.support import compiler  # noqa: F401


SOURCE = '''pick=(xs:array<int64>):>int64=>{
 $runtime_assert xs.length >? 0
 xs[0]
}
ordinary=(xs:array<int64>):>int64=>pick(xs)
checked=(xs:array<int64>):>int64=>{
 $runtime_checks
 pick(xs)
}
main=()=>{
 printl(ordinary([41]))
 printl(checked([42]))
 printl(checked([43]))
}
'''


def test_required_static_body_is_shared_by_inherited_checks(compiler, tmp_path):
    source = tmp_path / 'shared.dewy'
    source.write_text(SOURCE)
    result = subprocess.run([compiler, 'build', source, '--ir', '-o', tmp_path / 'shared'],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    assert len(re.findall(r'^fn f_pick_\d+ ', result.stdout, re.MULTILINE)) == 1
    run = subprocess.run([tmp_path / 'shared'], capture_output=True, text=True, timeout=30)
    assert (run.returncode, run.stdout) == (0, '41\n42\n43\n'), run.stderr


def test_checker_instances_checker_program_directive_ops_queries_twins(compiler, tmp_path, monkeypatch):
    from tests.support import ROOT
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    compilers = leaf_compilers(compiler, tmp_path,
                              ('checker_instances', 'checker_program', 'directive_ops', 'directive_queries'))
    source = tmp_path / 'shared.dewy'
    results = []
    for body in (SOURCE, SOURCE.replace(' $runtime_assert xs.length >? 0\n', '')):
        source.write_text(body)
        pair = []
        for binary in compilers:
            result = subprocess.run([binary, 'check', source, '--obligations'],
                                    capture_output=True, text=True, timeout=90)
            pair.append((result.returncode, result.stdout, result.stderr))
        assert pair[0] == pair[1]
        results.append(pair[0])
    assert results[0][0] == 0, results[0][2]
    assert results[1][0] != 0
    assert 'cannot prove index is in bounds' in results[1][2]
