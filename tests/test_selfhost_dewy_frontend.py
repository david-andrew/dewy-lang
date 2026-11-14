"""Lex/file entry ownership agrees with frozen Jo on byte output, lazy bodies and diagnostics."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_dewy_frontend_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_EMIT_WORKERS', '1')
    # Dense one-byte tokens force growth beyond the lexer's initial half-byte estimate.
    (tmp_path / 'dense.dewy').write_text('main=()=>{\nlet x=' + '(' * 64 + '1' + ')' * 64 + '\nprintl(x)\n}\n')
    globs = ('string/*.dewy', 'interpolation_spec_habit/*.dewy', 'decimal_restart/lazy*.dewy',
             'generic/*.dewy', 'metatag_prefix/*.dewy')
    cases = [p for glob in globs for p in sorted((ROOT / 'tests/cases').glob(glob))[:18]]
    paths = ['dense.dewy', 'tests/ladder/99_dewy_frontend/design.dewy'] + [str(p.relative_to(ROOT)) for p in cases]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('dewy_frontend',), paths,
                             flags=((), ('--release',), ('--ir',)))
    assert sum(r[2] == 0 for r in results) >= 6


def test_dewy_frontend_lex_snapshots(compiler, tmp_path, monkeypatch):
    import subprocess
    from tests import selfhost_lsp_double
    from tests.selfhost_lsp_double import leaf_compilers

    driver = r'''use 'main.jo'
use 'dewy_frontend.dewy'
use 'dewy_fast.jo'
use 'dewy_tokens.dewy'
use 'source_types.dewy'
use 'util.jo'
main = ():
    lower_test_cli()
    frontend_bind(&names as *int, &name_hash as *int, &name_tab as *int, &dn_lex_host as *int)
    file = files.len()
    source = "  ()[]{{}};,()[]{{}};,()[]{{}};, # tail\n"
    files.push(SrcFile(path="tokens.dewy", src=source))
    names_before = names.len()
    first = dn_lex(file, 0, len(source), false)
    assert(names.len() == names_before)
    count = first.len() - DN_EOF_SPARE - 1
    assert(count == 24 and first[0].symbol == .lparen and first[23].symbol == .comma)
    loop i in [count..first.len()):
        assert(first[i].kind == .eof and first[i].start == len(source) and first[i].stop == len(source))
    files[file].src = "abc abc #{{comment}}#\n"
    second = dn_lex(file, 0, len(files[file].src))
    assert(second[0].name == second[1].name and dn_block_comments.len() == 2)
    assert(first[0].symbol == .lparen and first[23].symbol == .comma)
    # Empty bounded interpolation spans still publish the complete spare EOF run.
    empty = dn_lex(file, 3, 3, false)
    assert(empty.len() == DN_EOF_SPARE + 1 and dn_block_comments.len() == 0)
    loop token in empty: assert(token.kind == .eof and token.start == 3 and token.stop == 3)
    print("lex ok")
'''
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', driver)
    source = tmp_path / 'empty.dewy'
    source.write_text('main=()=>{}\n')
    binaries = leaf_compilers(compiler, tmp_path, ('dewy_frontend',))
    outputs = []
    for binary in binaries:
        ran = subprocess.run([binary, 'build', source, '-o', tmp_path / 'empty'],
                             capture_output=True, timeout=120)
        assert ran.returncode == 0, ran.stderr
        outputs.append((ran.stdout, ran.stderr))
    assert outputs[0] == outputs[1] and outputs[0][0] == b'lex ok\n'
