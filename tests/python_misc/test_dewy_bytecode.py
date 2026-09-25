"""Dewy compiles to µDewy bytecode (ROADMAP "Direct binary fast path", step 4).

The native compiler spells each declaration as µDewy tokens and parses them
itself (dewy/bootstrap/backend/udewy/bytecode.dewy), so it writes a `.ubc`
stream instead of µDewy text. The stream must compile to exactly the
assembly the text does. The text route here has no source path: a stream has
no µDewy file for debug locations to fall back to, so both take locations
from the emitter's markers only. The hosted compiler keeps the same artifact:
it records the backend calls of its own compile.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy import p0, t0, t1
from udewy.backend import get_backend
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point
from udewy.stream import Stream

ROOT = Path(__file__).resolve().parents[2]

CASES = {
    'strings': 'let main=():>int64=>{\n    let name="world"\n    let text="hello {name} {40 + 2}"\n    printl(text)\n    return if text.length =? 14 42 else 1\n}\n',
    'control': '''let collatz=(n:int64):>int64=>{
    let steps:int64=0
    let x=n
    loop x not=? 1 {
        if x % 2 =? 0 {x=x // 2} else if x >? 1000000 {break} else {x=x * 3 + 1}
        steps+=1
    }
    return steps
}
let main=():>int64=>{
    let total:int64=0
    loop i in 1..30 {
        if i =? 7 or i =? 11 and not (total >? 1000) continue
        total+=collatz(i)
    }
    return if total >? 0 42 else 0
}
''',
    'containers': '''let main=():>int64=>{
    let xs:array<int64>=[3 1 2]
    xs.push(36)
    let seen:set<string>=set["a" "b"]
    let counts:dict<string int64>=["a"->1]
    counts["b"]=2
    let sum:int64=0
    loop x in xs {sum+=x}
    return if "a" in? seen and counts["b"] =? 2 sum else 0
}
''',
    'functions': '''let twice=(f:(y:int64):>int64 x:int64):>int64=>f(f(x))
let main=():>int64=>{
    let add=(y:int64):>int64=>y + 19
    let narrow:uint8=250
    let wrapped:uint8=narrow + 10
    let shifted=(-64) >> 3
    return if twice(@add 4) =? 42 and wrapped =? 4 and shifted =? -8 42 else 1
}
''',
    'globals': '''let counter:int64=0
let table:array<int64>=[1 2 3]
let bump=():>void=>{counter+=1}
let main=():>int64=>{
    bump() bump()
    return if counter =? 2 and table.length =? 3 42 else 1
}
''',
}


_DRIVER: Path | None = None
_PRELUDE_CACHE: Path | None = None


def _driver(tmp_path: Path) -> Path:
    global _DRIVER
    if _DRIVER is None:
        output = tmp_path / 'stream-driver.udewy'
        output.write_text(codegen(SrcFile.from_path(ROOT / 'tests/fixtures/bootstrap_stream.dewy'), debug_locations=False))
        assert entry_point(output, [], EntryPointOptions(compile_only=True, debug_info=False)) == 0
        _DRIVER = cache_artifact(output).resolve()
    return _DRIVER


def _emit(tmp_path: Path, name: str, debug: bool) -> tuple[Path, bytes]:
    global _PRELUDE_CACHE
    driver = _driver(tmp_path)
    if _PRELUDE_CACHE is None:
        _PRELUDE_CACHE = tmp_path / 'prelude-cache'
    source = tmp_path / f'{name}.dewy'
    source.write_text(CASES[name])
    text, stream = tmp_path / f'{name}.udewy', tmp_path / f'{name}.ubc'
    command = [driver, source, ROOT / 'library', _PRELUDE_CACHE, text, stream, *(['debug'] if debug else [])]
    built = subprocess.run(command, capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    return text, stream.read_bytes()


def _backend(target: str, debug: bool):
    backend = get_backend(target)
    backend.debug_info = debug
    return backend


@pytest.mark.parametrize('debug', [False, True], ids=['plain', 'debug'])
@pytest.mark.parametrize('name', sorted(CASES))
def test_the_stream_compiles_to_the_texts_assembly(tmp_path, name, debug):
    text, stream = _emit(tmp_path, name, debug)
    loaded = t0.load_program(text)
    for target in ('x86_64', 'arm'):
        backend = _backend(target, debug)
        backend.set_imported_sources([])
        expected = p0.parse(t1.tokenize(loaded.source), loaded.source, backend)
        assert Stream(stream).play(_backend(target, debug)) == expected, (name, target)


@pytest.mark.parametrize('name', sorted(CASES))
def test_the_stream_runs(tmp_path, name):
    _text, stream = _emit(tmp_path, name, False)
    path = tmp_path / f'{name}-run.ubc'
    path.write_bytes(stream)
    assert entry_point(path, [], EntryPointOptions(compile_only=True, debug_info=False)) == 0
    assert subprocess.run([cache_artifact(path).resolve()], capture_output=True, timeout=30).returncode == 42


def _hosted(source: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, '-m', 'dewy', '-c', str(source)], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=600)


def test_the_hosted_compiler_keeps_bytecode_unless_asked_for_text(tmp_path):
    source = tmp_path / 'answer.dewy'
    source.write_text(CASES['globals'])
    env = {**os.environ, 'PYTHONPATH': str(ROOT)}
    env.pop('DEWY_EMIT', None)
    stream = cache_artifact(source, '.ubc', cwd=ROOT)
    text = cache_artifact(source, '.udewy', cwd=ROOT)
    binary = ROOT / cache_artifact(source, cwd=ROOT)
    for path in (ROOT / stream, ROOT / text, binary):
        path.unlink(missing_ok=True)
    built = _hosted(source, env)
    assert built.returncode == 0, built.stdout + built.stderr
    assert (ROOT / stream).is_file() and not (ROOT / text).exists()
    assert subprocess.run([binary], timeout=30).returncode == 42
    # The recorded stream compiles by itself too.
    replayed = tmp_path / 'replayed.ubc'
    replayed.write_bytes((ROOT / stream).read_bytes())
    assert entry_point(replayed, [], EntryPointOptions(compile_only=True, debug_info=False)) == 0
    assert subprocess.run([cache_artifact(replayed).resolve()], timeout=30).returncode == 42

    binary.unlink()
    built = _hosted(source, {**env, 'DEWY_EMIT': 'udewy'})
    assert built.returncode == 0, built.stdout + built.stderr
    assert (ROOT / text).is_file()
    assert subprocess.run([binary], timeout=30).returncode == 42
