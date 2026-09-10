"""Physical type factors and explicit rational part representations."""
import test_bootstrap_check as source_values

WORD = 'Rational:type=[numerator:int64 denominator:int64 & ~0]\n'
CASES = [
    'let f=(duration:int64 * Time):>void=>void',
    'let f=(duration:Time * int64):>void=>void',
    'let f=(value:(2 * Time) * (3 * Length)):>void=>void',
    'let f=(value:Time * (uint64 * Length)):>void=>void',
    'Duration:type=<T of real>(T * Time)\nlet f=(duration:Duration<int64>):>void=>void',
    WORD + 'let f=(duration:rational<int64> * Time):>void=>void',
    WORD + 'let f=(duration:rational<int64>):>void=>void',
]
ERRORS = [
    'let f=(value:string * Time):>void=>void',
    WORD + 'let f=(value:rational<uint8>):>void=>void',
]


def test_native_type_products(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
