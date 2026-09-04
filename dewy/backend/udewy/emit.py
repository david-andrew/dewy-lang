"""Emit udewy source from HIR prepared by the udewy lowering pass."""

from dataclasses import dataclass, field, replace
from pathlib import Path
from textwrap import indent

from ...reporting import SrcFile
from ...semantic import builtins, check, hir, ty
from ...semantic.hir_display import type_to_dewy
from . import lower
from .lowering_shared import (
    ARGC_NAME,
    ARGV_NAME,
    ARRAY_CAPACITY_OFFSET,
    ARRAY_DATA_OFFSET,
    ARRAY_DESCRIPTOR_SIZE,
    ARRAY_FLAGS_OFFSET,
    ARRAY_LENGTH_OFFSET,
    ARRAY_MUTABLE,
    ARRAY_OWNER_OFFSET,
    ARRAY_STRIDE_OFFSET,
)

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
    '__nand__': 'nand',
    '__nor__': 'nor',
    '__xnor__': 'xnor',
}

UDEWY_PREFIX_DUNDERS = {
    '__unary_sub__': '-',
    '__not__': 'not',
}

LOWERED_RAW_SHIFT_DUNDERS = {
    '__dewy_raw_lshift__': '<<',
    '__dewy_raw_rshift__': '>>',
}

SIGNED_FIXED_INTS = {'int8', 'int16', 'int32', 'int64'}
UNSIGNED_FIXED_INTS = {'uint8', 'uint16', 'uint32', 'uint64'}
NARROW_FIXED_INTS = {'int8', 'int16', 'int32', 'uint8', 'uint16', 'uint32'}
NARROW_WRAPPING_DUNDERS = {
    '__add__',
    '__sub__',
    '__mul__',
    '__floordiv__',
    '__mod__',
    '__and__',
    '__or__',
    '__xor__',
    '__nand__',
    '__nor__',
    '__xnor__',
}
DERIVED_BITWISE_DUNDERS = {
    '__nand__': 'and',
    '__nor__': 'or',
    '__xnor__': 'xor',
}
UNSIGNED_DUNDER_INTRINSICS = {
    '__floordiv__': '__unsigned_idiv__',
    '__mod__': '__unsigned_mod__',
    '__gt__': '__unsigned_gt__',
    '__lt__': '__unsigned_lt__',
    '__ge__': '__unsigned_gte__',
    '__le__': '__unsigned_lte__',
}
FIXED_INTEGER_WIDTHS = {
    'int8': 8,
    'int16': 16,
    'int32': 32,
    'int64': 64,
    'uint8': 8,
    'uint16': 16,
    'uint32': 32,
    'uint64': 64,
}
UDEWY_INTRINSICS = set(builtins.udewy_intrinsic_types)

@dataclass
class EmitContext:
    """Names needed to choose udewy's direct versus indirect call syntax.

    ``direct_function_names`` contains module-level symbols produced by
    callable legalization. ``local_names`` tracks runtime bindings that shadow
    those symbols in the current lexical block.
    """

    direct_function_names: set[str]
    local_names: set[str]
    include_directives: dict[str, str] | None = None   # included file path -> bound name (prelude directives)
    source: SrcFile | None = None
    """The Dewy file the current function was written in: statements are
    preceded by `# @loc path:line:column` markers pointing into it, which
    the udewy compiler turns into debug line information."""
    last_marker: list[str | None] = field(default_factory=lambda: [None])
    """The marker last emitted in this function (shared by its blocks), so a
    run of udewy statements lowered from one Dewy statement is marked once."""
    debug_locations: bool = True
    debug_aliases: dict[str, tuple[str, int]] = field(default_factory=dict)
    debug_raw_arrays: dict[int, tuple[int, int]] = field(default_factory=dict)
    raw_array_thunks: dict[tuple[str, int, int], str] = field(default_factory=dict)   # (formatter, length, element bytes) -> thunk name

    def child(self, local_names: set[str]) -> 'EmitContext':
        return EmitContext(self.direct_function_names, local_names, self.include_directives, self.source, self.last_marker, self.debug_locations, self.debug_aliases, self.debug_raw_arrays, self.raw_array_thunks)


