"""Inference supplies the callback contract; its deleted annotation is unknown."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401

@pytest.mark.parametrize('tag', ['', '$parallel_safe\n'])
def test_batch4_parallel_annotation(compiler, tmp_path, tag):
    source=tmp_path/'callback.dewy'
    source.write_text(tag+'apply=(f:(x:int:>int) xs:array<int>):>array<int>=>[parallel x in xs f(x)]\nsquare=(x:int):>int=>x*x\nmain=()=>printl(apply(@square [1 2 3]))\n')
    result=subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    if tag:
        assert result.returncode != 0
    else:
        assert result.returncode == 0, result.stderr
