"""Completion offers only the names a file's language can call: Sloppy's file spellings are not Dewy's."""
import os
from pathlib import Path

import pytest

from tests.test_core_editor import Client

JO_ONLY = ['read_file', 'write_file', 'list_dir', 'run_program', 'run_shell', 'delete_file', 'join_path']


def complete(tmp_path, name, text):
    compiler = os.environ.get('DEWY_CORE_COMPILER')
    if not compiler:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    source = tmp_path / name
    source.write_text('')
    before, after = text.split('§')
    position = {'line': before.count('\n'), 'character': len(before.rsplit('\n', 1)[-1])}
    client = Client(Path(compiler).resolve(strict=True), tmp_path)
    try:
        client.set_text(source.as_uri(), before + after, 1)
        response = client.request('textDocument/completion', {
            'textDocument': {'uri': source.as_uri()}, 'position': position})
        return {item['label']: item for item in response['items']}
    finally:
        client.close()


def test_dewy_completion_hides_jo_spellings(tmp_path):
    items = complete(tmp_path, 'main.dewy', 'main=()=>{§ return 0}')
    assert not [name for name in JO_ONLY if name in items], sorted(items)
    # Dewy's own spellings stay, and a name both languages share shows Dewy's declaration.
    for name in ['read_text', 'write_text', 'list_directory', 'run', 'append_file']:
        assert name in items, (name, sorted(items))
    assert 'int64' in items['append_file']['detail'], items['append_file']
    assert 'Path' in items['is_dir']['detail'], items['is_dir']


def test_dewy_member_completion_hides_jo_spellings(tmp_path):
    items = complete(tmp_path, 'main.dewy', 'main=()=>{let path="notes.txt" path.§ return 0}')
    assert not [name for name in JO_ONLY if name in items], sorted(items)


def test_jo_completion_keeps_jo_spellings(tmp_path):
    items = complete(tmp_path, 'main.jo', 'main = () -> int:\n    §\n    0\n')
    for name in ['read_file', 'write_file', 'list_dir', 'run_program']:
        assert name in items, (name, sorted(items))
    assert 'bool' in items['append_file']['detail'], items['append_file']
