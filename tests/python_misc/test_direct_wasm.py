"""Direct wasm32 modules: acceptance checks (ROADMAP "Direct binary fast path").

The direct path encodes the wasm32 backend's WAT in process instead of
running `wat2wasm`. The dialect is closed and the section order and LEB128
sizes are `wat2wasm`'s, so the module must be byte-identical to it; it must
validate, and the Python and native encoders must agree.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from shutil import which

import pytest

from udewy import p0, t0, t1
from udewy.backend import get_backend
from udewy.backend.wasm_binary import assemble

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS = REPO_ROOT / 'udewy/tests'
PROGRAMS = ['fizzbuzz', 'test_indirect_call', 'test_short_circuit_cond', 'test_hello_wasm', 'test_address_displacements',
            'test_intrinsics', 'test_pending_operands', 'test_div_mod', 'test_stdlib', 'test_register_backend_stress',
            'test_webgl_water', 'test_bootstrap_t1']

pytestmark = pytest.mark.skipif(any(which(tool) is None for tool in ('wat2wasm', 'wasm-validate')),
                                reason='wabt is needed to check direct wasm32 modules against it')


def _wat(name: str) -> str:
    backend = get_backend('wasm32')
    backend.debug_info = False
    loaded = t0.load_program(TESTS / f'{name}.udewy', target_backend='wasm32')
    return p0.parse(t1.tokenize(loaded.source), loaded.source, backend)


@pytest.mark.parametrize('name', PROGRAMS)
def test_modules_match_wat2wasm_and_validate(tmp_path, name):
    wat = tmp_path / f'{name}.wat'
    wat.write_text(_wat(name))
    reference = tmp_path / 'reference.wasm'
    subprocess.run(['wat2wasm', str(wat), '-o', str(reference)], check=True)
    direct = tmp_path / 'direct.wasm'
    direct.write_bytes(assemble(wat.read_text()))
    assert direct.read_bytes() == reference.read_bytes()
    subprocess.run(['wasm-validate', str(direct)], check=True)


def test_the_compile_path_writes_the_same_module(tmp_path, monkeypatch):
    backend = get_backend('wasm32')
    backend.debug_info = False
    code = _wat('test_indirect_call')
    modules = []
    for mode in ('wat2wasm', 'direct'):
        if mode == 'direct':
            monkeypatch.setenv('UDEWY_OBJECT', 'direct')
        else:
            monkeypatch.delenv('UDEWY_OBJECT', raising=False)
        work = tmp_path / mode
        backend.compile_and_link(code, 'module', work, split_wasm=True)
        modules.append((work / 'module.wasm').read_bytes())
        assert (work / 'module.wat').exists() == (mode == 'wat2wasm')
    assert modules[0] == modules[1]


@pytest.fixture(scope='module')
def native_udewy(tmp_path_factory) -> Path:
    from native_udewy import native_udewy as build
    return build(tmp_path_factory.mktemp('native-udewy'))


@pytest.mark.parametrize('name', PROGRAMS)
def test_native_and_python_write_identical_modules(tmp_path, native_udewy, name):
    wat = tmp_path / f'{name}.wat'
    wat.write_text(_wat(name))
    native = tmp_path / 'native.wasm'
    subprocess.run([native_udewy, '--assemble', str(wat), str(native)], check=True,
                   env={key: value for key, value in os.environ.items() if key != 'UDEWY_OBJECT'})
    assert native.read_bytes() == assemble(wat.read_text())
