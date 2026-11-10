"""The compile-speed gate's unbuildable-source fallback: a base that cannot build this checkout's program is
measured on its own older copy, which must be announced, split and gated, never silently compared."""
import pytest

from tools.compiler import speed


def test_accept_reason_names_a_program_by_directory_number_or_word():
    row = 'ladder 84_tensor_broadcast'
    assert speed.names_item('84_tensor_broadcast uses exact int', row)
    assert speed.names_item('84 now proves what it checked at run time (+1.16% on 84 only)', row)
    assert speed.names_item('exact int in ladders 79, 84 and 90.', row)
    assert speed.names_item('flagship 97 proves its parsing', 'flagship 97_notes_service')
    assert speed.names_item('hello loads more', 'hello')
    assert not speed.names_item('bigger inlining budget', row)
    assert not speed.names_item('program 184 and 840 grew', row)
    assert not speed.names_item('cost 0.84 more', row)
    assert not speed.names_item('97 only', row)


def fallback(role='base', old=50_300_000, same=50_500_000, new=83_900_000, name='ladder 84_tensor_broadcast'):
    return speed.Fallback(role, name, 'c17f785a1c', old, new, same)


def test_fallback_row_reports_both_costs_and_splits_them():
    fb = fallback()
    assert fb.compiler == pytest.approx(0.40)
    assert fb.growth == pytest.approx(66.14)
    text = '\n'.join(fb.lines())
    assert 'FALLBACK' in text and 'different programs' in text
    assert '0.0503 G' in text and '0.0505 G' in text and '0.0839 G' in text
    assert '(compiler alone)' in text and "(this source's own growth)" in text
    unsplit = '\n'.join(fallback(same=None).lines())
    assert 'cannot build that either' in unsplit and 'not split' in unsplit


def test_grown_source_fails_unless_an_accept_line_names_the_program():
    fb = fallback()
    failures, accepted = speed.fallback_verdict([fb], 1.0, {'base': []})
    assert len(failures) == 1 and not accepted
    assert 'ladder 84_tensor_broadcast' in failures[0] and '+66.14%' in failures[0]
    assert '0.0503 G old source -> 0.0839 G this source' in failures[0]
    # an accept line that names another program, or none, waives nothing
    for reasons in (['97 now proves what it checked (+1.16% on 97 only)'], ['bigger inlining budget']):
        assert speed.fallback_verdict([fb], 1.0, {'base': reasons})[0]
    for reasons in (['84 uses exact int'], ['84_tensor_broadcast stores exact ints']):
        failures, accepted = speed.fallback_verdict([fb], 1.0, {'base': reasons})
        assert not failures and len(accepted) == 1 and reasons[0] in accepted[0]


def test_unsplit_growth_is_unknown_and_fails():
    failures, _ = speed.fallback_verdict([fallback(same=None)], 1.0, {'base': []})
    assert len(failures) == 1 and 'growth is unknown' in failures[0]


def test_source_that_did_not_grow_passes_without_an_accept_line():
    assert speed.fallback_verdict([fallback(old=90_000_000, same=90_300_000, new=50_000_000)], 1.0, {}) == ([], [])


def test_checkpoint_rows_read_the_checkpoints_accept_lines_only():
    fb = fallback(role='checkpoint')
    assert speed.fallback_verdict([fb], 1.0, {'base': ['84 uses exact int'], 'checkpoint': []})[0]
    assert not speed.fallback_verdict([fb], 1.0, {'base': [], 'checkpoint': ['84 uses exact int']})[0]


class Counting:
    """A counter whose compiler can only build the base's own copies (a base predating the source)."""
    def __init__(self):
        self.seen = []

    def count(self, command, env):
        path = command[2]
        self.seen.append(path)
        if 'inputs' not in str(path):
            raise speed.CompileError('error: the base cannot prove this')
        return 100


def test_measure_item_falls_back_to_the_bases_own_copy_and_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(speed, 'stage', lambda toolchain: tmp_path / 'active')
    counter = Counting()
    base = speed.Toolchain('base c17f785a1c', tmp_path / 'bin', tmp_path / 'lib', tmp_path / 'inputs')
    source = 'tests/ladder/84_tensor_broadcast/core.dewy'
    assert speed.measure_item(counter, base, source, []) == (100, tmp_path / 'inputs' / source)
    notes: list[str] = []
    assert speed.measure(counter, base, source, [], notes) == 100
    assert len(notes) == 1 and notes[0].startswith('FALLBACK:') and source in notes[0]
    # no inputs (the candidate) or an absolute source (a generated program): a compile error is an error
    candidate = speed.Toolchain('candidate', tmp_path / 'bin', tmp_path / 'lib')
    with pytest.raises(RuntimeError, match='cannot build'):
        speed.measure_item(counter, candidate, source, [])
    with pytest.raises(RuntimeError, match='cannot build'):
        speed.measure_item(counter, base, str(tmp_path / 'synthetic.dewy'), [])


def flagship_names():
    return [name for name, _, _ in speed.panel(False) if name.startswith('flagship ')]


def test_throughput_gate_leaves_different_sources_out(monkeypatch):
    names = flagship_names()
    report = lambda lines: ('instructions: 1000; root 10: load 5 optimize 1\nnodes: root 8, library 0, shared 0\n'
                            f'lines: root 1, library {lines}, instance 0; 0 instances; library parsed 1, bodies reached 0 of 0\n')
    monkeypatch.setattr(speed, 'time_run', lambda toolchain, source: report(100))
    candidate, base = speed.Toolchain('candidate', None, None), speed.Toolchain('base', None, None)
    counts = {n: 1000 for n in names}
    base_counts = dict(counts)
    # one flagship's source grew 50% against the base's older copy: same lines, more instructions
    grown = names[0]
    counts[grown] = 1500
    assert speed.throughput_gate(candidate, base, counts, base_counts, 1.0)
    assert speed.throughput_gate(candidate, base, counts, base_counts, 1.0, skip={grown}) == []
    assert speed.throughput_gate(candidate, base, counts, base_counts, 1.0, skip=set(names)) == []


def test_phase_gate_leaves_different_sources_out(monkeypatch):
    names = [source for name, source, _ in speed.panel(False) if name.startswith('flagship ')]
    report = lambda check: (f'instructions: 1000; shared 10: check {check} optimize 1; root 10: load 5 optimize 1\n'
                            'nodes: root 8, library 0, shared 0\n'
                            'lines: root 1, library 40, instance 0; 0 instances; library parsed 1, bodies reached 0 of 0\n')
    # the candidate's first flagship costs twice what the base's older copy did; the rest are unchanged
    monkeypatch.setattr(speed, 'time_run', lambda toolchain, source:
                        report(200 if toolchain.label == 'candidate' and source == names[0] else 100))
    candidate, base = speed.Toolchain('candidate', None, None), speed.Toolchain('base', None, None)
    assert [row for row, _ in speed.cost_model(candidate, base, 1.0)] == ['resolve+check']
    assert speed.cost_model(candidate, base, 1.0, skip={'flagship ' + names[0].split('/')[-2]}) == []