def location_marker(node: hir.AST, ctx: EmitContext) -> str | None:
    """The `# @loc` line for a statement, or None when it repeats the last one or has no source."""
    source = ctx.source
    if source is None or source.path is None or node.loc.stop > len(source.body):
        return None
    if node.loc.start == 0 and node.loc.stop == 0:
        return None   # a synthesized node without a position
    row, column = source.offset_to_row_col(node.loc.start)
    marker = f'# @loc {Path(source.path).resolve()}:{row + 1}:{column + 1}'
    if marker == ctx.last_marker[0]:
        return None
    ctx.last_marker[0] = marker
    return marker


def variable_marker(name: str, binding_id: int | None, ctx: EmitContext) -> str | None:
    """The `# @var name type [shown-as]` line naming a local's type for the
    debugger: its formatter's symbol when the checker made one, else its
    Dewy type; a temporary holding a loop variable is shown under the
    variable's name, and the compiler's other temporaries are hidden (`-`)."""
    if not ctx.debug_locations or ctx.source is None or ctx.source.path is None:
        return None   # (no file to debug)
    shown = name
    if name in ctx.debug_aliases:
        shown, binding_id = ctx.debug_aliases[name]
    if binding_id is None or shown.startswith('__dewy'):
        return f'# @var {name} -'
    spelled = check.debug_variable_types.get(binding_id)
    if spelled is None:
        return None
    formatter = check.debug_formatters.get(binding_id)
    formatter_name = formatter.declaration.name if formatter is not None and formatter.declaration is not None else None
    if formatter_name is not None and formatter_name not in ctx.direct_function_names:
        formatter_name = None   # the target could not lower the formatter
    raw = ctx.debug_raw_arrays.get(binding_id)
    if formatter_name is not None and raw is not None:
        # the slot is the array's data, the formatter takes a descriptor: a thunk builds one
        formatter_name = ctx.raw_array_thunks.setdefault((formatter_name, *raw), f'__dewy_debug_show_raw_{len(ctx.raw_array_thunks)}')
    return f'# @var {name} {shown if shown != name else "-"} {formatter_name or "-"} {spelled}'


def emit_statements(items: list[hir.AST], ctx: EmitContext) -> list[str]:
    """Statements in order, each behind its location marker (and a declaration
    behind its variable marker); declarations shadow direct names from then on."""
    lines: list[str] = []
    for item in items:
        marker = location_marker(item, ctx)
        if marker is not None:
            lines.append(marker)
        if isinstance(item, hir.Declare):
            variable = variable_marker(item.name, item.binding_id, ctx)
            if variable is not None:
                lines.append(variable)
        lines.append(emit_ast(item, ctx))
        if isinstance(item, hir.Declare):
            ctx.local_names.add(item.name)
    return lines

def codegen(srcfile:SrcFile, *, target: str = 'x86_64', test: bool = False, debug_locations: bool = True, debug_values: bool = False) -> str:
    """Type-check Dewy source and emit equivalent udewy source.

    With ``test``, the module's `$test` functions are compiled with the
    generated test runner as the program's entry (`dewy --test`). With
    ``debug_locations`` (the default) every statement is preceded by a
    `# @loc path:line:column` marker naming its Dewy position, and every
    declaration by a `# @var` marker, which the udewy compiler turns into
    debug line and variable information. ``debug_values`` (a `dewy debug`
    build) adds the per-type formatters that let a debugger show Dewy
    values; they cost compile time and size, so an ordinary build has none.
    """
    ast = check.typecheck_and_resolve(srcfile, include_prelude=True, target=target, test=test, debug=debug_locations and debug_values)
    return codegen_inner(ast, srcfile, entry_name=check.TEST_ENTRY_NAME if test else 'main', debug_locations=debug_locations)

