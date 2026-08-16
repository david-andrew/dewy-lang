from pathlib import Path
from shutil import which

import pytest

from src.cleanparse.backend.udewy import codegen
from src.cleanparse.reporting import SrcFile
from src.cleanparse.semantic.errors import UserError
from udewy.frontend import entry_point


def _write(path: Path, source: str) -> Path:
    path.write_text(source)
    return path


def test_selective_reversed_comma_and_alias_imports(tmp_path: Path) -> None:
    _write(
        tmp_path / 'lib.dewy',
        '''
const one:int64 = 1
const two:int64 = 2
const three:int64 = 3
''',
    )
    entry = _write(
        tmp_path / 'main.dewy',
        '''
from p"lib.dewy" import (one two as second)
import three from p"lib.dewy"
import (one as first two) from p"lib.dewy"
from p"lib.dewy" import one, two, three
let main = ():>int64 => first + second
''',
    )

    emitted = codegen(SrcFile.from_path(entry))

    assert '__dewy_module_1_lib_one' in emitted
    assert '__dewy_module_1_lib_two' in emitted
    assert '__dewy_module_1_lib_three' in emitted


def test_bound_exact_path_can_source_an_import(tmp_path: Path) -> None:
    _write(tmp_path / 'lib.dewy', 'const value:int64 = 42\n')
    entry = _write(
        tmp_path / 'main.dewy',
        '''
let source = p"lib.dewy"
from source import value
let main = ():>int64 => value
''',
    )

    assert '__dewy_module_1_lib_value' in codegen(SrcFile.from_path(entry))


def test_imported_source_filename_extension_has_no_semantics(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / 'somefile.txt',
        '''
const x:int64 = 10
const y:int64 = 12
const z:int64 = 20
''',
    )
    entry = _write(
        tmp_path / 'main.dewy',
        '''
from p"somefile.txt" import x, y, z
let main = ():>int64 => x
''',
    )

    emitted = codegen(SrcFile.from_path(entry))

    assert '__dewy_module_1_somefile_x' in emitted
    assert '__dewy_module_1_somefile_y' in emitted
    assert '__dewy_module_1_somefile_z' in emitted


def test_namespace_and_splat_imports_include_types(tmp_path: Path) -> None:
    _write(
        tmp_path / 'lib.dewy',
        '''
let Number:type = int64
const answer:int64 = 40
let add = (value:int64):>int64 => value + 2
''',
    )
    entry = _write(
        tmp_path / 'main.dewy',
        '''
import p"lib.dewy" as library
import p"lib.dewy"
let main = ():>int64 => {
    let value:library.Number = answer
    return library.add(value)
}
''',
    )

    emitted = codegen(SrcFile.from_path(entry))

    assert '__dewy_module_1_lib_add' in emitted
    assert 'let value:int64 = __dewy_module_1_lib_answer' in emitted


@pytest.mark.parametrize(
    ('main_source', 'message'),
    [
        (
            'from p"missing.dewy" import value',
            'import file not found',
        ),
        (
            'from p"lib.dewy" import missing',
            'module has no top-level binding `missing`',
        ),
        (
            '''
let make = (text:string):>Path => p(text)
let path = make("lib.dewy")
from path import value
''',
            'import path must be an exact `Path` value',
        ),
        (
            'from p"lib.dewy" import value\nlet value:int64 = 1',
            'imported name `value` conflicts with this module',
        ),
        (
            'from p"lib.dewy" import (value, other as alias)',
            'invalid imported name',
        ),
    ],
)
def test_import_diagnostics(
    tmp_path: Path,
    main_source: str,
    message: str,
) -> None:
    _write(
        tmp_path / 'lib.dewy',
        'const value:int64 = 40\nconst other:int64 = 2\n',
    )
    entry = _write(tmp_path / 'main.dewy', main_source)

    with pytest.raises(UserError, match=message):
        codegen(SrcFile.from_path(entry))


def test_import_cycles_are_rejected(tmp_path: Path) -> None:
    entry = _write(
        tmp_path / 'a.dewy',
        'from p"b.dewy" import b\nconst a:int64 = 1\n',
    )
    _write(
        tmp_path / 'b.dewy',
        'from p"a.dewy" import a\nconst b:int64 = 2\n',
    )

    with pytest.raises(UserError, match='cyclic import'):
        codegen(SrcFile.from_path(entry))


def test_transitive_modules_mangle_colliding_top_level_names(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / 'common.dewy',
        'const shared:int64 = 20\n',
    )
    _write(
        tmp_path / 'left.dewy',
        '''
from p"common.dewy" import shared
const private:int64 = 1
let left = ():>int64 => shared + private
''',
    )
    _write(
        tmp_path / 'right.dewy',
        '''
const private:int64 = 2
const base:int64 = 19
let right = ():>int64 => base + private
''',
    )
    entry = _write(
        tmp_path / 'main.dewy',
        '''
from p"left.dewy" import left
from p"right.dewy" import right
let main = ():>int64 => left() + right()
''',
    )

    emitted = codegen(SrcFile.from_path(entry))

    assert '__dewy_module_2_left_private' in emitted
    assert '__dewy_module_3_right_private' in emitted
    assert emitted.index('__dewy_module_1_common_shared = 20') < emitted.index(
        '__dewy_module_2_left_private = 1'
    )


@pytest.mark.skipif(
    which('as') is None or which('ld') is None,
    reason='as/ld not available',
)
def test_imported_program_compiles_and_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(
        tmp_path / 'lib.dewy',
        '''
const answer:int64 = 40
let add = (value:int64):>int64 => value + 2
let main = ():>int64 => 1
''',
    )
    entry = _write(
        tmp_path / 'main.dewy',
        '''
from p"lib.dewy" import (answer add)
let main = ():>int64 => add(answer)
''',
    )
    emitted = codegen(SrcFile.from_path(entry))
    udewy_path = tmp_path / 'main.udewy'
    udewy_path.write_text(emitted)

    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 42
    assert emitted.count('let main =') == 1
    assert 'import p"' not in emitted
