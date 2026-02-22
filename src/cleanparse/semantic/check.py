"""
semantic analysis pass 0: 
- type checking
- ambiguity resolution
"""

from ..parser import t2
from ..parser import p0
from . import hir
from . import ty

from ..reporting import SrcFile, ReportException, Error, Pointer, Span






def typecheck_and_resolve(srcfile: SrcFile) -> hir.AST:
    block = p0.parse(srcfile)
    import pdb; pdb.set_trace()


def test():
    from ...myargparse import ArgumentParser
    from pathlib import Path
    parser = ArgumentParser()
    parser.add_argument('path', type=Path, required=True, help='path to file to tokenize')
    args = parser.parse_args()
    path: Path = args.path
    src = path.read_text()
    srcfile = SrcFile(path, src)
    try:
        ast = typecheck_and_resolve(srcfile)
    except ReportException as e:
        print(e.report)
        exit(1)
    
    # TODO: some sort of tree print for HIR
    print(ast)
    
if __name__ == '__main__':
    test()