def codegen_inner(ast: hir.AST, srcfile: SrcFile | None = None, *, entry_name: str = 'main', debug_locations: bool = True) -> str:
    """Emit checked HIR after legalizing Dewy callable constructs.

    ``lower_for_udewy`` supplies concrete module-level function units, global
    storage, and the ordered items for module startup.
    """
    if not isinstance(ast, hir.Block):
        raise TypeError(f"Expected Block, got {type(ast)}")

    if srcfile is None:
        srcfile = SrcFile(None, ' ' * ast.loc.stop)
    program = lower.lower_for_udewy(ast, srcfile, entry_name=entry_name)
    functions: dict[str, hir.FunctionLiteral] = {}
    for function in program.functions:
        functions[function.symbol] = function.literal

    if program.needs_startup:
        functions[program.startup_symbol] = hir.FunctionLiteral(
            loc=ast.loc,
            type=ty.FunctionType([], [], None, ty.VOID_TYPE),
            pos_or_kw_args=[],
            kw_only_args=[],
            rest_args=None,
            rettype=ty.VOID_TYPE,
            body=hir.Block(
                ast.loc,
                ty.VOID_TYPE,
                program.startup_items,
                True,
            ),
        )
        functions['main'] = _entrypoint_wrapper(
            ast,
            program.startup_symbol,
            program.user_main_symbol,
            functions,
            argv_prologue=program.argv_prologue,
            argv_value=program.argv_value,
        )
    elif 'main' not in functions:
        functions['main'] = hir.FunctionLiteral(
            loc=ast.loc,
            type=ty.FunctionType([], [], None, ty.VOID_TYPE),
            pos_or_kw_args=[],
            kw_only_args=[],
            rest_args=None,
            rettype=ty.VOID_TYPE,
            body=hir.Block(
                ast.loc,
                ty.VOID_TYPE,
                [],
                ast.scoped,
            ),
        )

    code: list[str] = []
    global_names = {declaration.name for declaration in program.globals}
    ctx = EmitContext(
        set(functions) | set(builtins.builtin_types),
        global_names,
        debug_locations=debug_locations,
        debug_aliases=program.debug_aliases,
        debug_raw_arrays=program.debug_raw_arrays,
    )
    ctx.include_directives = {}
    for declaration in program.globals:
        code.append(emit_declare(declaration, ctx))
    for name, func in functions.items():
        code.append(emit_function_decl(name, func, ctx))
    formatters = sorted({
        formatter.declaration.name
        for formatter in check.debug_formatters.values()
        if formatter.declaration is not None and formatter.declaration.name in functions
    })
    for (formatter_name, length, element_bytes), thunk in ctx.raw_array_thunks.items():
        # an exact array kept as raw frame data: the thunk wraps it in a borrowed descriptor
        code.append('\n'.join([
            f'let {thunk} = (data:int64):>int64 => {{',
            f'    let descriptor:int64 = __alloca__({ARRAY_DESCRIPTOR_SIZE})',
            f'    __store_i64__(data descriptor + {ARRAY_DATA_OFFSET})',
            f'    __store_i64__({length} descriptor + {ARRAY_LENGTH_OFFSET})',
            f'    __store_i64__({length} descriptor + {ARRAY_CAPACITY_OFFSET})',
            f'    __store_i64__({element_bytes} descriptor + {ARRAY_STRIDE_OFFSET})',
            f'    __store_i64__({ARRAY_MUTABLE} descriptor + {ARRAY_FLAGS_OFFSET})',
            f'    __store_i64__(0 descriptor + {ARRAY_OWNER_OFFSET})',
            f'    return {formatter_name}(descriptor)',
            '}',
        ]))
        formatters.append(thunk)
    if formatters and debug_locations:
        # the debugger's formatters are called by nothing in the program: a
        # static table keeps them out of the unreachable-function sweep
        code.append(f'const __dewy_debug_formatters:int64 = __static_words__({" ".join(formatters)})')
    # included files are prelude directives: they precede everything else
    directives = [f'$include_bytes(p"{path}") as {name}' for path, name in ctx.include_directives.items()]
    return '\n'.join([*directives, *code]) + '\n'


