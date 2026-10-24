"""Witness notes for unproven obligations under the internal strict policy."""
import os
import re
import subprocess

import pytest

from tools.cases import match_patterns
from tests.support import ROOT, compiler  # noqa: F401

STALE = '''forbidden=(@xs:array<int64>):>int64=>{
    if xs.length =? 0 return 0
    let i:int64=0
    if i >=? xs.length return 0
    xs.clear()
    return xs[i]
}
main=()=>{ let items:array<int64>=[1]; printl(forbidden(@items)) }
'''

RESIZED = '''grow=(@xs:array<int64>)=>{ xs.push(1) }
pick=(@xs:array<int64> i:int64):>int64=>{
    if i <? 0 or i >=? xs.length return 0
    grow(@xs)
    return xs[i]
}
main=()=>{ let items:array<int64>=[1]; printl(pick(@items 0)) }
'''

CONTRACT = '''Positive:type=int64<i => i >? 0>
take=(x:Positive):>int64=>x
relay=(y:int64):>int64=>take(y)
main=()=>printl(relay(1))
'''

DIVISOR = '''quotient=(n:int64 d:int64):>int64=>{
    if d <? 5 return n//d
    return 0
}
main=()=>printl(quotient(12 3))
'''

STORE = '''put=(@xs:array<int64> i:int64)=>{
    if i <? 0 return
    xs[i]=99
}
main=()=>{ let items:array<int64>=[1]; put(@items 0); printl(items.length) }
'''

NESTED_STORE = '''grow=(@rows:array<array<int64>> i:int64)=>{
    if i >=? rows.length return
    rows[i].push(1)
}
main=()=>{ let rows:array<array<int64>>=[[1]]; grow(@rows 0); printl(rows.length) }
'''

CASES = [
    (STALE, ['/w.dewy:6:12: error: index is not in bounds$/', 'note: i is 0',
             '/w.dewy:5:5: note: xs.length is 0 after this clear$/',
             '/w.dewy:4:8: note: the earlier `i <\\? xs.length` fact described the value before the clear$/']),
    (RESIZED, ['/w.dewy:5:12: error: cannot prove index is in bounds: missing upper bound$/',
               '/w.dewy:4:5: note: xs.length may have changed at this call to grow$/',
               '/w.dewy:3:18: note: the earlier `i <\\? xs.length` fact described the value before the call to grow$/',
               'note: missing upper bound: nothing establishes `i <? xs.length` here',
               'possible witness (consistent with the known bounds, not an observed execution): i = 0, xs.length = 0']),
    (CONTRACT, ["/w.dewy:3:30: error: cannot prove refinement `y >\\? 0`: missing lower bound$/",
                '/w.dewy:1:\\d+: note: the contract is declared here$/',
                'possible witness (consistent with the known bounds, not an observed execution): y = 0']),
    (DIVISOR, ['cannot prove divisor is nonzero: missing bound', 'note: d is at most 4',
               'possible witness (consistent with the known bounds, not an observed execution): d = 0']),
    (STORE, ['/w.dewy:3:5: error: cannot prove index is in bounds: missing upper bound$/',
             'note: missing upper bound: nothing establishes `i <? xs.length` here']),
    (NESTED_STORE, ['/w.dewy:3:5: error: cannot prove index is in bounds: missing lower bound$/',
                    'note: missing lower bound: nothing establishes `i >=? 0` here']),
]


def strict(compiler, path, command='check'):
    arguments = [compiler, '--internal-fact-policy=require-static', command, path]
    if command == 'build':
        arguments += ['-o', path.with_suffix('')]
    return subprocess.run(arguments,
                          text=True, capture_output=True, timeout=30)


@pytest.mark.core_quick
@pytest.mark.parametrize('command', ['check', 'build'])
@pytest.mark.parametrize('index', range(len(CASES)), ids=['stale', 'resized', 'contract', 'divisor', 'store', 'nested_store'])
def test_strict_witness_notes(compiler, tmp_path, index, command):
    source, patterns = CASES[index]
    path = tmp_path / 'w.dewy'
    path.write_text(source)
    result = strict(compiler, path, command)
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert not match_patterns(patterns, output), output
    assert 'help: establish' in output and '$runtime_assert' in output, output


def test_help_never_suggests_static_assert(compiler, tmp_path):
    outputs = []
    for index, (source, _) in enumerate(CASES):
        path = tmp_path / f'w{index}.dewy'
        path.write_text(source)
        outputs.append(strict(compiler, path).stderr)
    for path in sorted((ROOT / 'tests/cases/witness').glob('*.dewy')):
        outputs.append(subprocess.run([compiler, 'check', path], text=True, capture_output=True,
                                      timeout=30).stderr)
    helps = [line for output in outputs for line in output.splitlines() if 'help:' in line]
    assert helps
    assert not [line for line in helps if re.search(r'\$assert\b', line)], helps
