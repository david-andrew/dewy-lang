"""Soft preconditions: `$warn_if condition "message"` before a function declaration warns at a
call where the compiler cannot prove the condition false (a type test from the argument's checked
type, integer comparisons from the facts at the call). The program still builds and runs, and the
editor shows the same warnings."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_core_editor import Client

SOURCE = '''Small:type=[n:int64]
Big:type=[n:int64]
$warn_if count >? 1000 "a large count is slow"
repeat=(count:int64):>int64=>count*2
$warn_if x isnt? Small "only a Small is cheap"
cost=(x:Small | Big):>int64=>x.n
$warn_if i <? 0 or i >=? xs.length "the index may be outside the array"
pick=(xs:array<int64> i:int64):>int64=>i
main=():>void=>{
    printl(repeat(10))
    let k=args().length
    printl(repeat(k))
    if k <? 100 { printl(repeat(k)) }
    printl(cost(Small[1]))
    let b:Small | Big=Big[2]
    printl(cost(b))
    if b is? Small { printl(cost(b)) }
    let xs:array<int64>=[1 2 3]
    printl(pick(xs 1))
    printl(pick(xs k))
}
'''

MESSAGES = ('a large count is slow', 'only a Small is cheap', 'the index may be outside the array')


def warned(stderr):
    found = []
    for line in stderr.splitlines():
        for message in MESSAGES:
            if line.endswith(message):
                found.append((int(line.split(':')[1]), message))
    return sorted(found)


def test_unproven_calls_warn(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True,
                             timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert warned(checked.stderr) == [(12, MESSAGES[0]), (16, MESSAGES[1]), (20, MESSAGES[2])], checked.stderr
    run = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0 and run.stdout.split() == ['20', '2', '2', '1', '2', '1', '1'], run.stdout + run.stderr


@pytest.mark.parametrize('declaration, error', [
    ('$warn_if count \n repeat=(count:int64):>int64=>count', 'needs a message after its condition'),
    ('$warn_if count >? 1 "slow"\nlimit=10', 'before the function declaration'),
    ('$warn_if count * 2 >? 1 "slow"\nrepeat=(count:int64):>int64=>count', 'unsupported `$warn_if` condition'),
])
def test_misplaced_or_unsupported(compiler, tmp_path, declaration, error):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(declaration + '\nmain=():>void=>printl(1)\n')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True,
                             timeout=60, check=False)
    assert checked.returncode != 0 and error in checked.stderr, checked.stderr


def test_editor_shows_the_warnings(tmp_path):
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    source = tmp_path / 'main.dewy'
    source.write_text('main=():>void=>exit(0)')
    client = Client(Path(value).resolve(strict=True), tmp_path)
    try:
        def found(diagnostics):
            return sorted((d['range']['start']['line'] + 1, d['message']) for d in diagnostics
                          if d['severity'] == 2 and d['message'] in MESSAGES)
        # (a type test is decided while checking; the facts' warnings come when the editor
        # lowers the document, after a quiet moment)
        diagnostics = client.set_text(source.as_uri(), SOURCE, 1)
        assert (16, MESSAGES[1]) in found(diagnostics), diagnostics
        while len(found(diagnostics)) < 3:
            message = client.receive()
            if message.get('method') == 'textDocument/publishDiagnostics':
                diagnostics = message['params']['diagnostics']
        assert found(diagnostics) == [(12, MESSAGES[0]), (16, MESSAGES[1]), (20, MESSAGES[2])], diagnostics
    finally:
        client.close()
