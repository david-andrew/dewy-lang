"""Truncating a resource array owns the retained prefix and drops the suffix."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/lifecycle_resource_array_truncate.dewy').read_text()
ERRORS = [SOURCE.replace('items.truncate(2)', 'items.truncate(-1)', 1)]

# Resource lowering must preserve the same relational facts as builtin
# truncation, not only its constant-count examples.
from test_truncate_relations import CASES as VALUE_CASES, ERRORS as VALUE_ERRORS
RESOURCE = 'Handle=type of [value:int64 $__drop__ release=():>void=>{}]\n'
def resource_case(source):
    return (RESOURCE + source.replace('array<int64>', 'array<Handle>')
            .replace('[40 2 9]', '[Handle[40] Handle[2] Handle[9]]')
            .replace('[1 42]', '[Handle[1] Handle[42]]')
            .replace('[42]', '[Handle[42]]')
            .replace('return xs[i]', 'return xs[i].value')
            .replace('=>xs[i]', '=>xs[i].value')
            .replace('xs[0]+xs[1]', 'xs[0].value+xs[1].value'))
RELATIONS = [resource_case(source) for source in VALUE_CASES]
RELATIONS.append(RESOURCE + 'size=(@groups:array<array<Handle>>):>1=>{const seen=groups.length return 1}\nmain=():>int64=>{let groups:array<array<Handle>>=[[Handle[42] Handle[9]]]\ngroups[0].truncate(size(@groups)) return groups[0][0].value}')
ERRORS.append(RESOURCE + 'reset=(@groups:array<array<Handle>>):>0=>{groups.clear groups.push([Handle[9]]) return 0}\nmain=():>int64=>{let groups:array<array<Handle>>=[[Handle[42]]]\ngroups[0].truncate(reset(@groups)) return 42}')

ERRORS.extend(resource_case(source) for source in VALUE_ERRORS)



@pytest.mark.parametrize('source', [SOURCE, *RELATIONS])
def test_resource_array_truncate(tmp_path, source):
    execute(tmp_path, 'truncate', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_resource_array_truncate_requires_bounds(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_resource_array_truncate(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE, *RELATIONS], errors=ERRORS)


def test_imported_count_effects(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    library = tmp_path / 'count.dewy'
    library.write_text('limit=():>1=>1')
    source = (f'from p"{library}" import limit\n' + RESOURCE +
              'main=():>int64=>{let items:array<Handle>=[Handle[42] Handle[9]] '
              'items.truncate(limit()) $assert items.length=?1 return items[0].value}')
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[source], errors=[])
