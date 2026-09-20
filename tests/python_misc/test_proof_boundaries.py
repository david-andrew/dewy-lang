"""Runtime fact procedures stay distinct from erased proof statements."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError
from tests.python_misc.test_scalar_projection import execute


def test_runtime_fact_procedure_keeps_its_write(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/runtime_fact_procedure.dewy'
    execute(tmp_path, 'runtime-fact-procedure', codegen(SrcFile.from_path(fixture)))


@pytest.mark.parametrize('body', ['return', 'if xs.length =? 0 return', 'if xs.length >? 0 return'])
def test_runtime_fact_procedure_checks_every_exit(body):
    with pytest.raises(UserError, match='refinement'):
        codegen(SrcFile(None, f'ensure=(@xs:array<int64>):> void & <xs.length >? 0> => {{ {body} }}'))
