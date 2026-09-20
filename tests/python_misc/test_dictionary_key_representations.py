"""Unsupported key storage must not be mistaken for value hashing."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute


@pytest.mark.parametrize('type_', [
    'int64|none', 'string|none', 'int64|string', '[x:int64]',
    'array<int64>',
])
def test_unsupported_key_representations_are_rejected(type_):
    source = SrcFile(None, f'f=(key:{type_}):>bool=>{{'
                     f'let seen:set<{type_}>=set[] seen.push(key) return key in? seen}}')
    with pytest.raises(ReportException, match='hashing this dictionary key representation'):
        codegen(source)


def test_optional_members_do_not_silently_use_cell_addresses():
    source = SrcFile(None, '''main=():>int64=>{
        let seen:set<int64|none>=set[none 0 42]
        if none not in? seen or 0 not in? seen or 42 not in? seen return 1
        return 42
    }''')
    with pytest.raises(ReportException, match='hashing this dictionary key representation'):
        codegen(source)


def test_supported_dictionary_key_values_execute(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'fixtures/dictionary_key_values.dewy'
    execute(tmp_path, 'key_values', codegen(SrcFile.from_path(path), debug_locations=False))