def _entrypoint_wrapper(
    root: hir.Block,
    startup_symbol: str,
    user_main_symbol: str | None,
    functions: dict[str, hir.FunctionLiteral],
    *,
    argv_prologue: list[hir.AST] | None = None,
    argv_value: hir.AST | None = None,
) -> hir.FunctionLiteral:
    """Call module startup before the optional source-defined entrypoint.

    When the user's ``main`` takes the command line, the wrapper receives the
    C ``argc``/``argv`` words from ``_start`` and runs the lowered prologue
    that turns them into an ``array<string>`` before the call.
    """
    startup_call = hir.FunctionCall(
        root.loc,
        ty.VOID_TYPE,
        hir.ExpressedIdentifier(
            root.loc,
            ty.FunctionType([], [], None, ty.VOID_TYPE),
            startup_symbol,
        ),
        [],
        {},
    )
    items: list[hir.AST] = [startup_call]
    rettype: ty.Type = ty.VOID_TYPE
    if user_main_symbol is None:
        items.append(hir.Return(root.loc, ty.BOTTOM_TYPE, None))
    else:
        user_main = functions[user_main_symbol]
        rettype = user_main.rettype
        call_args: list[hir.AST] = []
        if argv_prologue is not None and argv_value is not None:
            items.extend(argv_prologue)
            call_args = [argv_value]
        call = hir.FunctionCall(
            root.loc,
            rettype,
            hir.ExpressedIdentifier(root.loc, user_main.type, user_main_symbol),
            call_args,
            {},
        )
        if rettype in (ty.VOID_TYPE, ty.BOTTOM_TYPE):
            items.extend([call, hir.Return(root.loc, ty.BOTTOM_TYPE, None)])
        else:
            items.append(hir.Return(root.loc, ty.BOTTOM_TYPE, call))
    params: list[hir.Param | hir.BoundParam] = []
    param_types: list[ty.PosOrKwArg] = []
    if argv_prologue is not None:
        params = [hir.Param(ARGC_NAME, 'int64'), hir.Param(ARGV_NAME, 'int64')]
        param_types = [ty.PosOrKwArg(ARGC_NAME, 'int64'), ty.PosOrKwArg(ARGV_NAME, 'int64')]
    return hir.FunctionLiteral(
        root.loc,
        ty.FunctionType(param_types, [], None, rettype),
        params,
        [],
        None,
        rettype,
        hir.Block(root.loc, ty.BOTTOM_TYPE, items, True),
    )


def emit_type(t: ty.Type) -> str:
    if t == ty.BOTTOM_TYPE:
        return 'void'   # a diverging function's udewy signature; the body never returns
    """Render a semantic type in the annotation syntax accepted by udewy."""
    return type_to_dewy(t)


def emit_arg(arg: hir.Param | hir.BoundParam) -> str:
    if isinstance(arg, hir.BoundParam):
        raise ValueError('INTERNAL ERROR: default parameter reached udewy emission')
    return f'{arg.name}:{emit_type(arg.type)}'

def _contains_return(node: hir.AST) -> bool:
    if isinstance(node, hir.Return):
        return True
    if isinstance(node, hir.Suppress):
        return _contains_return(node.item)
    if isinstance(node, hir.Block):
        return any(_contains_return(item) for item in node.items)
    if isinstance(node, hir.Flow):
        return any(_contains_return(arm.body) for arm in node.arms) or (
            node.default is not None and _contains_return(node.default)
        )
    return False

