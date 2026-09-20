"""Reserved binders preserve the existing expression/type/index roles."""
import json
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.parser import p0
from dewy.reporting import SrcFile
from dewy.semantic import source_names
from dewy.semantic.errors import UserError
from tests.python_misc.test_scalar_projection import execute

SHAPES = [
    'let NAME=1', 'NAME:type=[x:int64]', 'f=(NAME:int64)=>NAME',
    'f=(NAME)=>NAME', 'f=(<NAME:int64>)=>NAME',
    'loop NAME in [1 2] {}', 'let [first NAME]=[1 2]',
    'T:type=[NAME:int64]', 'let record=[NAME=1]',
    'import reporting as NAME', 'from reporting import Error as NAME',
    'import Error as NAME from reporting',
    'match 1 {NAME:int64=>42}', 'match 1 {NAME=>42}',
    'f=<NAME>(x:NAME)=>x', 'T.NAME=():>int64=>42',
]


@pytest.mark.parametrize('name', sorted(source_names.RESERVED))
@pytest.mark.parametrize('shape', SHAPES)
def test_all_source_binding_forms_reserve_the_name(name, shape):
    source = SrcFile(None, shape.replace('NAME', name))
    with pytest.raises(UserError, match='reserved'):
        source_names.validate(p0.parse(source), source)


@pytest.mark.parametrize('name', sorted(source_names.RESERVED))
def test_compiler_enforces_reservation(name):
    with pytest.raises(UserError, match='reserved'):
        codegen(SrcFile(None, f'let {name}=42'))


def test_index_and_type_patterns_keep_their_existing_meaning(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/reserved_name_roles.dewy'
    execute(tmp_path, 'reserved-name-roles', codegen(SrcFile.from_path(fixture)))


def test_native_source_binding_validation_matches_hosted(tmp_path):
    root = Path(__file__).resolve().parents[2]
    cases = [shape.replace('NAME', name) for name in sorted(source_names.RESERVED) for shape in SHAPES]
    encoded = ' '.join(json.dumps(case).replace('{', '\\{') for case in cases)
    path = tmp_path / 'reserved-names.dewy'
    path.write_text(f'''from reporting import SrcFile, Error
import p"{root / 'dewy/bootstrap/parser/p0.dewy'}" as parser
import p"{root / 'dewy/bootstrap/semantic/source_names.dewy'}" as names
main=():>int64=>{{
    let cases:array<string>=[{encoded}]
    loop text in cases {{
        let source=SrcFile['input' text]
        let parsed=parser.parse(source)
        $runtime_assert parsed isnt? Error
        let result=names.validate(parsed.root source parsed.nodes)
        $runtime_assert result isnt? none
    }}
    return 42
}}
''')
    execute(tmp_path, 'native-reserved-names', codegen(SrcFile.from_path(path)))
