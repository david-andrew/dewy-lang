"""Constructor field names are private; genuine ambient reads stay effects."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/constructor_storage_scope.dewy').read_text()
CASES = [SOURCE,
    SOURCE.replace('Pair[first=39]', '[first=39 as int64 second=first+1]'),
    SOURCE.replace('Pair:type=[first:int64 second:int64=first+1]',
                   'Inner:type=[value:int64 next:int64=value+1]\nPair:type=[first:Inner second:int64=first.next]')
          .replace('Pair[first=39]', 'Pair[first=Inner[39]]'),
]
ERRORS = [
    # A real global remains an external read, even when a field shadows it.
    SOURCE.replace('Pair:type=', 'let outside:int64=39\nPair:type=')
          .replace('Pair[first=39]', 'Pair[first=outside]'),
    # Capture by a nested function is not made private to that function.
    '''Box:type=[value:int64 run:():>int64 & no_effects]
main=():>int64=>{
    let box=[value=42 as int64 run=():>int64 & no_effects=>value]
    return box.run()
}''',
    SOURCE.replace('return size(items)+pair.second', 'items.clear()\n    return size(items)+pair.second'),
]

@pytest.mark.parametrize('source', CASES)
def test_constructor_private_storage(tmp_path, source):
    execute(tmp_path, 'constructor-storage', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_constructor_scope_keeps_external_effects(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_constructor_private_storage(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
