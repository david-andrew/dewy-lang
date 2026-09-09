"""Partial result contracts refine the fixed-width range on both endpoints."""

import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_partial_call_contract_keeps_its_representation_bounds(tmp_path):
    source = '''
let upper=():>uint64<n => n <=? 255> => 7
let lower=():>int8<n => n >=? 0> => 9
let main=():>int64 => {
    let a=upper()
    let b=lower()
    printl(a as int64)
    printl(b as uint8)
    return 0
}
'''
    output = tmp_path / 'call_ranges.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['7', '9']


def test_unsigned_result_does_not_fit_a_signed_word_without_an_upper_bound():
    with pytest.raises(ReportException):
        codegen(SrcFile(None, '''
let large=():>uint64 => 18446744073709551615
let bad=():>int64 => large() as int64
'''))
