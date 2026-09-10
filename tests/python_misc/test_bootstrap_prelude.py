"""Ordered prelude modules share identities while user scopes can shadow them."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
_DRIVER = None


def module_driver(tmp_path):
    global _DRIVER
    if _DRIVER is None:
        output = tmp_path / 'module-checker.udewy'
        output.write_text(codegen(SrcFile.from_path(ROOT / 'tests/fixtures/bootstrap_module_check.dewy')))
        assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
        _DRIVER = cache_artifact(output).resolve()
    return _DRIVER


def run_module(tmp_path, entry, prelude, *, timeout=180):
    result = subprocess.run([module_driver(tmp_path), entry, *prelude], capture_output=True, text=True, timeout=timeout, check=False)
    assert result.returncode == 0, result.stderr + result.stdout
    return result.stdout.splitlines()


def test_native_ordered_prelude_and_shadowing(tmp_path):
    first = tmp_path / 'first.dewy'
    first.write_text('let answer:int64=7\nlet original=():>int64=>answer\n')
    second = tmp_path / 'second.dewy'
    second.write_text('let next=():>int64=>original()+1\n')
    entry = tmp_path / 'entry.dewy'
    entry.write_text('let answer:string="local"\nlet result:int64=next()\n')
    assert run_module(tmp_path, entry, [first, second]) == ['answer:string', 'result:int64']
    bare = tmp_path / 'bare.dewy'
    bare.write_text('$no_prelude=true\nlet answer:int64=7\n')
    assert run_module(tmp_path, bare, [tmp_path / 'must-not-be-read.dewy']) == ['answer:int64']


def test_native_filesystem_and_process_prelude(tmp_path):
    entry = tmp_path / 'entry.dewy'
    entry.write_text('let bytes:array<uint8>=_c_string("ok")\n')
    prelude = [ROOT / 'library/linux/files.dewy', ROOT / 'library/linux/process.dewy']
    assert run_module(tmp_path, entry, prelude) == ['bytes:array<uint8>']


def test_native_portable_prelude_and_embedded_unicode(tmp_path):
    entry = tmp_path / 'entry.dewy'
    entry.write_text('let value:int64=min(7 9)\nlet path=p"folder/file.txt"\nlet folded:string="Straße".casefold\n')
    names = ['linux/files', 'linux/process', 'strings', 'arrays', 'path', 'unicode', 'math']
    prelude = [ROOT / f'library/{name}.dewy' for name in names]
    assert run_module(tmp_path, entry, prelude, timeout=300) == ['value:int64', 'path:p"folder/file.txt"', 'folded:string']
