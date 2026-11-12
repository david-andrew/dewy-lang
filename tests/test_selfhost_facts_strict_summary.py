"""Strict callers must compute callee summaries without the array-length axiom."""
from tests.selfhost_build_double import compare_builds
from tests.selfhost_facts_double import LEAVES, compare_facts
from tests.support import compiler  # noqa: F401


def test_strict_summary_twins(compiler, tmp_path, monkeypatch):
    source = tmp_path / 'strict_summary.dewy'
    source.write_text('''$runtime_checks=false

length=(xs:array<int64>):>int64=>xs.length
ordinary=(xs:array<int64>):>int64=>length(xs)*16
strict=(xs:array<int64>):>int64=>{
    $no_assumed_bounds
    return length(xs)*16
}
main=()=>printl(ordinary([1 2 3])+strict([1 2 3]))
''')
    results = compare_builds(compiler, tmp_path, monkeypatch, LEAVES, [source])
    assert results[0][2] != 0
    assert 'fits int64' in results[0][4]


def test_record_field_length_summary_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'record_length_summary/accepted',
        'record_length_summary/grows',
        'record_length_summary/other_field',
    ]) > 0
