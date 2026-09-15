"""Source checking must retain contracts across stores and branch joins."""
import subprocess
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
STORED_HANDLE = (ROOT / 'tests/fixtures/native_stored_refinement_contracts.dewy').read_text()


@pytest.fixture(scope='module')
def source_validation_binary(tmp_path_factory):
    work = tmp_path_factory.mktemp('source-validation')
    seed = work / 'source-validation.udewy'
    seed.write_text(codegen(SrcFile.from_path(ROOT / 'tests/fixtures/bootstrap_source_validation.dewy'),
                            debug_locations=False))
    assert entry_point(seed, [], EntryPointOptions(compile_only=True)) == 0
    return cache_artifact(seed).resolve()


def test_native_stored_refinement_contracts(source_validation_binary, tmp_path):
    check_stored_refinement_contracts(source_validation_binary, tmp_path)


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


def test_native_global_call_facts_from_source(source_validation_binary, tmp_path):
    check_global_call_facts(source_validation_binary, tmp_path)


def check_global_call_facts(binary, tmp_path):
    # Native builtin calls carry binding ids, unlike hosted HIR adapters.
    # Exercise the checker-to-bounds boundary as well as the isolated visitor.
    from tests.python_misc.test_bootstrap_bounds import GLOBAL_CALL_CASES
    from dewy.semantic.prelude import prelude_files

    cases = [*GLOBAL_CALL_CASES.items(), ((ROOT / 'dewy/tests/brand_words.dewy').read_text(), 'ok')]
    for index, (body, expectation) in enumerate(cases):
        source = tmp_path / f'global-call-{index}.dewy'
        source.write_text(body)
        prelude = prelude_files('x86_64') if index == len(cases) - 1 else []
        result = subprocess.run([binary, source, *prelude], capture_output=True, text=True, timeout=60)
        assert result.returncode == (0 if expectation == 'ok' else 1), result.stdout + result.stderr
        if expectation != 'ok':
            assert expectation in result.stdout + result.stderr
