"""The hosted/native copy-inventory comparison (row C3) pairs and classifies.

`tools/copy_parity.py` removes identical notes, pairs what is left on a row
(by kind first, then across kinds, never pairing a string escape), and
requires every remaining difference to match a recorded class.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import copy_parity  # noqa: E402


def note(row, kind, site, reason, file='m.dewy'):
    return {'file': file, 'row': row, 'kind': kind, 'site': site, 'reason': reason}


def inventory(tmp_path, name, notes):
    path = tmp_path / f'{name}.json'
    path.write_text(json.dumps({'notes': notes}))
    return copy_parity.load(str(path))


def test_pairs_by_kind_then_across_kinds_but_not_strings(tmp_path):
    hosted = inventory(tmp_path, 'hosted', [
        note(1, 'record', 'returned', '`a` may be used again'),
        note(2, 'record', 'passed to a call', 'x'),
        note(3, 'cell', 'explicit copy', 'requested with `.copy`'),
        note(4, 'string', 'stored', 'built in the current frame'),
        note(5, 'array', 'iterated', 'stays owned by its container'),
    ])
    native = inventory(tmp_path, 'native', [
        note(1, 'record', 'returned', '`b` may be used again'),
        note(2, 'record', 'donated to a call', 'y'),
        note(3, 'record', 'explicit copy', 'requested with `.copy`'),
        note(4, 'record', 'kept', 'z'),
    ])
    found = {(d['row'], d['side'], d['kind']) for d in copy_parity.differences(hosted, native)}
    # Row 1 is identical after names are collapsed.
    assert not any(row == 1 for row, _side, _kind in found)
    assert (2, 'paired', 'record') in found
    assert (3, 'paired', 'cell => record') in found
    assert (4, 'hosted-only', 'string') in found and (4, 'native-only', 'record') in found
    assert (5, 'hosted-only', 'array') in found


def test_recorded_classes_cover_each_difference_kind():
    classes = json.loads((ROOT / 'tests/fixtures/copy_parity_classes.json').read_text())
    assert all(entry['explanation'] for entry in classes)
    cases = [
        dict(side='hosted-only', kind='string', site='stored', reason='this string is a parameter'),
        dict(side='paired', kind='cell => record', site='explicit copy', reason='a => b'),
        dict(side='hosted-only', kind='cell', site='converted to a union', reason='the call result is a borrowed view of its receiver'),
        dict(side='native-only', kind='record', site='donated to a call', reason='`_` may be used again, and no proven last-use move applies here'),
    ]
    for case in cases:
        assert copy_parity.classify(case, classes) is not None, case
    assert copy_parity.classify(dict(side='native-only', kind='record', site='kept', reason='something new'), classes) is None
