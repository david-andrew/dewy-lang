"""A union's unique array alternative supplies literal element context."""
import test_bootstrap_check as source_values

CASES = [
    'let choose=(missing:bool):>array<int64>|none=>{if missing return [] return [42]}',
    "Failure:type=[why:string]\nlet choose=(missing:bool):>array<int64>|Failure=>{if missing return [] return Failure[why='missing']}",
    'let values:array<uint8>|none=[]\nvalues',
    'let values:array<uint8>|none=[42]\nvalues',
    'let values:array<array<int64>>|none=[[]]\nvalues',
    'let use=(values:array<int64>|none):>void=>void\nuse([])',
    'let choose=(flag:bool):>array<int64>|none=>if flag [] else none',
    'let values:array<int64>|none=[]\nif values isnt? none {values.push(42)}\nvalues',
    'let values:array<int64>|none=[]\nvalues=[42 43]\nvalues',
    'let values:array<int64>|none=[]\nvalues=none\nvalues',
]
ERROR_CASES = [
    'let values:array<int64>|array<string>=[]',
    'let values:array<int64>|array<string>=[42]',
    'let values:array<int64 length=1>|none=[]',
    "let values:array<int64>|none=['wrong']",
]


def test_native_unique_union_array_context(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERROR_CASES)
    source_values.test_native_source_values(tmp_path, function_types=True)
