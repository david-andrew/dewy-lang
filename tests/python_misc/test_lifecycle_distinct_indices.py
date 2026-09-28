"""Resource separation is a checked fact, including implicit lifecycle effects."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_distinct_indices.dewy').read_text()
CASES = [
    SOURCE,
    SOURCE.replace('or i=?j', 'or i>=?j'),
    SOURCE.replace('consume(values[i])', 'let first=values[i]\n    consume(first)'),
    SOURCE.replace('    consume(values[i])', '    if i<?j {consume(values[i])}')
          .replace('trace=?21', 'trace=?12'),
    SOURCE.replace('Token[1] Token[2]', 'Token[1] Token[2] Token[3]')
          .replace('trace not=?12', 'trace not=?123').replace('trace=?21', 'trace=?213'),
    SOURCE.replace('consume(values[j])', 'let second=values[j]\n    consume(second)'),
]
CASES.extend([
    SOURCE.replace('or i=?j', 'or 0=?j').replace('consume(values[i])', 'consume(values[0])'),
    SOURCE.replace('consume(values[i])', 'consume(values[0])').replace('or i=?j', 'or j=?0'),
    SOURCE.replace('consume=(value:Token)', 'Box:type=[token:Token]\nconsume=(value:Token)')
          .replace('Token[1] Token[2]', 'Box[Token[1]] Box[Token[2]]')
          .replace('consume(values[i])', 'consume(values[i].token)')
          .replace('consume(values[j])', 'consume(values[j].token)'),
    (Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_distinct_indices_memory.dewy').read_text(),
])

ERRORS = [
    SOURCE.replace(' or i=?j', ''),
    SOURCE.replace('consume(values[j])', 'consume(values[i])'),
    SOURCE.replace('    consume(values[j])', '    i=j\n    consume(values[j])'),
    SOURCE.replace('    consume(values[j])', '    let snapshot=values\n    consume(values[j])'),
    SOURCE.replace('    consume(values[j])', '    values[j]=Token[3]\n    consume(values[j])'),
    SOURCE.replace('    consume(values[j])', '    let still_here=values[i].id\n    consume(values[j])'),
]


@pytest.mark.parametrize('source', CASES)
def test_distinct_resource_slots(tmp_path, source):
    execute(tmp_path, 'distinct-resource-slots', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_unproved_resource_separation(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_distinct_resource_slots(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
