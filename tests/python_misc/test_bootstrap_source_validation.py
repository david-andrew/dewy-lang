"""Source checking must retain contracts across stores and branch joins."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
STORED_HANDLE = (ROOT / 'tests/fixtures/native_stored_refinement_contracts.dewy').read_text()


def test_native_stored_refinement_contracts(tmp_path):
    seed = tmp_path / 'source-validation.udewy'
    seed.write_text(codegen(SrcFile.from_path(ROOT / 'tests/fixtures/bootstrap_source_validation.dewy')))
    assert entry_point(seed, [], EntryPointOptions(compile_only=True)) == 0
    binary = cache_artifact(seed).resolve()
    check_stored_refinement_contracts(binary, tmp_path)


def check_stored_refinement_contracts(binary, tmp_path):
    cases = [
        (STORED_HANDLE, 0),
        (STORED_HANDLE.replace('if inhabitant isnt? none {value=inhabitant}',
                              'if inhabitant isnt? none {value=inhabitant}\nelse {value=x}'), 0),
        # Recording a store's required type must not discharge its proof.
        (STORED_HANDLE.replace('value=inhabitant', 'value=-1'), 1),
        (STORED_HANDLE.replace('x:addr flag:bool', 'x:addr flag:bool raw:int64=0')
         .replace('value=inhabitant', 'value=raw'), 1),
    ]
    for index, (body, status) in enumerate(cases):
        source = tmp_path / f'case-{index}.dewy'
        source.write_text(body)
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=60, check=False)
        assert result.returncode == status, result.stdout + result.stderr
        if status:
            expected = 'refinement refuted' if index == 2 else 'cannot prove refinement'
            assert expected in result.stdout + result.stderr
