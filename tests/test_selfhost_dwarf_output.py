"""DWARF demand: no line rows, no sections; a module is the user's unless the prelude's."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_dwarf_format import SETUP

STEMS = ('checker_types', 'checker_state', 'source_types', 'elf_format', 'leb128', 'module_paths',
         'json_doc', 'dwarf_format', 'dwarf_output')

CHECK = '''struct Module:
    is_prelude: bool
modules: Module[]
'''

DRIVER = "use 'check.jo'\n" + SETUP + r'''
main = ():
    reset()
    modules = [Module(is_prelude=true), Module(), Module(is_prelude=true)]
    loop m in [-1, 0, 1, 2, 3]: print(dw_user_module(m))
    host = DwarfHost(host_name, host_layout, host_store, host_field, host_line, dw_user_module)
    binding = dwarf_bind(&input)
    sections = dwarf_sections(0x400000, 64, "main.dewy", "test")
    assert(sections.len() > 0, "line rows make sections")
    loop arm0 in [false, true]:
        arm = arm0
        reset()
        loop section in dwarf_sections(0x400000, 64, "src/prøgram.dewy", "test"):
            print(section.0)
            print(section.1)
    line_rows = []
    print(dwarf_sections(0x400000, 64, "main.dewy", "test").len())
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_dwarf_output_twins(compiler, tmp_path, release):  # noqa: F811
    run = tmp_path / 'run'
    run.mkdir()
    output = compare_narrow(compiler, tmp_path, release, STEMS, DRIVER, doubles={'check.jo': CHECK}, run_in=lambda: run)
    assert output.split()[:5] == [b'false', b'false', b'true', b'false', b'false']
    assert output.rstrip().endswith(b'0')
