"""Cold expression helpers agree with the frozen twin on their existing golden cases."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

PATHS = (
    'tests/cases/record/function_field_sibling.dewy',
    'tests/cases/object/static_calls.dewy',
    'tests/cases/frontend/m_forms_direct_forms_identity_1.dewy',
    'tests/cases/debugging/breakpoint_quit.dewy',
    'tests/cases/console/streams.dewy',
    'tests/cases/byte_read/unproven.dewy',
)


def test_expr_routes_match_twin(compiler, tmp_path, monkeypatch):
    nested = tmp_path / 'é'
    nested.mkdir()
    source = nested / 'breakpoint.dewy'
    source.write_text('main=()=>{let x=3; $breakpoint; printl(x)}\n')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('expr_routes',), (*PATHS, source))
    assert results[-1][2] == 0
