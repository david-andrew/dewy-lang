"""Build a bounded lexer probe from the lexer and its current Dewy leaf dependencies."""
import re
import shutil
from pathlib import Path


def lexer_span_helpers(compiler, out):
    directory = compiler.parent.parent / 'compiler'
    if not directory.exists():
        directory = Path(__file__).resolve().parents[1] / 'compiler'
    copied = set()

    def copy_leaf(module):
        if module in copied:
            return
        copied.add(module)
        source = directory / module
        shutil.copy2(source, out / module)
        for dependency in re.findall(r'^from p"([^"]+\.dewy)"', source.read_text(), re.M):
            if not dependency.startswith('@lib/'):
                copy_leaf(dependency)

    for module in ('dewy_tokens.dewy', 'dewy_lex.dewy', 'intern.dewy', 'dewy_parser.dewy', 'node_store.dewy'):
        copy_leaf(module)
    fast = (directory / 'dewy_fast.jo').read_text()
    util = (directory / 'util.jo').read_text()
    lex = (directory / 'lex.jo').read_text()
    payload = fast.index('dn_payload =')
    end = payload + len(re.match(r'[^\n]+\n(?:[ \t]+[^\n]*\n|\n)*', fast[payload:])[0])
    return '\n'.join([
        "use 'dewy_tokens.dewy'\nuse 'dewy_lex.dewy'\nuse 'intern.dewy'\nuse 'dewy_parser.dewy'",
        lex[lex.index('lx_cls:'):lex.index('is_ident_start =')],
        util[util.index('struct SrcFile:'):util.index('# position encoding')],
        'mkpos = (file: int, off: int) -> int: (file << 40) | off\n'
        'fatal = (pos: int, message: str): panic(message)\n'
        'err_notes: (int, str)[]',
        'dc_parser: ParserContext',
        fast[fast.index('dn_word_tokens:'):end],
    ])
