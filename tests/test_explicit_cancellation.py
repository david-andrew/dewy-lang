"""`$explicit_cancellation` (docs/LANGUAGE.md, "Bundles"; decisions.md batch 5): `$bulletproof`
holds it, so a `??` that would pass `Canceled` on unwritten is an error there, and
`$bulletproof=false` opts a scope back out. The other cases are tests/cases/explicit_cancellation."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_core_editor import Client

SOURCE = '''$bulletproof

outcome = (kind:int64):>(int64 | Missing | Canceled) & no panics => {
    if kind =? 0 return Canceled
    if kind =? 1 return Missing
    9
}
plain = (kind:int64):>(int64 | Canceled) & no panics => {BODY}
main = ():>(void | Canceled | OutOfMemory) & no panics => {
    let n = plain(2) or_throw
    printl(n)
}
'''


def check(compiler, tmp_path, body):
    (tmp_path / 'main.dewy').write_text(SOURCE.replace('BODY', body))
    return subprocess.run([compiler, 'run', 'main.dewy'], text=True, capture_output=True, timeout=120, cwd=tmp_path)


def test_bulletproof_holds_it(compiler, tmp_path):
    result = check(compiler, tmp_path, 'outcome(kind) ?? 0')
    assert result.returncode != 0
    assert ('main.dewy:8:58: error: `outcome(kind)` may be `Canceled`, which this `??` would pass on unwritten '
            'under `$explicit_cancellation`: write `outcome(kind) or_throw<Canceled>` to forward it') in result.stderr, result.stderr


def test_bulletproof_accepts_the_fix(compiler, tmp_path):
    result = check(compiler, tmp_path, 'outcome(kind) or_throw<Canceled> ?? 0')
    assert result.returncode == 0 and result.stdout == '9\n', result.stdout + result.stderr


def test_bulletproof_opt_out(compiler, tmp_path):
    result = check(compiler, tmp_path, '\n    $bulletproof=false\n    outcome(kind) ?? 0\n')
    assert result.returncode == 0 and result.stdout == '9\n', result.stdout + result.stderr


def test_quickfix_writes_the_forwarding(tmp_path):
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    source = tmp_path / 'main.dewy'
    source.write_text('main=():>void=>exit(0)')
    text = ('$explicit_cancellation\n\noutcome=(k:int64):>int64|Missing|Canceled=>if k =? 0 Canceled else 9\nplain=(k:int64)=>outcome(k) ?? 0\nmain=()=>{printl(plain(1))}\n')
    client = Client(Path(value).resolve(strict=True), tmp_path)
    try:
        diagnostics = client.set_text(source.as_uri(), text, 1)
        errors = [d for d in diagnostics if '`$explicit_cancellation`' in d['message']]
        assert len(errors) == 1, diagnostics
        actions = client.request('textDocument/codeAction', {
            'textDocument': {'uri': source.as_uri()}, 'range': errors[0]['range'],
            'context': {'diagnostics': errors},
        })
        assert len(actions) == 1, actions
        edits = actions[0]['edit']['changes'][source.as_uri()]
        at = {'line': 2, 'character': 27}
        assert edits == [{'range': {'start': at, 'end': at}, 'newText': ' or_throw<Canceled>'}], edits
        fixed = text.replace('outcome(k) ??', 'outcome(k) or_throw<Canceled> ??')
        diagnostics = client.set_text(source.as_uri(), fixed, 2)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
    finally:
        client.close()
