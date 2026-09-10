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


def test_native_numeric_prelude(tmp_path):
    entry = tmp_path / 'numeric.dewy'
    entry.write_text('let value:int64=min(7 9)\n')
    names = ['linux/files', 'linux/process', 'strings', 'arrays', 'path', 'unicode',
             'math', 'rational', 'fixed', 'bigint', 'bigrational']
    prelude = [ROOT / f'library/{name}.dewy' for name in names]
    assert run_module(tmp_path, entry, prelude, timeout=600) == ['value:int64']


def test_native_library_search_roots(tmp_path):
    library = tmp_path / 'library'
    library.mkdir()
    (library / 'example.dewy').write_text('Word:type=int64\nlet answer:Word=42\n')
    entry = tmp_path / 'uses-library.dewy'
    entry.write_text('from example import Word, answer\nlet value:Word=answer\n')
    assert run_module(tmp_path, entry, ['--library-root', library]) == ['value:int64']


def test_native_string_methods_after_literal_exclusions(tmp_path):
    prelude = tmp_path / 'string-method.dewy'
    prelude.write_text('_string_startswith=(text:string prefix:string):>bool=>false\n')
    entry = tmp_path / 'options.dewy'
    entry.write_text('''classify=(arg:string):>int64=>{
        if arg =? '--help' or arg =? '-h' return 0
        else if arg.startswith('-') return 1
        return arg.length
    }
''')
    assert run_module(tmp_path, entry, [prelude]) == ['classify:<(arg:string):>int64>']


def test_native_string_enum_interpolation(tmp_path):
    entry = tmp_path / 'stage-label.dewy'
    entry.write_text('Stage:type="t0"|"t1"|"t2"|"p0"\nlabel=(stage:Stage):>string=>"{stage} tokens"\n')
    result = run_module(tmp_path, entry, [])
    assert result[-1].startswith('label:')
