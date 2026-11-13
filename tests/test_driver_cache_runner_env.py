"""Runner paths do not rebuild a driver; actual build inputs still do."""
import os
import subprocess

from tests.driver_cache import build_driver, identity
from tests.support import compiler  # noqa: F401


def test_bookkeeping_paths_reuse_the_executable(compiler, tmp_path, monkeypatch):  # noqa: F811
    modules = {'driver.jo': 'main = ():\n    print(7)\n'}
    monkeypatch.setenv('DEWY_EMIT_WORKERS', '1')
    first = build_driver(compiler, modules, cache=tmp_path / 'cache')
    stamp = first.stat().st_mtime_ns
    for name in ('DEWY_TWIN_SCOPE_REPORT', 'DEWY_TWIN_SCOPED_OUT', 'DEWY_TEST_TRACE'):
        for value in ('first', 'second'):
            monkeypatch.setenv(name, str(tmp_path / name / value))
            assert build_driver(compiler, modules, cache=tmp_path / 'cache') == first
            assert first.stat().st_mtime_ns == stamp
    assert subprocess.run([first], capture_output=True, timeout=10, check=False).stdout == b'7\n'
    base = identity(compiler, modules)
    monkeypatch.setenv('DEWY_EMIT_WORKERS', '2')
    assert identity(compiler, modules) != base


def test_compiler_and_library_restored_mtime_edits_change_the_key(tmp_path, monkeypatch):
    compiler_path = tmp_path / 'compiler'
    compiler_path.write_bytes(b'one')
    library = tmp_path / 'lib'
    library.mkdir()
    source = library / 'rt.jo'
    source.write_bytes(b'one')
    monkeypatch.setenv('DEWY_CORE_LIB', str(library))
    modules = {'driver.jo': 'main = (): pass\n'}
    base = identity(compiler_path, modules)
    for path in (compiler_path, source):
        stamp = path.stat()
        path.write_bytes(b'two')
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        assert identity(compiler_path, modules) != base
        path.write_bytes(b'one')
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        assert identity(compiler_path, modules) == base
