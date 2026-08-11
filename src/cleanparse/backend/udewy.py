"""
udewy backend for dewy compiler

for now, HIR->udewy src



features
- handle imports

- collect non-udewy constructs

"""
from dataclasses import dataclass
from textwrap import indent

from ..reporting import SrcFile
from ..semantic import builtins, check, hir, ty
from ..semantic.hir_display import type_to_dewy

TAB = '    '

UDEWY_BINOP_DUNDERS = {
    '__add__': '+',
    '__sub__': '-',
    '__mul__': '*',
    '__floordiv__': '//',
    '__mod__': '%',
    '__lshift__': '<<',
    '__rshift__': '>>',
    '__eq__': '=?',
    '__ne__': 'not=?',
    '__gt__': '>?',
    '__lt__': '<?',
    '__ge__': '>=?',
    '__le__': '<=?',
    '__and__': 'and',
    '__or__': 'or',
    '__xor__': 'xor',
}

UDEWY_PREFIX_DUNDERS = {
    '__unary_sub__': '-',
    '__not__': 'not',
}

SIGNED_FIXED_INTS = {'int8', 'int16', 'int32', 'int64'}
UNSIGNED_FIXED_INTS = {'uint8', 'uint16', 'uint32', 'uint64'}
NARROW_FIXED_INTS = {'int8', 'int16', 'int32', 'uint8', 'uint16', 'uint32'}
UNSUPPORTED_NARROW_DUNDERS = {
    '__add__',
    '__sub__',
    '__mul__',
    '__floordiv__',
    '__mod__',
    '__lshift__',
    '__rshift__',
}
SIGNED_ONLY_DUNDERS = {'__floordiv__', '__mod__', '__gt__', '__lt__', '__ge__', '__le__'}

@dataclass
class EmitContext:
    direct_function_names: set[str]
    local_names: set[str]



def codegen(srcfile:SrcFile) -> str:
    ast = check.typecheck_and_resolve(srcfile)
    return codegen_inner(ast)

def codegen_inner(ast: hir.AST) -> str:
    functions: dict[str, hir.FunctionLiteral] = {}
    # imports
    # etc.
    code: list[str] = []

    if not isinstance(ast, hir.Block):
        raise TypeError(f"Expected Block, got {type(ast)}")

    for item in ast.items:
        if isinstance(item, hir.Declare) and isinstance(item.expr, hir.FunctionLiteral):
            functions[item.name] = item.expr
        else:
            #TODO: handling of all other stuff
            raise NotImplementedError(f'udewy codegen not implemented for top-level item: {type(item).__name__}')

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

    ctx = EmitContext(set(functions) | set(builtins.builtin_types), set())
    for name, func in functions.items():
        code.append(emit_function_decl(name, func, ctx))

    return '\n'.join(code) + '\n'


def emit_type(t: ty.Type) -> str:
    """Render a semantic type in the annotation syntax accepted by udewy."""
    return type_to_dewy(t)


def emit_arg(arg: hir.Param | hir.BoundParam) -> str:
    if isinstance(arg, hir.BoundParam):
        return f'{arg.name}:{emit_type(arg.type)}={arg.value}'
    return f'{arg.name}:{emit_type(arg.type)}'

def _contains_return(node: hir.AST) -> bool:
    if isinstance(node, hir.Return):
        return True
    if isinstance(node, hir.Block):
        return any(_contains_return(item) for item in node.items)
    return False