def emit_function_decl(name: str, func: hir.FunctionLiteral, ctx: EmitContext) -> str:
    code: list[str] = []
    if ctx.debug_locations and func.source is not None:
        for arg in func.pos_or_kw_args:
            marker = variable_marker(arg.name, arg.binding_id, replace(ctx, source=func.source))
            if marker is not None:
                code.append(marker + '\n')
    code.append(f'let {name} = (')

    # build the argument list
    args: list[str] = []
    for arg in func.pos_or_kw_args:
        args.append(emit_arg(arg))
    if func.rest_args is not None or func.kw_only_args:
        raise ValueError(
            'INTERNAL ERROR: non-positional function signature reached udewy emission'
        )

    code.append(' '.join(args))
    code.append(f'):>{emit_type(func.rettype)} => ')

    # udewy function bodies must return explicitly, so expression bodies get wrapped in a return.
    local_names = {arg.name for arg in func.pos_or_kw_args}
    local_names.update(arg.name for arg in func.kw_only_args)
    if func.rest_args is not None:
        local_names.add(func.rest_args.name)
    func_ctx = EmitContext(ctx.direct_function_names, local_names, ctx.include_directives, func.source if ctx.debug_locations else None, debug_locations=ctx.debug_locations, debug_aliases=ctx.debug_aliases, debug_raw_arrays=ctx.debug_raw_arrays, raw_array_thunks=ctx.raw_array_thunks)
    body = func.body
    if _contains_return(body):
        code.append(emit_ast(body, func_ctx))
    elif func.rettype in (ty.VOID_TYPE, ty.BOTTOM_TYPE):
        stmts = emit_statements(body.items, func_ctx) if isinstance(body, hir.Block) else emit_statements([body], func_ctx)
        code.append('{\n' + indent('\n'.join([*stmts, 'return void']), TAB) + '\n}')
    else:
        marker = location_marker(body, func_ctx)
        prefix = f'{marker}\n' if marker is not None else ''
        code.append('{\n' + indent(f'{prefix}return {emit_ast(body, func_ctx)}', TAB) + '\n}')
    return ''.join(code)

def emit_ast(ast: hir.AST, ctx: EmitContext) -> str:
    match ast:
        case hir.Block(): return emit_block(ast, ctx)
        case hir.Return(): return emit_return(ast, ctx)
        case hir.Flow(): return emit_flow(ast, ctx)
        case hir.ScopeMetatag():
            raise ValueError('INTERNAL ERROR: scope metatag reached udewy emission')
        case hir.Break(): return emit_loop_exit(ast, 'break')
        case hir.Continue(): return emit_loop_exit(ast, 'continue')
        case hir.ShortCircuit(): return emit_short_circuit(ast, ctx)
        case hir.Integer(): return emit_integer(ast)
        case hir.String(): return emit_string(ast)
        case hir.BasedString(): return emit_based_string(ast, ctx)
        case hir.Bool(): return 'true' if ast.value else 'false'
        case hir.Void(): return 'void'
        case hir.Declare(): return emit_declare(ast, ctx)
        case hir.Assign(): return emit_assign(ast, ctx)
        case hir.ValueCast(): return emit_ast(ast.expr, ctx)
        case hir.Transmute(): return emit_transmute(ast, ctx)
        case hir.ExpressedIdentifier():
            # a function used as a value: `@name` reads the same under udewy and Dewy
            if isinstance(ast.type, (ty.FunctionType, ty.OverloadType)):
                return f'@{ast.name}'
            return ast.name
        case hir.FunctionCall(): return emit_function_call(ast, ctx)
        case _:
            raise NotImplementedError(f'emit_ast not implemented for AST type: {type(ast).__name__}')


def emit_loop_exit(ast: hir.Break | hir.Continue, keyword: str) -> str:
    """Emit an exit only after labeled metadata has been lowered away."""
    if ast.label is not None or ast.loop_levels != 0:
        raise ValueError('INTERNAL ERROR: labeled loop exit reached udewy emission')
    return keyword


def emit_string(string: hir.String) -> str:
    """Emit decoded Dewy text as an exact UTF-8 byte literal for udewy."""

    content = ''.join(f'\\x{byte:02x}' for byte in string.content.encode('utf-8'))
    return f'"{content}"'


