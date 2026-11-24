"""The recorded-output oracle for leaf probes: records, merges and checks."""
import json

import pytest

from tests import leaf_oracle


@pytest.fixture
def oracle(tmp_path, monkeypatch):
    monkeypatch.setattr(leaf_oracle, 'FIXTURES', tmp_path / 'outputs')
    monkeypatch.setattr(leaf_oracle, '_loaded', {})
    monkeypatch.setattr(leaf_oracle, '_ordinals', leaf_oracle.defaultdict(int))
    monkeypatch.setattr(leaf_oracle, 'capture_dir', tmp_path / 'capture')
    (tmp_path / 'capture').mkdir()
    return tmp_path


def run(monkeypatch, mode, test, outputs):
    monkeypatch.setattr(leaf_oracle, 'mode', mode)
    monkeypatch.setattr(leaf_oracle, 'current', ('test_probe', test))
    for status, output in outputs:
        leaf_oracle.check((), status, output)


def test_capture_then_check(oracle, monkeypatch):
    big = bytes(range(256)) * 200
    run(monkeypatch, 'capture', 't[default]', [(0, b'a\n'), (46, b'call-error:2\n'), (0, big)])
    assert leaf_oracle.merge(oracle / 'capture') == 1
    runs = json.loads((oracle / 'outputs/test_probe.json').read_text())['t[default]']
    assert [r['status'] for r in runs] == [0, 46, 0]
    assert runs[0]['stdout'] == 'a\n' and runs[2]['bytes'] == len(big)
    leaf_oracle._ordinals.clear()
    run(monkeypatch, 'expected', 't[default]', [(0, b'a\n'), (46, b'call-error:2\n'), (0, big)])


@pytest.mark.parametrize('runs', [
    [(0, b'a\n'), (46, b'call-error:3\n')],      # a changed answer
    [(0, b'a\n'), (0, b'call-error:2\n')],       # a changed status
])
def test_check_rejects_a_difference(oracle, monkeypatch, runs):
    run(monkeypatch, 'capture', 't', [(0, b'a\n'), (46, b'call-error:2\n')])
    leaf_oracle.merge(oracle / 'capture')
    leaf_oracle._ordinals.clear()
    with pytest.raises(AssertionError):
        run(monkeypatch, 'expected', 't', runs)


def test_unrecorded_run_fails(oracle, monkeypatch):
    run(monkeypatch, 'capture', 't', [(0, b'a\n')])
    leaf_oracle.merge(oracle / 'capture')
    leaf_oracle._ordinals.clear()
    with pytest.raises(AssertionError):
        run(monkeypatch, 'expected', 't', [(0, b'a\n'), (0, b'more\n')])


def test_merge_rejects_unstable_output(oracle, monkeypatch):
    run(monkeypatch, 'capture', 't', [(0, b'1\n')])
    leaf_oracle._ordinals.clear()
    run(monkeypatch, 'capture', 't', [(0, b'2\n')])
    with pytest.raises(AssertionError):
        leaf_oracle.merge(oracle / 'capture')
