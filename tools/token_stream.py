"""Print a Dewy file's token stream one token per line, for comparing the
bootstrap tokenizer/parser against the Python reference:

    python tools/token_stream.py FILE            # t0: the raw tokens (class, span, source)
    python tools/token_stream.py FILE --stage t1 # t1: post-tokens (numbers, strings, blocks nested)
    python tools/token_stream.py FILE --stage t2 # t2: chains and juxtaposition (nested)
    python tools/token_stream.py FILE --stage p0 # p0: the AST tree

The bootstrap side should print the same shape from its own stages so the two
can be diffed. Whitespace tokens are included (they matter for juxtaposition).
"""
from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dewy.parser import p0, t0, t1, t2   # noqa: E402
from dewy.reporting import ReportException, SrcFile   # noqa: E402


def _span(token) -> str:
    return f'{token.loc.start}..{token.loc.stop}'


def _text(srcfile: SrcFile, token) -> str:
    return repr(srcfile.body[token.loc.start:token.loc.stop])


def dump_t0(srcfile: SrcFile) -> None:
    for token in t0.tokenize(srcfile):
        print(f'{type(token).__name__:<28} {_span(token):<12} {_text(srcfile, token)}')


def _dump_nested(srcfile: SrcFile, tokens, depth: int = 0) -> None:
    for token in tokens:
        children = next((value for value in (getattr(token, name, None) for name in ('inner', 'items', 'parts', 'arms')) if isinstance(value, list)), None)
        label = type(token).__name__
        detail = ''
        if isinstance(token, t1.Operator):
            detail = f' {token.symbol!r}'
        elif isinstance(token, (t1.Identifier, t1.Keyword, t1.Metatag)):
            detail = f' {token.name!r}'
        elif isinstance(token, t1.Block):
            detail = f' {token.kind!r}'
        elif isinstance(token, t2.InvertedComparisonOp):
            detail = f' not{token.op!r}'
        print(f'{"  " * depth}{label}{detail:<20} {_span(token):<12} {_text(srcfile, token) if children is None else ""}')
        if children is not None:
            _dump_nested(srcfile, children, depth + 1)


def dump_t1(srcfile: SrcFile) -> None:
    _dump_nested(srcfile, t1.tokenize(srcfile))


def dump_t2(srcfile: SrcFile) -> None:
    _dump_nested(srcfile, t2.postok(srcfile))


def dump_p0(srcfile: SrcFile) -> None:
    print(p0.ast_to_tree_str(p0.parse(srcfile)))


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description='print a Dewy file\'s token stream or AST from the Python reference stages')
    parser.add_argument('path', type=Path)
    parser.add_argument('--stage', choices=['t0', 't1', 't2', 'p0'], default='t0')
    args = parser.parse_args(argv)
    srcfile = SrcFile(args.path, args.path.read_text())
    try:
        {'t0': dump_t0, 't1': dump_t1, 't2': dump_t2, 'p0': dump_p0}[args.stage](srcfile)
    except ReportException as e:
        print(e.report, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
