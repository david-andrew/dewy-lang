"""µDewy bytecode (udewy/BYTECODE.md): recording and replaying backend calls.

Replaying a recorded stream must reach the same assembly as parsing the
source, and the Python and native recorders must write the same stream for
one program (stream ids are dense per id space, whatever a backend returns).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from udewy import p0, t0, t1
from udewy.backend import get_backend
from udewy.stream import Recorder, Stream

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS = REPO_ROOT / 'udewy/tests'
PROGRAMS = ['test_comprehensive', 'test_address_displacements', 'test_cached_operands', 'test_alloca_spills',
            'test_intrinsics', 'test_short_circuit_cond', 'test_jump_table', 'test_indirect_call',
            'test_immediate_operands', 'test_pending_operands', 'test_local_registers', 'test_hello', 'test_import']
GLOBALS = '''
const words:int = __static_words__(3 5 @bump)
const greeting:int = "hello"
let counter:int = 0
let handler:int = @bump
let storage:int = __static_alloca__(32)
let bump = (by:int):>int => {
    counter = counter + by
    return counter
}
let main = ():>int => {
    let buffer:int = __alloca__(64)
    let i:int = 0
    loop i <? 8 and i >=? 0 { __store__(i * i buffer + i * 8)  i = i + 1 }
    let sum:int = 0
    i = 0
    loop i <? 8 { sum = sum + __load__(buffer + i * 8)  i = i + 1 }
    if sum =? 140 or sum =? 0 { sum = sum + 1 }
    (@handler)(5)
    __store__(sum storage)
    if bump(1) not=? 6 { return 3 }
    return __load__(storage) + __load__(words + 8) - 141 + 42 - 5 + __load__(greeting - 8) - 5
}
'''


def _source(tmp_path: Path, name: str) -> Path:
    if name == 'globals':
        path = tmp_path / 'globals.udewy'
        path.write_text(GLOBALS)
        return path
    return TESTS / f'{name}.udewy'


def _record(path: Path, debug_info: bool) -> tuple[str, bytes]:
    backend = get_backend('x86_64')
    backend.debug_info = debug_info
    loaded = t0.load_program(path, target_backend='x86_64')
    recorder = Recorder(backend, loaded.link_artifacts)
    recorder.set_imported_sources([Path(source) for source in loaded.imported_sources])
    asm = p0.parse(t1.tokenize(loaded.source), loaded.source, recorder, source_path=str(path.resolve()))
    return asm, recorder.stream()


@pytest.mark.parametrize('debug_info', [False, True])
@pytest.mark.parametrize('name', PROGRAMS + ['globals'])
def test_replay_reaches_the_parsed_assembly(tmp_path, name, debug_info):
    asm, stream = _record(_source(tmp_path, name), debug_info)
    backend = get_backend('x86_64')
    backend.debug_info = debug_info
    assert Stream(stream).play(backend) == asm


def test_a_replayed_program_runs(tmp_path):
    from udewy.cache import cache_artifact
    from udewy.frontend import EntryPointOptions, entry_point
    _, stream = _record(_source(tmp_path, 'globals'), False)
    replay = tmp_path / 'globals.ubc'
    replay.write_bytes(stream)
    assert entry_point(replay, [], EntryPointOptions(compile_only=True, debug_info=False)) == 0
    assert subprocess.run([cache_artifact(replay).resolve()]).returncode == 42


@pytest.fixture(scope='module')
def native_udewy(tmp_path_factory) -> Path:
    from native_udewy import native_udewy as build
    return build(tmp_path_factory.mktemp('native-udewy'))


@pytest.mark.parametrize('name', PROGRAMS + ['globals'])
def test_native_and_python_write_the_same_stream(tmp_path, native_udewy, name):
    source = _source(tmp_path, name)
    _, stream = _record(source, False)
    recorded = tmp_path / 'native.ubc'
    env = {**os.environ, 'UDEWY_RECORD': str(recorded), 'UDEWY_JOBS': '1'}
    subprocess.run([native_udewy, '--no-debug-info', '-c', str(source)], cwd=tmp_path, check=True, env=env,
                   capture_output=True)
    assert recorded.read_bytes() == stream


@pytest.mark.parametrize('name', ['globals', 'test_comprehensive', 'test_short_circuit_cond'])
def test_native_replay_reaches_the_parsed_assembly(tmp_path, native_udewy, name):
    source = _source(tmp_path, name)
    work = tmp_path / 'work'
    work.mkdir()
    local = work / f'{name}.udewy'
    local.write_text(source.read_text())
    env = {key: value for key, value in os.environ.items() if key not in ('UDEWY_OBJECT', 'UDEWY_RECORD')}
    env['UDEWY_JOBS'] = '1'
    subprocess.run([native_udewy, '--no-debug-info', '-c', str(local)], cwd=work, check=True, capture_output=True,
                   env={**env, 'UDEWY_RECORD': str(work / 'replay.ubc')})
    subprocess.run([native_udewy, '--no-debug-info', '-c', str(work / 'replay.ubc')], cwd=work, check=True,
                   capture_output=True, env=env)
    cache = work / '__dewycache__'
    assert (cache / 'replay.s').read_text() == (cache / f'{name}.s').read_text()
