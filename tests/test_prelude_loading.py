"""Demand-loaded declarations retain eager lookup, initialization and runtime roots."""
import os
import re
import shutil
import subprocess
import sys

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tools.compiler import gen_prelude_index


def run(command, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, timeout=60, **kwargs)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope='module')
def scan_check(compiler, tmp_path_factory):
    binary = tmp_path_factory.mktemp('scan-check') / 'scan_check'
    run([compiler, 'build', ROOT / 'tools/compiler/scan_check.jo', '-o', binary])
    return binary


@pytest.mark.core_quick
def test_optional_prelude_index_is_current():
    source = (ROOT / 'compiler/prelude.jo').read_text(encoding='utf-8')
    gen_prelude_index.check(ROOT, source)
    # Assignment lookup has to find the texture slot global before bulk loading.
    for target, backend in [('linux', 'vk.jo'), ('windows', 'vk.jo'), ('macos', 'metal.jo'), ('wasm', None)]:
        routes = gen_prelude_index.read_index(source, game_target=target)['game']
        for symbol in ('__vk_slot_next', '__VK_MAX_TEXTURES', '__vk_slot_new'):
            assert routes.get(symbol, set()) == ({backend} if backend else set()), (target, symbol)
        # The rasterizer needs GL constants registered by the bulk loader.
        assert '__sw_init_window' not in routes


def test_optional_prelude_index_detects_missing_entry(tmp_path):
    for folder in ('core', 'runtime', 'std', 'prelude', 'game'):
        (tmp_path / 'lib' / folder).mkdir(parents=True)
    (tmp_path / 'lib/std/optional.jo').write_text('''when TARGET == "windows":
    when not BOOTSTRAP:
        # A local and a line in a string do not name prelude declarations.
        run = ():
            local = 1
            "{local}"
        text = """
fake = 2
"""
        let first, _ = 1, 0
        wake = (): 0
    else: alternate = (): 1
else when TARGET == "macos":
    @lib("test") extern wake = () -> int
else:
    wake = (): 2
''')
    (tmp_path / 'lib/runtime/caller.jo').write_text('caller = (): "{wake()}"\n')
    (tmp_path / 'lib/prelude/caller.dewy').write_text('caller = () => p"{wake()}/file"\n')
    (tmp_path / 'lib/prelude/comment.dewy').write_text('#{\nwake()\n}#\nempty = () => "wake"\n')
    source = f'''std_optional_file = (n: str) -> bool:
    n in ["optional.jo"]
{gen_prelude_index.START}
{gen_prelude_index.END}
'''
    library = gen_prelude_index.read_library(tmp_path, source)
    names = library.optional['std']['optional.jo']
    assert names == {'alternate', 'first', 'run', 'text', 'wake'}
    names.remove('wake')
    stale = gen_prelude_index.replace_block(source, gen_prelude_index.generated_block(library))
    with pytest.raises(ValueError) as failure:
        gen_prelude_index.check(tmp_path, stale)
    assert 'stale prelude index' in str(failure.value)
    assert 'optional symbol wake is missing' in str(failure.value)
    assert 'lib/runtime/caller.jo: cross-file reference to wake in lib/std/optional.jo is missing' in str(failure.value)
    assert 'lib/prelude/caller.dewy: cross-file reference to wake' in str(failure.value)
    assert 'lib/prelude/comment.dewy' not in str(failure.value)


def test_declaration_index_matches_parser(scan_check):
    """Each library file's scanned names and units are what the parser finds in it."""
    run([scan_check, ROOT / 'lib'])


def test_prelude_known_names_listed():
    """Names the compiler reads from the prelude map directly are registered from the start."""
    listed = re.search(r'prelude_known = \[([^\]]*)\]', (ROOT / 'compiler/prelude.jo').read_text())
    known = set(re.findall(r'"([^"]+)"', listed.group(1)))
    used = set()
    for path in (ROOT / 'compiler').glob('*.jo'):
        if path.name == 'prelude.jo':
            continue
        text = path.read_text()
        used |= set(re.findall(r'prelude\.get\(intern\("([^"]+)"\)\)', text))
        used |= set(re.findall(r'rt_global\("([^"]+)"\)', text))
    assert used <= known, sorted(used - known)


def test_prelude_transitive_order(compiler, tmp_path):
    library = tmp_path / 'lib'
    shutil.copytree(ROOT / 'lib', library)
    # Request the later module first, then the earlier one through a lazy body.
    # Both overloads must be available before choosing the better match.
    (library / 'game/00_demand.jo').write_text('''__demand_order = ""
__demand_first = __demand_note("a")
__demand_note = (s: str) -> int:
    __demand_order += s
    1
demand_pick = (n: int) -> int: 10 + n
''')
    (library / 'game/01_demand.jo').write_text('''__demand_second = __demand_note("b")
demand_pick = (n: f64) -> int: 99
demand_result = () -> str:
    assert(__demand_first + __demand_second == 2)
    __demand_order
''')
    source = tmp_path / 'main.dewy'
    source.write_text('printl("{demand_result()} {demand_pick(2)}")\n')
    binary = tmp_path / 'program'
    env = dict(os.environ, DEWY_CORE_LIB=str(library))
    run([compiler, 'build', source, '-o', binary], env=env)
    assert run([binary]).stdout == 'ab 12\n'


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux C library')
def test_prelude_implicit_exit_roots(compiler, tmp_path):
    source = tmp_path / 'exit.jo'
    source.write_text('''@lib("libc.so.6")
extern puts = (s: *u8) -> i32
finish = (): print("end")
main = ():
    __at_end(finish)
    puts(data(bytes("C buffered\\0")))
    print("Dewy buffered")
''')
    binary = tmp_path / 'exit'
    run([compiler, 'build', source, '-o', binary])
    assert sorted(run([binary]).stdout.splitlines()) == ['C buffered', 'Dewy buffered', 'end']
