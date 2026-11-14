"""The Dewy fast lexer adapter and its frozen Jo twin agree on tokens and state."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''use 'main.jo'
use 'dewy_fast.jo'
use 'dewy_frontend.dewy'
use 'dewy_fast_lex.dewy'
use 'dewy_context.jo'
use 'source_types.dewy'
use 'util.jo'
main = ():
    a = args()
    source = read_file(a[1]) ?? ""
    files.push(SrcFile(a[1], "", source, true))
    dc_parser.file = files.len() - 1
    dn_skip_bodies = a[2] == "lazy"
    canonical = dn_identifier_canonical("x₁_2¹²µμ")
    print("canon:{canonical}")
    tokens = dn_lex(dc_parser.file, 0, len(source), a[2] != "nointern")
    loop t in tokens: print("{int(t.kind)}:{t.name}:{t.start}:{t.stop}:{t.space}:{t.newline}:{int(t.symbol)}:{dn_payload(t)}")
    print("meta:{dn_metatags}:lazy:{dc_parser.reader.dn_lazy_left}")
    loop c in dn_block_comments: print("comment:{c}")
'''


def test_fast_lex_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('dewy_fast_lex',))
    sources = [
        b'', b'let x = 1\n', b'foo() +=? 3\n', b'#{note\n}#\n$tag x',
        'x₁₂ x_12 x¹² x‾12 µ μ'.encode(),
        b'f=()=>{let x=1}\ng=()=>{$runtime_checks printl("x")}',
        b'0b"101" 0x10 1.2e3 r"raw" "{x}"\n',
    ]
    for i, data in enumerate(sources):
        source = tmp_path / f'case-{i}.dewy'
        source.write_bytes(data)
        for mode in ('intern', 'nointern', 'lazy'):
            results = [subprocess.run([binary, source, mode], capture_output=True, timeout=15)
                       for binary in binaries]
            assert (results[0].returncode, results[0].stdout, results[0].stderr) == (
                results[1].returncode, results[1].stdout, results[1].stderr), (source, mode, results)
            assert results[0].returncode == 0, (source, mode, results[0].stderr)
    assert b'canon:x_12' in results[0].stdout
