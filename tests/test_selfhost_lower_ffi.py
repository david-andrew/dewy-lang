"""C-call thunks agree for native, nullable, macOS and Windows bindings."""
import json
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


@pytest.mark.parametrize('mode', ['native', 'release', 'aarch64-mac', 'x86_64-windows', 'structs', 'aarch64-linux'])
def test_lower_ffi_twins(compiler, tmp_path, monkeypatch, mode):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source = tmp_path / 'input.dewy'
    output = tmp_path / ('program.exe' if mode == 'x86_64-windows' else 'program')
    if mode == 'x86_64-windows':
        source.write_text("""ticks=():>uint64=>$extern(name='GetTickCount64' lib='kernel32.dll')
main=()=>$unsafe {printl(ticks())}
""")
    elif mode in ('structs', 'aarch64-linux'):
        # (C structs by value: libc's div and ldiv return them in registers)
        source.write_text((ROOT / 'tests/cases/ffi_structs/libc_div.dewy').read_text())
    else:
        source.write_text((ROOT / 'tests/cases/ffi/libc_calls.dewy').read_text())
    flags = () if mode in ('native', 'structs') else ('--release',) if mode == 'release' else ('--target', mode)
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('lower_ffi',),
                         jo_doubles=modules_for(source, output, 'lower_ffi', flags=flags))
    assert image == output.read_bytes() + b'\n'
    if mode == 'structs':
        ran = subprocess.run([output], capture_output=True, timeout=30)
        assert (ran.returncode, ran.stdout) == (0, b'9 2\n-10000000000 -7\n'), ran.stderr
    if mode in ('native', 'release'):
        ran = subprocess.run([output], capture_output=True, timeout=30)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout == b'3\ntrue\n5 7\n1235\ntrue\n'