def emit_based_string(string: hir.BasedString, ctx: 'EmitContext | None' = None) -> str:
    """Emit packed binary data in one canonical udewy spelling.

    Bytes that came from a file are embedded by a `$include_bytes(p"…") as
    name` prelude directive (the path is absolute) and referenced by name,
    so the program text stays small.
    """

    if string.include_path is not None and ctx is not None and ctx.include_directives is not None:
        name = ctx.include_directives.get(string.include_path)
        if name is None:
            name = f'__dewy_include_{len(ctx.include_directives) + 1}'
            ctx.include_directives[string.include_path] = name
        return name
    return f'0x"{string.content.hex()}"'


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
    # the target is a place, never a function value: no `@` even for function-typed bindings
    target = assign.target.name if isinstance(assign.target, hir.ExpressedIdentifier) else emit_ast(assign.target, ctx)
    return f'{target} {assign.op} {emit_ast(assign.value, ctx)}'


def emit_flow(flow: hir.Flow, ctx: EmitContext) -> str:
    """Emit an ordered `if` chain or a while-style `loop`."""
    parts: list[str] = []
    for index, arm in enumerate(flow.arms):
        if index:
            parts.append(' else ')
        keyword = 'if' if isinstance(arm, hir.IfArm) else 'loop'
        parts.append(
            f'{keyword} {emit_ast(arm.condition, ctx)} '
            f'{_emit_flow_body(arm.body, ctx)}'
        )
    if flow.default is not None:
        parts.append(f' else {_emit_flow_body(flow.default, ctx)}')
    return ''.join(parts)


def _emit_flow_body(body: hir.AST, ctx: EmitContext) -> str:
    """Ensure a flow arm is represented by a scoped udewy block."""
    if isinstance(body, hir.Block) and body.scoped:
        return emit_block(body, ctx)
    return '{\n' + indent(emit_ast(body, ctx), TAB) + '\n}'


def emit_short_circuit(expr: hir.ShortCircuit, ctx: EmitContext) -> str:
    """Emit a lazy boolean condition, preserving left-to-right evaluation."""
    left = emit_ast(expr.left, ctx)
    right = emit_ast(expr.right, ctx)
    if isinstance(expr.left, hir.ShortCircuit):
        left = f'({left})'
    if isinstance(expr.right, hir.ShortCircuit):
        right = f'({right})'
    return f'{left} {expr.op} {right}'


def emit_transmute(transmute: hir.Transmute, ctx: EmitContext) -> str:
    expr = emit_ast(transmute.expr, ctx)
    if isinstance(transmute.expr, hir.Transmute):
        expr = f'({expr})'
    return f'{expr} transmute {emit_type(transmute.type)}'


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
    operand_type = call.func.type.pos_or_kw[0].type
    # Abstract integers are 64-bit words by the time they reach emission (the
    # bounds analysis proved they fit), so they take the word's signedness.
    return {'int': 'int64', 'uint': 'uint64'}.get(operand_type, operand_type) if isinstance(operand_type, str) else operand_type


def _check_supported_integer_operation(call: hir.FunctionCall) -> None:
    if not isinstance(call.func, hir.ExpressedIdentifier):
        return
    name = call.func.name
    if name not in UDEWY_BINOP_DUNDERS and name not in UDEWY_PREFIX_DUNDERS:
        return
    # Abstract `int`/`uint` operations reach here only after the bounds
    # analysis proved their values fit a 64-bit word, so they emit as int64.
    return


def _wrap_fixed_integer(expression: str, operand_type: ty.TypeExpr | None) -> str:
    """Reduce a word expression to the source integer width and signedness."""

    if not isinstance(operand_type, str) or operand_type not in NARROW_FIXED_INTS:
        return expression
    width = FIXED_INTEGER_WIDTHS[operand_type]
    if operand_type in UNSIGNED_FIXED_INTS:
        return f'({expression}) and {(1 << width) - 1}'
    shift = 64 - width
    return f'__signed_shr__(({expression}) << {shift} {shift})'


