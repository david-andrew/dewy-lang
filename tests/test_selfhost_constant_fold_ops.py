"""Constant-check folding (time literals, regex and melody patterns) agrees with frozen Jo."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

CASES = '''dogfood/09_logs dogfood/11_markdown dogfood/125_markdown_html dogfood/144_shift_roster
dogfood/145_log_analyzer dogfood/24_wordcount_cli dogfood/55_tiny_regex dogfood37_proofs/duration_constant_coerces
dogfood37_proofs/quantize_instant_utc_minute facts/regex_capture_changed facts/regex_capture_dynamic
facts/regex_capture_lengths facts/regex_capture_missing_group facts/regex_capture_pattern_changed
melody_check/computed_text_needs_opt_in melody_check/literal_fits melody_check/literal_needs_no_opt_in
melody_check/runtime_text search/regex_error_message search/regex_limits time/core_arithmetic
time/machine_zone time/zoned_meetings'''.split()


def test_constant_fold_ops_match_twin(compiler, tmp_path, monkeypatch):
    results = compare_builds(compiler, tmp_path, monkeypatch, ('constant_fold_ops',),
                             [f'tests/cases/{c}.dewy' for c in CASES])
    assert any(r[1] == 0 for r in results) and any(r[1] != 0 for r in results)
