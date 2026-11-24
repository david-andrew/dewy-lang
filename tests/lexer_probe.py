"""Link bounded-span probes with the live lexer and its initialized host services."""
from pathlib import Path
import shutil


def lexer_span_helpers(compiler, out):
    directory = compiler.parent.parent / 'compiler'
    if not directory.is_dir():
        directory = Path(__file__).resolve().parents[1] / 'compiler'
    copied = out / 'compiler'
    shutil.copytree(directory, copied)
    # All cyclic imports still resolve to one main module. The probe supplies
    # the entry point and selects its own optimization level.
    main = copied / 'main.jo'
    prefix, entry, _ = main.read_text().partition('main = ():\n')
    assert entry
    main.write_text(prefix.replace('build:\n    opt = release\n', ''))
    return ''.join(f"use '{(copied / name).as_posix()}'\n" for name in (
        'main.jo', 'dewy_fast.jo', 'dewy_context.jo', 'dewy_frontend.dewy',
        'dewy_fast_lex.dewy', 'dewy_lexer.dewy', 'dewy_lex.dewy', 'dewy_parser.dewy',
        'source_types.dewy', 'dewy_tokens.dewy', 'util.jo'))
