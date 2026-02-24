"""
semantic analysis pass 0: 
- type checking
- ambiguity resolution
"""
from dataclasses import dataclass
from ..parser import t2, t1
from ..parser import p0
from . import hir
from . import ty

from ..reporting import SrcFile, ReportException, Error, Pointer, Span


import pdb


@dataclass
class Context:
    srcfile: SrcFile
    declarations: dict[str, ty.Type]
    # TODO: probably stuff around declarations/etc

def typecheck_and_resolve(srcfile: SrcFile) -> hir.AST:
    ctx = Context(srcfile, {
        'printf': ty.TypeFunc(args=['string'], ret=ty.VOID_TYPE)
    })
    block = p0.parse(srcfile)
    return tcr_block(block, ctx=ctx)


def typecheck_and_resolve_inner(ast: p0.AST, *, ctx: Context) -> hir.AST:
    match ast:
        case p0.Block(): return tcr_block(ast, ctx=ctx)
        case p0.BinOp(): return tcr_binop(ast, ctx=ctx)
        case p0.Atom(item=t1.Identifier()): return tcr_identifier(ast.item, ctx=ctx)
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'typecheck_and_resolve_inner not implemented for {type(ast)}')


def tcr_block(block: p0.Block, *, ctx: Context) -> hir.AST:
    results = [typecheck_and_resolve_inner(item, ctx=ctx) for item in block.inner]
    pdb.set_trace()

def tcr_binop(binop: p0.BinOp, *, ctx: Context) -> hir.AST:
    # full expression
    if isinstance(binop.op, t2.QJuxtapose): #TODO: other binops that also just do both sides
        left = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        right = typecheck_and_resolve_inner(binop.right, ctx=ctx)
        pdb.set_trace()



    # more specialized structures (e.g. assignment, spread, collect, parameterization, etc.)


    pdb.set_trace()


def tcr_identifier(identifier: t1.Identifier, *, ctx: Context) -> hir.AST:
    if identifier.name in ctx.declarations:
        pdb.set_trace().
        return hir.Identifier(span, name, type=ctx.declarations[name])
        return ctx.declarations[identifier]
    
    pdb.set_trace()


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