"""Frame array buffers and their owned record elements have distinct lifetimes."""
from pathlib import Path
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_fixed_array_field_cleanup_does_not_release_frame_records(tmp_path, target):
    fixtures = Path(__file__).resolve().parents[2] / 'dewy/tests'
    source = tmp_path / 'record-elements.dewy'
    source.write_text(f'''
import p"{fixtures / 'object_array_borrowed_params.dewy'}" as reader
import p"{fixtures / 'value_places.dewy'}" as places
let main=():>int64=>{{
    if reader.main() not=?42 return 1
    return places.main()
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr
