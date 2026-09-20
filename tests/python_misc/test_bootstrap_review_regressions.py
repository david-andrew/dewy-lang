"""Regression cases from the post-bootstrap compiler review."""
from test_bootstrap_structural_text import build_program_driver, check_structural_text
from test_bootstrap_lowering import ROOT


def test_review_regressions(tmp_path):
    cases = [(ROOT / 'tests/fixtures' / f'{name}.dewy').read_text() for name in (
        'native_field_store_aliases', 'native_raw_record_arguments',
        'native_power_operator', 'native_prefixed_combining_quote',
    )]
    errors = [(ROOT / 'tests/fixtures/prototype_shadowed_intrinsic.dewy').read_text()]
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=cases, errors=errors)
