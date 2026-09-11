"""Mixed-width comparisons retain a checked conversion to the left word."""

import test_bootstrap_check as source_values

CASES = [
    f'let compare=(left:{left} right:{right}):>bool=>left {operator} right'
    for left, right in [('int64', 'uint64'), ('uint64', 'int64'),
                        ('uint8', 'int16'), ('int8', 'uint16'), ('int32', 'uint8')]
    for operator in ['<?', '<=?', '>?', '>=?', '=?', 'not=?']
] + [
    'let compare=(length:addr? limit:uint64<n => n <=? 281474976710655>):>bool=>if length isnt? none length >=? limit else false',
]


def test_native_mixed_word_comparisons(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', [])
    source_values.test_native_source_values(tmp_path, function_types=True)