def emit_function_decl(name: str, func: hir.FunctionLiteral, ctx: EmitContext) -> str:
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
    code.append(f'):>{emit_type(func.rettype)} => ')

    # udewy function bodies must return explicitly, so expression bodies get wrapped in a
    # return. NOTE: this lowering's real home is MIR (see the terminator sketch in mir.py)
    local_names = {arg.name for arg in func.pos_or_kw_args}
    local_names.update(arg.name for arg in func.kw_only_args)
    if func.rest_args is not None:
        local_names.add(func.rest_args.name)
    func_ctx = EmitContext(ctx.direct_function_names, local_names)
    body = func.body
    if _contains_return(body):
        code.append(emit_ast(body, func_ctx))
    elif func.rettype == ty.VOID_TYPE:
        stmts = [emit_ast(item, func_ctx) for item in body.items] if isinstance(body, hir.Block) else [emit_ast(body, func_ctx)]
        code.append('{\n' + indent('\n'.join([*stmts, 'return void']), TAB) + '\n}')
    else:
        code.append('{\n' + indent(f'return {emit_ast(body, func_ctx)}', TAB) + '\n}')
    return ''.join(code)

def emit_ast(ast: hir.AST, ctx: EmitContext) -> str:
    match ast:
        case hir.Block(): return emit_block(ast, ctx)
        case hir.Return(): return emit_return(ast, ctx)
        case hir.Integer(): return emit_integer(ast)
        case hir.Bool(): return 'true' if ast.value else 'false'
        case hir.Void(): return 'void'
        case hir.Declare(): return emit_declare(ast, ctx)
        case hir.Assign(): return emit_assign(ast, ctx)
        case hir.Transmute(): return emit_transmute(ast, ctx)
        case hir.ExpressedIdentifier(): return ast.name
        case hir.FunctionCall(): return emit_function_call(ast, ctx)
        case _:
            raise NotImplementedError(f'emit_ast not implemented for AST type: {type(ast).__name__}')

def emit_declare(decl: hir.Declare, ctx: EmitContext) -> str:
    # udewy requires a type annotation on every binding; derive one from the
    # checked expression when the source didn't provide it explicitly
    if isinstance(decl.expr, hir.FunctionLiteral):
        raise NotImplementedError(
            'udewy target does not support local function literals or closures'
        )
    annotation = decl.annotation if decl.annotation is not None else decl.expr.type
    return f'{decl.decltype} {decl.name}:{emit_type(annotation)} = {emit_ast(decl.expr, ctx)}'


def emit_assign(assign: hir.Assign, ctx: EmitContext) -> str:
    return f'{emit_ast(assign.target, ctx)} {assign.op} {emit_ast(assign.value, ctx)}'


def emit_transmute(transmute: hir.Transmute, ctx: EmitContext) -> str:
    return f'{emit_ast(transmute.expr, ctx)} transmute {emit_type(transmute.type)}'


def _binop_call(call: hir.FunctionCall) -> tuple[str, hir.AST, hir.AST] | None:
    if len(call.pos_args) != 2 or call.kw_args or not isinstance(call.func, hir.ExpressedIdentifier):
        return None
    symbol = UDEWY_BINOP_DUNDERS.get(call.func.name)
    if symbol is None:
        return None
    return symbol, call.pos_args[0], call.pos_args[1]


def _prefix_call(call: hir.FunctionCall) -> tuple[str, hir.AST] | None:
    if len(call.pos_args) != 1 or call.kw_args or not isinstance(call.func, hir.ExpressedIdentifier):
        return None
    symbol = UDEWY_PREFIX_DUNDERS.get(call.func.name)
    if symbol is None:
        return None
    return symbol, call.pos_args[0]


def _selected_first_parameter(call: hir.FunctionCall) -> ty.TypeExpr | None:
    if not isinstance(call.func, hir.ExpressedIdentifier):
        return None
    if not isinstance(call.func.type, ty.FunctionType) or not call.func.type.pos_or_kw:
        return None
    return call.func.type.pos_or_kw[0].type


def _check_supported_integer_operation(call: hir.FunctionCall) -> None:
    if not isinstance(call.func, hir.ExpressedIdentifier):
        return
    name = call.func.name
    if name not in UDEWY_BINOP_DUNDERS and name not in UDEWY_PREFIX_DUNDERS:
        return
    operand_type = _selected_first_parameter(call)
    if operand_type == 'int':
        raise NotImplementedError(
            f'udewy codegen for abstract `int` operation `{name}` requires range-based lowering'
        )
    if operand_type in NARROW_FIXED_INTS and (
        name in UNSUPPORTED_NARROW_DUNDERS or name in {'__unary_sub__', '__not__'}
    ):
        raise NotImplementedError(
            f'udewy codegen for rollover operation `{name}` on `{operand_type}`'
        )
    if operand_type in UNSIGNED_FIXED_INTS and name in SIGNED_ONLY_DUNDERS:
        raise NotImplementedError(
            f'udewy codegen for unsigned operation `{name}` on `{operand_type}`'
        )


