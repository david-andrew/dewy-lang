"""Truncated text is a diagnostic, never a panic or a hang: a bounded run of the truncation
fuzzer (tools/compiler/truncation_fuzz.py) over the syntax and truncated golden cases."""
from tests.support import compiler  # noqa: F401  (fixture)
from tools.compiler import truncation_fuzz


def test_truncated_prefixes_are_diagnosed(compiler, tmp_path):  # noqa: F811
    sources = [p for p in truncation_fuzz.corpus()
               if p.parent.name in ('syntax', 'truncated') and p.parent.parent.name == 'cases']
    result = truncation_fuzz.fuzz(compiler, sources, per_file=3, seed=1, workers=2, work=tmp_path, quiet=True)
    assert result['prefixes'] > 100
    assert not result['failures'], sorted(result['failures'])
