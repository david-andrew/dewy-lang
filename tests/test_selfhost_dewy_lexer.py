"""Check tokenization and first diagnostics on pinned and generated inputs."""
import random
import shutil
import subprocess

import pytest

from tests.corpus_cache import corpus_paths, SHARDS, built_once, shard_of
from tests.support import compiler  # noqa: F401
from tests import leaf_oracle
from tools.compiler import parser_diff


PROBE = '''    if a.len() > 3 and a[1] == "--lexer-probe":
        path = a[2]
        source = read_file(path) ?? ""
        files.push(SrcFile(path, "", source, true))
        dc_parser.file = files.len() - 1
        dn_skip_bodies = a[3] == "lazy" or a[3] == "lazy-nointern"
        begin = if a.len() > 4: to_int(a[4]) ?? 0 else: 0
        stop = if a.len() > 5: to_int(a[5]) ?? len(source) else: len(source)
        tokens = dn_lex(dc_parser.file, begin, stop, a[3] == "lazy" or a[3] == "intern" or a[3] == "snapshot")
        assert(tokens.len() >= DN_EOF_SPARE + 1)
        loop i in [0..tokens.len()):
            t = tokens[i]
            assert(begin <= t.start and t.start <= t.stop and t.stop <= stop)
            assert((t.kind == .eof) == (i >= tokens.len() - DN_EOF_SPARE - 1))
            if t.kind == .eof: assert(t.start == stop and t.stop == stop)
            if a[3] == "snapshot": print("{int(t.kind)} {t.name} {t.start} {t.stop} {t.space} {t.newline} {int(t.symbol)}")
        print("meta {dn_metatags} lazy {dc_parser.reader.dn_lazy_left}")
        if a[3] == "snapshot":
            loop c in dn_block_comments: print("comment {c}")
        return
'''


def build_pair(seed, work, release):
    tree = work / 'source'
    for name in ('compiler', 'lib'):
        shutil.copytree(parser_diff.ROOT / name, tree / name)
    main = tree / 'compiler/main.jo'
    text = "use 'source_types.dewy'\n" + main.read_text().replace('build:\n    opt = release\n', '')
    entry = 'main = ():\n'
    assert text.count(entry) == 1
    main.write_text("use 'dewy_fast.jo'\nuse 'dewy_frontend.dewy'\nuse 'dewy_fast_lex.dewy'\nuse 'dewy_context.jo'\n" +
                    text.replace(entry, entry + '    a = args()\n' + PROBE))
    binary = work / 'dewy'
    run = subprocess.run([seed, 'build', main, '-o', binary, *(['--release'] if release else [])],
                         env=parser_diff.environment(tree / 'lib'), capture_output=True, timeout=300)
    assert run.returncode == 0, (run.stdout + run.stderr).decode(errors='replace')
    return binary


def probe(pair, source, mode, begin=None, stop=None):
    arguments = ['--lexer-probe', str(source), mode]
    if begin is not None:
        arguments += [str(begin), str(stop)]
    a = subprocess.run([pair, *arguments], capture_output=True, timeout=15,
                       env=parser_diff.environment(parser_diff.ROOT / 'lib'))
    assert b'panic:' not in a.stderr, (source, a.stderr)
    assert a.returncode in (0, 1), (source, arguments, a.stderr)
    assert b'meta ' in a.stdout if a.returncode == 0 else b'error:' in a.stderr, (source, a.stderr)
    if mode == 'snapshot':
        leaf_oracle.check(arguments, a.returncode, leaf_oracle.without(None, a.stdout + a.stderr))
    return a


def shared_pair(compiler, release):
    return built_once(('lexer', str(compiler), release), lambda directory: build_pair(compiler, directory, release))


@pytest.mark.parametrize('release, shard', [
    pytest.param(release, k, id=f'{name}-{k}of{SHARDS}', marks=pytest.mark.xdist_group(name=f'lexer-{name}-{k}'))
    for release, name in ((False, 'default'), (True, 'release')) for k in range(SHARDS)])
def test_lexer_corpus(compiler, release, shard):
    pair = shared_pair(compiler, release)
    sources = corpus_paths()
    assert sources
    for source in shard_of(sources, shard):
        probe(pair, source, 'snapshot')


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_lexer_generated_spans(compiler, tmp_path, release):
    pair = shared_pair(compiler, release)
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
            whole = probe(pair, source, mode)
            if number < 2:  # empty input and enough delimiters to grow the token array
                assert whole.returncode == 0, whole.stderr
            if 8 <= number <= 10:  # unterminated comment, quote and interpolation
                assert whole.returncode == 1, whole.stdout
            cut = rng.randrange(len(data) + 1)
            probe(pair, source, mode, cut, len(data))


@pytest.mark.core_quick
def test_lexer_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_lexer.dewy\0' in binary
    assert b'/compiler/dewy_lexer.jo\0' not in binary
