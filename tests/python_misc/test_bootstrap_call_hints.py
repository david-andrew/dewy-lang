"""An expected storage type is not always a useful overload-selection hint."""
import test_bootstrap_check as source_values

CASES = [
    'let f=(a:int64 b:int64):>uint8=>__load_u8__(a+b)',
    'let f=(a:int64 b:int64 c:int64):>uint8=>__load_u8__(a + b + c)',
    'let take=(x:any):>int64=>42\nlet f=(a:int64 b:int64):>int64=>take(a+b)',
    'Choice:type=int64|[message:string]\nlet f=(a:int64 b:int64):>Choice=>a+b',
    'let f=(a:int64 b:int64):>any=>a+b',
]


def test_native_call_result_hints(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', [])
    source_values.test_native_source_values(tmp_path, function_types=True)