def emit_function_call(call: hir.FunctionCall, ctx: EmitContext) -> str:
    _check_supported_integer_operation(call)
    if (
        isinstance(call.func, hir.ExpressedIdentifier)
        and call.func.name in LOWERED_RAW_SHIFT_DUNDERS
        and len(call.pos_args) == 2
        and not call.kw_args
    ):
        symbol = LOWERED_RAW_SHIFT_DUNDERS[call.func.name]
        left, right = call.pos_args
        return f'({emit_operand(left, ctx)} {symbol} {emit_operand(right, ctx)})'
    if (
        isinstance(call.func, hir.ExpressedIdentifier)
        and call.func.name in UNSIGNED_DUNDER_INTRINSICS
        and len(call.pos_args) == 2
        and not call.kw_args
        and _selected_first_parameter(call) in UNSIGNED_FIXED_INTS
    ):
        intrinsic = UNSIGNED_DUNDER_INTRINSICS[call.func.name]
        left, right = call.pos_args
        return f'{intrinsic}({emit_ast(left, ctx)} {emit_ast(right, ctx)})'
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
            assert operand_type is not None
            raise NotImplementedError(
                f'udewy codegen for right shift of `{type_to_dewy(operand_type)}`'
            )
    if (binop := _binop_call(call)) is not None:
        sym, left, right = binop
        left_text = emit_operand(left, ctx)
        right_text = emit_operand(right, ctx)
        if (
            isinstance(call.func, hir.ExpressedIdentifier)
            and call.func.name in DERIVED_BITWISE_DUNDERS
        ):
            base = DERIVED_BITWISE_DUNDERS[call.func.name]
            expression = f'not ({left_text} {base} {right_text})'
        else:
            expression = f'{left_text} {sym} {right_text}'
        if (
            isinstance(call.func, hir.ExpressedIdentifier)
            and call.func.name in NARROW_WRAPPING_DUNDERS
        ):
            return _wrap_fixed_integer(expression, _selected_first_parameter(call))
        return expression
    if (prefix := _prefix_call(call)) is not None:
        sym, item = prefix
        separator = ' ' if sym.isalpha() else ''
        expression = f'{sym}{separator}{emit_operand(item, ctx)}'
        return _wrap_fixed_integer(expression, _selected_first_parameter(call))
    if call.kw_args:
        raise ValueError('INTERNAL ERROR: keyword argument reached udewy emission')
    args = ' '.join(_emit_call_arg(arg, ctx) for arg in call.pos_args)
    if isinstance(call.func, hir.ExpressedIdentifier):
        if (
            call.func.name in ctx.direct_function_names
            or call.func.name in UDEWY_INTRINSICS
        ) and call.func.name not in ctx.local_names:
            return f'{call.func.name}({args})'
        # an indirect call through a name: udewy requires the `@` spelling
        return f'(@{call.func.name})({args})'
    callee = emit_ast(call.func, ctx)
    if isinstance(call.func, hir.Block) and not call.func.scoped:
        return f'{callee}({args})'
    return f'({callee})({args})'


def emit_operand(node: hir.AST, ctx: EmitContext) -> str:
    # TODO: precedence-aware parenthesization; for now always wrap nested infix calls
    if (
        isinstance(node, hir.FunctionCall)
        and _binop_call(node) is not None
        or isinstance(node, hir.Transmute)
    ):
        return f'({emit_ast(node, ctx)})'
    return emit_ast(node, ctx)


def _emit_call_arg(node: hir.AST, ctx: EmitContext) -> str:
    if (
        isinstance(node, hir.Transmute)
        or isinstance(node, hir.Integer) and node.value < 0
        or isinstance(node, hir.FunctionCall) and _prefix_call(node) is not None
    ):
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
        item = block.items[0]
        if isinstance(item, (hir.Assign, hir.MemberAssign, hir.IndexAssign, hir.DictStore, hir.Declare, hir.Return, hir.Break, hir.Continue)):
            # `if cond (stack += 1)`: a parenthesized statement — udewy
            # assignments are statements, so the parens must not survive
            return emit_ast(item, ctx)
        return f'({emit_ast(item, ctx)})'
    block_ctx = ctx.child(set(ctx.local_names)) if block.scoped else ctx
    items = emit_statements(block.items, block_ctx)
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
