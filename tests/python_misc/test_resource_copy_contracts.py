"""The checked component helpers honor explicit copies and return contracts."""
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

SOURCE = '''$explicit_copies
Handle=type of [id:int64 data:array<int64>
$__drop__
release=():>void=>data.clear
$__copy__
duplicate=():>Handle=>Handle[id data.copy()]
]
main=():>int64=>{
let source:array<Handle>=[Handle[42 [1]]]
let copied=source.copy()
return copied[0].id
}
'''


def test_explicit_resource_array_copy(tmp_path):
    execute(tmp_path, 'explicit-resource-copy', codegen(SrcFile(None, SOURCE), debug_locations=False))


def test_native_explicit_resource_array_copy(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=[])
