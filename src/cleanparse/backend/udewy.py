"""
udewy backend for dewy compiler

for now, HIR->udewy src



features
- handle imports

- collect non-udewy constructs

"""
from textwrap import indent
from ..reporting import SrcFile
from ..semantic import hir, check, ty
from ..semantic.hir_display import type_to_dewy
from dataclasses import dataclass

import pdb

TAB = '    '

@dataclass
class Context:
    srcfile: SrcFile
    imports: list #TBD type here. maybe hir.AST



def codegen(srcfile:SrcFile) -> str:
    ast = check.typecheck_and_resolve(srcfile)
    return codegen_inner(ast)

def codegen_inner(ast: hir.AST) -> str:
    functions: dict[str, hir.FunctionLiteral] = {}
    # imports
    # etc.
    code: list[str] = []

    if not isinstance(ast, hir.Block):
        pdb.set_trace()
        raise ValueError(f"Expected Block, got {type(ast)}")

    for item in ast.items:
        if isinstance(item, hir.Declare) and isinstance(item.expr, hir.FunctionLiteral):
            functions[item.name] = item.expr
        else:
            #TODO: handling of all other stuff
            pdb.set_trace()

    # if main not declared, use the whole top level block as the main function
    if 'main' not in functions:
        functions['main'] = hir.FunctionLiteral(
            loc=ast.loc,
            type='function',
            pos_or_kw_args=[],
            kw_only_args=[],
            rest_args=None,
            rettype=ty.VOID_TYPE,
            body=ast,
        )
    
    for name, func in functions.items():
        code.append(emit_function_decl(name, func))

    return '\n'.join(code)
def emit_arg(arg: hir.Param | hir.BoundParam) -> str:
    if isinstance(arg, hir.BoundParam):
        return f'{arg.name}:{type_to_dewy(arg.type)}={arg.value}'
    return f'{arg.name}:{type_to_dewy(arg.type)}'

def _contains_return(node: hir.AST) -> bool:
    if isinstance(node, hir.Return):
        return True
    if isinstance(node, hir.Block):
        return any(_contains_return(item) for item in node.items)
    return False

def emit_function_decl(name: str, func: hir.FunctionLiteral) -> str:
    code: list[str] = []
    code.append(f'let {name} = (')

    # build the argument list
    args: list[str] = []
    for arg in func.pos_or_kw_args:
        args.append(emit_arg(arg))
    if func.rest_args is not None:
        args.append(f'...{emit_arg(func.rest_args)}')
    if func.kw_only_args:
        if func.rest_args is None: args.append('...')
        for arg in func.kw_only_args:
            args.append(emit_arg(arg))

    code.append(' '.join(args))
    code.append(f'):>{type_to_dewy(func.rettype)} => ')

    # udewy function bodies must return explicitly, so expression bodies get wrapped in a
    # return. NOTE: this lowering's real home is MIR (see the terminator sketch in mir.py)
    body = func.body
    if _contains_return(body):
        code.append(emit_ast(body))
    elif func.rettype == ty.VOID_TYPE:
        stmts = [emit_ast(item) for item in body.items] if isinstance(body, hir.Block) else [emit_ast(body)]
        code.append('{\n' + indent('\n'.join([*stmts, 'return void']), TAB) + '\n}')
    else:
        code.append('{\n' + indent(f'return {emit_ast(body)}', TAB) + '\n}')
    return ''.join(code)

def emit_ast(ast: hir.AST) -> str:
    match ast:
        case hir.Block(): return emit_block(ast)
        case hir.Return(): return emit_return(ast)
        case hir.Integer(): return emit_integer(ast)
        case _: 
            pdb.set_trace()
            raise NotImplementedError(f'emit_ast not implemented for AST type: {type(ast)}')

def emit_integer(i: hir.Integer) -> str:
    if i.prefix == '0d': return f'{i.value}'

    pdb.set_trace()

def emit_block(block: hir.Block) -> str:
    inner = indent('\n'.join(emit_ast(item) for item in block.items), TAB)
    if block.scoped:
        return f'{{\n{inner}\n}}'
    return f'(\n{inner}\n)'
# def emit_expr(expr: hir.AST. ctx: Context) -> str:

def emit_bool(expr: hir.Bool, ctx: Context) -> str:
    pdb.set_trace()


def emit_return(expr: hir.Return) -> str:
    #TODO: check is this type returnable?
    if expr.item is None:
        return 'return void'  # udewy requires an explicit value
    return f'return {emit_ast(expr.item)}'


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
    from udewy.frontend import entry_point, EntryPointOptions
    
    pdb.set_trace()
    ...