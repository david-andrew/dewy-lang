"""Integer exclusions are source facts, including the numeric prelude's divisors."""
import test_bootstrap_check as source_values

CASES = [
    'let negative=(value:int64 & ~0):>bool=>value <? 0\nnegative(-1)',
    'let add=(value:int64 & ~0):>int64=>value+1\nadd(2)',
    'let divide=(value:int64 divisor:int64 & ~0):>int64=>value // divisor\ndivide(7 2)',
    'let compare=(value:int64 & ~(0|1)):>bool=>value >? 1\ncompare(2)',
    'Choice:type=0|[value:int64]\nNonzero:type=Choice & ~0\nlet read=(value:Nonzero):>int64=>value.value\nread([7])',
    'let negative=(value:~0 & int64):>bool=>value <? 0\nnegative(-1)',
    'Fixed:type=[raw:int64]\nlet nonzero=(value:Fixed):>bool=>value not=? 0\nnonzero([7])',
    'Fixed:type=[raw:int64]\nlet zero=(value:Fixed):>bool=>0 =? value\nzero([0])',
    'Rational:type=[numerator:int64 denominator:int64]\nlet zero=(value:Rational):>bool=>value =? 0\nzero([0 1])',
]
ERRORS = [
    'Bad:type=(0|[value:int64]) & ~1',
    'let value=[raw=7]\nvalue =? 0',
]


def test_native_numeric_contracts(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
