"""
udewy backend for dewy compiler

for now, HIR->udewy src
"""
from ..reporting import SrcFile
from ..semantic import hir, check

import pdb

def codegen(srcfile:SrcFile) -> str:
    ast = check.typecheck_and_resolve(srcfile)
    return codegen_inner(ast)

def codegen_inner(ast: hir.AST) -> str:
    pdb.set_trace()
    ...




if __name__ == '__main__':
    from ...myargparse import ArgumentParser
    from pathlib import Path
    parser = ArgumentParser()
    parser.add_argument('path', type=Path, required=True, help='path to file to compile')
    args = parser.parse_args()
    path: Path = args.path
    srcfile = SrcFile.from_path(path)
    udewy = codegen(srcfile)
    
    # would run the udewy src through the udewy compiler at this point...
    pdb.set_trace()
    ...