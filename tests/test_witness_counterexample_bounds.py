"""Counterexample differences use mathematical arithmetic at signed endpoints."""
import itertools
import re
import subprocess

import pytest

from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler


def test_witness_counterexample_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch,
                         ['witness_bounds/minimum', 'witness_bounds/guarded'],
                         leaves=('witness_ops',)) == 1


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
def test_witness_difference_oracle(compiler, tmp_path, extension):
    minimum, maximum = -(1 << 63), (1 << 63) - 1
    ends = [minimum, minimum + 1, -1, 0, 1, maximum - 1, maximum]
    cases = list(itertools.product(ends, repeat=3))
    text = (ROOT / f'compiler/witness_ops.{extension}').read_text()
    definition = re.search(r'(?ms)^wit_difference_holds\s*=.*?(?=^\w|\Z)', text).group()
    if extension == 'dewy':
        calls = '\n'.join(f'printl(wit_difference_holds({x} {y} {limit}))'
                          for x, y, limit in cases)
        source = '$runtime_checks\n\n' + definition + '\nmain=()=>{\n' + calls + '\n}\n'
    else:
        calls = '\n'.join(f'    print(wit_difference_holds({x}, {y}, {limit}))'
                          for x, y, limit in cases)
        source = (f'const FACT_MIN = {minimum}\nconst FACT_MAX = {maximum}\n'
                  + definition + '\nmain = ():\n' + calls + '\n')
    path = tmp_path / f'predicate.{extension}'
    path.write_text(source)
    binary = tmp_path / 'predicate'
    built = subprocess.run([compiler, 'build', path, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    run = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == [str(x - y <= limit).lower() for x, y, limit in cases]
