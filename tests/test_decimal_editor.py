"""Decimal literals adapt to a later float write the same way in the editor as when compiling."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.test_core_editor import Client

PROGRAM = '''let elapsed=0.0
tick=(dt:float64):>void=>{elapsed+=dt}
best_of=(xs:array<float64>)=>{
    let best=0.0
    loop x in xs { if x >? best { best=x } }
    best
}
main=()=>{
    let acc=0.0
    let f:float64=1.5
    acc+=f
    let exact=0.1
    exact+=0.2
    tick(0.5)
    let wide:float64=best_of([1.5 2.5])+acc+elapsed
    printl(wide)
    printl(exact =? 0.3)
}
$runtime_checks
'''


def compiler():
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    return Path(value).resolve(strict=True)


def hover(client, uri, text, needle):
    index = text.index(needle)
    line = text.count('\n', 0, index)
    column = index - (text.rfind('\n', 0, index) + 1)
    result = client.request('textDocument/hover', {
        'textDocument': {'uri': uri}, 'position': {'line': line, 'character': column}})
    return str(result['contents']['value']) if result else ''


def test_float_writes_match_the_compiler(tmp_path):
    binary = compiler()
    source = tmp_path / 'main.dewy'
    source.write_text(PROGRAM)
    run = subprocess.run([binary, str(source)], capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    assert run.stdout.split() == ['4.5', 'true']
    check = subprocess.run([binary, 'check', str(source)], capture_output=True, text=True, timeout=300)
    assert check.returncode == 0, check.stderr
    client = Client(binary, tmp_path)
    try:
        diagnostics = client.set_text(source.as_uri(), PROGRAM, 1)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        assert 'float64' in hover(client, source.as_uri(), PROGRAM, 'acc=0.0')
        assert 'float64' in hover(client, source.as_uri(), PROGRAM, 'best=0.0')
        assert 'float64' in hover(client, source.as_uri(), PROGRAM, 'elapsed=0.0')
        assert 'rational' in hover(client, source.as_uri(), PROGRAM, 'exact=0.1')
        # (a float written to an exact binding the compiler rejects: the same error here)
        bad = PROGRAM.replace('let exact=0.1', 'let exact=0.1\n    let third=1/3\n    third=f')
        source.write_text(bad)
        check = subprocess.run([binary, 'check', str(source)], capture_output=True, text=True, timeout=300)
        assert check.returncode != 0 and 'cannot hold this float64' in check.stderr, check.stderr
        message = check.stderr.split(' error: ', 1)[1].split('\n', 1)[0]
        diagnostics = client.set_text(source.as_uri(), bad, 2)
        errors = [d for d in diagnostics if d['severity'] == 1]
        assert errors and errors[0]['message'].startswith(message), diagnostics
        assert errors[0]['range']['start']['line'] == bad.count('\n', 0, bad.index('third=f')), errors
    finally:
        client.close()
