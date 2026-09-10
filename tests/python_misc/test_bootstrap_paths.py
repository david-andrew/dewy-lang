"""Literal path views and included bytes follow ordinary constructor bindings."""
import test_bootstrap_check as source_values

PATH = '''
let Path:type=[
    path:string
    text=():>string=>path
]
let p=(path:string):>Path=>[path=path]
'''


def test_native_literal_paths_and_included_bytes(tmp_path, monkeypatch):
    blob = tmp_path / 'table.bin'
    blob.write_bytes(bytes([0, 1, 127, 128, 255]))
    include = f'$include_bytes(p"{blob}")'
    cases = [
        PATH + 'p"folder/file"',
        PATH + 'p(path="folder/file")',
        PATH + 'let value:string="folder/file"\np(value)',
        PATH + 'p"folder/file".text',
        PATH + 'let make=(value:string):>Path=>[path=value]\nmake("somewhere")',
        PATH + include,
        PATH + f'let bytes={include}\nbytes[4]',
        PATH + f'{include} as bytes\nbytes.length',
        PATH + f'let bytes:array<uint8 length=5>={include}\nbytes[4]',
        PATH + f'let bytes:int64=7\n{include} as bytes\nbytes.length',
    ]
    errors = [
        PATH + f'$include_bytes("{blob}")',
        PATH + f'let path:string="{blob}"\n$include_bytes(p(path))',
        PATH + '$include_bytes(p"/no-such-native-bootstrap-input.bin")',
        PATH + '$include_bytes()',
        PATH + f'$include_bytes(p"{blob}" p"{blob}")',
    ]
    monkeypatch.setattr(source_values, 'CASES', cases)
    monkeypatch.setattr(source_values, 'ERROR_CASES', errors)
    source_values.test_native_source_values(tmp_path, function_types=True)
