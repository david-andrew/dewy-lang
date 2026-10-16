"""Runtime helper availability must not root every helper in an executable."""
import os
import re
import subprocess

import pytest
from driver_artifacts import isolated_codegen

from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_native_runtime_reachability(tmp_path, monkeypatch):
    if not os.environ.get('DEWY_TEST_DRIVER_COMPILER'):
        pytest.skip('set DEWY_TEST_DRIVER_COMPILER to the current native CLI')
    monkeypatch.setenv('DEWY_NATIVE_MAP', '1')
    source = tmp_path / 'tiny.dewy'
    source.write_text('main=():>int64=>42\n')
    output = source.with_suffix('.udewy')
    isolated_codegen(output, source, debug_locations=False)
    # A scalar entry needs no UTF-8 decoding or string-release helpers.
    # Global runtime initialization currently still uses allocator helpers.
    functions = re.findall(r'^let (_f\d+_\w+)\s*=', output.read_text(), re.MULTILINE)
    assert any(name.endswith('_main') for name in functions), functions
    for unused in ('_utf8_boundaries', '_utf8_boundaries_into', '_native_string_drop'):
        assert not any(name.endswith('_' + unused) for name in functions), functions

    (tmp_path / 'dependency.dewy').write_text('''
initialize=():>int64=>6
stamp=initialize()
helper=():>int64=>36
read=(n:int64=helper()):>int64=>n+stamp
callback=():>int64=>read()
table:array<():>int64>=[@callback]
unused=():>int64=>999
''')
    source = tmp_path / 'main.dewy'
    source.write_text('''
import p"dependency.dewy" as dependency
main=(args:array<string>):>int64=>{
    if args.length not=? 2 return 1
    let text=args[1]
    if text.length not=? 2 or text[0] not=? 'é' or text[1] not=? '🙂' return 2
    if dependency.table.length =? 0 return 3
    return dependency.table[0]()
}
''')
    output = source.with_suffix('.udewy')
    isolated_codegen(output, source, debug_locations=False)
    emitted = output.read_text()
    assert not re.search(r'^let _f\d+_unused\s*=', emitted, re.MULTILINE)
    for name in ('initialize', 'helper', 'read', 'callback'):
        assert re.search(rf'^let _f\d+_{name}\s*=', emitted, re.MULTILINE), name
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve(), 'é🙂'],
                             capture_output=True, timeout=10, check=False)
        assert run.returncode == 42, (target, run.returncode, run.stderr)
