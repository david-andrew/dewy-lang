"""Foreign function layouts and recursive boxes match the frozen checker."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_checker_ffi_layout_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [p for group in ('ffi', 'ffi_structs', 'coverlayout_ffi')
             for p in sorted((ROOT / 'tests/cases' / group).glob('*.dewy'))]
    boxed = tmp_path / 'recursive.jo'
    boxed.write_text('struct Node:\n    next: Node?\nextern use_node = (n: *Node)\n'
                     'main = ():\n    n: Node\n    use_node(&n)\n')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_ffi_layout',), [*cases, boxed])
    assert results[-1][2] != 0 and 'cannot cross the C ABI' in results[-1][4]
    assert any(r[2] == 0 for r in results)
