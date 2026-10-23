"""An exact value carried around a loop through `*`, `/` or `^` warns that it grows each
iteration, with an editor fix-it annotating its declaration `float64`; bounded and
integer-like updates, and annotated bindings, do not warn."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_core_editor import Client

MESSAGE = 'this exact value grows each iteration'

# The confirmed case ran 20000 iterations (35 s, a 268k-character fraction); 40 show it.
GROWING = '''damped=(steps:int64):>void=>{
    let position=0.0
    let velocity=1.0
    loop _ in [0..steps) {
        velocity=velocity*0.999
        position+=velocity*0.01
    }
    printl"{position}"
}
newton=():>void=>{
    let x=1.5
    loop _ in [0..4) x=(x+2/x)/2
    printl(x)
}
halving=():>void=>{
    let step=1/3
    loop _ in [0..3) step/=2
    printl(step)
}
temporaries=():>void=>{
    let balance=100.0
    loop _ in [0..3) {
        let interest=balance*0.05
        balance=balance+interest
    }
    printl(balance)
}
squares=():>void=>{
    let value=0.5
    loop _ in [0..3) value^=2
    printl(value)
}
let script=0.5
loop _ in [0..3) script=script*script
main=():>void=>{
    damped(40)
    newton()
    halving()
    temporaries()
    squares()
}
'''

QUIET = '''main=():>void=>{
    let total=0.0
    let doubled=1/3
    let flip=2/3
    let shifted=0.5
    let annotated:rational=1.5
    let floating=1.5
    let dt:float64=0.25
    let rate=1.05
    let whole=2.0
    loop i in [0..10) {
        if i <? 4 whole=whole*whole+1
        total+=0.1
        doubled=doubled*2
        doubled=doubled*3+1
        flip=1/flip
        shifted=(shifted+rate)-rate
        annotated=annotated*1.5
        floating=floating*1.05
        floating+=dt
        let once=rate*rate
        printl"{once}"
    }
    printl"{total} {doubled} {flip} {shifted} {annotated} {floating}"
}
'''


def warnings_of(compiler, path):  # noqa: F811
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True,
                             timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    return [line for line in checked.stderr.splitlines() if MESSAGE in line]


def test_growing_values_warn(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(GROWING)
    found = warnings_of(compiler, source)
    lines = sorted(int(line.split(':')[-4]) for line in found)
    # (position grows too, but through velocity: only velocity's own update is reported)
    expected = [n for n, line in enumerate(GROWING.splitlines(), 1)
                if any(update in line for update in ('velocity=', 'x=(', 'step/=', 'balance=', 'value^=', 'script='))
                and 'let ' not in line]
    assert lines == expected and len(expected) == 6, found
    assert all('annotate `float64` (or another explicit representation)' in line for line in found)
    run = subprocess.run([compiler, 'run', source], capture_output=True, text=True,
                         timeout=60, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    output = run.stdout.splitlines()
    # (never switched: still exact, printed as written)
    assert output[1:] == ['886731088897/627013566048', '1/24', '115.7625', '0.00390625'], output


def test_bounded_and_integer_updates_do_not_warn(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(QUIET)
    assert warnings_of(compiler, source) == []


def test_growth_quickfix(tmp_path):
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    source = tmp_path / 'main.dewy'
    source.write_text('main=():>void=>exit(0)')
    text = 'main=():>void=>{\n    let x=1.5\n    loop _ in [0..3) x=x*1.05\n    printl(x)\n}\n'
    client = Client(Path(value).resolve(strict=True), tmp_path)
    try:
        diagnostics = client.set_text(source.as_uri(), text, 1)
        warnings = [d for d in diagnostics if d['severity'] == 2 and MESSAGE in d['message']]
        assert len(warnings) == 1, diagnostics
        assert warnings[0]['range']['start'] == {'line': 2, 'character': 21}, warnings
        actions = client.request('textDocument/codeAction', {
            'textDocument': {'uri': source.as_uri()}, 'range': warnings[0]['range'],
            'context': {'diagnostics': warnings},
        })
        assert len(actions) == 1, actions
        edits = actions[0]['edit']['changes'][source.as_uri()]
        at = {'line': 1, 'character': 9}
        assert edits == [{'range': {'start': at, 'end': at}, 'newText': ':float64'}], edits
        fixed = text.replace('let x=', 'let x:float64=')
        diagnostics = client.set_text(source.as_uri(), fixed, 2)
        assert not [d for d in diagnostics if MESSAGE in d['message'] or d['severity'] == 1], diagnostics
    finally:
        client.close()
