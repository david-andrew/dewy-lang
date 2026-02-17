"""
semantic analysis pass 0: 
- type checking
- ambiguity resolution
"""

from . import t2
from . import p0

from .reporting import SrcFile, ReportException, Error, Pointer, Span

def test():
    from ..myargparse import ArgumentParser
    from pathlib import Path
    parser = ArgumentParser()
    parser.add_argument('path', type=Path, required=True, help='path to file to tokenize')
    args = parser.parse_args()
    path: Path = args.path
    src = path.read_text()
    srcfile = SrcFile(path, src)
    try:
        asts, types = typecheck_and_resolve(srcfile)
    except ReportException as e:
        print(e.report)
        exit(1)
    
    for ast in asts:
        print(p0.ast_to_tree_str(ast))
        # TODO: print the top level type of the AST
        print()
    