"""Dictionary entry views retain descriptors, lifetimes and value boundaries."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/dictionary_array_views.dewy').read_text()
CASES = [
    SOURCE,
    SOURCE.replace('const view=@values[1]', 'const view=values[1]'),
    """read=():>array<int64>=>{
        let values:dict<int64 array<int64>>=[1->[42]]
        const view=@values[1]
        return view
    }
    main=():>int64=>{let value=read() if value.length>?0 return value[0] return 0}""",
    """main=():>int64=>{
        let values:dict<int64 array<int64>>=[1->[42]]
        const view=@values[1]
        let saved=view.copy()
        values.clear()
        if saved.length>?0 return saved[0]
        return 0
    }""",
    # The hosted stored-owner check must follow dictionary routes for records too.
    """Box=type of [value:int64]
    main=():>int64=>{let values:dict<int64 Box>=[1->Box[42]]
        const view=@values[1]
        return view.value
    }""",
    """main=():>int64=>{
        let values:dict<int64 array<array<int64>>>=[1->[[42]]]
        const view=@values[1]
        if view.length>?0 and view[0].length>?0 return view[0][0]
        return 0
    }""",
]
ERRORS = [
    """main=():>int64=>{let values:dict<int64 array<int64>>=[1->[42]]
        const view=@values[1]
        values.clear()
        return view.length
    }""",
    """main=():>int64=>{let values:dict<int64 array<int64>>=[1->[42]]
        const view=@values[1]
        values[1]=[0]
        return view.length
    }""",
    """main=():>int64=>{let values:dict<int64 array<int64>>=[1->[42]]
        const view=@values[1]
        view.clear()
        return 42
    }""",
    """main=():>int64=>{let values:dict<int64 array<int64>>=[]
        const view=@values.get(1 [42])
        return view.length
    }""",
    # Receiver stability also covers eager default evaluation.
    """clear=(@values:dict<int64 array<int64>>):>array<int64>=>{values.clear() return [42]}
    main=():>int64=>{let values:dict<int64 array<int64>>=[1->[42]]
        const view=@values.get(1 clear(@values))
        return view.length
    }""",
]


@pytest.mark.parametrize('source', CASES)
def test_dictionary_entry_view_lifetimes(source, tmp_path):
    execute(tmp_path, 'dictionary-entry-views', codegen(SrcFile(None, source)))


@pytest.mark.parametrize('source', ERRORS)
def test_dictionary_entry_views_need_stable_stored_values(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_dictionary_array_views(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
