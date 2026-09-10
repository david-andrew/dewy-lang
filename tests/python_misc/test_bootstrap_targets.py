"""Target provenance selects platform arms without changing literal flows."""
import test_bootstrap_check as source_values

CASES = [
    '$target',
    '$target =? "x86_64"',
    'if $target =? "x86_64" 7 else missing',
    'if $target =? "wasm32" missing else 7',
    'if "x86_64" =? $target 7 else missing',
    'if $target not=? "wasm32" 7 else missing',
    'if $target in? ["arm" "x86_64"] 7 else missing',
    'if $target not in? ["wasm32"] 7 else missing',
    'if not ($target =? "wasm32") 7 else missing',
    'if ($target =? "x86_64") and ($target not=? "wasm32") 7 else missing',
    'if ($target =? "wasm32") or ($target =? "x86_64") 7 else missing',
    'if ($target =? "wasm32") xor ($target =? "x86_64") 7 else missing',
    'if $target =? "x86_64" {let chosen:int64=7}\nchosen',
    'if $target =? "wasm32" {let bad=missing}\nlet good:int64=7\ngood',
    'if $target =? "wasm32" missing else if $target =? "x86_64" 7 else also_missing',
    'let choose=():>int64=>if $target =? "x86_64" 7 else missing\nchoose()',
]
ERRORS = [
    'if true 7 else missing',
    'if false missing else 7',
    'if true {let local:int64=7}\nlocal',
    'if ($target =? "x86_64") and true 7 else missing',
    'if $target =? "wasm32" {let absent:int64=7}\nabsent',
]


def test_native_target_queries_and_selected_flows(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
