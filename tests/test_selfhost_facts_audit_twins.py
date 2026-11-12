"""Recent fact-proof branches agree with their frozen Jo implementations."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_exact_zero_and_share_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'generic_own_zero/guard',
        'generic_own_zero/different',
        'dogfood37_proofs/share_of_length_proves',
        'dogfood37_proofs/share_above_divisor_rejected',
        'dogfood38_proofs/ring_head_wraps_by_length',
        'dogfood38_proofs/ring_head_no_upper',
    ]) > 0


def test_map_entry_and_key_callback_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'dogfood38_followups/global_keys_after_dict_loop',
        'dogfood38_followups/global_keys_dict_loop_writes_rejected',
        'dogfood38_followups/sorted_key_record_keys',
        'dogfood38_proofs/key_set_sorted_by_entry',
        'dogfood38_proofs/key_set_sorted_other_map',
    ]) > 0


def test_readonly_call_counted_push_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'dogfood38_proofs/range_push_row_call_reads',
        'dogfood38_proofs/range_push_row_call_lends',
        'dogfood38_followups/min_by_nested_literal_loops',
        'dogfood38_followups/min_by_nested_break_rejected',
    ]) > 0


def test_range_push_and_replacement_rows_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'dogfood38_proofs/range_push_row_reads_previous',
        'dogfood38_proofs/range_push_row_off_by_one',
        'dogfood38_proofs/range_push_count_negative_end',
        'dogfood38_proofs/row_swap_edit_distance',
        'dogfood38_proofs/row_swap_one_short',
    ]) > 0


def test_push_widening_help_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'dogfood38_proofs/pushed_wide_value_names_array',
        'dogfood38_proofs/pushed_wide_value_typed_array',
    ]) == 0


def test_swap_and_gpu_readonly_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'default_proofs/swap_in_loop_keeps_length',
        'default_proofs/swap_loop_with_pop',
        'gpu_broadcast/guard_elements',
        'gpu_broadcast/guard_after_write',
    ]) > 0


def test_growing_length_loop_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'dogfood37_proofs/growth_keeps_position',
        'dogfood37_proofs/growth_pop_after_rejected',
        'dogfood37_proofs/growth_helper_shrinks_rejected',
    ]) > 0
