"""The driver's once-per-run pieces (command-line refusals, the library's place, the target, the
main file's build block and settings, standard-input runs, the run cache, `dewy-core test` over a
directory, other systems' libraries, a web page's save name) as a Dewy leaf agree with frozen Jo:
the same exit codes, output and files."""
import re
import subprocess

from tests.selfhost_build_double import compare_builds
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

SETTINGS = '''# $target = 'wasm32' (a comment: not a setting)
#{ nested #{ $build.mode = 'release' }# }#
$build.mode = 'release'   # the first one counts
$target = "x86_64-linux"
text = """
$target = 'wasm32'
"""
update = (dt:float64):>void => {}
main = ():>void => printl"settings {text.length}"
'''

BLOCK = '''build:
    target = x86_64-linux
    name = "Block Demo"   # a comment
    opt = release

main = ():
    print("block")
'''

# (bytes that are not UTF-8, and multi-byte characters, where the build block and settings are read)
RAGGED = (b"# \xff\x80 caf\xc3\xa9 $target = 'wasm32'\n$build.mode = 'release'   # \xe2\x80\xa6 \xff\n"
          b"$target = 'x86_64-linux' # \x80\n"
          b'main = ():>void => printl"caf\xc3\xa9"\n')

RAGGED_BLOCK = (b'build:\n    name = "Caf\xc3\xa9 \xff"   # \x80 comment\n    opt = release\n\n'
                b'main = ():\n    print("block")\n')

EXTERN = '''$extern(lib='libc.so.6')
getpid = ():>int32
main = ():>void => $unsafe printl"{getpid() >? 0}"
'''

SAVES = '''main = ():>void => {save_value("score" "3");}
'''

PASSING = '''$test
adds = ():>void => $runtime_assert(1 + 1 =? 2)
'''

# (refuted when built: the file does not build)
REFUTED = '''$test
fails = ():>void => $runtime_assert(1 + 1 =? 3)
'''

FAILING = '''$test
fails = ():>void => {
    printl"some output"
    let words = "a b c".split(" ")
    $runtime_assert(words.length =? 4)
}
$test
passes = ():>void => $runtime_assert(true)
'''


def run(binary, args, cwd, env=None, stdin=None):
    r = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, errors='surrogateescape',
                       timeout=120, check=False, input=stdin, env=env)
    # (a test's time differs from run to run)
    return r.returncode, re.sub(r'"ms":[0-9.e-]+', '"ms":0', r.stdout), r.stderr.replace(str(binary), 'dewy-core')


def test_driver_cli_builds_match_twin(compiler, tmp_path, monkeypatch):
    for name, text in (('settings.dewy', SETTINGS), ('block.jo', BLOCK), ('ext.dewy', EXTERN),
                       ('saves.dewy', SAVES)):
        (tmp_path / name).write_text(text)
    (tmp_path / 'ragged.dewy').write_bytes(RAGGED)
    (tmp_path / 'ragged_block.jo').write_bytes(RAGGED_BLOCK)
    compare_builds(compiler, tmp_path, monkeypatch, ('driver_cli',),
                   ['settings.dewy', 'block.jo', 'ext.dewy', 'saves.dewy', 'ragged.dewy', 'ragged_block.jo'],
                   flags=((), ('--target', 'x86_64-windows'), ('--target', 'wasm32')))


def test_driver_cli_commands_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    tests = tmp_path / 'suite'
    (tests / 'more').mkdir(parents=True)
    (tests / '.hidden').mkdir()
    (tests / 'a_test.dewy').write_text(PASSING)
    (tests / 'more' / 'b_test.dewy').write_text(FAILING)
    (tests / '.hidden' / 'c_test.dewy').write_text(PASSING)
    (tests / 'more' / 'r_test.dewy').write_text(REFUTED)
    (tests / 'plain.dewy').write_text('main = ():>void => printl"no tests"\n')
    (tmp_path / 'settings.dewy').write_text(SETTINGS)
    (tmp_path / 'hello.dewy').write_text('main = ():>void => printl"hello"\n')
    cases = [
        ['--bogus'], ['--runtime-checks'], ['--caf\u00e9=1'], ['--\udcff'], ['--no_hidden_costs=false'], ['$target=wasm32'],
        ['build'], ['--internal-collide-locals', 'check', 'settings.dewy'],
        ['--internal-fact-policy=require-static', 'check', 'settings.dewy'],
        ['check', 'settings.dewy'], ['hello.dewy'], ['--release', 'hello.dewy'],
        ['test', 'suite'], ['test', '--json', 'suite'], ['test', 'suite', 'adds'], ['test', 'suite', 'nothing'],
        ['test', 'suite/more'], ['test', 'suite/.hidden'],
    ]
    dewy, jo = leaf_compilers(compiler, tmp_path, ('driver_cli',))
    for args in cases:
        assert run(dewy, args, tmp_path) == run(jo, args, tmp_path), args
    # (--time: timings differ from run to run; the source counts do not)
    timed = [run(binary, ['build', '--time', 'settings.dewy', '-o', 'timed'], tmp_path) for binary in (dewy, jo)]
    sources = [[line for line in t[2].splitlines() if line.startswith('sources:')] for t in timed]
    assert sources[0] == sources[1] and len(sources[0]) == 1, timed
    program = 'main=():>void=>printl"from stdin"\n'
    assert run(dewy, [], tmp_path, stdin=program) == run(jo, [], tmp_path, stdin=program)
    # (no library beside these compilers: where they looked)
    env = {'PATH': '/usr/bin:/bin', 'DEWY_CORE_LIB': ''}
    got, expected = run(dewy, ['hello.dewy'], tmp_path, env), run(jo, ['hello.dewy'], tmp_path, env)
    assert got[0] == expected[0] == 2
    assert got[2].replace(str(dewy.parent.parent), '<dir>') == expected[2].replace(str(jo.parent.parent), '<dir>')
