"""Named callbacks use the literal specialization's effect and panic boundaries."""
import subprocess

import pytest

from tests.support import compiler, run_value_batch, build_exit_batch
from tests.test_core_callback_specialization import CASES


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_named_callback_effect_order(compiler, tmp_path, release, target):
    cases = {
        'argument-order': CASES['argument-order'].replace(
            'let result=visit',
            'let callback=()=>{trace=trace*10+3 return bias}\n let result=visit'
        ).replace('callback=()=>{trace=trace*10+3 return bias} a=', 'callback=@callback a='),
        'forwarded-effects': CASES['forwarded-effects'].replace(
            'let answer=forward((x:int64):>int64=>{trace=trace*10+x return x+bias})',
            'let callback=(x:int64):>int64=>{trace=trace*10+x return x+bias}\n let answer=forward(@callback)'),
        'private-state': CASES['private-state-fallback'],
    }
    for name, (value, diagnostic) in run_value_batch(
            compiler, tmp_path, cases, release, target).items():
        assert value == '42', f'{name}: {diagnostic or value}'


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_named_callback_panic_order(compiler, tmp_path, release, target):
    cases = {'bounds': '''Callback:type=(x:int64):>int64
visit=(callback:Callback)=>{callback(0); callback(1); printl"after"}
main=()=>{
 let xs:array<int64>=[7]
 let callback=(x:int64):>int64=>{printl"before {x}" return xs[x]}
 visit(@callback)
}'''}
    command, failure = build_exit_batch(compiler, tmp_path, cases, release, target)
    assert command is not None, failure
    ran = subprocess.run([*command, '0'], capture_output=True, text=True, timeout=15)
    output = ran.stdout + ran.stderr
    assert ran.returncode != 0, output
    assert 'before 0\nbefore 1\n' in output, output
    assert 'after' not in ran.stdout, output
