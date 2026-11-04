"""Cold intrinsic lowering preserves shader payloads across native backends."""
import json

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for
from tests.test_shader_units import PROGRAM


@pytest.mark.parametrize('target', ['native', 'aarch64-mac', 'wasm32'])
def test_lower_intrinsics_twins(compiler, tmp_path, monkeypatch, target):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source = tmp_path / 'input.dewy'
    output = tmp_path / ('program.html' if target == 'wasm32' else 'program')
    source.write_text(PROGRAM)
    flags = () if target == 'native' else ('--target', target)
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('lower_intrinsics',),
                         jo_doubles=modules_for(source, output, 'lower_intrinsics', flags=flags))
    assert image == output.read_bytes() + b'\n'
