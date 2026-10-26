"""The tokenizing loop and frozen twin agree on every tracked Dewy source.

The probe enters the real Jo adapter, comparing every token field, spare EOFs,
block-comment spans, metatag/lazy state and first lexical diagnostics. Generated
inputs also exercise non-interning layout, lazy bodies, malformed bytes, token
array growth and nonzero source spans. Both compiler build modes are checked.
"""
import random
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tools.compiler import parser_diff


PROBE = '''    if a.len() > 3 and a[1] == "--lexer-probe":
        path = a[2]
        source = read_file(path) ?? ""
        files.push(SrcFile(path, "", source, true))
        dc_parser.file = files.len() - 1
        dn_skip_bodies = a[3] == "lazy" or a[3] == "lazy-nointern"
        begin = if a.len() > 4: to_int(a[4]) ?? 0 else: 0
        stop = if a.len() > 5: to_int(a[5]) ?? len(source) else: len(source)
        tokens = dn_lex(dc_parser.file, begin, stop, a[3] == "lazy" or a[3] == "intern")
        loop t in tokens: print("{int(t.kind)} {t.name} {t.start} {t.stop} {t.space} {t.newline} {int(t.symbol)}")
        print("meta {dn_metatags} lazy {dc_parser.reader.dn_lazy_left}")
        loop c in dn_block_comments: print("comment {c}")
        return
'''


def build_pair(seed, work, release):
    tree = work / 'source'
    for name in ('compiler', 'lib'):
        shutil.copytree(parser_diff.ROOT / name, tree / name)
    main = tree / 'compiler/main.jo'
    text = "use 'source_types.dewy'\n" + main.read_text().replace('build:\n    opt = release\n', '')
    main.write_text("use 'dewy_fast.jo'\nuse 'dewy_context.jo'\n" +
                    text.replace('    a = args()\n', '    a = args()\n' + PROBE, 1))
    binaries = []
    for side in ('dewy', 'twin'):
        if side == 'twin':
            for path in (tree / 'compiler').glob('*.jo'):
                path.write_text(path.read_text().replace("use 'dewy_lexer.dewy'", "use 'dewy_lexer.jo'"))
        binary = work / side
        run = subprocess.run([seed, 'build', main, '-o', binary,
                              *(['--release'] if release else [])],
                             env=parser_diff.environment(tree / 'lib'),
                             capture_output=True, timeout=300)
        assert run.returncode == 0, (run.stdout + run.stderr).decode(errors='replace')
        binaries.append(binary)
    return binaries


def compare(pair, source, mode, begin=None, stop=None):
    arguments = ['--lexer-probe', str(source), mode]
    if begin is not None:
        arguments += [str(begin), str(stop)]
    results = [subprocess.run([binary, *arguments], capture_output=True, timeout=15,
                             env=parser_diff.environment(parser_diff.ROOT / 'lib'))
               for binary in pair]
    a, b = results
    assert (a.returncode, a.stdout, a.stderr) == (b.returncode, b.stdout, b.stderr), (
        source, mode, begin, stop, a.stdout[:1000], b.stdout[:1000], a.stderr, b.stderr)
    assert b'panic:' not in a.stderr, (source, a.stderr)


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_lexer_matches_frozen_corpus(compiler, tmp_path, release):
    pair = build_pair(compiler, tmp_path, release)
    sources = parser_diff.corpus()
    assert sources
    for source in sources:
        compare(pair, source, 'intern')
    rng = random.Random(117)
    examples = [b'', b'()[]{}' * 2000, b'#!\n#{outer\n#{inner}#}# x\\ \n+y',
                b'let x="{if true {"{1}"} else {"x"}}"',
                b'f=()=>{let x=1}\ng=()=>{$runtime_checks printl("x")}',
                b'and= or= xor= is? isnt? in? >>=> >>= .not<=? .//= $thing',
                'x₁₂ x_12 x¹² x‾12 µ μ'.encode(),
                b'"\xff" \x80abc r"\x80" 0b"101" 0x 1e+ #\xff',
                b'#{not closed', b'"not closed', b'"{not closed', b'\\\n$']
    alphabet = b'abc09_ \n\t#{}[]()\\\'".:=<>?\x80\xff'
    examples += [bytes(rng.choice(alphabet) for _ in range(rng.randrange(100))) for _ in range(32)]
    for number, data in enumerate(examples):
        source = tmp_path / f'generated-{number}.dewy'
        source.write_bytes(data)
        for mode in ('intern', 'nointern', 'lazy', 'lazy-nointern'):
            compare(pair, source, mode)
            cut = rng.randrange(len(data) + 1)
            compare(pair, source, mode, cut, len(data))


@pytest.mark.core_quick
def test_lexer_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_lexer.dewy\0' in binary
    assert b'/compiler/dewy_lexer.jo\0' not in binary
