"""Compare plan keys, mark generations, invalidations and finished obligations across the slice-builder twins."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_build_double import compare_golden_cases
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_facts_slice_builder_twins(compiler, tmp_path, monkeypatch):
    compare_golden_cases(compiler, tmp_path, monkeypatch, "facts_slice_builder", (
        "facts/call_shares_keep_facts", "facts/call_shares_shrink",
        "facts/array_count_bounds", "facts/array_count_bounds_end",
        "facts/enum_member_store_index", "member_template/ordered_columns",
        "member_template/partial_byte_proof",
    ))


def test_facts_slice_builder_keys_and_marks(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv("DEWY_CORE_LIB", str(ROOT / "lib"))
    monkeypatch.setattr(selfhost_lsp_double, "DRIVER", """use 'main.jo'
use 'facts_slice_prep.dewy'
use 'facts_slice_builder.dewy'
use 'facts.jo'
use 'checker_tokens.dewy'
use 'effect_types.dewy'
use 'ast.jo'
main = ():
    loop i in [0..int(Tok.lazy) + 1):
        t = Tok(i)
        want = t == .eq or t == .ne or t == .gt or t == .lt or t == .ge or t == .le
        assert(fact_comparison(t) == want and fact_comparison_raw(i32(i)) == want)
    loop i in [0..5):
        assert(fact_root_key(PlaceIdentity(PlaceRoot(i), 9, 17)) == 136 + i)
    nodes.resize(11)
    fact_mark_begin()
    fact_mark_set(2, 19)
    assert(fact_mark_of(2) == 19)
    fact_mark_begin()
    assert(fact_mark_of(2) == 0)
    nodes.resize(2500)
    fact_mark_begin()
    fact_mark_set(2499, 7)
    assert(fact_mark_of(2) == 0 and fact_mark_of(2499) == 7)
    print("ok")
""")
    for binary in leaf_compilers(compiler, tmp_path, ("facts_slice_builder",)):
        result = subprocess.run([binary], capture_output=True, timeout=60)
        assert (result.returncode, result.stdout, result.stderr) == (0, b"ok\n", b"")
