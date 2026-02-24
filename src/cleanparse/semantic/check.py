"""
semantic analysis pass 0: 
- type checking
- ambiguity resolution
"""
from dataclasses import dataclass
from ..parser import p0, t2, t1
from . import hir, ty
from ..reporting import SrcFile, ReportException, Error, Pointer, Span

import pdb

@dataclass
class Context:
    """global context for the typechecker"""
    srcfile: SrcFile
    declarations: dict[str, ty.Type] #TODO: handling different scopes...
    # TODO: etc stuff

def typecheck_and_resolve(srcfile: SrcFile) -> hir.AST:
    ctx = Context(srcfile, {
        'printf': ty.TypeFunc(args=['string'], ret=ty.VOID_TYPE),
        'true': 'bool',
        'false': 'bool',
    })
    block = p0.parse(srcfile)
    return tcr_block(block, ctx=ctx)


def typecheck_and_resolve_inner(ast: p0.AST, *, ctx: Context, type_block:bool=False) -> hir.AST:
    match ast:
        case p0.Block(): return tcr_block(ast, ctx=ctx)
        case p0.BinOp(): return tcr_binop(ast, ctx=ctx, type_block=type_block)
        case p0.Atom(item=t1.Identifier()): return tcr_identifier(ast.item, ctx=ctx)
        case p0.Atom(item=t1.String()): return hir.String(ast.item.loc, 'string', ast.item.content)
        # case p0.Atom(item=t1.Real()): ...
        # case p0.Atom(item=t1.BasedString()): ...
        # case p0.Atom(item=t1.Semicolon()): ...
        # case p0.Atom(item=t1.Metatag()): ...
        # case p0.Atom(item=t1.Integer()): ...
        # case p0.Atom(item=t1.Bool()): return hir.Bool(ast.item.loc, ast.item.value)
        # case p0.Atom(item=t2.OpFn()): ...
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'typecheck_and_resolve_inner not implemented for {type(ast)}')


def tcr_block(block: p0.Block, *, ctx: Context) -> hir.AST:
    # TODO: if kind=='<>' then typecheck and resolve needs to behave differently, e.g. because `|` means `type union`, not regular `or`
    type_block = block.kind == '<>'
    # scoped = block.kind == '{}' #TODO: would need to make a nested scope/context for this...
    results = [typecheck_and_resolve_inner(item, ctx=ctx, type_block=type_block) for item in block.inner]

    match block.kind:
        case '()':
            if len(results) > 1:
                return hir.Block(block.loc, results, scoped=False)
            if len(results) == 1:
                item = results[0]
                if isinstance(item, hir.Range) and item.bounds is None:
                    return hir.Range(block.loc, item.type, '()', item.step_pair, item.left, item.right) # specify exclusive bounds for this range
                return item
            return hir.Void(block.loc)
        
        case '{}':
            if len(results) > 1:
                pdb.set_trace()
                return hir.Block(block.loc, ty.BlockType, results, scoped=True) #TODO: parameterize block type based on inner content... e.g. tuple of types
            if len(results) == 1:
                return hir.Block(block.loc, results[0].type, results, scoped=True)
            return hir.Void(block.loc)

        case '[]':
            # if len==1 might be a range
            # otherwise it's an array. also arrays should handle multi-dimensions via spacing, nested arrays, ;, etc.
            # might also be a generator...
            pdb.set_trace()
        case '[)':
            if len(results) != 1 or not isinstance(results[0], hir.Range) or results[0].bounds is not None:
                # TODO: full user error report
                raise ValueError(f'USER ERROR: [) delimiter for range may only contain one (bare range) expression, got {len(results)}. {results=}')
            return hir.Range(block.loc, results[0].type, '[)', results[0].step_pair, results[0].left, results[0].right)
        case '(]':
            if len(results) != 1 or not isinstance(results[0], hir.Range) or results[0].bounds is not None:
                # TODO: full user error report
                raise ValueError(f'USER ERROR: (] delimiter for range may only contain one (bare range) expression, got {len(results)}. {results=}')
        case '<>':
            pdb.set_trace()
        case _:
            # unreachable
            raise ValueError(f'INTERNAL ERROR: invalid block kind: {block.kind}')
        
    # unreachable 
    pdb.set_trace()

def tcr_binop(binop: p0.BinOp, *, ctx: Context, type_block:bool=False) -> hir.AST:
    """
    typecheck and resolve a binary operator node.
    
    NOTE:
    type_block is used to disambiguate the context these binops occur in. 
    mainly for distinguishing type expressions using literals from regular operations between said literals
    e.g. `true | false` -> `true` vs `<true | false>` -> `literal<true>|literal<false>`
    most other operators are unaffected by this flag.
    """
    # TODO: how to handle the fact that `and` and `or` might have inner elements that need type_block? for now just pass in to left and right
    # full expression
    if isinstance(binop.op, (t2.QJuxtapose, t2.CallJuxtapose, t2.IndexJuxtapose, t2.MultiplyJuxtapose)): #TODO: other binops that also just do both sides
        left = typecheck_and_resolve_inner(binop.left, ctx=ctx, type_block=type_block)
        right = typecheck_and_resolve_inner(binop.right, ctx=ctx, type_block=type_block)
        match binop.op:
            case t2.QJuxtapose():
                pdb.set_trace()
            case t2.CallJuxtapose():
                if not isinstance(left.type, ty.TypeFunc):
                    # TODO: full user error report
                    # might have some early errors for things that are function-like, but different instances.
                    # also what about partial eval
                    pdb.set_trace() 
                    raise ValueError(f'USER ERROR: Expected a function, got {left.type} for call expression {binop}')
                # TODO: check the arguments of the function to make sure it matches the calling arguments
                
                if isinstance(right, hir.Block): 
                    args = right.items
                else:
                    args = [right]

                #TODO:perhaps we can make calls even more uniform here... e.g. dealing with named vs positional vs unpack vs collect vs etc. args
                return hir.Call(Span(left.loc.start, right.loc.stop), left.type.ret, left, args)
                pdb.set_trace()
            case t2.IndexJuxtapose():
                pdb.set_trace()
            case t2.MultiplyJuxtapose():
                pdb.set_trace()
            case _:
                pdb.set_trace()
                raise NotImplementedError(f'tcr_binop not implemented for {type(binop.op)}')
        pdb.set_trace()



    # more specialized structures (e.g. assignment, spread, collect, parameterization, etc.)
    pdb.set_trace()


# def typecheck_function_call(left: hir.AST, right: hir.AST) -> hir.Call:
#     pdb.set_trace()

# def typecheck_partial_eval(left: hir.AST, right: hir.AST) -> hir.Partial:
#     pdb.set_trace()

def tcr_identifier(id: t1.Identifier, *, ctx: Context) -> hir.AST:
    if id.name in ctx.declarations:
        return hir.Identifier(id.loc, ctx.declarations[id.name], id.name)
    
    pdb.set_trace()
    raise NotImplementedError(f'Identifier "{id.name}" not found in context')


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