"""Pending library bodies are inherited by partition workers, not checked again."""
import re

from tests.support import compiler
from tests.test_core_fused_determinism import build, check, pytestmark
from tools.compiler.speed import generate_dewy


def test_partitioned_library_closure(compiler, tmp_path):
    source = tmp_path / 'library.dewy'
    # String interpolation and numeric operations need runtime instances, some
    # still pending after the root prefix. Preserve diagnostics across the fork.
    source.write_text(generate_dewy(600).replace(
        'let s="item 400"', 'let unused_library_guard=1\n    let s="item 400"'))
    check(compiler, source, tmp_path)
    _, timed = build(compiler, source, tmp_path / 'library-trace', 4, DEWY_PAR_TIME='1')
    shared = re.search(r'pcheck: checked (\d+) pending library instances before fork', timed)
    assert shared and int(shared.group(1)) > 0, timed
    assert 'pcheck: 4 workers checked 598 roots' in timed
    assert 'pcheck: closed-state check rejected' not in timed