def emit_function_call(call: hir.FunctionCall, ctx: EmitContext) -> str:
    _check_supported_integer_operation(call)
    if (
        isinstance(call.func, hir.ExpressedIdentifier)
        and call.func.name == '__rshift__'
        and len(call.pos_args) == 2
        and not call.kw_args
    ):
        left, right = call.pos_args
        operand_type = _selected_first_parameter(call)
        if operand_type in SIGNED_FIXED_INTS:
            return f'__signed_shr__({emit_ast(left, ctx)} {emit_ast(right, ctx)})'
        if operand_type not in UNSIGNED_FIXED_INTS:
            raise NotImplementedError(
                f'udewy codegen for right shift of `{type_to_dewy(operand_type)}`'
            )
    if (binop := _binop_call(call)) is not None:
        sym, left, right = binop
        return f'{emit_operand(left, ctx)} {sym} {emit_operand(right, ctx)}'
    if (prefix := _prefix_call(call)) is not None:
        sym, item = prefix
        separator = ' ' if sym.isalpha() else ''
        return f'{sym}{separator}{emit_operand(item, ctx)}'
    if call.kw_args:
        raise NotImplementedError('udewy codegen for keyword arguments')
    args = ' '.join(emit_ast(arg, ctx) for arg in call.pos_args)
    callee = emit_ast(call.func, ctx)
    if (
        isinstance(call.func, hir.ExpressedIdentifier)
        and call.func.name in ctx.direct_function_names
        and call.func.name not in ctx.local_names
    ):
        return f'{callee}({args})'
    if isinstance(call.func, hir.Block) and not call.func.scoped:
        return f'{callee}({args})'
    return f'({callee})({args})'


def emit_operand(node: hir.AST, ctx: EmitContext) -> str:
    # TODO: precedence-aware parenthesization; for now always wrap nested infix calls
    if isinstance(node, hir.FunctionCall) and _binop_call(node) is not None:
        return f'({emit_ast(node, ctx)})'
    return emit_ast(node, ctx)

def emit_integer(i: hir.Integer) -> str:
    if i.prefix == '0x':
        return f'0x{i.value:x}'
    if i.prefix == '0b':
        return f'0b{i.value:b}'
    return str(i.value)

def emit_block(block: hir.Block, ctx: EmitContext) -> str:
    if not block.scoped and len(block.items) == 1:
        return f'({emit_ast(block.items[0], ctx)})'
    block_ctx = EmitContext(ctx.direct_function_names, set(ctx.local_names)) if block.scoped else ctx
    items: list[str] = []
    for item in block.items:
        items.append(emit_ast(item, block_ctx))
        if isinstance(item, hir.Declare):
            block_ctx.local_names.add(item.name)
    inner = indent('\n'.join(items), TAB)
    if block.scoped:
        return f'{{\n{inner}\n}}'
    return f'(\n{inner}\n)'
# def emit_expr(expr: hir.AST. ctx: Context) -> str:

def emit_return(expr: hir.Return, ctx: EmitContext) -> str:
    #TODO: check is this type returnable?
    if expr.item is None:
        return 'return void'  # udewy requires an explicit value
    return f'return {emit_ast(expr.item, ctx)}'


if __name__ == '__main__':
    from pathlib import Path

    from ...myargparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('path', type=Path, required=True, help='path to file to compile')
    args = parser.parse_args()
    path: Path = args.path
    srcfile = SrcFile.from_path(path)
    udewy = codegen(srcfile)
    print(udewy, end='')