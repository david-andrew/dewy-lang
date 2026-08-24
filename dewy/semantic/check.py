"""
semantic analysis pass 0: 
- type checking
- ambiguity resolution
"""
from dataclasses import dataclass, replace, field, fields, is_dataclass
from collections import ChainMap
from typing import Literal, cast
from ..parser import p0, t2, t1, t0
from . import bindings as sb
from . import builtins, hir, ty
from .errors import TypeCheckError, UserError, NotImplementedYet, type_error, user_error, not_implemented, require_valued
from .hir_display import type_to_dewy
from ..reporting import SrcFile, ReportException, Pointer, Span


@dataclass
class Catcher:
    """non-local exits bound for one boundary. 
    E.g. top level return is illegal because there is nothing to catch it. Inside a function body return is valid"""
    returns: list[tuple[Span, ty.Type]] = field(default_factory=list)
    expected: ty.Type | None = None  # the boundary's annotated `:>` type, checked at each return site


@dataclass(eq=False)
class LabelScope:
    """Scope-wide metatag declarations for one lexical block."""

    labels: dict[str, Span]


@dataclass(frozen=True)
class LoopBoundary:
    """An active loop and the lexical scope containing it."""

    parent_label_scope: LabelScope


@dataclass
class Context:
    """global context for the typechecker"""
    srcfile: SrcFile
    declarations: ChainMap[str, ty.Type] = field(default_factory=ChainMap) #TODO: handling different scopes...
    type_system: ty.TypeSystem = field(default_factory=ty.TypeSystem)
    binding_scopes: ChainMap[str, sb.Binding] = field(default_factory=ChainMap)
    binding_registry: sb.BindingRegistry = field(default_factory=sb.BindingRegistry)
    catcher: Catcher | None = None  # installed by the nearest enclosing return boundary
    label_scopes: tuple[LabelScope, ...] = ()
    loop_boundaries: tuple[LoopBoundary, ...] = ()
    function_boundary_labels: dict[str, Span] = field(default_factory=dict)
    refinements: dict[int, ty.Type] = field(default_factory=dict)
    type_alias_asts: dict[int, p0.AST] = field(default_factory=dict)
    resolving_type_aliases: set[int] = field(default_factory=set)
    module_loader: object | None = None
    module_namespaces: ChainMap[str, object] = field(default_factory=ChainMap)
    module_declared_names: set[str] = field(default_factory=set)
    allow_place_expression: bool = False
    # TODO: etc stuff

def typecheck_and_resolve(
    srcfile: SrcFile,
    *,
    include_prelude: bool | None = None,
) -> hir.AST:
    from .modules import typecheck_program

    return typecheck_program(
        srcfile,
        include_prelude=(
            srcfile.path is not None
            if include_prelude is None
            else include_prelude
        ),
    )


def _parse_module(srcfile: SrcFile) -> tuple[p0.Block, bool]:
    block = p0.parse(srcfile)
    no_prelude: bool | None = None
    items: list[p0.AST] = []
    for item in block.inner:
        if not (
            isinstance(item, p0.BinOp)
            and isinstance(item.op, t1.Operator)
            and item.op.symbol == '='
            and isinstance(item.left, p0.Atom)
            and isinstance(item.left.item, t1.Metatag)
            and item.left.item.name == 'no_prelude'
        ):
            items.append(item)
            continue
        if no_prelude is not None:
            user_error(
                srcfile,
                'duplicate `$no_prelude` directive',
                Pointer(span=item.loc, message='this module already sets the directive'),
            )
        if not isinstance(item.right, p0.Atom) or not isinstance(item.right.item, t1.Bool):
            user_error(
                srcfile,
                '`$no_prelude` must be a boolean literal',
                Pointer(span=item.right.loc, message='expected `true` or `false`'),
            )
        no_prelude = item.right.item.value
    return replace(block, inner=items), bool(no_prelude)


def _typecheck_module(
    srcfile: SrcFile,
    *,
    block: p0.Block | None = None,
    type_system: ty.TypeSystem | None = None,
    registry: sb.BindingRegistry | None = None,
    module_loader: object | None = None,
    prelude_bindings: dict[str, sb.Binding] | None = None,
) -> tuple[hir.Block, Context]:
    # set up the base type system/builtins
    if type_system is None:
        type_system = ty.TypeSystem()
        builtins.apply_builtin_promote_rules(type_system)
    prelude_bindings = prelude_bindings or {}
    prelude_declarations = {
        name: binding.type
        for name, binding in prelude_bindings.items()
        if binding.type is not None
    }
    declarations = ChainMap(prelude_declarations, builtins.builtin_types)

    if block is None:
        block, _ = _parse_module(srcfile)
    declared_names = {
        declaration[0]
        for item in block.inner
        if (declaration := _declaration_parts(item)) is not None
    }
    ctx = Context(
        srcfile,
        declarations,
        type_system,
        binding_scopes=ChainMap(prelude_bindings),
        binding_registry=registry or sb.BindingRegistry(),
        module_loader=module_loader,
        module_declared_names=declared_names,
    )
    checked = tcr_block(block, ctx=ctx)
    if not isinstance(checked, hir.Block):
        raise TypeError('INTERNAL ERROR: source module did not produce a block')
    return checked, ctx

def typecheck_and_resolve_inner(ast: p0.AST, *, ctx: Context, type_block:bool=False, expected: ty.Type|None=None, call_target: bool=False) -> hir.AST:
    match ast:
        case p0.Ambiguous(candidates=candidates):
            # speculatively check each candidate reading against a forked declarations layer
            # (and forked catcher) so that effects of rejected candidates are discarded
            passes: list[tuple[hir.AST, Context]] = []
            rejections: list[ReportException] = []
            for candidate in candidates:
                fork = replace(ctx,
                    declarations=ctx.declarations.new_child(),
                    binding_scopes=ctx.binding_scopes.new_child(),
                    module_namespaces=ctx.module_namespaces.new_child(),
                    refinements=dict(ctx.refinements),
                    catcher=Catcher(list(ctx.catcher.returns), ctx.catcher.expected) if ctx.catcher is not None else None)
                try:
                    passes.append((typecheck_and_resolve_inner(candidate, ctx=fork, type_block=type_block, expected=expected), fork))
                except (TypeCheckError, UserError, NotImplementedYet) as e:
                    # NotImplementedYet prunes too so an unimplemented reading doesn't block a
                    # valid one, but it is reported preferentially when nothing survives since
                    # the failure may be a compiler gap rather than a user error
                    rejections.append(e)
            if len(passes) == 0:
                user_rejections = [r for r in rejections if isinstance(r, UserError)]
                if user_rejections:
                    raise user_rejections[0]
                unimplemented = [r for r in rejections if isinstance(r, NotImplementedYet)]
                if unimplemented:
                    raise unimplemented[0]
                reasons = '\n'.join(f'- {r.report.title or r.report.message}' for r in rejections)
                user_error(ctx.srcfile, 'no valid interpretation for ambiguous expression',
                    Pointer(span=ast.loc, message=f'all {len(candidates)} possible readings of this expression failed to typecheck'),
                    hint=f'each reading was rejected because:\n{reasons}')
            if len(passes) > 1:
                user_error(ctx.srcfile, 'ambiguous expression',
                    Pointer(span=ast.loc, message=f'{len(passes)} readings of this expression typecheck; unable to choose between them'),
                    hint='add explicit operators or parenthesis to disambiguate')
            result, fork = passes[0]
            # merge the winning candidate's effects back into the enclosing context
            ctx.declarations.maps[0].update(fork.declarations.maps[0])
            ctx.binding_scopes.maps[0].update(fork.binding_scopes.maps[0])
            ctx.module_namespaces.maps[0].update(fork.module_namespaces.maps[0])
            ctx.refinements.clear()
            ctx.refinements.update(fork.refinements)
            if ctx.catcher is not None:
                assert fork.catcher is not None
                ctx.catcher.returns[:] = fork.catcher.returns
            return result

        case p0.Flow():
            return tcr_flow(ast, ctx=ctx, expected=expected)

        
        case p0.KeywordExpr(parts=[t1.Keyword(name='let'|'const'), *_]):
            return tcr_declare(ast, ctx=ctx)

        case p0.KeywordExpr(parts=[t1.Keyword(name='import'|'from'), *_]):
            return tcr_import(ast, ctx=ctx)
        
        case p0.KeywordExpr(parts=[t1.Keyword(name='return'), *_]):
            return tcr_return(ast, ctx=ctx, expected=expected)

        case p0.KeywordExpr(parts=[t1.Keyword(name='break'|'continue'), *_]):
            return tcr_loop_exit(ast, ctx=ctx)

        # etc. keyword cases as outlined in t2
        case p0.KeywordExpr(parts=[t1.Keyword(name=name), *_]):
            not_implemented(ctx.srcfile, ast.loc, f'`{name}` expression')
        case p0.KeywordExpr():
            raise ValueError(f'INTERNAL ERROR: unrecognized keyword expression structure: {ast=}')

        case p0.BinOp(op=t1.Operator(symbol=':='|'='|'::')):
            return tcr_assign(ast, ctx=ctx)

        case p0.IString(): return tcr_istring(ast, ctx=ctx)
        case p0.Block(): return tcr_block(ast, ctx=ctx, expected=expected)
        case p0.Prefix(): return tcr_prefix(ast, ctx=ctx, expected=expected)
        case p0.BinOp(): return tcr_binop(ast, ctx=ctx, type_block=type_block, expected=expected, call_target=call_target)
        case p0.Atom(item=t1.Identifier(name='..')): return hir.Range(ast.item.loc, 'range', bounds=None, step_pair=None, left=None, right=None)
        case p0.Atom(item=t1.Identifier(name='void')): return hir.Void(ast.item.loc, ty.VOID_TYPE)
        case p0.Atom(item=t1.Identifier(name='undefined')):
            return hir.Undefined(ast.item.loc, 'undefined')
        case p0.Atom(item=t1.Identifier()): return tcr_identifier(ast.item, ctx=ctx)
        case p0.Atom(item=t1.String(content=content)):
            from .unicode.graphemes import unicode_scalars

            try:
                unicode_scalars(content)
            except ValueError:
                user_error(
                    ctx.srcfile,
                    'string literal contains a Unicode surrogate',
                    Pointer(
                        span=ast.item.loc,
                        message='Dewy strings contain Unicode scalar values only',
                    ),
                )
            return hir.String(ast.item.loc, ty.StringLiteralType(content), content)
        case p0.Atom(item=t1.BasedString() as literal):
            content, digits = _pack_based_string(literal, ctx=ctx)
            return hir.BasedString(
                literal.loc,
                ty.BinaryLiteralType(content),
                literal.base,
                digits,
                content,
            )
        case p0.Atom(item=t1.Integer(value=value)):
            parsed = t0.parse_integer(value.src, value.prefix)
            return hir.Integer(ast.item.loc, ty.IntegerLiteralType(parsed), value.prefix, parsed)
        case p0.Atom(item=t1.Metatag(name=name)):
            return tcr_scope_metatag(ast, name=name, ctx=ctx)
        # case p0.Atom(item=t1.Real()): ...
        case p0.Atom(item=t1.Semicolon()):
            not_implemented(
                ctx.srcfile,
                ast.loc,
                'standalone semicolon array-dimension syntax',
            )
        # case p0.Atom(item=t1.Metatag()): ...
        # case p0.Atom(item=t1.Integer()): ...
        case p0.Atom(item=t1.Bool(value=value)): return hir.Bool(ast.item.loc, 'bool', value)
        # case p0.Atom(item=t2.OpFn()): ...
        # case p0.Atom(item=t2.Placeholder()): ...
        case p0.Flat(op=t2.RangeJuxtapose()):
            return tcr_bare_range(ast, ctx=ctx, expected=expected)
        case _:
            not_implemented(ctx.srcfile, ast.loc, f'{type(ast).__name__} expression')


_BASED_STRING_DIGIT_WIDTHS: dict[t0.BasePrefix, int] = {
    '0b': 1,
    '0q': 2,
    '0o': 3,
    '0x': 4,
    '0u': 5,
    '0g': 6,
}


def tcr_istring(ast: p0.IString, *, ctx: Context) -> hir.InterpolatedString:
    """Typecheck interpolation fields while retaining literal chunks."""

    from .unicode.graphemes import unicode_scalars

    parts: list[hir.AST] = []
    for part in ast.content:
        if isinstance(part, str):
            try:
                unicode_scalars(part)
            except ValueError:
                user_error(
                    ctx.srcfile,
                    'string literal contains a Unicode surrogate',
                    Pointer(
                        span=ast.loc,
                        message='Dewy strings contain Unicode scalar values only',
                    ),
                )
            if part:
                parts.append(
                    hir.String(ast.loc, ty.StringLiteralType(part), part)
                )
            continue
        if isinstance(part, p0.ParametricEscape):
            not_implemented(
                ctx.srcfile,
                part.loc,
                'parametric escape inside an interpolated string',
            )
        if not isinstance(part, p0.Block):
            raise TypeError(
                f'INTERNAL ERROR: unexpected interpolated string part {type(part).__name__}'
            )
        if len(part.inner) != 1:
            user_error(
                ctx.srcfile,
                'string interpolation requires one expression',
                Pointer(
                    span=part.loc,
                    message='place exactly one expression between these braces',
                ),
            )
        value = typecheck_and_resolve_inner(part.inner[0], ctx=ctx)
        require_valued(
            value.type,
            ctx.srcfile,
            value.loc,
            'string interpolation field',
        )
        parts.append(value)
    return hir.InterpolatedString(ast.loc, ty.StringType(), parts)


def _pack_based_string(
    literal: t1.BasedString,
    *,
    ctx: Context,
) -> tuple[bytes, str]:
    digit_width = _BASED_STRING_DIGIT_WIDTHS.get(literal.base)
    if digit_width is None:
        user_error(
            ctx.srcfile,
            'based-string packing is reserved',
            Pointer(
                span=literal.loc,
                message=(
                    f'base-{t0.base_radixes[literal.base]} based strings are '
                    'reserved for future dense packing'
                ),
            ),
        )

    digits = ''.join(chunk.src for chunk in literal.digits)
    if literal.base == '0g':
        first_padding = digits.find('=')
        if (
            first_padding != -1
            and any(digit != '=' for digit in digits[first_padding:])
        ):
            user_error(
                ctx.srcfile,
                'invalid base-64 padding',
                Pointer(
                    span=literal.loc,
                    message='`=` may only appear at the end of a base-64 based string',
                ),
            )

    values = t0.base_digit_values[literal.base]
    packed = bytearray()
    pending = 0
    pending_bits = 0
    for digit in digits:
        value = values.get(digit)
        if value is None:
            if digit == '_' and literal.base != '0g':
                continue
            if digit == '=' and literal.base == '0g':
                continue
            raise ValueError(f'INTERNAL ERROR: invalid based-string digit {digit!r}')
        pending = pending << digit_width | value
        pending_bits += digit_width
        while pending_bits >= 8:
            pending_bits -= 8
            packed.append((pending >> pending_bits) & 0xff)
            pending &= (1 << pending_bits) - 1
    if pending_bits:
        packed.append(pending << (8 - pending_bits))
    return bytes(packed), digits


def _complete_binding(
    ast: p0.AST,
    declaration: hir.Declare,
    *,
    ctx: Context,
) -> hir.Declare:
    binding = ctx.binding_registry.by_syntax.get(id(ast))
    if binding is None:
        kind: sb.BindingKind = (
            'function'
            if isinstance(declaration.expr, hir.FunctionLiteral)
            else 'overload'
            if isinstance(declaration.expr.type, ty.OverloadType)
            else 'value'
        )
        binding = ctx.binding_registry.allocate(
            ast,
            declaration.name,
            kind,
            declaration.loc,
        )
    binding.kind = (
        'function'
        if isinstance(declaration.expr, hir.FunctionLiteral)
        else 'overload'
        if isinstance(declaration.expr.type, ty.OverloadType)
        else 'value'
    )
    binding.type = declaration.expr.type
    if isinstance(declaration.expr, hir.TypeValue):
        binding.type_value = declaration.expr.value
    declaration = replace(declaration, binding_id=binding.id)
    binding.declaration = declaration
    if isinstance(declaration.expr, hir.FunctionLiteral):
        binding.function = declaration.expr
    ctx.binding_scopes[declaration.name] = binding
    return declaration


def _widen_inferred_let_value(expr: hir.AST) -> hir.AST:
    if isinstance(expr, hir.Integer) and isinstance(expr.type, ty.IntegerLiteralType):
        return replace(expr, type='int')
    return expr


def tcr_declare(ast: p0.KeywordExpr, *, ctx: Context, expected: ty.Type|None=None) -> hir.AST:
    """
    let|const <id>
    let|const <id> = <expr>
    let|const <id>:<typeexpr>
    let|const <id>:<typeexpr> = <expr>

    TODO := and ::

    basically 4 parameters:
    - let vs const
    - typed vs untyped
    - = vs := vs ::   (though := is a bit of a special case since it doesn't need let or const)
    - expr vs undefined

    """
    # typeexpr = None
    # right = None
    # compiletime = False
    # keyword = ast.parts[0].name
    # assert keyword in ['let', 'const'], f'INTERNAL ERROR: invalid keyword: {keyword}'




    match ast.parts:
        case [
            t1.Keyword(name='let'|'const' as keyword), 
            p0.BinOp(
                left=p0.Atom(item=t1.Identifier(name=name)), 
                op=t1.Operator(symbol='='|'::'|':='),
                right=p0.AST() as right)
            ]:
            expr = typecheck_and_resolve_inner(right, ctx=ctx)
            require_valued(expr.type, ctx.srcfile, expr.loc, 'declaration initializer')
            if keyword == 'let':
                expr = _widen_inferred_let_value(expr)

            # if this declaration was pre-bound by the two-phase pass, verify the checked
            # type matches the pre-bound signature rather than silently overwriting it
            prebound = ctx.declarations.maps[0].get(name)
            if isinstance(prebound, ty.FunctionType) and isinstance(expr.type, ty.FunctionType):
                assert ctx.type_system.function_subtype(expr.type, prebound) and ctx.type_system.function_subtype(prebound, expr.type), \
                    f'INTERNAL ERROR: checked function type {expr.type} does not match the pre-bound signature {prebound} for `{name}`'

            # use the type directly from the expression since no type annotation was provided
            ctx.declarations[name] = expr.type

            return _complete_binding(
                ast,
                hir.Declare(ast.loc, ty.VOID_TYPE, keyword, name, None, expr),
                ctx=ctx,
            )
        
        case [
            t1.Keyword(name='let'|'const' as keyword),
            p0.BinOp(
                left=p0.BinOp(
                    left=p0.Atom(item=t1.Identifier(name=name)),
                    op=t1.Operator(symbol=':'),
                    right=p0.AST() as typeexpr),
                op=t1.Operator(symbol='='|'::'|':='),
                right=p0.AST() as right)
            ]:
            # decl assign + type annotation: check the expression against the annotation
            annotation = ast_to_type(typeexpr, ctx=ctx)
            if annotation == ty.TYPE_TYPE:
                binding = ctx.binding_registry.by_syntax.get(id(ast))
                type_value = (
                    binding.type_value
                    if binding is not None and binding.type_value is not None
                    else _type_alias_value(right, ctx=ctx)
                )
                expr = hir.TypeValue(right.loc, ty.TYPE_TYPE, type_value)
                ctx.declarations[name] = ty.TYPE_TYPE
                declaration = _complete_binding(
                    ast,
                    hir.Declare(ast.loc, ty.VOID_TYPE, keyword, name, annotation, expr),
                    ctx=ctx,
                )
                binding = ctx.binding_registry.by_id[declaration.binding_id]
                binding.type = ty.TYPE_TYPE
                binding.type_value = type_value
                return declaration
            optional_payload = ty.optional_payload(annotation)
            expression_expected = (
                optional_payload
                if optional_payload is not None
                and isinstance(right, p0.Block)
                and right.kind == '[]'
                else annotation
            )
            expr = typecheck_and_resolve_inner(
                right,
                ctx=ctx,
                expected=expression_expected,
            )
            expr = check_against(expr, annotation, ctx=ctx)
            optional_annotation_payload = ty.optional_payload(annotation)
            ctx.declarations[name] = (
                expr.type
                if isinstance(annotation, (ty.ArrayType, ty.ObjectType))
                and isinstance(expr.type, type(annotation))
                else ty.optional(expr.type)
                if isinstance(optional_annotation_payload, (ty.ArrayType, ty.ObjectType))
                and isinstance(expr.type, type(optional_annotation_payload))
                else annotation
            )
            return _complete_binding(
                ast,
                hir.Declare(ast.loc, ty.VOID_TYPE, keyword, name, annotation, expr),
                ctx=ctx,
            )
        
        case [
            t1.Keyword(name='let'|'const'),
            p0.Atom(item=t1.Identifier(name=name))
        ]:
            # decl only
            not_implemented(ctx.srcfile, ast.loc, 'declaration without assignment')
        case [
            t1.Keyword(name='let'|'const'),
            p0.BinOp(
                left=p0.Atom(item=t1.Identifier(name=name)),
                op=t1.Operator(symbol=':'),
                right=p0.AST() as typeexpr
            ),
        ]:
            # decl only + type annotation
            not_implemented(ctx.srcfile, ast.loc, 'declaration with type annotation and no assignment')
        case _:
            not_implemented(ctx.srcfile, ast.loc, 'this declaration form')

def tcr_assign(ast: p0.BinOp, *, ctx: Context, expected: ty.Type|None=None) -> hir.AST:
    """
    non-declare assignments, e.g. `name=value`
    compiletime assignments, e.g. `name::value`
    implicit declarations, e.g. `name:=value`
    """
    assert isinstance(ast.op, t1.Operator)
    if ast.op.symbol != '=':
        not_implemented(ctx.srcfile, ast.op.loc, f'assignment operator `{ast.op.symbol}`')

    if (
        isinstance(ast.left, p0.Atom)
        and isinstance(ast.left.item, t1.Identifier)
        and ast.left.item.name not in ctx.declarations
    ):
        name = ast.left.item.name
        value = typecheck_and_resolve_inner(ast.right, ctx=ctx)
        require_valued(value.type, ctx.srcfile, value.loc, 'declaration initializer')
        value = _widen_inferred_let_value(value)
        ctx.declarations[name] = value.type
        return _complete_binding(
            ast,
            hir.Declare(
                ast.loc,
                ty.VOID_TYPE,
                'let',
                name,
                None,
                value,
            ),
            ctx=ctx,
        )

    target = tcr_assignment_target(ast.left, ctx=ctx)
    value = typecheck_and_resolve_inner(ast.right, ctx=ctx, expected=target.type)
    value = check_against(value, target.type, ctx=ctx)
    if isinstance(target, hir.Index):
        return hir.IndexAssign(ast.loc, ty.VOID_TYPE, target, value)
    if isinstance(target, hir.MemberAccess):
        if isinstance(target.type, (ty.FunctionType, ty.OverloadType)):
            if not isinstance(value, hir.FunctionLiteral):
                not_implemented(
                    ctx.srcfile,
                    value.loc,
                    'assigning a non-literal function to an object field',
                )
            assert isinstance(target.value.type, ty.ObjectType)
            value = replace(
                value,
                object_receiver=True,
                object_type=target.value.type,
            )
        return hir.MemberAssign(ast.loc, ty.VOID_TYPE, target, value)
    if target.binding_id is not None:
        ctx.refinements.pop(target.binding_id, None)
    return hir.Assign(ast.loc, ty.VOID_TYPE, target, '=', value)


def tcr_combined_assign(ast: p0.BinOp, *, ctx: Context) -> hir.Assign:
    """Typecheck a simple compound assignment while retaining its source operator."""
    assert isinstance(ast.op, t2.CombinedAssignmentOp)
    if not isinstance(ast.op.op, t1.Operator):
        not_implemented(ctx.srcfile, ast.op.loc, 'broadcast compound assignment')
    symbol = ast.op.op.symbol
    if symbol not in builtins.BINOP_DUNDER_MAP:
        not_implemented(ctx.srcfile, ast.op.loc, f'compound assignment operator `{symbol}=`')

    if (
        isinstance(ast.left, p0.BinOp)
        and isinstance(ast.left.op, t1.Operator)
        and ast.left.op.symbol == '=>'
    ):
        # TODO: Link to the operator-precedence table once it has a stable URL.
        user_error(
            ctx.srcfile,
            'function literal is not a valid compound assignment target',
            Pointer(
                span=ast.left.loc,
                message=(
                    f'`=>` binds more tightly than `{symbol}=`, so this '
                    'function literal became the assignment target'
                ),
            ),
            Pointer(
                span=ast.op.loc,
                message='this operator applies to the entire function literal on its left',
            ),
            hint=(
                'you might need to wrap the in-place assignment in '
                f'parentheses, for example `() => (value {symbol}= 1)`'
            ),
        )

    target = tcr_assignment_target(ast.left, ctx=ctx, refined=True)
    if isinstance(target, hir.Index):
        not_implemented(
            ctx.srcfile,
            ast.left.loc,
            'compound indexed assignment',
        )
    if isinstance(target, hir.MemberAccess):
        not_implemented(
            ctx.srcfile,
            ast.left.loc,
            'compound member assignment',
        )
    value = typecheck_and_resolve_inner(ast.right, ctx=ctx, expected=target.type)
    result = _dispatch_builtin(
        builtins.BINOP_DUNDER_MAP[symbol],
        [target, value],
        loc=ast.loc,
        op_loc=ast.op.loc,
        source_name=symbol,
        ctx=ctx,
        expected=target.type,
    )
    check_against(result, target.type, ctx=ctx)
    return hir.Assign(ast.loc, ty.VOID_TYPE, target, f'{symbol}=', value)


def tcr_import(ast: p0.KeywordExpr, *, ctx: Context, expected: ty.Type|None=None) -> hir.AST:
    if ctx.module_loader is None:
        user_error(
            ctx.srcfile,
            'imports require a file-backed compilation',
            Pointer(span=ast.loc, message='no module loader is available here'),
        )

    path_ast: p0.AST
    names_ast: p0.AST | None = None
    namespace_name: str | None = None
    splat = False
    match ast.parts:
        case [
            t1.Keyword(name='from'),
            p0.AST() as source,
            t1.Keyword(name='import'),
            p0.AST() as names,
        ]:
            path_ast, names_ast = source, names
        case [
            t1.Keyword(name='import'),
            p0.AST() as names,
            t1.Keyword(name='from'),
            p0.AST() as source,
        ]:
            path_ast, names_ast = source, names
        case [
            t1.Keyword(name='import'),
            p0.BinOp(
                op=t1.Operator(symbol='as'),
                left=p0.AST() as source,
                right=p0.Atom(item=t1.Identifier(name=alias)),
            ),
        ]:
            path_ast, namespace_name = source, alias
        case [t1.Keyword(name='import'), p0.AST() as source]:
            path_ast, splat = source, True
        case _:
            user_error(
                ctx.srcfile,
                'invalid import syntax',
                Pointer(span=ast.loc, message='cannot interpret this import'),
            )

    path_text = _literal_import_path(path_ast, ctx=ctx)
    loader = ctx.module_loader
    record = loader.import_module(path_text, ctx=ctx, loc=path_ast.loc)  # type: ignore[attr-defined]

    if namespace_name is not None:
        _check_import_name_available(namespace_name, ast.loc, ctx=ctx)
        ctx.module_namespaces[namespace_name] = record
        return hir.Void(ast.loc, ty.VOID_TYPE)

    imports = (
        [(name, name, ast.loc) for name in record.exports]
        if splat
        else _parse_import_names(names_ast, ctx=ctx)
    )
    for source_name, local_name, loc in imports:
        binding = record.exports.get(source_name)
        if binding is None:
            user_error(
                ctx.srcfile,
                f'module has no top-level binding `{source_name}`',
                Pointer(span=loc, message='this name is not exported by the module'),
                hint=(
                    'available names: '
                    + (', '.join(record.exports) if record.exports else '(none)')
                ),
            )
        existing = ctx.binding_scopes.maps[0].get(local_name)
        if existing is binding:
            continue
        _check_import_name_available(local_name, loc, ctx=ctx)
        if binding.type is None:
            raise ValueError(
                f'INTERNAL ERROR: imported binding `{source_name}` has no type'
            )
        ctx.declarations[local_name] = binding.type
        ctx.binding_scopes[local_name] = binding
    return hir.Void(ast.loc, ty.VOID_TYPE)


def _literal_import_path(ast: p0.AST, *, ctx: Context) -> str:
    value = typecheck_and_resolve_inner(ast, ctx=ctx)
    value = _unwrap_literal_value(value)
    if isinstance(value.type, ty.PathLiteralType):
        return value.type.value
    if isinstance(value.type, ty.ObjectType):
        path_field = value.type.field('path')
        if (
            path_field is not None
            and isinstance(path_field.type, ty.StringLiteralType)
        ):
            return path_field.type.value
    user_error(
        ctx.srcfile,
        'import source requires an exact `path` field',
        Pointer(
            span=ast.loc,
            message=(
                'use a literal path constructor or an object such as '
                '`[path="relative/file.dewy"]`'
            ),
        ),
    )


def _parse_import_names(
    ast: p0.AST | None,
    *,
    ctx: Context,
) -> list[tuple[str, str, Span]]:
    if ast is None:
        raise ValueError('INTERNAL ERROR: selective import has no names')
    if isinstance(ast, p0.Block) and ast.kind == '()':
        items = list(ast.inner)
    elif (
        isinstance(ast, p0.Flat)
        and isinstance(ast.op, t1.Operator)
        and ast.op.symbol == ','
    ):
        items = list(ast.items)
    else:
        items = [ast]
    if (
        len(items) == 1
        and isinstance(items[0], p0.Flat)
        and isinstance(items[0].op, t1.Operator)
        and items[0].op.symbol == ','
    ):
        items = list(items[0].items)

    parsed: list[tuple[str, str, Span]] = []
    for item in items:
        if isinstance(item, p0.Atom) and isinstance(item.item, t1.Identifier):
            parsed.append((item.item.name, item.item.name, item.loc))
            continue
        if (
            isinstance(item, p0.BinOp)
            and isinstance(item.op, t1.Operator)
            and item.op.symbol == 'as'
            and isinstance(item.left, p0.Atom)
            and isinstance(item.left.item, t1.Identifier)
            and isinstance(item.right, p0.Atom)
            and isinstance(item.right.item, t1.Identifier)
        ):
            parsed.append((item.left.item.name, item.right.item.name, item.loc))
            continue
        user_error(
            ctx.srcfile,
            'invalid imported name',
            Pointer(
                span=item.loc,
                message='expected `name` or `name as alias`',
            ),
        )
    return parsed


def _check_import_name_available(name: str, loc: Span, *, ctx: Context) -> None:
    if (
        name in ctx.module_declared_names
        or name in ctx.binding_scopes.maps[0]
        or name in ctx.module_namespaces.maps[0]
    ):
        user_error(
            ctx.srcfile,
            f'imported name `{name}` conflicts with this module',
            Pointer(span=loc, message='choose a distinct `as` alias'),
        )

def tcr_return(ast: p0.KeywordExpr, *, ctx: Context, expected: ty.Type|None=None) -> hir.AST:
    if len(ast.parts) > 2: raise ValueError(f'INTERNAL ERROR: return statement may only contain zero or one expression, got {len(ast.parts)}. {ast.parts=}. (should have been caught during p0 phase)')
    kw_loc = ast.parts[0].loc
    if ctx.catcher is None:
        user_error(ctx.srcfile, '`return` outside a function',
            Pointer(span=kw_loc, message='nothing here catches this return'),
            hint='`return` is only valid inside a function body')
    # a return's own type is `never` (control never proceeds past it); the *exit* type
    # carried to the catcher is the value's type, or `void` for a bare return
    if len(ast.parts) == 1:
        ctx.catcher.returns.append((kw_loc, ty.VOID_TYPE))
        return hir.Return(kw_loc, ty.BOTTOM_TYPE)
    # the returned value's expected type is the boundary's annotation, not whatever
    # expected type the return expression itself sat in (a return never produces a value there)
    item = typecheck_and_resolve_inner(ast.parts[1], ctx=ctx, expected=ctx.catcher.expected)
    if ctx.catcher.expected is not None and ctx.catcher.expected != ty.VOID_TYPE:
        item = check_against(item, ctx.catcher.expected, ctx=ctx)
    ctx.catcher.returns.append((kw_loc, item.type))
    return hir.Return(kw_loc, ty.BOTTOM_TYPE, item)


def _loop_exit_metatag(ast: p0.KeywordExpr, *, ctx: Context) -> t1.Metatag | None:
    """Decode the parser's optional one-metatag keyword payload."""
    parts = cast(list[object], ast.parts)
    if len(parts) == 1:
        return None
    if (
        len(parts) == 2
        and isinstance(parts[1], list)
        and len(parts[1]) == 1
        and isinstance(parts[1][0], t1.Metatag)
    ):
        return parts[1][0]
    user_error(
        ctx.srcfile,
        'invalid labeled loop exit',
        Pointer(span=ast.loc, message='expected exactly one `$name` label'),
        hint='use `break $name` or `continue $name`',
    )


def _visible_label_scope(name: str, *, ctx: Context) -> LabelScope | None:
    return next(
        (scope for scope in reversed(ctx.label_scopes) if name in scope.labels),
        None,
    )


def tcr_loop_exit(ast: p0.KeywordExpr, *, ctx: Context) -> hir.Break | hir.Continue:
    """Resolve an unlabeled or scope-metatag-targeted loop exit."""
    keyword = ast.parts[0]
    assert isinstance(keyword, t1.Keyword)
    metatag = _loop_exit_metatag(ast, ctx=ctx)

    loop_levels = 0
    label = None
    label_scope = None
    if metatag is not None:
        label = metatag.name
        label_scope = _visible_label_scope(label, ctx=ctx)
        if label_scope is None:
            inaccessible = ctx.function_boundary_labels.get(label)
            if inaccessible is not None:
                user_error(
                    ctx.srcfile,
                    f'loop label `${label}` cannot cross a function boundary',
                    Pointer(span=metatag.loc, message='this exit is in a nested function'),
                    Pointer(span=inaccessible, message='the label is declared outside that function'),
                )
            user_error(
                ctx.srcfile,
                f'unknown loop label `${label}`',
                Pointer(span=metatag.loc, message='no visible scope declares this metatag'),
            )

    if not ctx.loop_boundaries:
        user_error(
            ctx.srcfile,
            f'`{keyword.name}` outside a loop',
            Pointer(span=keyword.loc, message='there is no enclosing loop to exit'),
        )

    if metatag is not None:
        assert label_scope is not None
        target_index = next(
            (
                index
                for index in range(len(ctx.loop_boundaries) - 1, -1, -1)
                if ctx.loop_boundaries[index].parent_label_scope is label_scope
            ),
            None,
        )
        if target_index is None:
            user_error(
                ctx.srcfile,
                f'`${label}` does not label an enclosing loop',
                Pointer(span=metatag.loc, message='this metatag is visible, but its scope contains no active target loop'),
                Pointer(span=label_scope.labels[label], message='the metatag is declared in this scope'),
                hint='a labeled exit targets a loop whose parent lexical scope declares the metatag',
            )
        loop_levels = len(ctx.loop_boundaries) - 1 - target_index

    if keyword.name == 'break':
        return hir.Break(ast.loc, ty.BOTTOM_TYPE, label, loop_levels)
    assert keyword.name == 'continue'
    return hir.Continue(ast.loc, ty.BOTTOM_TYPE, label, loop_levels)


def _flow_expected(expected: ty.Type | None) -> ty.Type | None:
    """Expected scalar branch type, excluding statement/inference sentinels."""
    if expected in (None, ty.VOID_TYPE, ty.INFERRED_TYPE):
        return None
    return expected


def _check_flow_condition(condition_ast: p0.AST, *, ctx: Context) -> hir.AST:
    """Typecheck one Dewy flow condition as a strict boolean."""
    condition = typecheck_and_resolve_inner(condition_ast, ctx=ctx, expected='bool')
    return check_against(condition, 'bool', ctx=ctx)


def _flow_value_type(
    bodies: list[hir.AST],
    *,
    exhaustive: bool,
    ctx: Context,
    loc: Span,
) -> ty.Type:
    """Synthesize a scalar conditional result from its continuing branches."""
    continuing = [body.type for body in bodies if body.type != ty.BOTTOM_TYPE]
    if not exhaustive:
        return ty.VOID_TYPE
    if not continuing:
        return ty.BOTTOM_TYPE
    if any(isinstance(result, ty.SequenceType) for result in continuing):
        not_implemented(ctx.srcfile, loc, 'multi-value conditional result')
    has_void = any(result == ty.VOID_TYPE for result in continuing)
    has_value = any(result != ty.VOID_TYPE for result in continuing)
    if has_void and has_value:
        user_error(
            ctx.srcfile,
            'conditional branches disagree on whether they produce a value',
            Pointer(span=loc, message='some continuing branches produce values and others do not'),
        )
    if has_void:
        return ty.VOID_TYPE
    values = [
        require_valued(result, ctx.srcfile, body.loc, 'conditional branch')
        for body, result in zip(
            [body for body in bodies if body.type != ty.BOTTOM_TYPE],
            continuing,
        )
    ]
    return ty.union(*values)


def _refine_type_test(
    current: ty.Type,
    test: ty.TypeExpr,
    *,
    matches: bool,
    ctx: Context,
) -> ty.Type:
    payload = ty.optional_payload(current)
    variants: list[ty.TypeExpr] = (
        [payload, 'undefined']
        if payload is not None
        else [cast(ty.TypeExpr, current)]
    )
    selected = [
        variant
        for variant in variants
        if ctx.type_system.is_subtype(variant, test) == matches
    ]
    return ty.union(*selected)


def _refine_condition_context(
    ctx: Context,
    condition: hir.AST,
    *,
    truth: bool,
) -> Context:
    refinements = dict(ctx.refinements)
    if isinstance(condition, hir.TypeTest):
        value = condition.value
        if isinstance(value, hir.ExpressedIdentifier) and value.binding_id is not None:
            current = refinements.get(value.binding_id, value.type)
            refinements[value.binding_id] = _refine_type_test(
                current,
                condition.test_type,
                matches=truth != condition.negated,
                ctx=ctx,
            )
        return replace(ctx, refinements=refinements)
    if isinstance(condition, hir.ShortCircuit):
        if condition.op == 'and' and truth:
            left_ctx = _refine_condition_context(ctx, condition.left, truth=True)
            return _refine_condition_context(left_ctx, condition.right, truth=True)
        if condition.op == 'or' and not truth:
            left_ctx = _refine_condition_context(ctx, condition.left, truth=False)
            return _refine_condition_context(left_ctx, condition.right, truth=False)
        if condition.op == 'nand' and not truth:
            left_ctx = _refine_condition_context(ctx, condition.left, truth=True)
            return _refine_condition_context(left_ctx, condition.right, truth=True)
        if condition.op == 'nor' and truth:
            left_ctx = _refine_condition_context(ctx, condition.left, truth=False)
            return _refine_condition_context(left_ctx, condition.right, truth=False)
    return ctx


@dataclass(frozen=True)
class _NormalizedIntegerRange:
    first: int
    step: int
    last: int | None
    count: int | None
    target_type: ty.TypeExpr


def _constant_scalar_grapheme(node: hir.AST) -> int | None:
    while isinstance(node, hir.RepresentationCast):
        node = node.expr
    if not isinstance(node, hir.String):
        return None
    if len(node.content) != 1 or ty.string_literal_lengths(node.content)[2] != 1:
        return None
    from .unicode.graphemes import unicode_scalar_ordinal

    return unicode_scalar_ordinal(ord(node.content))


def _normalize_integer_range(
    iterable: hir.Range,
    *,
    ctx: Context,
) -> _NormalizedIntegerRange:
    if iterable.left is None:
        user_error(
            ctx.srcfile,
            'range iteration requires a left anchor',
            Pointer(
                span=iterable.loc,
                message='this range has no first value to iterate from',
            ),
            hint='left-unbounded ranges may be used as range values, but not iterated',
        )

    string_range = _is_string_type(iterable.left.type)
    first_anchor = (
        _constant_scalar_grapheme(iterable.left)
        if string_range
        else _constant_integer(iterable.left, ctx=ctx)
    )
    second_anchor: int | None = None
    if iterable.step_pair is not None:
        second_anchor = (
            _constant_scalar_grapheme(iterable.step_pair[1])
            if string_range
            else _constant_integer(iterable.step_pair[1], ctx=ctx)
        )
    right = (
        (
            _constant_scalar_grapheme(iterable.right)
            if string_range
            else _constant_integer(iterable.right, ctx=ctx)
        )
        if iterable.right is not None
        else None
    )
    if (
        first_anchor is None
        or iterable.step_pair is not None
        and second_anchor is None
        or iterable.right is not None
        and right is None
    ):
        user_error(
            ctx.srcfile,
            (
                'character range anchors must be single-scalar graphemes'
                if string_range
                else 'range iterator anchors must be compile-time integers'
            ),
            Pointer(
                span=iterable.loc,
                message=(
                    'multi-scalar grapheme and whole-string iteration requires '
                    'an explicit alphabet or collation'
                    if string_range
                    else 'each supplied range anchor must have one exact integer value'
                ),
            ),
        )

    step = 1 if second_anchor is None else second_anchor - first_anchor
    if step == 0:
        user_error(
            ctx.srcfile,
            'range iterator step cannot be zero',
            Pointer(
                span=iterable.loc,
                message='the first two anchors produce a step of zero',
            ),
            hint='choose a distinct second anchor',
        )

    bounds_kind = iterable.bounds or '[]'
    first = first_anchor + (step if bounds_kind[0] == '(' else 0)
    if right is None:
        if string_range:
            from .unicode.graphemes import MAX_UNICODE_SCALAR_ORDINAL

            right = MAX_UNICODE_SCALAR_ORDINAL if step > 0 else 0
        else:
            return _NormalizedIntegerRange(first, step, None, None, 'int')

    right_inclusive = bounds_kind[1] == ']'
    if step > 0:
        distance = right - first - (0 if right_inclusive else 1)
    else:
        distance = first - right - (0 if right_inclusive else 1)
    count = max(0, distance // abs(step) + 1)
    last = first + (count - 1) * step if count else first - step
    backend_values = (first, step, last, count, right)
    target_type: ty.TypeExpr = (
        ty.StringType(1)
        if string_range
        else 'int64'
        if all(ty.integer_literal_fits(value, 'int64') for value in backend_values)
        else 'int'
    )
    return _NormalizedIntegerRange(first, step, last, count, target_type)


def _tcr_range_membership(
    value: hir.AST,
    range_: hir.Range,
    *,
    ctx: Context,
) -> hir.AST:
    """Fold exact membership or build runtime checks for unstepped bounds."""

    candidate = _constant_integer(value, ctx=ctx)
    if range_.step_pair is None:
        left = (
            _constant_integer(range_.left, ctx=ctx)
            if range_.left is not None
            else None
        )
        right = (
            _constant_integer(range_.right, ctx=ctx)
            if range_.right is not None
            else None
        )
        all_exact = (
            candidate is not None
            and (range_.left is None or left is not None)
            and (range_.right is None or right is not None)
        )
        bounds = range_.bounds or '[]'
        if all_exact:
            assert candidate is not None
            included = True
            if left is not None:
                included = (
                    candidate >= left
                    if bounds[0] == '['
                    else candidate > left
                )
            if included and right is not None:
                included = (
                    candidate <= right
                    if bounds[1] == ']'
                    else candidate < right
                )
            return hir.Bool(value.loc, 'bool', included)

        runtime_value = check_against(value, 'int64', ctx=ctx)
        runtime_range = replace(
            range_,
            left=(
                check_against(range_.left, 'int64', ctx=ctx)
                if range_.left is not None
                else None
            ),
            right=(
                check_against(range_.right, 'int64', ctx=ctx)
                if range_.right is not None
                else None
            ),
        )
        return hir.RangeMembership(
            range_.loc,
            'bool',
            runtime_value,
            runtime_range,
        )

    if range_.left is None:
        not_implemented(
            ctx.srcfile,
            range_.loc,
            'left-unbounded stepped range membership',
        )

    normalized = _normalize_integer_range(range_, ctx=ctx)
    if candidate is None:
        backend_values = [
            normalized.first,
            normalized.step,
            *([] if normalized.last is None else [normalized.last]),
        ]
        if not all(
            ty.integer_literal_fits(item, 'int64')
            for item in backend_values
        ):
            not_implemented(
                ctx.srcfile,
                range_.loc,
                'runtime stepped range membership requires bigint lowering',
            )
        return hir.RangeMembership(
            range_.loc,
            'bool',
            check_against(value, 'int64', ctx=ctx),
            range_,
            normalized.first,
            normalized.step,
            normalized.last,
            normalized.count,
        )
    delta = candidate - normalized.first
    aligned = delta % abs(normalized.step) == 0
    ordinal = delta // normalized.step if aligned else -1
    included = aligned and ordinal >= 0 and (
        normalized.count is None or ordinal < normalized.count
    )
    return hir.Bool(value.loc, 'bool', included)


def _tcr_range_iterator(
    condition_ast: p0.AST,
    *,
    ctx: Context,
) -> tuple[hir.IteratorExpression, Context] | None:
    """Check and normalize a static integer range loop condition."""

    if not (
        isinstance(condition_ast, p0.BinOp)
        and isinstance(condition_ast.op, t1.Operator)
        and condition_ast.op.symbol == 'in'
        and isinstance(condition_ast.left, p0.Atom)
        and isinstance(condition_ast.left.item, t1.Identifier)
    ):
        return None

    identifier = condition_ast.left.item
    iterable = typecheck_and_resolve_inner(condition_ast.right, ctx=ctx)
    if not isinstance(iterable, hir.Range):
        target_type: ty.TypeExpr | None = None
        count: int | None = None
        if _is_string_type(iterable.type):
            target_type = ty.StringType(1)
            count = _known_string_length(iterable.type)
        elif isinstance(iterable.type, ty.ArrayType):
            element_type = iterable.type.element
            if not (
                element_type == 'bool'
                or ty.fixed_integer_layout(element_type) is not None
                or isinstance(
                    element_type,
                    (ty.FunctionType, ty.StringLiteralType, ty.StringType),
                )
                or isinstance(element_type, str)
                and element_type in {'string', 'grapheme', 'char'}
            ):
                not_implemented(
                    ctx.srcfile,
                    condition_ast.right.loc,
                    'array iteration over elements with unsettled identity semantics',
                )
            target_type = element_type
            count = iterable.type.length
        if target_type is not None:
            binding = ctx.binding_registry.allocate_param(
                identifier.name,
                target_type,
                identifier.loc,
            )
            iterator_ctx = replace(
                ctx,
                declarations=ctx.declarations.new_child(
                    {identifier.name: target_type}
                ),
                binding_scopes=ctx.binding_scopes.new_child(
                    {identifier.name: binding}
                ),
            )
            target = hir.ExpressedIdentifier(
                identifier.loc,
                target_type,
                identifier.name,
                binding_id=binding.id,
            )
            return (
                hir.IteratorExpression(
                    condition_ast.loc,
                    ty.TypeParameterize('iterator', [target_type]),
                    target,
                    iterable,
                    0,
                    1,
                    None if count is None else count - 1,
                    count,
                ),
                iterator_ctx,
            )
        not_implemented(
            ctx.srcfile,
            condition_ast.right.loc,
            'iteration over a non-range value',
        )
    normalized = _normalize_integer_range(iterable, ctx=ctx)
    binding = ctx.binding_registry.allocate_param(
        identifier.name,
        normalized.target_type,
        identifier.loc,
    )
    iterator_ctx = replace(
        ctx,
        declarations=ctx.declarations.new_child(
            {identifier.name: normalized.target_type}
        ),
        binding_scopes=ctx.binding_scopes.new_child({identifier.name: binding}),
    )
    target = hir.ExpressedIdentifier(
        identifier.loc,
        normalized.target_type,
        identifier.name,
        binding_id=binding.id,
    )
    iterator = hir.IteratorExpression(
        condition_ast.loc,
        ty.TypeParameterize('iterator', [normalized.target_type]),
        target,
        iterable,
        normalized.first,
        normalized.step,
        normalized.last,
        normalized.count,
    )
    return iterator, iterator_ctx


_ITERATOR_LOGICAL_OPS: dict[str, hir.IteratorLogicalOp] = {
    'and': 'and',
    '&': 'and',
    'or': 'or',
    '|': 'or',
    'xor': 'xor',
    'nand': 'nand',
    'nor': 'nor',
    'xnor': 'xnor',
}


def _eval_iterator_formula(
    formula: list[hir.IteratorFormulaToken],
    active: list[bool],
) -> bool:
    stack: list[bool] = []
    for token in formula:
        if isinstance(token, int):
            stack.append(active[token])
            continue
        right = stack.pop()
        left = stack.pop()
        result = {
            'and': left and right,
            'or': left or right,
            'xor': left != right,
            'nand': not (left and right),
            'nor': not (left or right),
            'xnor': left == right,
        }[token]
        stack.append(result)
    if len(stack) != 1:
        raise ValueError('INTERNAL ERROR: malformed iterator postfix formula')
    return stack[0]


def _contains_iterator_syntax(ast: p0.AST) -> bool:
    if not isinstance(ast, p0.BinOp):
        return False
    if isinstance(ast.op, t1.Operator) and ast.op.symbol == 'in':
        return True
    return _contains_iterator_syntax(ast.left) or _contains_iterator_syntax(ast.right)


def _tcr_loop_iterator(
    condition_ast: p0.AST,
    *,
    ctx: Context,
) -> tuple[hir.IteratorExpression | hir.MultiIteratorExpression, Context] | None:
    iterators: list[hir.IteratorExpression] = []
    names: set[str] = set()

    def collect(
        ast: p0.AST,
        current_ctx: Context,
    ) -> tuple[list[hir.IteratorFormulaToken], Context] | None:
        if (
            isinstance(ast, p0.BinOp)
            and isinstance(ast.op, t1.Operator)
            and ast.op.symbol in _ITERATOR_LOGICAL_OPS
        ):
            left = collect(ast.left, current_ctx)
            if left is None:
                return None
            left_formula, right_ctx = left
            right = collect(ast.right, right_ctx)
            if right is None:
                return None
            right_formula, result_ctx = right
            return [
                *left_formula,
                *right_formula,
                _ITERATOR_LOGICAL_OPS[ast.op.symbol],
            ], result_ctx

        result = _tcr_range_iterator(ast, ctx=current_ctx)
        if result is None:
            return None
        iterator, iterator_ctx = result
        if iterator.target.name in names:
            user_error(
                ctx.srcfile,
                f'duplicate iterator target `{iterator.target.name}`',
                Pointer(
                    span=iterator.target.loc,
                    message='each target may occur only once in a multiiterator condition',
                ),
            )
        names.add(iterator.target.name)
        index = len(iterators)
        iterators.append(iterator)
        return [index], iterator_ctx

    collected = collect(condition_ast, ctx)
    if collected is None:
        if _contains_iterator_syntax(condition_ast):
            not_implemented(
                ctx.srcfile,
                condition_ast.loc,
                'mixed Boolean and iterator loop condition',
            )
        return None
    formula, iterator_ctx = collected
    if len(iterators) == 1:
        return iterators[0], iterator_ctx

    dynamic_array = next(
        (
            iterator
            for iterator in iterators
            if isinstance(iterator.iterable.type, ty.ArrayType)
            and iterator.count is None
        ),
        None,
    )
    if dynamic_array is not None:
        not_implemented(
            ctx.srcfile,
            dynamic_array.iterable.loc,
            'dynamic-length arrays in multiiterator formulas',
        )

    counts = [iterator.count for iterator in iterators]
    stop: int | None = None
    boundaries = {
        count
        for count in counts
        if count is not None
    }
    for iteration in sorted({0, *boundaries}):
        active = [
            count is None or iteration < count
            for count in counts
        ]
        if not _eval_iterator_formula(formula, active):
            stop = iteration
            break
    repeats = stop is None
    typed_iterators: list[hir.IteratorExpression] = []
    for iterator in iterators:
        if (
            isinstance(iterator.iterable, hir.Range)
            and iterator.count is None
            and stop is not None
        ):
            effective_last = (
                iterator.first + (stop - 1) * iterator.step
                if stop > 0
                else iterator.first - iterator.step
            )
            if all(
                ty.integer_literal_fits(value, 'int64')
                for value in (
                    iterator.first,
                    iterator.step,
                    effective_last,
                    stop,
                )
            ):
                narrowed_target = replace(iterator.target, type='int64')
                iterator = replace(
                    iterator,
                    type=ty.TypeParameterize('iterator', ['int64']),
                    target=narrowed_target,
                    last=effective_last,
                    count=stop,
                )
        target_type: ty.Type = (
            ty.optional(iterator.target.type)
            if iterator.count is not None
            and (stop is None or stop > iterator.count)
            else iterator.target.type
        )
        target = replace(iterator.target, type=target_type)
        typed_iterators.append(replace(iterator, target=target))
        if target.binding_id is not None:
            binding = ctx.binding_registry.by_id[target.binding_id]
            binding.type = target_type
        iterator_ctx.declarations[target.name] = target_type
    condition = hir.MultiIteratorExpression(
        condition_ast.loc,
        ty.TypeParameterize(
            'multiiterator',
            [
                'int'
                if any(
                    iterator.target.type == 'int'
                    for iterator in typed_iterators
                )
                else 'int64'
            ],
        ),
        typed_iterators,
        formula,
        repeats,
    )
    return condition, iterator_ctx


def tcr_flow(ast: p0.Flow, *, ctx: Context, expected: ty.Type | None = None) -> hir.Flow:
    """Typecheck supported structured `if` and while-style `loop` flows."""
    if not ast.arms:
        raise ValueError('INTERNAL ERROR: Flow has no arms')

    keywords: list[str] = []
    for arm in ast.arms:
        if not arm.parts or not isinstance(arm.parts[0], t1.Keyword):
            raise ValueError(f'INTERNAL ERROR: malformed flow arm: {arm.parts!r}')
        keywords.append(arm.parts[0].name)

    unsupported = next(
        (keyword for keyword in keywords if keyword not in {'if', 'loop'}),
        None,
    )
    if unsupported is not None:
        not_implemented(ctx.srcfile, ast.loc, f'`{unsupported}` flow')

    if all(keyword == 'if' for keyword in keywords):
        branch_expected = _flow_expected(expected)
        if isinstance(branch_expected, ty.SequenceType):
            not_implemented(ctx.srcfile, ast.loc, 'multi-value conditional result')
        arms: list[hir.IfArm | hir.LoopArm] = []
        bodies: list[hir.AST] = []
        arm_ctx = ctx
        for arm in ast.arms:
            if len(arm.parts) != 3:
                raise ValueError(f'INTERNAL ERROR: malformed if arm: {arm.parts!r}')
            _, condition_ast, body_ast = arm.parts
            assert isinstance(condition_ast, p0.AST)
            assert isinstance(body_ast, p0.AST)
            condition = _check_flow_condition(condition_ast, ctx=arm_ctx)
            body_ctx = _refine_condition_context(
                arm_ctx,
                condition,
                truth=True,
            )
            body = typecheck_and_resolve_inner(
                body_ast,
                ctx=body_ctx,
                expected=branch_expected,
            )
            if branch_expected is not None:
                body = check_against(body, branch_expected, ctx=ctx)
            arms.append(hir.IfArm(arm.loc, body.type, condition, body))
            bodies.append(body)
            arm_ctx = _refine_condition_context(
                arm_ctx,
                condition,
                truth=False,
            )

        default = None
        if ast.default is not None:
            default = typecheck_and_resolve_inner(
                ast.default,
                ctx=arm_ctx,
                expected=branch_expected,
            )
            if branch_expected is not None:
                default = check_against(default, branch_expected, ctx=ctx)
            bodies.append(default)
        elif (
            branch_expected is not None
            and any(body.type != ty.BOTTOM_TYPE for body in bodies)
        ):
            user_error(
                ctx.srcfile,
                'value-producing conditional requires a default branch',
                Pointer(span=ast.loc, message='this conditional is not exhaustive'),
                hint='add an `else` branch that produces the missing value',
            )

        result_type = _flow_value_type(
            bodies,
            exhaustive=default is not None,
            ctx=ctx,
            loc=ast.loc,
        )
        if (
            branch_expected is not None
            and result_type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE)
        ):
            result_type = branch_expected
        return hir.Flow(ast.loc, result_type, arms, default)

    if len(ast.arms) == 1 and keywords == ['loop'] and ast.default is None:
        arm = ast.arms[0]
        if len(arm.parts) != 3:
            not_implemented(ctx.srcfile, arm.loc, 'iterator or generator loop form')
        _, condition_ast, body_ast = arm.parts
        assert isinstance(condition_ast, p0.AST)
        assert isinstance(body_ast, p0.AST)
        iterator_result = _tcr_loop_iterator(condition_ast, ctx=ctx)
        if iterator_result is None:
            condition = _check_flow_condition(condition_ast, ctx=ctx)
            body_ctx = _refine_condition_context(ctx, condition, truth=True)
        else:
            condition, body_ctx = iterator_result
        if not ctx.label_scopes:
            raise ValueError('INTERNAL ERROR: loop has no containing lexical label scope')
        boundary = LoopBoundary(ctx.label_scopes[-1])
        body = typecheck_and_resolve_inner(
            body_ast,
            ctx=replace(
                body_ctx,
                loop_boundaries=(*body_ctx.loop_boundaries, boundary),
            ),
        )
        loop_arm = hir.LoopArm(arm.loc, ty.VOID_TYPE, condition, body)
        return hir.Flow(ast.loc, ty.VOID_TYPE, [loop_arm], None)

    not_implemented(ctx.srcfile, ast.loc, 'mixed or advanced flow chain')

def _direct_scope_metatag(item: p0.AST) -> t1.Metatag | None:
    if isinstance(item, p0.Atom) and isinstance(item.item, t1.Metatag):
        return item.item
    return None


def _collect_label_scope(block: p0.Block, *, ctx: Context) -> LabelScope:
    labels: dict[str, Span] = {}
    for item in block.inner:
        metatag = _direct_scope_metatag(item)
        if metatag is None:
            continue
        previous = labels.get(metatag.name)
        duplicate = previous is not None
        if not duplicate:
            ancestor = _visible_label_scope(metatag.name, ctx=ctx)
            if ancestor is not None:
                previous = ancestor.labels[metatag.name]
        if previous is not None:
            user_error(
                ctx.srcfile,
                (
                    f'duplicate scope metatag `${metatag.name}`'
                    if duplicate
                    else f'scope metatag `${metatag.name}` shadows an active declaration'
                ),
                Pointer(span=metatag.loc, message='this declaration repeats an active metatag name'),
                Pointer(span=previous, message='the active declaration is here'),
                hint='metatag names may be reused only in disjoint sibling scopes',
            )
        labels[metatag.name] = metatag.loc
    return LabelScope(labels)


def tcr_scope_metatag(ast: p0.Atom, *, name: str, ctx: Context) -> hir.ScopeMetatag:
    """Extract a direct bare metatag previously collected for this scope."""
    if not ctx.label_scopes or ctx.label_scopes[-1].labels.get(name) != ast.loc:
        not_implemented(ctx.srcfile, ast.loc, 'metatag expression outside a direct scoped-block declaration')
    return hir.ScopeMetatag(ast.loc, ty.VOID_TYPE, name)


def _declaration_parts(
    item: p0.AST,
) -> tuple[str, p0.AST] | None:
    if not isinstance(item, p0.KeywordExpr) or len(item.parts) != 2:
        return None
    expression = item.parts[1]
    if not isinstance(expression, p0.BinOp):
        return None
    target = expression.left
    if isinstance(target, p0.Atom) and isinstance(target.item, t1.Identifier):
        return target.item.name, expression.right
    if (
        isinstance(target, p0.BinOp)
        and isinstance(target.op, t1.Operator)
        and target.op.symbol == ':'
        and isinstance(target.left, p0.Atom)
        and isinstance(target.left.item, t1.Identifier)
    ):
        return target.left.item.name, expression.right
    return None


def _collect_block_bindings(block: p0.Block, *, ctx: Context) -> None:
    for item in block.inner:
        declaration = _declaration_parts(item)
        if declaration is None:
            continue
        if id(item) in ctx.binding_registry.by_syntax:
            continue
        name, expression = declaration
        kind: sb.BindingKind = (
            'function'
            if isinstance(expression, p0.BinOp)
            and isinstance(expression.op, t1.Operator)
            and expression.op.symbol == '=>'
            else 'value'
        )
        ctx.binding_registry.allocate(item, name, kind, item.loc)


def _type_alias_rhs(item: p0.AST) -> tuple[str, p0.AST] | None:
    if not _is_top_level_declare(item):
        return None
    if not isinstance(item, p0.KeywordExpr) or len(item.parts) != 2:
        return None
    expression = item.parts[1]
    if not (
        isinstance(expression, p0.BinOp)
        and isinstance(expression.op, t1.Operator)
        and expression.op.symbol in {'=', '::', ':='}
    ):
        return None
    if (
        isinstance(expression.left, p0.BinOp)
        and isinstance(expression.left.op, t1.Operator)
        and expression.left.op.symbol == ':'
        and isinstance(expression.left.left, p0.Atom)
        and isinstance(expression.left.left.item, t1.Identifier)
        and isinstance(expression.left.right, p0.Atom)
        and isinstance(expression.left.right.item, t1.Identifier)
        and expression.left.right.item.name == 'type'
    ):
        return expression.left.left.item.name, expression.right
    if (
        isinstance(expression.left, p0.Atom)
        and isinstance(expression.left.item, t1.Identifier)
        and isinstance(expression.right, p0.Block)
        and expression.right.kind == '<>'
        and len(expression.right.inner) == 1
    ):
        return expression.left.item.name, expression.right
    return None


def _prebind_type_aliases(block: p0.Block, *, ctx: Context) -> None:
    aliases: list[sb.Binding] = []
    for item in block.inner:
        alias = _type_alias_rhs(item)
        if alias is None:
            continue
        name, rhs = alias
        binding = ctx.binding_registry.by_syntax.get(id(item))
        if binding is None:
            binding = ctx.binding_registry.allocate(item, name, 'value', item.loc)
        binding.type = ty.TYPE_TYPE
        ctx.type_alias_asts[binding.id] = rhs
        ctx.declarations[name] = ty.TYPE_TYPE
        ctx.binding_scopes[name] = binding
        aliases.append(binding)
    for binding in aliases:
        _resolve_type_alias(binding, ctx=ctx)


def _generic_type_alias_parts(
    ast: p0.AST,
) -> tuple[p0.Block, p0.AST] | None:
    if not (
        isinstance(ast, p0.BinOp)
        and isinstance(ast.op, t2.TypeParamJuxtapose)
        and isinstance(ast.left, p0.Block)
        and ast.left.kind == '<>'
    ):
        return None
    return ast.left, ast.right


def _generic_type_alias(
    parameters: p0.Block,
    body: p0.AST,
    *,
    ctx: Context,
) -> ty.GenericTypeAlias:
    alias_ctx = replace(
        ctx,
        declarations=ctx.declarations.new_child(),
        binding_scopes=ctx.binding_scopes.new_child(),
    )
    params: list[ty.GenericParam] = []
    names: set[str] = set()
    for item in parameters.inner:
        if isinstance(item, p0.Atom) and isinstance(
            item.item,
            t1.Identifier,
        ):
            name = item.item.name
            bound: ty.TypeExpr = ty.TOP_TYPE
            loc = item.loc
        elif (
            isinstance(item, p0.BinOp)
            and isinstance(item.op, t1.Operator)
            and item.op.symbol == 'of'
            and isinstance(item.left, p0.Atom)
            and isinstance(item.left.item, t1.Identifier)
        ):
            name = item.left.item.name
            bound = ast_to_type(item.right, ctx=alias_ctx)
            loc = item.left.loc
        else:
            user_error(
                ctx.srcfile,
                'invalid generic type parameter',
                Pointer(
                    span=item.loc,
                    message='expected `T` or `T of Bound`',
                ),
            )
        if name in names:
            user_error(
                ctx.srcfile,
                f'duplicate generic type parameter `{name}`',
                Pointer(span=loc, message='this parameter name is repeated'),
            )
        names.add(name)
        param = ty.GenericParam(name, bound)
        params.append(param)
        binding = alias_ctx.binding_registry.allocate_param(
            name,
            ty.TYPE_TYPE,
            loc,
        )
        binding.type_value = ty.TypeVariable(name, bound)
        alias_ctx.declarations[name] = ty.TYPE_TYPE
        alias_ctx.binding_scopes[name] = binding
    if not params:
        user_error(
            ctx.srcfile,
            'generic type alias requires at least one parameter',
            Pointer(span=parameters.loc, message='this parameter list is empty'),
        )
    return ty.GenericTypeAlias(params, ast_to_type(body, ctx=alias_ctx))


def _type_alias_value(ast: p0.AST, *, ctx: Context) -> ty.TypeAliasValue:
    generic = _generic_type_alias_parts(ast)
    if generic is not None:
        parameters, body = generic
        return _generic_type_alias(parameters, body, ctx=ctx)
    return ast_to_type(ast, ctx=ctx)


def _resolve_type_alias(binding: sb.Binding, *, ctx: Context) -> ty.TypeAliasValue:
    if binding.type_value is not None:
        return binding.type_value
    if binding.id in ctx.resolving_type_aliases:
        user_error(
            ctx.srcfile,
            f'cyclic type alias involving `{binding.name}`',
            Pointer(span=binding.loc, message='this alias is part of the cycle'),
        )
    rhs = ctx.type_alias_asts[binding.id]
    ctx.resolving_type_aliases.add(binding.id)
    try:
        binding.type_value = _type_alias_value(rhs, ctx=ctx)
    finally:
        ctx.resolving_type_aliases.remove(binding.id)
    return binding.type_value


def _is_top_level_arrow(item: p0.AST) -> bool:
    return (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol in {'->', '<->'}
    )


def _is_top_level_assign(item: p0.AST) -> bool:
    return (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol == '='
    )


def _is_top_level_declare(item: p0.AST) -> bool:
    return (
        isinstance(item, p0.KeywordExpr)
        and item.parts
        and isinstance(item.parts[0], t1.Keyword)
        and item.parts[0].name in {'let', 'const'}
    )


def _bracket_kind(items: list[p0.AST]) -> Literal['dict', 'bidict', 'object', 'array']:
    if items and all(
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol == '->'
        for item in items
    ):
        return 'dict'
    if items and all(
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol == '<->'
        for item in items
    ):
        return 'bidict'
    if any(_is_top_level_arrow(item) for item in items):
        return 'dict'
    if any(_is_top_level_assign(item) or _is_top_level_declare(item) for item in items):
        return 'object'
    return 'array'


def _object_field_syntax(
    item: p0.AST,
    *,
    ctx: Context,
) -> tuple[str, p0.AST | None, p0.AST, Span, bool]:
    """Return the name, annotation, initializer, location, and mutability."""

    if _is_top_level_declare(item):
        declaration = _declaration_parts(item)
        if declaration is None:
            not_implemented(ctx.srcfile, item.loc, 'this object field declaration')
        name, value = declaration
        assert isinstance(item, p0.KeywordExpr)
        keyword = item.parts[0]
        assert isinstance(keyword, t1.Keyword)
        annotation = None
        if (
            isinstance(item, p0.KeywordExpr)
            and isinstance(item.parts[1], p0.BinOp)
            and isinstance(item.parts[1].left, p0.BinOp)
            and isinstance(item.parts[1].left.op, t1.Operator)
            and item.parts[1].left.op.symbol == ':'
        ):
            annotation = item.parts[1].left.right
        return name, annotation, value, item.loc, keyword.name != 'const'
    if (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol == '='
        and isinstance(item.left, p0.Atom)
        and isinstance(item.left.item, t1.Identifier)
    ):
        return item.left.item.name, None, item.right, item.loc, True
    if (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol == '='
        and isinstance(item.left, p0.BinOp)
        and isinstance(item.left.op, t1.Operator)
        and item.left.op.symbol == ':'
        and isinstance(item.left.left, p0.Atom)
        and isinstance(item.left.left.item, t1.Identifier)
    ):
        return item.left.left.item.name, item.left.right, item.right, item.loc, True
    user_error(
        ctx.srcfile,
        'object fields must be assignments or declarations',
        Pointer(span=item.loc, message='this is not a named field'),
    )


def _function_uses_bindings(node: hir.AST, binding_ids: set[int]) -> bool:
    if isinstance(node, hir.ExpressedIdentifier):
        return node.binding_id in binding_ids
    if isinstance(node, hir.FunctionLiteral):
        return False
    if isinstance(node, hir.Block):
        return any(_function_uses_bindings(item, binding_ids) for item in node.items)
    if isinstance(node, hir.Declare):
        return _function_uses_bindings(node.expr, binding_ids)
    if isinstance(node, hir.Assign):
        return (
            _function_uses_bindings(node.target, binding_ids)
            or _function_uses_bindings(node.value, binding_ids)
        )
    if isinstance(node, hir.FunctionCall):
        return (
            _function_uses_bindings(node.func, binding_ids)
            or any(_function_uses_bindings(arg, binding_ids) for arg in node.pos_args)
            or any(_function_uses_bindings(arg, binding_ids) for arg in node.kw_args.values())
        )
    if isinstance(node, hir.Flow):
        return any(
            _function_uses_bindings(arm.condition, binding_ids)
            or _function_uses_bindings(arm.body, binding_ids)
            for arm in node.arms
        ) or (
            node.default is not None
            and _function_uses_bindings(node.default, binding_ids)
        )
    if isinstance(node, hir.ShortCircuit):
        return (
            _function_uses_bindings(node.left, binding_ids)
            or _function_uses_bindings(node.right, binding_ids)
        )
    if isinstance(node, hir.Return) and node.item is not None:
        return _function_uses_bindings(node.item, binding_ids)
    if isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Transmute)):
        return _function_uses_bindings(node.expr, binding_ids)
    if isinstance(node, hir.MemberAccess):
        return _function_uses_bindings(node.value, binding_ids)
    if isinstance(node, hir.MemberAssign):
        return (
            _function_uses_bindings(node.target, binding_ids)
            or _function_uses_bindings(node.value, binding_ids)
        )
    if isinstance(node, hir.ObjectLiteral):
        return any(_function_uses_bindings(field.value, binding_ids) for field in node.fields)
    if isinstance(node, hir.ArrayLiteral):
        return any(_function_uses_bindings(item, binding_ids) for item in node.items)
    if isinstance(node, hir.ArrayLength):
        return _function_uses_bindings(node.array, binding_ids)
    if isinstance(node, hir.Index):
        return (
            _function_uses_bindings(node.array, binding_ids)
            or _function_uses_bindings(node.index, binding_ids)
        )
    if isinstance(node, hir.IndexAssign):
        return (
            _function_uses_bindings(node.target, binding_ids)
            or _function_uses_bindings(node.value, binding_ids)
        )
    if isinstance(node, hir.StringLength):
        return _function_uses_bindings(node.string, binding_ids)
    if isinstance(node, hir.StringIndex):
        return (
            _function_uses_bindings(node.string, binding_ids)
            or _function_uses_bindings(node.index, binding_ids)
        )
    if isinstance(node, hir.StringSlice):
        return (
            _function_uses_bindings(node.string, binding_ids)
            or _function_uses_bindings(node.range, binding_ids)
        )
    if isinstance(node, hir.StringEqual):
        return (
            _function_uses_bindings(node.left, binding_ids)
            or _function_uses_bindings(node.right, binding_ids)
        )
    if isinstance(node, hir.StringConcat):
        return (
            _function_uses_bindings(node.left, binding_ids)
            or _function_uses_bindings(node.right, binding_ids)
        )
    if isinstance(node, hir.InterpolatedString):
        return any(
            _function_uses_bindings(part, binding_ids)
            for part in node.parts
        )
    if isinstance(node, hir.TypeTest):
        return _function_uses_bindings(node.value, binding_ids)
    if isinstance(node, hir.IfArm) or isinstance(node, hir.LoopArm):
        return (
            _function_uses_bindings(node.condition, binding_ids)
            or _function_uses_bindings(node.body, binding_ids)
        )
    return False


def _mark_object_receiver(
    value: hir.AST,
    field_bindings: tuple[tuple[int, str], ...],
    object_type: ty.ObjectType,
) -> hir.AST:
    if not isinstance(value, hir.FunctionLiteral):
        return value
    binding_ids = {binding_id for binding_id, _name in field_bindings}
    uses_fields = _function_uses_bindings(value.body, binding_ids)
    return replace(
        value,
        object_receiver=True,
        object_fields=field_bindings if uses_fields else (),
        object_type=object_type,
    )


def _maybe_auto_call_member(node: hir.AST, *, ctx: Context) -> hir.AST:
    if not isinstance(node, hir.MemberAccess):
        return node
    if ty.is_zero_arg_function(node.type):
        assert isinstance(node.type, ty.FunctionType)
        return hir.FunctionCall(node.loc, node.type.ret, node, [], {})
    if isinstance(node.type, (ty.FunctionType, ty.OverloadType)):
        not_implemented(
            ctx.srcfile,
            node.loc,
            'extracting an object method as a function value',
        )
    return node


def _tcr_object_literal(
    block: p0.Block,
    *,
    expected: ty.Type | None,
    ctx: Context,
) -> hir.ObjectLiteral:
    expected_object = expected if isinstance(expected, ty.ObjectType) else None
    if expected is not None and expected_object is None:
        type_error(
            ctx.srcfile,
            'type mismatch',
            Pointer(
                span=block.loc,
                message=f'expected `{type_to_dewy(expected)}`, got an object literal',
            ),
        )

    ctx = replace(
        ctx,
        declarations=ctx.declarations.new_child(),
        binding_scopes=ctx.binding_scopes.new_child(),
    )
    specs = [_object_field_syntax(item, ctx=ctx) for item in block.inner]
    seen: dict[str, Span] = {}
    for name, _annotation, _value, loc, _mutable in specs:
        previous = seen.get(name)
        if previous is not None:
            user_error(
                ctx.srcfile,
                f'duplicate object field `{name}`',
                Pointer(span=loc, message='this field repeats a name'),
                Pointer(span=previous, message='the earlier field is here'),
            )
        seen[name] = loc

    if expected_object is not None:
        expected_names = [field.name for field in expected_object.fields]
        actual_names = [
            name for name, _annotation, _value, _loc, _mutable in specs
        ]
        if actual_names != expected_names:
            type_error(
                ctx.srcfile,
                'object fields do not match the expected type',
                Pointer(
                    span=block.loc,
                    message=(
                        f'expected `[{ " ".join(f"{field.name}:{type_to_dewy(field.type)}" for field in expected_object.fields) }]`, '
                        f'got fields `{" ".join(actual_names)}`'
                    ),
                ),
            )

    field_bindings: list[sb.Binding] = []
    deferred: set[int] = set()
    for index, (name, annotation_ast, value_ast, loc, _mutable) in enumerate(specs):
        kind: sb.BindingKind = (
            'function'
            if isinstance(value_ast, p0.BinOp)
            and isinstance(value_ast.op, t1.Operator)
            and value_ast.op.symbol == '=>'
            else 'value'
        )
        binding = ctx.binding_registry.allocate(block.inner[index], name, kind, loc)
        field_bindings.append(binding)
        if kind != 'function':
            continue
        try:
            signature = signature_of(value_ast, ctx=ctx)
        except ReportException:
            continue
        if signature is None:
            continue
        deferred.add(index)
        binding.type = signature
        ctx.declarations[name] = signature
        ctx.binding_scopes[name] = binding

    checked_fields: list[hir.AST | None] = [None] * len(specs)
    for index, (name, annotation_ast, value_ast, loc, _mutable) in enumerate(specs):
        if index in deferred:
            continue
        field_expected: ty.Type | None = None
        if annotation_ast is not None:
            field_expected = ast_to_type(annotation_ast, ctx=ctx)
        elif expected_object is not None:
            field_expected = expected_object.fields[index].type
        value = typecheck_and_resolve_inner(value_ast, ctx=ctx, expected=field_expected)
        require_valued(value.type, ctx.srcfile, value.loc, 'object field')
        if isinstance(value.type, (ty.FunctionType, ty.OverloadType)) and not isinstance(
            value,
            hir.FunctionLiteral,
        ):
            not_implemented(
                ctx.srcfile,
                value.loc,
                'storing a non-literal function in an object field',
            )
        if field_expected is not None:
            value = check_against(value, field_expected, ctx=ctx)
            field_type: ty.Type = field_expected
        elif isinstance(value.type, ty.IntegerLiteralType):
            value = check_against(value, 'int64', ctx=ctx)
            field_type = 'int64'
        else:
            field_type = value.type
        binding = field_bindings[index]
        binding.type = field_type
        binding.kind = (
            'function'
            if isinstance(value, hir.FunctionLiteral)
            else 'value'
        )
        ctx.declarations[name] = field_type
        ctx.binding_scopes[name] = binding
        checked_fields[index] = value
    for index, (name, annotation_ast, value_ast, loc, _mutable) in enumerate(specs):
        if index not in deferred:
            continue
        field_expected = field_bindings[index].type
        if annotation_ast is not None:
            field_expected = ast_to_type(annotation_ast, ctx=ctx)
        elif expected_object is not None:
            field_expected = expected_object.fields[index].type
        value = typecheck_and_resolve_inner(value_ast, ctx=ctx, expected=field_expected)
        require_valued(value.type, ctx.srcfile, value.loc, 'object field')
        if field_expected is not None:
            value = check_against(value, field_expected, ctx=ctx)
            field_type = field_expected
        else:
            field_type = value.type
        binding = field_bindings[index]
        binding.type = field_type
        if isinstance(value, hir.FunctionLiteral):
            binding.function = value
        ctx.declarations[name] = field_type
        ctx.binding_scopes[name] = binding
        checked_fields[index] = value

    object_fields = tuple(
        (binding.id, name)
        for binding, (name, _annotation, _value, _loc, _mutable) in zip(
            field_bindings,
            specs,
        )
    )
    fields: list[hir.ObjectField] = []
    types: list[ty.ObjectField] = []
    for index, (name, _annotation, _value_ast, loc, mutable) in enumerate(specs):
        value = checked_fields[index]
        assert value is not None
        binding = field_bindings[index]
        fields.append(hir.ObjectField(loc, name, value, binding.id, mutable))
        types.append(ty.ObjectField(name, binding.type or value.type, mutable))
    object_type = ty.ObjectType(tuple(types))
    if expected_object is not None:
        check_against(
            hir.ObjectLiteral(block.loc, object_type, fields),
            expected_object,
            ctx=ctx,
        )
        object_type = expected_object
    marked: list[hir.ObjectField] = []
    for object_field, binding in zip(fields, field_bindings):
        value = _mark_object_receiver(
            object_field.value,
            object_fields,
            object_type,
        )
        if isinstance(value, hir.FunctionLiteral):
            binding.function = value
        marked.append(replace(object_field, value=value))
    return hir.ObjectLiteral(block.loc, object_type, marked)


def _tcr_member_access(binop: p0.BinOp, *, ctx: Context) -> hir.AST:
    if not (
        isinstance(binop.right, p0.Atom)
        and isinstance(binop.right.item, t1.Identifier)
    ):
        not_implemented(ctx.srcfile, binop.loc, 'computed member access')
    name = binop.right.item.name
    if (
        isinstance(binop.left, p0.Atom)
        and isinstance(binop.left.item, t1.Identifier)
        and (module := ctx.module_namespaces.get(binop.left.item.name)) is not None
    ):
        binding = module.exports.get(name)  # type: ignore[attr-defined]
        if binding is None:
            user_error(
                ctx.srcfile,
                f'module has no top-level binding `{name}`',
                Pointer(span=binop.right.loc, message='this member is not exported'),
                hint='available names: ' + ', '.join(module.exports),  # type: ignore[attr-defined]
            )
        if binding.type_value is not None or binding.type == ty.TYPE_TYPE:
            not_implemented(ctx.srcfile, binop.loc, 'runtime use of an imported type')
        if binding.type is None:
            raise ValueError(f'INTERNAL ERROR: module member `{name}` has no type')
        return hir.ExpressedIdentifier(
            binop.loc,
            binding.type,
            binding.name,
            binding_id=binding.id,
        )
    if name == 'length':
        value = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        if isinstance(value.type, ty.BinaryLiteralType):
            value = hir.RepresentationCast(
                value.loc,
                ty.ArrayType('uint8', len(value.type.value)),
                value,
            )
        if isinstance(value.type, ty.ArrayType):
            result_type: ty.Type = (
                ty.IntegerLiteralType(value.type.length)
                if value.type.length is not None
                else 'int64'
            )
            return hir.ArrayLength(binop.loc, result_type, value)
        string_length = _known_string_length(value.type)
        if _is_string_type(value.type):
            result_type = (
                ty.IntegerLiteralType(string_length)
                if string_length is not None
                else 'int64'
            )
            return hir.StringLength(binop.loc, result_type, value)
    value = typecheck_and_resolve_inner(binop.left, ctx=ctx)
    source_place = value if isinstance(value, hir.Place) else None
    if source_place is not None:
        value = source_place.target
    if not isinstance(value.type, ty.ObjectType):
        if name == 'length':
            type_error(
                ctx.srcfile,
                '`.length` requires an array or string',
                Pointer(
                    span=value.loc,
                    message=f'this has type `{type_to_dewy(value.type)}`',
                ),
            )
        type_error(
            ctx.srcfile,
            'member access requires an object',
            Pointer(
                span=value.loc,
                message=f'this has type `{type_to_dewy(value.type)}`',
            ),
        )
    field = value.type.field(name)
    if field is None:
        user_error(
            ctx.srcfile,
            f'unknown object field `{name}`',
            Pointer(span=binop.right.loc, message='this field is not present'),
            hint=f'available fields: {", ".join(item.name for item in value.type.fields) or "(none)"}',
        )
    access = hir.MemberAccess(binop.loc, field.type, value, name, field.mutable)
    if source_place is None:
        return access
    if not field.mutable:
        user_error(
            ctx.srcfile,
            f'cannot take the place of const object field `{name}`',
            Pointer(span=binop.loc, message='this field is const'),
        )
    return hir.Place(binop.loc, field.type, access)


def _member_root_binding(node: hir.AST, *, ctx: Context) -> sb.Binding | None:
    root = node
    while True:
        if isinstance(root, hir.MemberAccess):
            root = root.value
            continue
        if isinstance(root, hir.Index):
            root = root.array
            continue
        if isinstance(root, hir.Block) and not root.scoped and len(root.items) == 1:
            root = root.items[0]
            continue
        if isinstance(root, (hir.ValueCast, hir.RepresentationCast, hir.Transmute)):
            root = root.expr
            continue
        break
    if isinstance(root, hir.ExpressedIdentifier) and root.binding_id is not None:
        return ctx.binding_registry.by_id.get(root.binding_id)
    return None


def _tcr_array_literal(
    block: p0.Block,
    items: list[hir.AST],
    *,
    expected: ty.Type | None,
    ctx: Context,
) -> hir.ArrayLiteral:
    """Check a one-dimensional homogeneous array with a supported element layout."""

    expected_array = expected if isinstance(expected, ty.ArrayType) else None
    if expected is not None and expected_array is None:
        type_error(
            ctx.srcfile,
            'type mismatch',
            Pointer(
                span=block.loc,
                message=f'expected `{type_to_dewy(expected)}`, got an array literal',
            ),
        )
    if expected_array is not None and expected_array.length not in (None, len(items)):
        type_error(
            ctx.srcfile,
            'array length mismatch',
            Pointer(
                span=block.loc,
                message=(
                    f'expected length {expected_array.length}, '
                    f'got {len(items)} elements'
                ),
            ),
        )

    if expected_array is not None:
        element_type = expected_array.element
    else:
        concrete_types: list[ty.Type] = []
        for item in items:
            if isinstance(
                item.type,
                (
                    ty.IntegerLiteralType,
                    ty.StringLiteralType,
                    ty.BinaryLiteralType,
                ),
            ):
                continue
            if item.type not in concrete_types:
                concrete_types.append(item.type)
        if not items:
            type_error(
                ctx.srcfile,
                'cannot infer empty array element type',
                Pointer(
                    span=block.loc,
                    message='add an annotation such as `array<int64>`',
                ),
            )
        if not concrete_types:
            if all(isinstance(item.type, ty.IntegerLiteralType) for item in items):
                element_type = 'int64'
            elif all(isinstance(item.type, ty.StringLiteralType) for item in items):
                element_type = ty.StringType(
                    1
                    if all(
                        _known_string_length(item.type) == 1
                        for item in items
                    )
                    else None
                )
            elif all(isinstance(item.type, ty.BinaryLiteralType) for item in items):
                lengths = {
                    len(item.type.value)
                    for item in items
                    if isinstance(item.type, ty.BinaryLiteralType)
                }
                if len(lengths) != 1:
                    type_error(
                        ctx.srcfile,
                        'array elements are not homogeneous',
                        *[
                            Pointer(
                                span=item.loc,
                                message=f'element has type `{type_to_dewy(item.type)}`',
                            )
                            for item in items
                        ],
                    )
                element_type = ty.ArrayType('uint8', lengths.pop())
            else:
                type_error(
                    ctx.srcfile,
                    'array elements are not homogeneous',
                    *[
                        Pointer(
                            span=item.loc,
                            message=f'element has type `{type_to_dewy(item.type)}`',
                        )
                        for item in items
                    ],
                )
        elif len(concrete_types) == 1:
            element_type = concrete_types[0]
        else:
            type_error(
                ctx.srcfile,
                'array elements are not homogeneous',
                *[
                    Pointer(
                        span=item.loc,
                        message=f'element has type `{type_to_dewy(item.type)}`',
                    )
                    for item in items
                ],
            )

    if not _supported_array_element_type(element_type):
        type_error(
            ctx.srcfile,
            'unsupported array element type',
            Pointer(
                span=block.loc,
                message=(
                    'arrays require a fixed-width scalar or handle element type, '
                    f'got `{type_to_dewy(element_type)}`'
                ),
            ),
        )

    checked_items: list[hir.AST] = []
    for item in items:
        require_valued(item.type, ctx.srcfile, item.loc, 'array element')
        checked_items.append(check_against(item, element_type, ctx=ctx))
    array_type = ty.ArrayType(element_type, len(checked_items))
    return hir.ArrayLiteral(block.loc, array_type, checked_items)


def _supported_array_element_type(type_: ty.Type) -> bool:
    return (
        isinstance(
            type_,
            (
                ty.ArrayType,
                ty.FunctionType,
                ty.StringLiteralType,
                ty.StringType,
            ),
        )
        or isinstance(type_, str)
        and (
            type_ in ty.FIXED_INTEGER_TYPES
            or type_ in {'bool', 'string', 'grapheme', 'char'}
        )
    )


def _literal_path_parameter(expression: p0.BinOp) -> str | None:
    body = expression.right
    if not isinstance(body, p0.Block) or body.kind != '[]':
        return None
    path_fields = [
        item
        for item in body.inner
        if (
            isinstance(item, p0.BinOp)
            and isinstance(item.op, t1.Operator)
            and item.op.symbol == '='
            and isinstance(item.left, p0.Atom)
            and isinstance(item.left.item, t1.Identifier)
            and item.left.item.name == 'path'
        )
    ]
    if len(path_fields) != 1:
        return None
    value = path_fields[0].right
    if not isinstance(value, p0.Atom) or not isinstance(value.item, t1.Identifier):
        return None
    return value.item.name


def tcr_block(block: p0.Block, *, ctx: Context, expected: ty.Type|None=None) -> hir.AST:
    if block.kind == '<>':
        if len(block.inner) != 1:
            user_error(
                ctx.srcfile,
                'type block requires one type expression',
                Pointer(
                    span=block.loc,
                    message=f'found {len(block.inner)} separate expressions',
                ),
                hint='combine alternatives with `|`, for example `<int64 | string>`',
            )
        return hir.TypeValue(
            block.loc,
            ty.TYPE_TYPE,
            ast_to_type(block.inner[0], ctx=ctx),
        )

    # open a new scope if the block is a scoped block
    type_block = False
    if block.kind == '{}':
        ctx = replace(
            ctx,
            declarations=ctx.declarations.new_child(),
            binding_scopes=ctx.binding_scopes.new_child(),
            module_namespaces=ctx.module_namespaces.new_child(),
            label_scopes=(*ctx.label_scopes, _collect_label_scope(block, ctx=ctx)),
        )

    if block.kind == '[]':
        arrows = [item for item in block.inner if _is_top_level_arrow(item)]
        if arrows and len(arrows) != len(block.inner):
            user_error(
                ctx.srcfile,
                'cannot mix dictionary arrows with other `[]` items',
                Pointer(span=arrows[0].loc, message='this arrow is inside a mixed container'),
            )
        arrow_symbols = {
            item.op.symbol
            for item in arrows
            if isinstance(item, p0.BinOp) and isinstance(item.op, t1.Operator)
        }
        if len(arrow_symbols) > 1:
            user_error(
                ctx.srcfile,
                'cannot mix `->` and `<->` in one container',
                Pointer(span=arrows[0].loc, message='dictionary arrows must all use the same operator'),
            )
        kind = _bracket_kind(block.inner)
        if kind in {'dict', 'bidict'}:
            not_implemented(ctx.srcfile, block.loc, 'dictionary literals')
        if kind == 'object' or isinstance(expected, ty.ObjectType):
            return _tcr_object_literal(block, expected=expected, ctx=ctx)

    _collect_block_bindings(block, ctx=ctx)
    _prebind_type_aliases(block, ctx=ctx)

    deferred_functions: set[int] = set()
    if not type_block:
        for item in block.inner:
            declaration = _declaration_parts(item)
            if declaration is None:
                continue
            name, expression = declaration
            if not (
                isinstance(expression, p0.BinOp)
                and isinstance(expression.op, t1.Operator)
                and expression.op.symbol == '=>'
            ):
                continue
            try:
                signature = signature_of(expression, ctx=ctx)
            except ReportException:
                continue
            if signature is None:
                continue
            deferred_functions.add(id(item))
            binding = ctx.binding_registry.by_syntax[id(item)]
            binding.type = signature
            binding.literal_path_parameter = _literal_path_parameter(expression)
            ctx.declarations[name] = signature
            ctx.binding_scopes[name] = binding

    # Check eager source items in order, postponing only functions whose complete
    # signatures are already known. Their bodies use the scope after sequential
    # declarations have supplied the remaining value types.
    # `()` / `{}` are non-semantic (aside from `{}` opening a scope), so an expected type
    # must flow through them. For now only the single-item wrapper case forwards it —
    # enough for `():>float => {1}` / `(1)` to match bare `1`.
    # TODO: full generality — push expected into the expressed-value slots of a multi-item
    # block (skipping void/never items like declarations), and when expected is a
    # SequenceType distribute it pointwise across those slots. Can't forward expected to
    # every item blindly: `{ let x = 1; x }` must not shove the outer expected into the decl.
    results: list[hir.AST | None] = [None] * len(block.inner)
    for index, item in enumerate(block.inner):
        if id(item) in deferred_functions:
            continue
        item_expected = (
            expected.element
            if block.kind == '[]' and isinstance(expected, ty.ArrayType)
            else expected
            if expected is not None and len(block.inner) == 1
            else None
        )
        results[index] = typecheck_and_resolve_inner(
            item,
            ctx=ctx,
            type_block=type_block,
            expected=item_expected,
        )
    for index, item in enumerate(block.inner):
        if id(item) not in deferred_functions:
            continue
        results[index] = typecheck_and_resolve_inner(item, ctx=ctx, type_block=type_block)
    checked_results = [result for result in results if result is not None]
    if len(checked_results) != len(results):
        raise ValueError('INTERNAL ERROR: block item was not checked')
    results = checked_results

    match block.kind:
        case '()'|'{}':
            scoped = block.kind == '{}'  # only difference between () and {} is the scoped flag  (or possibly a non-inclusive range)
            if len(results) == 0:
                return hir.Void(block.loc, ty.VOID_TYPE)
            if len(results) == 1:
                if not scoped and isinstance(results[0], hir.Range) and results[0].bounds is None:
                    return replace(results[0], loc=block.loc, bounds=block.kind)
                return hir.Block(block.loc, results[0].type, results, scoped=scoped)

            # any `never` item (e.g. a return) means control can't fall out the end of the block
            if any(r.type == ty.BOTTOM_TYPE for r in results):
                return hir.Block(block.loc, ty.BOTTOM_TYPE, results, scoped=scoped)

            # otherwise the block's value is its expressed (non-void) values, collapsed
            expressed = [r.type for r in results if r.type != ty.VOID_TYPE]
            return hir.Block(block.loc, ty.sequence(*expressed), results, scoped=scoped)


        case '[]':
            if len(results) == 1 and isinstance(results[0], hir.Range) and results[0].bounds is None:
                return replace(results[0], loc=block.loc, bounds=block.kind)
            return _tcr_array_literal(block, results, expected=expected, ctx=ctx)
        case '[)' | '(]':
            if len(results) != 1 or not isinstance(results[0], hir.Range) or results[0].bounds is not None:
                user_error(ctx.srcfile, f'invalid contents for `{block.kind}` range delimiters',
                    Pointer(span=block.loc, message=f'`{block.kind}` may only contain a single bare range expression, got {len(results)} expressions'),
                    hint='e.g. `[1..10)`. use `[]` for arrays or `()` for grouping')
            return replace(results[0], loc=block.loc, bounds=block.kind)
        case _:
            # unreachable
            raise ValueError(f'INTERNAL ERROR: invalid block kind: {block.kind}')

def _function_alternates(node: hir.AST) -> list[hir.AST]:
    if isinstance(node, hir.OverloadedFunction):
        return list(node.alternates)
    if isinstance(node.type, (ty.FunctionType, ty.OverloadType)):
        return [node]
    raise ValueError(f'INTERNAL ERROR: expected callable for overload construction, got {node.type}')


def _function_methods(t: ty.Type) -> list[ty.FunctionType]:
    if isinstance(t, ty.FunctionType):
        return [t]
    if isinstance(t, ty.OverloadType):
        return list(t.methods)
    raise ValueError(f'INTERNAL ERROR: expected callable type for overload construction, got {t}')


def _is_overload_constructor(fname: str, method: ty.FunctionType) -> bool:
    """Whether the selected builtin method constructs an overload set instead of executing."""
    return fname == '__and__' and method.ret == 'multifunction'


def _numeric_product_type(
    left: ty.TypeExpr,
    right: ty.TypeExpr,
    *,
    ctx: Context,
) -> ty.TypeExpr | None:
    """Return the ordinary numeric result type for a type-level product."""

    if not (
        ctx.type_system.is_subtype(left, 'number')
        and ctx.type_system.is_subtype(right, 'number')
    ):
        return None
    # Multiplying two numeric singleton types produces another singleton.
    # Unit constants deliberately use singleton representations (for example,
    # ``ms:Duration<1000000>``), so this also retains their compile-time scale.
    if isinstance(left, ty.IntegerLiteralType) and isinstance(right, ty.IntegerLiteralType):
        return ty.IntegerLiteralType(left.value * right.value)
    if left == right:
        return left
    if ctx.type_system.is_subtype(left, right):
        return right
    if ctx.type_system.is_subtype(right, left):
        return left
    # An integer scale factor can be represented in any wider real type.  This
    # is what lets the same unit constant preserve the representation of an
    # ``int``, ``uint64``, or floating-point quantity multiplied by it.
    if isinstance(left, ty.IntegerLiteralType) and ctx.type_system.is_subtype(right, 'real'):
        return right
    if isinstance(right, ty.IntegerLiteralType) and ctx.type_system.is_subtype(left, 'real'):
        return left
    return ctx.type_system.promote_type(left, right)


def _quantity_product_type(
    left: ty.TypeExpr,
    right: ty.TypeExpr,
    *,
    ctx: Context,
) -> ty.TypeExpr | None:
    """Compose numeric representations and physical dimensions for ``*``."""

    left_number: ty.TypeExpr
    left_dimension: ty.DimensionType
    if isinstance(left, ty.QuantityType):
        left_number, left_dimension = left.number, left.dimension
    else:
        left_number, left_dimension = left, ty.dimension()

    right_number: ty.TypeExpr
    right_dimension: ty.DimensionType
    if isinstance(right, ty.QuantityType):
        right_number, right_dimension = right.number, right.dimension
    else:
        right_number, right_dimension = right, ty.dimension()

    if not (
        isinstance(left, ty.QuantityType)
        or isinstance(right, ty.QuantityType)
    ):
        return None
    number = _numeric_product_type(left_number, right_number, ctx=ctx)
    if number is None:
        return None
    dimension = ty.multiply_dimensions(left_dimension, right_dimension)
    return number if not dimension.powers else ty.QuantityType(number, dimension)


def _dispatch_builtin(
    fname: str,
    args: list[hir.AST],
    *,
    loc: Span,
    op_loc: Span,
    source_name: str,
    ctx: Context,
    expected: ty.Type | None = None,
) -> hir.AST:
    """Resolve a builtin dunder call and apply any selected promotions."""
    arg_types = [
        require_valued(
            arg.type,
            ctx.srcfile,
            arg.loc,
            f'operand of `{source_name}`',
        )
        for arg in args
    ]
    if (
        fname in {'__lshift__', '__rshift__'}
        and len(args) == 2
        and not ctx.type_system.is_subtype(arg_types[1], 'uint')
    ):
        type_error(
            ctx.srcfile,
            'shift count must be unsigned',
            Pointer(
                span=args[1].loc,
                message=(
                    f'this count has type `{type_to_dewy(arg_types[1])}`; '
                    'negative shifts are not defined'
                ),
            ),
        )
    if fname == '__mul__' and len(args) == 2:
        quantity_result = _quantity_product_type(
            arg_types[0],
            arg_types[1],
            ctx=ctx,
        )
        if quantity_result is not None:
            constant_values = [
                _constant_integer(arg, ctx=ctx)
                for arg in args
            ]
            if all(value is not None for value in constant_values):
                left_value, right_value = cast(list[int], constant_values)
                value = left_value * right_value
                representation = (
                    quantity_result.number
                    if isinstance(quantity_result, ty.QuantityType)
                    else quantity_result
                )
                if (
                    isinstance(representation, str)
                    and representation in ty.FIXED_INTEGER_TYPES
                    and not ty.integer_literal_fits(value, representation)
                ):
                    type_error(
                        ctx.srcfile,
                        'physical quantity is outside its numeric representation',
                        Pointer(
                            span=loc,
                            message=(
                                f'`{value}` does not fit in '
                                f'`{type_to_dewy(representation)}`'
                            ),
                        ),
                    )
                return hir.Integer(
                    loc,
                    quantity_result,
                    t0.base10,
                    value,
                )
            method = ty.FunctionType(
                [
                    ty.PosOrKwArg('left', arg_types[0]),
                    ty.PosOrKwArg('right', arg_types[1]),
                ],
                [],
                None,
                quantity_result,
            )
            return hir.FunctionCall(
                loc,
                quantity_result,
                hir.ExpressedIdentifier(op_loc, method, fname),
                args,
                {},
            )

    ftype = ctx.declarations[fname]
    assert isinstance(ftype, (ty.FunctionType, ty.OverloadType)), (
        f'INTERNAL ERROR: builtin function type expected, got {type(ftype)}'
    )
    methods = ftype.methods if isinstance(ftype, ty.OverloadType) else [ftype]
    try:
        expected_return = expected if expected not in (None, ty.VOID_TYPE, ty.INFERRED_TYPE) else None
        result = ctx.type_system.match_best_function(methods, arg_types, expected_return=expected_return)
    except ty.DispatchError as e:
        pointers = [Pointer(span=op_loc, message=str(e))]
        pointers.extend(
            Pointer(span=arg.loc, message=f'operand has type `{type_to_dewy(arg.type)}`')
            for arg in args
        )
        type_error(ctx.srcfile, f'no matching overload for operator `{source_name}`', *pointers)

    if len(args) == 2 and _is_overload_constructor(fname, result.method):
        left, right = args
        combined = ty.OverloadType(_function_methods(left.type) + _function_methods(right.type))
        return hir.OverloadedFunction(
            loc,
            combined,
            _function_alternates(left) + _function_alternates(right),
        )

    contextual_args = [
        check_against(
            _contextualize_flow_result(arg, param.type, ctx=ctx),
            param.type,
            ctx=ctx,
        )
        for arg, param in zip(args, result.method.pos_or_kw)
    ]
    if (
        fname in {'__eq__', '__ne__'}
        and len(contextual_args) == 2
        and all(_is_string_type(arg.type) for arg in contextual_args)
    ):
        return hir.StringEqual(
            loc,
            'bool',
            contextual_args[0],
            contextual_args[1],
            fname == '__ne__',
        )
    if (
        fname == '__add__'
        and len(contextual_args) == 2
        and all(_is_string_type(arg.type) for arg in contextual_args)
    ):
        left, right = contextual_args
        if isinstance(args[0].type, ty.StringLiteralType) and isinstance(
            args[1].type,
            ty.StringLiteralType,
        ):
            content = args[0].type.value + args[1].type.value
            return hir.String(loc, ty.StringLiteralType(content), content)
        return hir.StringConcat(loc, ty.StringType(), left, right)
    return hir.FunctionCall(
        loc,
        result.method.ret,
        hir.ExpressedIdentifier(op_loc, result.method, fname),
        apply_promotions(contextual_args, result.promote_pos),
        {},
    )


def tcr_prefix(prefix: p0.Prefix, *, ctx: Context, expected: ty.Type | None = None) -> hir.AST:
    """Typecheck a prefix operator through its builtin dunder."""
    if not isinstance(prefix.op, t1.Operator):
        not_implemented(ctx.srcfile, prefix.op.loc, 'broadcast prefix operator')
    if prefix.op.symbol == '@':
        if not ctx.allow_place_expression:
            type_error(
                ctx.srcfile,
                'a place can only be used as a function argument',
                Pointer(
                    span=prefix.loc,
                    message='this place would escape its immediate call',
                ),
                hint='pass `@name` directly to a parameter declared with `@`',
            )
        target_ast = prefix.item
        if (
            isinstance(target_ast, p0.Block)
            and target_ast.kind == '()'
            and len(target_ast.inner) == 1
        ):
            target_ast = target_ast.inner[0]
        target = tcr_assignment_target(target_ast, ctx=ctx)
        if isinstance(target.type, (ty.FunctionType, ty.OverloadType)):
            not_implemented(
                ctx.srcfile,
                prefix.loc,
                'function handles and partial application with `@`',
            )
        binding = _member_root_binding(target, ctx=ctx)
        if binding is not None:
            if (
                binding.declaration is not None
                and binding.declaration.decltype == 'const'
            ):
                user_error(
                    ctx.srcfile,
                    'cannot pass a const binding as a mutable place',
                    Pointer(
                        span=prefix.loc,
                        message=f'`{binding.name}` is declared const',
                    ),
                    Pointer(
                        span=binding.declaration.loc,
                        message='const declaration is here',
                    ),
                )
        return hir.Place(prefix.loc, target.type, target)
    if prefix.op.symbol not in builtins.UNARY_PREFIX_DUNDER_MAP:
        not_implemented(ctx.srcfile, prefix.op.loc, f'prefix operator `{prefix.op.symbol}`')
    if (
        prefix.op.symbol == '-'
        and isinstance(expected, str)
        and expected in ty.FIXED_INTEGER_TYPES
        and isinstance(prefix.item, p0.Atom)
        and isinstance(prefix.item.item, t1.Integer)
    ):
        parsed = t0.parse_integer(
            prefix.item.item.value.src,
            prefix.item.item.value.prefix,
        )
        value = -parsed
        return hir.Integer(
            prefix.loc,
            ty.IntegerLiteralType(value),
            t0.base10,
            value,
        )

    item = typecheck_and_resolve_inner(prefix.item, ctx=ctx)
    result = _dispatch_builtin(
        builtins.UNARY_PREFIX_DUNDER_MAP[prefix.op.symbol],
        [item],
        loc=prefix.loc,
        op_loc=prefix.op.loc,
        source_name=prefix.op.symbol,
        ctx=ctx,
        expected=expected,
    )
    if isinstance(item, hir.Integer) and isinstance(result, hir.FunctionCall):
        if prefix.op.symbol == '-':
            return replace(result, type=ty.IntegerLiteralType(-item.value))
        if prefix.op.symbol in ('not', '~'):
            return replace(result, type=ty.IntegerLiteralType(~item.value))
    return result


def _constant_integer(
    node: hir.AST,
    *,
    ctx: Context,
    seen_bindings: set[int] | None = None,
) -> int | None:
    """Evaluate the small pure integer subset accepted for Stage 4a indices."""

    if isinstance(node.type, ty.IntegerLiteralType):
        return node.type.value
    if isinstance(node, hir.Integer):
        return node.value
    if isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Transmute)):
        return _constant_integer(node.expr, ctx=ctx, seen_bindings=seen_bindings)
    if isinstance(node, hir.ArrayLength) and isinstance(node.array.type, ty.ArrayType):
        return node.array.type.length
    if isinstance(node, hir.StringLength):
        return _known_string_length(node.string.type)
    if isinstance(node, hir.ExpressedIdentifier) and node.binding_id is not None:
        seen = set() if seen_bindings is None else seen_bindings
        if node.binding_id in seen:
            return None
        binding = ctx.binding_registry.by_id.get(node.binding_id)
        if (
            binding is None
            or binding.declaration is None
            or binding.declaration.decltype != 'const'
        ):
            return None
        seen.add(node.binding_id)
        return _constant_integer(
            binding.declaration.expr,
            ctx=ctx,
            seen_bindings=seen,
        )
    if not isinstance(node, hir.FunctionCall):
        return None
    if not isinstance(node.func, hir.ExpressedIdentifier):
        return None
    values = [
        _constant_integer(arg, ctx=ctx, seen_bindings=seen_bindings)
        for arg in node.pos_args
    ]
    if any(value is None for value in values):
        return None
    integers = cast(list[int], values)
    name = node.func.name
    if len(integers) == 1:
        if name == '__unary_sub__':
            return -integers[0]
        if name == '__not__':
            return ~integers[0]
        return None
    if len(integers) != 2:
        return None
    left, right = integers
    if name == '__add__':
        return left + right
    if name == '__sub__':
        return left - right
    if name == '__mul__':
        return left * right
    if name == '__floordiv__' and right != 0:
        return left // right
    if name == '__mod__' and right != 0:
        return left % right
    if name == '__lshift__' and right >= 0:
        return left << right
    if name == '__rshift__' and right >= 0:
        return left >> right
    return None


def _tcr_array_length(binop: p0.BinOp, *, ctx: Context) -> hir.ArrayLength:
    if not (
        isinstance(binop.right, p0.Atom)
        and isinstance(binop.right.item, t1.Identifier)
        and binop.right.item.name == 'length'
    ):
        not_implemented(ctx.srcfile, binop.loc, 'member access other than array `.length`')
    array = typecheck_and_resolve_inner(binop.left, ctx=ctx)
    if isinstance(array.type, ty.BinaryLiteralType):
        array = hir.RepresentationCast(
            array.loc,
            ty.ArrayType('uint8', len(array.type.value)),
            array,
        )
    if not isinstance(array.type, ty.ArrayType):
        type_error(
            ctx.srcfile,
            '`.length` requires an array',
            Pointer(
                span=array.loc,
                message=f'this has type `{type_to_dewy(array.type)}`',
            ),
        )
    result_type: ty.Type = (
        ty.IntegerLiteralType(array.type.length)
        if array.type.length is not None
        else 'int64'
    )
    return hir.ArrayLength(binop.loc, result_type, array)


def _known_string_length(type_: ty.Type) -> int | None:
    if isinstance(type_, ty.StringLiteralType):
        return ty.string_literal_lengths(type_.value)[2]
    if isinstance(type_, ty.StringType):
        return type_.length
    if isinstance(type_, str) and type_ in {'char', 'grapheme'}:
        return 1
    return None


def _tcr_index(binop: p0.BinOp, *, ctx: Context) -> hir.AST:
    array = typecheck_and_resolve_inner(binop.left, ctx=ctx)
    source_place = array if isinstance(array, hir.Place) else None
    if source_place is not None:
        array = source_place.target
    if isinstance(array.type, ty.BinaryLiteralType):
        array = hir.RepresentationCast(
            array.loc,
            ty.ArrayType('uint8', len(array.type.value)),
            array,
        )
    if not isinstance(array.type, ty.ArrayType) and not _is_string_type(array.type):
        type_error(
            ctx.srcfile,
            'index target is not an array or string',
            Pointer(
                span=array.loc,
                message=f'this has type `{type_to_dewy(array.type)}`',
            ),
        )
    if not isinstance(binop.right, p0.Block) or len(binop.right.inner) != 1:
        user_error(
            ctx.srcfile,
            'Stage 4a indexing requires one scalar index',
            Pointer(span=binop.right.loc, message='expected exactly one index expression'),
        )
    length = (
        array.type.length
        if isinstance(array.type, ty.ArrayType)
        else _known_string_length(array.type)
    )
    index_ctx = ctx
    if length is not None:
        index_ctx = replace(
            ctx,
            declarations=ctx.declarations.new_child(
                {'end': ty.IntegerLiteralType(length - 1)}
            ),
            binding_scopes=ctx.binding_scopes.new_child(),
        )
    index_ast: p0.AST = (
        binop.right.inner[0]
        if binop.right.kind == '[]'
        else binop.right
    )
    index = typecheck_and_resolve_inner(index_ast, ctx=index_ctx)
    if isinstance(index, hir.Range):
        if source_place is not None:
            user_error(
                ctx.srcfile,
                'a slice is a value, not a mutable place',
                Pointer(span=index.loc, message='select one indexed element instead'),
            )
        if index.step_pair is not None:
            not_implemented(ctx.srcfile, index.loc, 'stepped sequence slicing')
        slice_length: int | None = None
        if length is None and (index.left is not None or index.right is not None):
            user_error(
                ctx.srcfile,
                'sequence slice is not proven in bounds',
                Pointer(
                    span=index.loc,
                    message='bounded slicing requires a known sequence length',
                ),
            )
        start = 0
        stop = -1
        left: int | None = None
        right: int | None = None
        if length is not None:
            left = 0 if index.left is None else _constant_integer(index.left, ctx=index_ctx)
            right = (
                length - 1
                if index.right is None
                else _constant_integer(index.right, ctx=index_ctx)
            )
            if left is not None and right is not None:
                bounds_kind = index.bounds or '[]'
                start = left + (1 if bounds_kind[0] == '(' else 0)
                stop = right - (1 if bounds_kind[1] == ')' else 0)
                if start < 0 or start > length or stop < -1 or stop >= length:
                    user_error(
                        ctx.srcfile,
                        'sequence slice is out of bounds',
                        Pointer(
                            span=index.loc,
                            message=f'this slice is outside `0..{length - 1}`',
                        ),
                    )
                slice_length = max(0, stop - start + 1)
        if _is_string_type(array.type):
            return hir.StringSlice(
                binop.loc,
                ty.StringType(slice_length),
                array,
                index,
            )
        assert isinstance(array.type, ty.ArrayType)
        if length is None or left is None or right is None:
            user_error(
                ctx.srcfile,
                'sequence slice is not proven in bounds',
                Pointer(
                    span=index.loc,
                    message=(
                        'dynamic array slices require a runtime-sized array '
                        'result, which is not implemented yet'
                    ),
                ),
            )
        if not isinstance(array, hir.ExpressedIdentifier):
            not_implemented(
                ctx.srcfile,
                array.loc,
                'slicing an array expression with runtime evaluation',
            )
        items = [
            hir.Index(
                index.loc,
                array.type.element,
                array,
                hir.Integer(
                    index.loc,
                    ty.IntegerLiteralType(position),
                    t0.base10,
                    position,
                ),
                position,
            )
            for position in range(start, stop + 1)
        ]
        return hir.ArrayLiteral(
            binop.loc,
            ty.ArrayType(array.type.element, len(items)),
            items,
        )
    if not (
        isinstance(index.type, ty.IntegerLiteralType)
        or (
            isinstance(index.type, str)
            and ctx.type_system.is_subtype(index.type, 'int')
        )
    ):
        user_error(
            ctx.srcfile,
            'array index must be an integer',
            Pointer(
                span=index.loc,
                message=f'this has type `{type_to_dewy(index.type)}`',
            ),
        )
    constant_index = _constant_integer(index, ctx=index_ctx)
    if length is None:
        user_error(
            ctx.srcfile,
            'sequence index is not proven in bounds',
            Pointer(
                span=array.loc,
                message='this sequence does not have an exact compile-time length',
            ),
        )
    if (
        constant_index is not None
        and not 0 <= constant_index < length
    ):
        user_error(
            ctx.srcfile,
            'array index is out of bounds',
            Pointer(
                span=index.loc,
                message=(
                    f'index {constant_index} is outside '
                    f'`0..{length - 1}`'
                ),
            ),
        )
    if _is_string_type(array.type):
        if source_place is not None:
            user_error(
                ctx.srcfile,
                'cannot take an indexed place in an immutable string',
                Pointer(span=binop.loc, message='string elements cannot be replaced'),
            )
        return hir.StringIndex(
            binop.loc,
            ty.StringType(1),
            array,
            index,
            constant_index,
        )
    assert isinstance(array.type, ty.ArrayType)
    result = hir.Index(
        binop.loc,
        array.type.element,
        array,
        index,
        constant_index,
    )
    if source_place is None:
        return result
    return hir.Place(binop.loc, result.type, result)


def tcr_binop(binop: p0.BinOp, *, ctx: Context, type_block:bool=False, expected: ty.Type|None=None, call_target: bool=False) -> hir.AST:
    """
    typecheck and resolve a binary operator node.
    
    NOTE:
    type_block is used to disambiguate the context these binops occur in. 
    mainly for distinguishing type expressions using literals from regular operations between said literals
    e.g. `true | false` -> `true` vs `<true | false>` -> `literal<true>|literal<false>`
    most other operators are unaffected by this flag.
    """

    # quantum juxtapose: which operator this is depends on the operand types,
    # so try each reading as a candidate like an Ambiguous node
    if isinstance(binop.op, t2.QJuxtapose):
        candidates: list[p0.AST] = [replace(binop, op=option) for option in binop.op.options]
        return typecheck_and_resolve_inner(p0.Ambiguous(binop.loc, candidates), ctx=ctx, type_block=type_block, expected=expected)

    if isinstance(binop.op, t2.CallJuxtapose):
        left = typecheck_and_resolve_inner(binop.left, ctx=ctx, type_block=type_block, call_target=True)
        return tcr_function_call(left, binop.right, ctx=ctx, expected=expected)

    if isinstance(binop.op, t2.CombinedAssignmentOp):
        return tcr_combined_assign(binop, ctx=ctx)

    if isinstance(binop.op, t2.SemicolonJuxtapose):
        item = typecheck_and_resolve_inner(
            binop.left,
            ctx=ctx,
            type_block=type_block,
        )
        result_type = (
            ty.BOTTOM_TYPE
            if item.type == ty.BOTTOM_TYPE
            else ty.VOID_TYPE
        )
        return hir.Suppress(binop.loc, result_type, item)

    # Special cases that don't just typecheck both sides
    symbol = binop.op.symbol if isinstance(binop.op, t1.Operator) else None
    if isinstance(binop.op, t2.IndexJuxtapose):
        return _tcr_index(binop, ctx=ctx)
    if symbol == '.':
        access = _tcr_member_access(binop, ctx=ctx)
        return access if call_target else _maybe_auto_call_member(access, ctx=ctx)
    if symbol == '=>': return tcr_function_literal(binop, ctx=ctx, expected=expected)

    if symbol == '|>':
        callable_value = typecheck_and_resolve_inner(binop.right, ctx=ctx, call_target=True)
        return tcr_function_call(callable_value, binop.left, ctx=ctx, expected=expected)

    if symbol == 'transmute':
        item = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        require_valued(item.type, ctx.srcfile, item.loc, 'transmute operand')
        target = ast_to_type(binop.right, ctx=ctx)
        if not _transmute_compatible(item.type, target):
            type_error(
                ctx.srcfile,
                'incompatible transmute representations',
                Pointer(
                    span=binop.loc,
                    message=(
                        f'`{type_to_dewy(item.type)}` and '
                        f'`{type_to_dewy(target)}` do not share a runtime layout'
                    ),
                ),
            )
        return hir.Transmute(binop.loc, target, item)

    if symbol == 'as':
        item = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        require_valued(item.type, ctx.srcfile, item.loc, 'conversion operand')
        target = ast_to_type(binop.right, ctx=ctx)
        return _explicit_value_conversion(item, target, binop.loc, ctx=ctx)

    if symbol in {'is?', 'isnt?'}:
        value = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        require_valued(value.type, ctx.srcfile, value.loc, 'type-test operand')
        test_type = ast_to_type(binop.right, ctx=ctx)
        return hir.TypeTest(
            binop.loc,
            'bool',
            value,
            test_type,
            symbol == 'isnt?',
        )

    if symbol in ('=','::',':='):
        return tcr_assign(binop, ctx=ctx, expected=expected)

    if isinstance(binop.op, t2.InvertedComparisonOp):
        if binop.op.op in {'is?', 'isnt?'}:
            value = typecheck_and_resolve_inner(binop.left, ctx=ctx)
            require_valued(value.type, ctx.srcfile, value.loc, 'type-test operand')
            test_type = ast_to_type(binop.right, ctx=ctx)
            return hir.TypeTest(
                binop.loc,
                'bool',
                value,
                test_type,
                binop.op.op == 'is?',
            )
        fname = builtins.INVERTED_COMPARISON_DUNDER_MAP.get(binop.op.op)
        if fname is None:
            not_implemented(ctx.srcfile, binop.op.loc, f'inverted comparison `not{binop.op.op}`')
        left = typecheck_and_resolve_inner(binop.left, ctx=ctx, type_block=type_block)
        right = typecheck_and_resolve_inner(binop.right, ctx=ctx, type_block=type_block)
        return _dispatch_builtin(
            fname,
            [left, right],
            loc=binop.loc,
            op_loc=binop.op.loc,
            source_name=f'not{binop.op.op}',
            ctx=ctx,
            expected=expected,
        )

    # TODO: other more specialized structures (e.g. assignment, spread, collect, parameterization, etc.)


    # regular cases where left and right are both normal expressions
    # TODO: how to handle the fact that `and` and `or` might have inner elements that need type_block? for now just pass in to left and right
    # full expression
    left = typecheck_and_resolve_inner(binop.left, ctx=ctx, type_block=type_block)
    right_ctx = ctx
    if left.type == 'bool':
        if symbol in {'and', '&', 'nand'}:
            right_ctx = _refine_condition_context(ctx, left, truth=True)
        elif symbol in {'or', '|', 'nor'}:
            right_ctx = _refine_condition_context(ctx, left, truth=False)
    right = typecheck_and_resolve_inner(
        binop.right,
        ctx=right_ctx,
        type_block=type_block,
    )

    if symbol == 'in?' and isinstance(right, hir.Range):
        return _tcr_range_membership(left, right, ctx=ctx)
    
    match binop.op:
        case t2.QJuxtapose():
            not_implemented(ctx.srcfile, binop.loc, 'quantum juxtapose')
        case t2.IndexJuxtapose():
            not_implemented(ctx.srcfile, binop.loc, 'index juxtapose')
        case t2.MultiplyJuxtapose():
            return _dispatch_builtin(
                '__mul__',
                [left, right],
                loc=binop.loc,
                op_loc=binop.op.loc,
                source_name='*',
                ctx=ctx,
                expected=expected,
            )
        case t2.RangeJuxtapose(): not_implemented(ctx.srcfile, binop.loc, 'range juxtapose')
        case t2.EllipsisJuxtapose(): not_implemented(ctx.srcfile, binop.loc, 'ellipsis juxtapose')
        case t2.TypeParamJuxtapose(): not_implemented(ctx.srcfile, binop.loc, 'type parameterization')
        case t2.BroadcastOp(): not_implemented(ctx.srcfile, binop.loc, 'broadcast operator')
    
    # TODO: eventually should be able to remove this check once all the arms of the above match are implemented
    assert isinstance(binop.op, t1.Operator), f'INTERNAL ERROR: unexpected operator type: {binop.op}'


    # general case, delegate to the builtin __dunder__ method
    if binop.op.symbol in builtins.BINOP_DUNDER_MAP:
        result = _dispatch_builtin(
            builtins.BINOP_DUNDER_MAP[binop.op.symbol],
            [left, right],
            loc=Span(left.loc.start, right.loc.stop),
            op_loc=binop.op.loc,
            source_name=binop.op.symbol,
            ctx=ctx,
            expected=expected,
        )
        short_circuit_ops: dict[str, Literal['and', 'or', 'nand', 'nor']] = {
            'and': 'and',
            '&': 'and',
            'or': 'or',
            '|': 'or',
            'nand': 'nand',
            'nor': 'nor',
        }
        if (
            binop.op.symbol in short_circuit_ops
            and isinstance(result, hir.FunctionCall)
            and result.type == 'bool'
            and isinstance(result.func, hir.ExpressedIdentifier)
            and isinstance(result.func.type, ty.FunctionType)
            and len(result.func.type.pos_or_kw) == 2
            and all(param.type == 'bool' for param in result.func.type.pos_or_kw)
        ):
            return hir.ShortCircuit(
                result.loc,
                result.type,
                short_circuit_ops[binop.op.symbol],
                left,
                right,
            )
        return result
    

    not_implemented(ctx.srcfile, binop.op.loc, f'operator `{binop.op.symbol}`')

    # # TODO: BINOP_DUNDER_MAP is mostly commented out
    # #       as soon as `&` is uncommented, the handling here will never be reached..
    # match binop.op.symbol:
    #     # case '+': return tcr_add(left, right)
    #     case 'and' | '&':
    #         # `and` and `&` are the same operator; meaning is selected by operand types
    #         # (bitwise, logical, type intersect in type position, overload combine for callables, …).
    #         # Full resolution should go through the dispatch system; handle callables here for now.
    #         if isinstance(left.type, (ty.FunctionType, ty.OverloadType)) and isinstance(right.type, (ty.FunctionType, ty.OverloadType)):
    #             left_methods = left.type.methods if isinstance(left.type, ty.OverloadType) else [left.type]
    #             right_methods = right.type.methods if isinstance(right.type, ty.OverloadType) else [right.type]
    #             combined = ty.OverloadType(left_methods + right_methods)
    #             return hir.OverloadedFunction(
    #                 Span(left.loc.start, right.loc.stop),
    #                 combined,
    #                 _function_alternates(left) + _function_alternates(right),
    #             )
    #         # TODO: dispatch __and__ for int/bool/etc. (same path as other binops)
    #         pdb.set_trace()
    #         raise NotImplementedError(f'tcr_binop and/& not yet implemented for operand types: {left.type=}, {right.type=}')
    #     # case '-': return tcr_sub(left, right)
    #     # case '*': return tcr_mul(left, right)
    #     # case '/': return tcr_div(left, right)
    #     # case '%': return tcr_mod(left, right)
    #     # case '//': return tcr_floordiv(left, right)
    #     # case '^': return tcr_pow(left, right)
    #     # case '<<': return tcr_lshift(left, right)
    #     # case '>>': return tcr_rshift(left, right)
        
        
        
    #     case _:
    #         raise NotImplementedError(f'tcr_binop not implemented for {type(binop.op)}')




def tcr_assignment_target(
    target: p0.AST,
    *,
    ctx: Context,
    refined: bool = False,
) -> hir.ExpressedIdentifier | hir.Index | hir.MemberAccess:
    """Resolve an identifier, array-element, or object-field assignment target."""

    if isinstance(target, p0.Atom) and isinstance(target.item, t1.Identifier):
        resolved = tcr_identifier(target.item, ctx=ctx, refined=refined)
        assert isinstance(resolved, hir.ExpressedIdentifier)
        return resolved

    if isinstance(target, p0.BinOp):
        if isinstance(target.op, t1.Operator) and target.op.symbol == '.':
            access = _tcr_member_access(target, ctx=ctx)
            if not isinstance(access, hir.MemberAccess):
                not_implemented(ctx.srcfile, target.loc, 'assignment to `.length`')
            if not access.mutable:
                user_error(
                    ctx.srcfile,
                    f'cannot mutate const object field `{access.name}`',
                    Pointer(span=target.loc, message='this field is const'),
                )
            binding = _member_root_binding(access, ctx=ctx)
            if (
                binding is not None
                and binding.declaration is not None
                and binding.declaration.decltype == 'const'
            ):
                user_error(
                    ctx.srcfile,
                    'cannot mutate a field of a const object',
                    Pointer(
                        span=access.value.loc,
                        message=f'`{binding.name}` is declared const',
                    ),
                    Pointer(
                        span=binding.declaration.loc,
                        message='const declaration is here',
                    ),
                )
            return access
        if isinstance(target.op, t2.QJuxtapose):
            index_op = next(
                (
                    option
                    for option in target.op.options
                    if isinstance(option, t2.IndexJuxtapose)
                ),
                None,
            )
            if index_op is not None:
                target = replace(target, op=index_op)
        if isinstance(target.op, t2.IndexJuxtapose):
            resolved = _tcr_index(target, ctx=ctx)
            if isinstance(resolved, (hir.StringIndex, hir.StringSlice)):
                user_error(
                    ctx.srcfile,
                    'cannot mutate an immutable string',
                    Pointer(
                        span=target.loc,
                        message='convert to a mutable array representation first',
                    ),
                )
            assert isinstance(resolved, hir.Index)
            root = resolved.array
            while True:
                if isinstance(root, hir.Index):
                    root = root.array
                    continue
                if (
                    isinstance(root, hir.Block)
                    and not root.scoped
                    and len(root.items) == 1
                ):
                    root = root.items[0]
                    continue
                if isinstance(root, (hir.ValueCast, hir.RepresentationCast, hir.Transmute)):
                    root = root.expr
                    continue
                break
            if isinstance(root, hir.ExpressedIdentifier) and root.binding_id is not None:
                binding = ctx.binding_registry.by_id[root.binding_id]
                if (
                    binding.declaration is not None
                    and binding.declaration.decltype == 'const'
                ):
                    user_error(
                        ctx.srcfile,
                        'cannot mutate an element of a const array',
                        Pointer(
                            span=root.loc,
                            message=f'`{root.name}` is declared const',
                        ),
                        Pointer(
                            span=binding.declaration.loc,
                            message='const declaration is here',
                        ),
                    )
            return resolved

    not_implemented(ctx.srcfile, target.loc, 'this assignment target')

def tcr_bare_range(ast: p0.Flat, *, ctx: Context, expected: ty.Type|None=None) -> hir.Range:
    """
    typecheck and resolve a bare range expression, e.g. `1..2`
    """
    # collect the left and right items
    match ast.items:
        case [left, p0.Atom(item=t1.Identifier(name='..')), right]: ...
        case [p0.Atom(item=t1.Identifier(name='..')), right]:
            left = None #hir.Void(Span(ast.loc.start, ast.loc.start), type=ty.VOID_TYPE)
        case [left, p0.Atom(item=t1.Identifier(name='..'))]:
            right = None #hir.Void(Span(ast.loc.stop, ast.loc.stop), type=ty.VOID_TYPE)
        case _:
            raise ValueError(f'INTERNAL ERROR: unrecognized bare range structure: {ast=}')
    
    def comma_pair(item: p0.AST | None) -> tuple[p0.AST, p0.AST] | None:
        if not (
            isinstance(item, p0.Flat)
            and isinstance(item.op, t1.Operator)
            and item.op.symbol == ','
        ):
            return None
        if len(item.items) != 2:
            user_error(
                ctx.srcfile,
                'range step syntax requires exactly two anchors',
                Pointer(
                    span=item.loc,
                    message='expected `first,second..last`',
                ),
            )
        return item.items[0], item.items[1]

    left_pair = comma_pair(left)
    right_pair = comma_pair(right)
    if left_pair is not None and right_pair is not None:
        user_error(
            ctx.srcfile,
            'range cannot specify step anchors on both sides',
            Pointer(span=ast.loc, message='choose one step-pair form'),
        )
    if right_pair is not None and left is not None:
        user_error(
            ctx.srcfile,
            'trailing range step pairs require an unbounded left side',
            Pointer(
                span=right.loc,
                message='`first..second_last,last` is not a valid range',
            ),
            hint='write `first,second..last` instead',
        )

    step_pair: tuple[hir.AST, hir.AST] | None = None
    if left_pair is not None:
        first = typecheck_and_resolve_inner(left_pair[0], ctx=ctx)
        second = typecheck_and_resolve_inner(left_pair[1], ctx=ctx)
        checked_left: hir.AST | None = first
        checked_right = (
            typecheck_and_resolve_inner(right, ctx=ctx)
            if right is not None
            else None
        )
        step_pair = (first, second)
    elif right_pair is not None:
        second_last = typecheck_and_resolve_inner(right_pair[0], ctx=ctx)
        last = typecheck_and_resolve_inner(right_pair[1], ctx=ctx)
        checked_left = None
        checked_right = last
        step_pair = (second_last, last)
    else:
        checked_left = (
            typecheck_and_resolve_inner(left, ctx=ctx)
            if left is not None
            else None
        )
        checked_right = (
            typecheck_and_resolve_inner(right, ctx=ctx)
            if right is not None
            else None
        )

    anchors = [
        *([] if step_pair is None else step_pair),
        *([] if checked_left is None else [checked_left]),
        *([] if checked_right is None else [checked_right]),
    ]
    scalar_range_context = (
        isinstance(expected, ty.TypeParameterize)
        and expected.t == 'range'
        and expected.args == ['uint32']
    )
    if scalar_range_context:
        converted: dict[int, hir.AST] = {}
        for anchor in anchors:
            value = anchor
            while isinstance(value, hir.RepresentationCast):
                value = value.expr
            if isinstance(value, hir.String) and len(value.content) == 1:
                converted[id(anchor)] = hir.Integer(
                    anchor.loc,
                    'uint32',
                    t0.base10,
                    ord(value.content),
                )
            else:
                converted[id(anchor)] = check_against(anchor, 'uint32', ctx=ctx)
        checked_left = (
            converted.get(id(checked_left), checked_left)
            if checked_left is not None
            else None
        )
        checked_right = (
            converted.get(id(checked_right), checked_right)
            if checked_right is not None
            else None
        )
        step_pair = (
            (
                converted.get(id(step_pair[0]), step_pair[0]),
                converted.get(id(step_pair[1]), step_pair[1]),
            )
            if step_pair is not None
            else None
        )
        anchors = [
            *([] if step_pair is None else step_pair),
            *([] if checked_left is None else [checked_left]),
            *([] if checked_right is None else [checked_right]),
        ]
    string_anchors = [anchor for anchor in anchors if _is_string_type(anchor.type)]
    range_type: ty.TypeExpr = expected if scalar_range_context else 'range'
    if string_anchors:
        if len(string_anchors) != len(anchors):
            type_error(
                ctx.srcfile,
                'range anchors must use one ordinal domain',
                *[
                    Pointer(
                        span=anchor.loc,
                        message=f'this anchor has type `{type_to_dewy(anchor.type)}`',
                    )
                    for anchor in anchors
                ],
            )
        grapheme_domain = all(
            _known_string_length(anchor.type) == 1
            for anchor in string_anchors
        )
        target = ty.StringType(1) if grapheme_domain else ty.StringType()
        transformed = {
            id(anchor): check_against(anchor, target, ctx=ctx)
            for anchor in string_anchors
        }
        checked_left = (
            transformed.get(id(checked_left), checked_left)
            if checked_left is not None
            else None
        )
        checked_right = (
            transformed.get(id(checked_right), checked_right)
            if checked_right is not None
            else None
        )
        step_pair = (
            (
                transformed.get(id(step_pair[0]), step_pair[0]),
                transformed.get(id(step_pair[1]), step_pair[1]),
            )
            if step_pair is not None
            else None
        )
        range_type = ty.TypeParameterize('range', [target])
    return hir.Range(
        ast.loc,
        range_type,
        bounds=None,
        step_pair=step_pair,
        left=checked_left,
        right=checked_right,
    )



def typefunc_from_hir_params(
    pos_or_kw_args: list[hir.Param | hir.BoundParam],
    kw_only_args: list[hir.Param | hir.BoundParam],
    rest_args: hir.Param | hir.BoundParam | None,
    rettype: ty.Type,
) -> ty.FunctionType:
    pos = [
        ty.PosOrKwArg(
            None if p.position_only else p.name,
            p.type if p.type != ty.INFERRED_TYPE else ty.TOP_TYPE,
            required=not isinstance(p, hir.BoundParam),
            place=p.place,
        )
        for p in pos_or_kw_args
    ]
    kw: list[ty.KwOnlyArg] = []
    for p in kw_only_args:
        ptype = p.type if p.type != ty.INFERRED_TYPE else ty.TOP_TYPE
        required = not isinstance(p, hir.BoundParam)
        kw.append(ty.KwOnlyArg(p.name, ptype, required, p.place))
    rest_name = rest_args.name if rest_args is not None else None
    ret = rettype if rettype != ty.INFERRED_TYPE else ty.TOP_TYPE
    return ty.FunctionType(pos, kw, rest_name, ret)


def signature_of(fn_ast: p0.BinOp, *, ctx: Context) -> ty.FunctionType | None:
    """FunctionType for a function literal whose params and return type are fully annotated, else None.

    Used by the pre-binding pass; unannotated (inference-requiring) functions stay order-dependent.
    """
    signature = fn_ast.left
    if not (isinstance(signature, p0.BinOp) and isinstance(signature.op, t1.Operator) and signature.op.symbol == ':>'):
        return None
    rettype = ast_to_type(signature.right, ctx=ctx)
    pos_or_kw_args, kw_only_args, rest_args = collect_function_signature_args(signature.left, ctx=ctx)
    params = [*pos_or_kw_args, *kw_only_args, *([rest_args] if rest_args is not None else [])]
    if any(p.type == ty.INFERRED_TYPE for p in params):
        return None
    return typefunc_from_hir_params(pos_or_kw_args, kw_only_args, rest_args, rettype)


def _discarded_expressed_sites(body: hir.AST) -> list[hir.AST]:
    """expressed-value (non-void, non-never) items in a checked body, walking only Block.items.

    Descending exclusively through Block is what keeps `x = { 1 2 3 }` out of the results,
    since that block is reached via Declare.expr rather than Block.items.
    (When if/Flow lands in HIR, this walk gains a branch for flow arms.)
    """
    sites: list[hir.AST] = []
    def walk(node: hir.AST) -> None:
        if isinstance(node, hir.Block):
            for item in node.items:
                walk(item)
        elif isinstance(node, hir.Flow):
            for arm in node.arms:
                walk(arm.body)
            if node.default is not None:
                walk(node.default)
        elif node.type != ty.VOID_TYPE and node.type != ty.BOTTOM_TYPE:
            sites.append(node)
    if isinstance(body, hir.Block):
        walk(body)
    return sites


def tcr_function_literal(binop: p0.BinOp, *, ctx: Context, expected: ty.Type|None=None) -> hir.FunctionLiteral:
    """
    function literal: `args => body`
    """
    #analyze the signature
    signature = binop.left
    rettype: ty.Type = ty.INFERRED_TYPE
    rettype_loc: Span | None = None
    
    # if the return type was annotated, capture it
    if isinstance(signature, p0.BinOp) and signature.op.symbol == ':>':
        rettype = ast_to_type(signature.right, ctx=ctx)
        rettype_loc = signature.right.loc
        signature = signature.left
    
    # collect function signature parameters
    pos_or_kw_args, kw_only_args, rest_args = collect_function_signature_args(signature, ctx=ctx)

    # insert the arguments from the signature into the body, and install a fresh catcher
    # for this function's returns
    inner_scope = ctx.declarations.new_child()
    inner_bindings = ctx.binding_scopes.new_child()

    def bind_param(param: hir.Param | hir.BoundParam) -> hir.Param | hir.BoundParam:
        binding = ctx.binding_registry.allocate_param(param.name, param.type, binop.loc)
        inner_bindings[param.name] = binding
        return replace(param, binding_id=binding.id)

    pos_or_kw_args = [bind_param(param) for param in pos_or_kw_args]
    kw_only_args = [bind_param(param) for param in kw_only_args]
    rest_args = bind_param(rest_args) if rest_args is not None else None
    for param in pos_or_kw_args:
        inner_scope[param.name] = param.type
    for param in kw_only_args:
        inner_scope[param.name] = param.type
    if rest_args is not None:
        inner_scope[rest_args.name] = rest_args.type
    annotated = rettype if rettype != ty.INFERRED_TYPE else None
    catcher = Catcher(expected=annotated)
    function_boundary_labels = dict(ctx.function_boundary_labels)
    for label_scope in ctx.label_scopes:
        function_boundary_labels.update(label_scope.labels)
    inner_ctx = replace(
        ctx,
        declarations=inner_scope,
        binding_scopes=inner_bindings,
        catcher=catcher,
        label_scopes=(LabelScope({}),),
        loop_boundaries=(),
        function_boundary_labels=function_boundary_labels,
        refinements={},
    )
    body = typecheck_and_resolve_inner(binop.right, ctx=inner_ctx, expected=annotated)

    # resolve the return type from the caught returns and the fall-through value
    if not catcher.returns:
        # no returns: the body's expressed value is the return value.
        # check_against covers non-literal promotion (e.g. `():>float => { a }` with a:int)
        # after the expected type has already been pushed into the body for literal adoption.
        # Prefer casting inside a single-item `()`/`{}` wrapper so the delimiters stay transparent.
        if annotated is not None:
            if isinstance(body, hir.Block) and len(body.items) == 1:
                item = check_against(body.items[0], annotated, ctx=ctx)
                body = replace(body, items=[item], type=item.type)
            else:
                body = check_against(body, annotated, ctx=ctx)
        resolved_ret: ty.Type = body.type
    else:
        fall_through = body.type  # `never` iff control can't reach the end of the body
        valued = [(span, t) for span, t in catcher.returns if t != ty.VOID_TYPE]
        bare = [(span, t) for span, t in catcher.returns if t == ty.VOID_TYPE]
        if valued and bare:
            user_error(ctx.srcfile, 'not all paths return a value',
                Pointer(span=valued[0][0], message=f'returns `{type_to_dewy(valued[0][1])}` here'),
                Pointer(span=bare[0][0], message='bare `return` returns no value'),
                hint='either give every `return` a value, or none of them')
        if bare:
            # all returns valueless: void directly — must short-circuit before union(), since
            # void is deliberately not a TypeExpr. Fall-through is fine (implicit `return void`)
            resolved_ret = ty.VOID_TYPE
        else:
            resolved_ret = ty.union(*(t for _, t in valued))
            if fall_through != ty.BOTTOM_TYPE:
                pointers = [Pointer(span=span, message=f'returns `{type_to_dewy(t)}` here') for span, t in valued]
                pointers.append(Pointer(span=Span(body.loc.stop - 1, body.loc.stop), message='control reaches the end of the body without returning'))
                user_error(ctx.srcfile, 'not all paths return a value', *pointers,
                    hint='add a `return` at the end of the body, or drop the explicit returns and let the body express its value')
        # a body that returns treats bare expressed values as statements, which silently drops them
        discarded = _discarded_expressed_sites(body)
        if discarded:
            pointers = [Pointer(span=site.loc, message=f'this expresses `{type_to_dewy(site.type)}`, but the value is dropped') for site in discarded]
            pointers.append(Pointer(span=catcher.returns[0][0], message='this block returns, so bare expressions are statements'))
            user_error(ctx.srcfile, 'expressed value is discarded', *pointers,
                hint='use `return` to return it, `yield` to make a generator, or `;` to suppress the value')

    # check against the `:>` annotation if there was one, otherwise adopt the resolved type
    if rettype == ty.INFERRED_TYPE:
        rettype = resolved_ret
    else:
        if rettype == ty.VOID_TYPE or resolved_ret == ty.VOID_TYPE:
            ok = rettype == resolved_ret
        else:
            ok = ctx.type_system.is_subtype(resolved_ret, rettype)
        if not ok:
            user_error(ctx.srcfile, 'function body does not match declared return type',
                Pointer(span=rettype_loc, message=f'declared to return `{type_to_dewy(rettype)}`'),
                Pointer(span=body.loc, message=f'but the body produces `{type_to_dewy(resolved_ret) if resolved_ret != ty.VOID_TYPE else "void"}`'))

    ftype = typefunc_from_hir_params(pos_or_kw_args, kw_only_args, rest_args, rettype)

    return hir.FunctionLiteral(binop.loc, ftype, pos_or_kw_args, kw_only_args, rest_args, rettype, body)

def _function_type_args(ast: p0.AST, *, ctx: Context) -> list[ty.PosOrKwArg]:
    """Parse named parameter contracts to the left of a function type's `:>`."""
    items = ast.inner if isinstance(ast, p0.Block) and ast.kind == '()' else [ast]
    args: list[ty.PosOrKwArg] = []
    for item in items:
        if (
            isinstance(item, p0.BinOp)
            and isinstance(item.op, t1.Operator)
            and item.op.symbol == ':'
            and isinstance(item.left, p0.Atom)
            and isinstance(item.left.item, t1.Identifier)
        ):
            args.append(ty.PosOrKwArg(item.left.item.name, ast_to_type(item.right, ctx=ctx)))
        elif isinstance(item, p0.Atom) and isinstance(item.item, t1.Identifier):
            # Types and parameter names share the identifier syntax. A bare
            # identifier is therefore a parameter name with an unconstrained
            # type, matching the same spelling in a function literal.
            args.append(ty.PosOrKwArg(item.item.name, ty.TOP_TYPE))
        else:
            user_error(
                ctx.srcfile,
                'function type parameter requires a name',
                Pointer(span=item.loc, message='write this parameter as `name:type`'),
                hint='anonymous and positional-only source parameters do not yet have a syntax',
            )
    return args


def _object_type_member(item: p0.AST, *, ctx: Context) -> ty.ObjectField:
    """Parse one `name:type` row of an object type, including `fn:(T):>U` desugaring."""

    mutable = True
    if (
        isinstance(item, p0.KeywordExpr)
        and len(item.parts) == 2
        and isinstance(item.parts[0], t1.Keyword)
        and item.parts[0].name in {'let', 'const'}
        and isinstance(item.parts[1], p0.AST)
    ):
        mutable = item.parts[0].name != 'const'
        item = item.parts[1]
    if (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol == ':>'
        and isinstance(item.left, p0.BinOp)
        and isinstance(item.left.op, t1.Operator)
        and item.left.op.symbol == ':'
        and isinstance(item.left.left, p0.Atom)
        and isinstance(item.left.left.item, t1.Identifier)
    ):
        return ty.ObjectField(
            item.left.left.item.name,
            ty.FunctionType(
                _function_type_args(item.left.right, ctx=ctx),
                [],
                None,
                ast_to_type(item.right, ctx=ctx),
            ),
            mutable,
        )
    if (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol == ':'
        and isinstance(item.left, p0.Atom)
        and isinstance(item.left.item, t1.Identifier)
    ):
        return ty.ObjectField(
            item.left.item.name,
            ast_to_type(item.right, ctx=ctx),
            mutable,
        )
    user_error(
        ctx.srcfile,
        'object type fields must be `name:type`',
        Pointer(span=item.loc, message='this is not a named field type'),
    )


def _named_type_alias_value(
    ast: p0.AST,
    *,
    ctx: Context,
) -> ty.TypeAliasValue | None:
    if isinstance(ast, p0.Atom) and isinstance(ast.item, t1.Identifier):
        binding = ctx.binding_scopes.get(ast.item.name)
        if binding is not None:
            if binding.type_value is not None:
                return binding.type_value
            if binding.id in ctx.type_alias_asts:
                return _resolve_type_alias(binding, ctx=ctx)
        return builtins.builtin_type_aliases.get(ast.item.name)
    if (
        isinstance(ast, p0.BinOp)
        and isinstance(ast.op, t1.Operator)
        and ast.op.symbol == '.'
        and isinstance(ast.left, p0.Atom)
        and isinstance(ast.left.item, t1.Identifier)
        and isinstance(ast.right, p0.Atom)
        and isinstance(ast.right.item, t1.Identifier)
        and (module := ctx.module_namespaces.get(ast.left.item.name)) is not None
    ):
        binding = module.exports.get(ast.right.item.name)  # type: ignore[attr-defined]
        return None if binding is None else binding.type_value
    return None


def _instantiate_type_alias(
    alias: ty.GenericTypeAlias,
    arguments: list[ty.TypeExpr],
    *,
    loc: Span,
    ctx: Context,
) -> ty.TypeExpr:
    if len(arguments) != len(alias.params):
        user_error(
            ctx.srcfile,
            'wrong number of generic type arguments',
            Pointer(
                span=loc,
                message=(
                    f'expected {len(alias.params)}, got {len(arguments)}'
                ),
            ),
        )
    bindings: dict[str, ty.TypeExpr] = {}
    for param, argument in zip(alias.params, arguments):
        bound = ty.substitute_type(param.bound, bindings)
        if not ctx.type_system.is_subtype(argument, bound):
            type_error(
                ctx.srcfile,
                'generic type argument does not satisfy its bound',
                Pointer(
                    span=loc,
                    message=(
                        f'`{type_to_dewy(argument)}` is not a subtype of '
                        f'`{type_to_dewy(bound)}` for `{param.name}`'
                    ),
                ),
            )
        bindings[param.name] = argument
    return ty.substitute_type(alias.body, bindings)


def ast_to_type(ast: p0.AST, *, ctx: Context) -> ty.Type:
    """convert an AST from a position that is expected to be a type into a type"""
    if (
        isinstance(ast, p0.BinOp)
        and isinstance(ast.op, t2.TypeParamJuxtapose)
        and isinstance(ast.right, p0.Block)
        and ast.right.kind == '<>'
        and (alias_value := _named_type_alias_value(ast.left, ctx=ctx))
        is not None
    ):
        if not isinstance(alias_value, ty.GenericTypeAlias):
            type_error(
                ctx.srcfile,
                'type alias is not generic',
                Pointer(span=ast.left.loc, message='this alias takes no arguments'),
            )
        arguments = [ast_to_type(item, ctx=ctx) for item in ast.right.inner]
        return _instantiate_type_alias(
            alias_value,
            arguments,
            loc=ast.loc,
            ctx=ctx,
        )

    match ast:
        case p0.BinOp(
            op=t1.Operator(symbol='.'),
            left=p0.Atom(item=t1.Identifier(name=module_name)),
            right=p0.Atom(item=t1.Identifier(name=member_name)),
        ) if (module := ctx.module_namespaces.get(module_name)) is not None:
            binding = module.exports.get(member_name)  # type: ignore[attr-defined]
            if binding is None:
                user_error(
                    ctx.srcfile,
                    f'module has no top-level binding `{member_name}`',
                    Pointer(span=ast.right.loc, message='this type is not exported'),
                )
            if binding.type_value is None:
                type_error(
                    ctx.srcfile,
                    'module member is not a type',
                    Pointer(span=ast.right.loc, message=f'`{member_name}` is a value'),
                )
            if isinstance(binding.type_value, ty.GenericTypeAlias):
                type_error(
                    ctx.srcfile,
                    'generic type alias requires arguments',
                    Pointer(
                        span=ast.loc,
                        message=f'use `{member_name}<...>`',
                    ),
                )
            return binding.type_value

        case p0.Atom(item=t1.Identifier(name=name)):
            binding = ctx.binding_scopes.get(name)
            if binding is not None:
                if binding.type_value is not None:
                    if isinstance(binding.type_value, ty.GenericTypeAlias):
                        type_error(
                            ctx.srcfile,
                            'generic type alias requires arguments',
                            Pointer(span=ast.loc, message=f'use `{name}<...>`'),
                        )
                    return binding.type_value
                if binding.id in ctx.type_alias_asts:
                    resolved = _resolve_type_alias(binding, ctx=ctx)
                    if isinstance(resolved, ty.GenericTypeAlias):
                        type_error(
                            ctx.srcfile,
                            'generic type alias requires arguments',
                            Pointer(span=ast.loc, message=f'use `{name}<...>`'),
                        )
                    return resolved
                return name
            if name in builtins.builtin_type_aliases:
                return builtins.builtin_type_aliases[name]
            return name

        case p0.Atom(item=t1.Integer(value=value)):
            return ty.IntegerLiteralType(
                t0.parse_integer(value.src, value.prefix)
            )

        case p0.Block(kind='[]', inner=items):
            seen: dict[str, Span] = {}
            fields: list[ty.ObjectField] = []
            for item in items:
                field = _object_type_member(item, ctx=ctx)
                previous = seen.get(field.name)
                if previous is not None:
                    user_error(
                        ctx.srcfile,
                        f'duplicate object field `{field.name}`',
                        Pointer(span=item.loc, message='this field repeats a name'),
                        Pointer(span=previous, message='the earlier field is here'),
                    )
                seen[field.name] = item.loc
                fields.append(field)
            return ty.ObjectType(tuple(fields))

        case p0.BinOp(
            op=t2.TypeParamJuxtapose(),
            left=p0.Atom(item=t1.Identifier(name='array')),
            right=p0.Block(kind='<>', inner=items),
        ):
            element_ast: p0.AST | None = None
            length: int | None = None
            for item in items:
                if (
                    isinstance(item, p0.BinOp)
                    and isinstance(item.op, t1.Operator)
                    and item.op.symbol == '='
                    and isinstance(item.left, p0.Atom)
                    and isinstance(item.left.item, t1.Identifier)
                    and item.left.item.name == 'length'
                ):
                    if length is not None:
                        user_error(
                            ctx.srcfile,
                            'duplicate array length parameter',
                            Pointer(span=item.loc, message='`length` was already specified'),
                        )
                    if not (
                        isinstance(item.right, p0.Atom)
                        and isinstance(item.right.item, t1.Integer)
                    ):
                        user_error(
                            ctx.srcfile,
                            'array length must be an integer literal',
                            Pointer(span=item.right.loc, message='expected a non-negative integer'),
                        )
                    length = t0.parse_integer(
                        item.right.item.value.src,
                        item.right.item.value.prefix,
                    )
                    if length < 0:
                        user_error(
                            ctx.srcfile,
                            'array length cannot be negative',
                            Pointer(span=item.right.loc, message=f'got {length}'),
                        )
                    continue
                if element_ast is not None:
                    user_error(
                        ctx.srcfile,
                        'invalid array type parameters',
                        Pointer(
                            span=item.loc,
                            message='expected one element type and optional `length=N`',
                        ),
                    )
                element_ast = item
            if element_ast is None:
                user_error(
                    ctx.srcfile,
                    'array type requires an element type',
                    Pointer(span=ast.loc, message='use `array<T>`'),
                )
            element = ast_to_type(element_ast, ctx=ctx)
            if not _supported_array_element_type(element):
                type_error(
                    ctx.srcfile,
                    'unsupported array element type',
                    Pointer(
                        span=element_ast.loc,
                        message=(
                            'arrays require a fixed-width scalar or handle type, '
                            f'got `{type_to_dewy(element)}`'
                        ),
                    ),
                )
            return ty.ArrayType(element, length)

        case p0.BinOp(
            op=t2.TypeParamJuxtapose(),
            left=p0.Atom(item=t1.Identifier(name='range')),
            right=p0.Block(kind='<>', inner=[element_ast]),
        ):
            return ty.TypeParameterize(
                'range',
                [ast_to_type(element_ast, ctx=ctx)],
            )

        case p0.Block(kind='<>'|'()', inner=[inner]):
            return ast_to_type(inner, ctx=ctx)

        case p0.BinOp(op=t1.Operator(symbol=':>')):
            return ty.FunctionType(
                _function_type_args(ast.left, ctx=ctx),
                [],
                None,
                ast_to_type(ast.right, ctx=ctx),
            )

        case p0.BinOp(op=t1.Operator(symbol='*')):
            left = ast_to_type(ast.left, ctx=ctx)
            right = ast_to_type(ast.right, ctx=ctx)
            if isinstance(left, ty.DimensionType) and isinstance(
                right,
                ty.DimensionType,
            ):
                return ty.multiply_dimensions(left, right)
            if isinstance(left, ty.DimensionType):
                if isinstance(right, ty.QuantityType):
                    return ty.QuantityType(
                        right.number,
                        ty.multiply_dimensions(left, right.dimension),
                    )
                if ctx.type_system.is_subtype(right, 'number'):
                    return ty.QuantityType(right, left)
            if isinstance(right, ty.DimensionType):
                if isinstance(left, ty.QuantityType):
                    return ty.QuantityType(
                        left.number,
                        ty.multiply_dimensions(left.dimension, right),
                    )
                if ctx.type_system.is_subtype(left, 'number'):
                    return ty.QuantityType(left, right)
            quantity = _quantity_product_type(left, right, ctx=ctx)
            if quantity is not None:
                return quantity
            number = _numeric_product_type(left, right, ctx=ctx)
            if number is not None:
                return number
            type_error(
                ctx.srcfile,
                'invalid type product',
                Pointer(
                    span=ast.loc,
                    message=(
                        f'cannot form a result type from '
                        f'`{type_to_dewy(left)} * {type_to_dewy(right)}`'
                    ),
                ),
            )
        
        case p0.BinOp(op=t1.Operator(symbol='or'|'|')):
            left = ast_to_type(ast.left, ctx=ctx)
            right = ast_to_type(ast.right, ctx=ctx)
            if isinstance(left, ty.TypeOr) and isinstance(right, ty.TypeOr):
                return ty.TypeOr(left.items + right.items)
            elif isinstance(left, ty.TypeOr):
                return ty.TypeOr(left.items + [right])
            elif isinstance(right, ty.TypeOr):
                return ty.TypeOr([left] + right.items)
            return ty.TypeOr([left, right])
        
        case p0.BinOp(op=t1.Operator(symbol='and'|'&')):
            left = ast_to_type(ast.left, ctx=ctx)
            right = ast_to_type(ast.right, ctx=ctx)
            if isinstance(left, ty.TypeAnd) and isinstance(right, ty.TypeAnd):
                return ty.TypeAnd(left.items + right.items)
            elif isinstance(left, ty.TypeAnd):
                return ty.TypeAnd(left.items + [right])
            elif isinstance(right, ty.TypeAnd):
                return ty.TypeAnd([left] + right.items)
            return ty.TypeAnd([left, right])
        
        case p0.Prefix(op=t1.Operator(symbol='not'|'~')):
            item = ast_to_type(ast.item, ctx=ctx)
            return ty.TypeNot(item)
        
        # e.g. probably parameterizations (type jux), types wrapped in blocks, etc. other type expressions...
        # also catch all probably involves typecheck_and_resolve_inner(ast, ctx=ctx, type_block=True)
        case _:
            not_implemented(ctx.srcfile, ast.loc, f'{type(ast).__name__} in type position')

def collect_function_signature_args(signature: p0.AST, *, ctx: Context) -> tuple[list[hir.Param|hir.BoundParam], list[hir.Param|hir.BoundParam], hir.Param|hir.BoundParam|None]:
    """
    collect the parameters from a function signature
    
    Returns:
        list of positional-or-keyword parameters (required or defaulted)
        list of keyword only parameters (bound or unbound)
        ...rest parameter (if any) or None (bound or unbound)
    """

    # make sure we are operating on a block at the top level
    if not isinstance(signature, p0.Block): return collect_function_signature_args(p0.Block(signature.loc, [signature], kind='()'))

    pos_or_kw_args: list[hir.Param|hir.BoundParam] = []
    kw_only_args: list[hir.Param|hir.BoundParam] = []
    saw_rest: bool = False
    rest_args: hir.Param|hir.BoundParam|None = None

    def collect_param(item: p0.AST, *, position_only: bool = False) -> hir.Param | hir.BoundParam:
        def mark_place(
            param: hir.Param | hir.BoundParam,
            loc: Span,
        ) -> hir.Param:
            if isinstance(param, hir.BoundParam):
                user_error(
                    ctx.srcfile,
                    'place parameters cannot have defaults',
                    Pointer(
                        span=loc,
                        message='a place must be supplied explicitly by every call',
                    ),
                )
            if param.type == ty.INFERRED_TYPE:
                user_error(
                    ctx.srcfile,
                    'place parameters require an explicit type',
                    Pointer(
                        span=loc,
                        message='write `@name:Type` so calls can match exactly',
                    ),
                )
            if isinstance(param.type, (ty.FunctionType, ty.OverloadType)):
                not_implemented(
                    ctx.srcfile,
                    loc,
                    'function-handle place parameters',
                )
            return replace(param, place=True)

        if isinstance(item, p0.Prefix) and item.op.symbol == '@':
            return mark_place(
                collect_param(item.item, position_only=position_only),
                item.loc,
            )
        if (
            isinstance(item, p0.BinOp)
            and isinstance(item.left, p0.Prefix)
            and item.left.op.symbol == '@'
        ):
            return mark_place(
                collect_param(
                    replace(item, left=item.left.item),
                    position_only=position_only,
                ),
                item.left.loc,
            )
        if (
            isinstance(item, p0.BinOp)
            and isinstance(item.left, p0.BinOp)
            and isinstance(item.left.left, p0.Prefix)
            and item.left.left.op.symbol == '@'
        ):
            normalized_left = replace(
                item.left,
                left=item.left.left.item,
            )
            return mark_place(
                collect_param(
                    replace(item, left=normalized_left),
                    position_only=position_only,
                ),
                item.left.left.loc,
            )
        match item:
            case p0.Atom(item=t1.Identifier(name=name)):
                return hir.Param(name, type=ty.INFERRED_TYPE, position_only=position_only)
            case p0.BinOp(op=t1.Operator(symbol=':'), left=p0.Atom(item=t1.Identifier(name=name))):
                return hir.Param(
                    name,
                    type=ast_to_type(item.right, ctx=ctx),
                    position_only=position_only,
                )
            case p0.BinOp(op=t1.Operator(symbol='='), left=p0.Atom(item=t1.Identifier(name=name)), right=p0.AST() as right):
                value = typecheck_and_resolve_inner(right, ctx=ctx)
                param_type: ty.Type = (
                    'int64'
                    if isinstance(value.type, ty.IntegerLiteralType)
                    else value.type
                )
                return hir.BoundParam(
                    name,
                    type=param_type,
                    value=value,
                    position_only=position_only,
                )
            case p0.BinOp(op=t1.Operator(symbol='='), left=p0.BinOp(op=t1.Operator(symbol=':'), left=p0.Atom(item=t1.Identifier(name=name)), right=p0.AST() as typeexpr), right=p0.AST() as right):
                param_type = ast_to_type(typeexpr, ctx=ctx)
                value = check_against(
                    typecheck_and_resolve_inner(right, ctx=ctx, expected=param_type),
                    param_type,
                    ctx=ctx,
                )
                return hir.BoundParam(
                    name,
                    type=param_type,
                    value=value,
                    position_only=position_only,
                )
            case _:
                not_implemented(ctx.srcfile, item.loc, f'{type(item).__name__} in function signature')

    for item in signature.inner:
        match item:
            case p0.Atom(item=t1.Identifier(name='...')):
                if saw_rest:
                    user_error(ctx.srcfile, 'multiple `...` in function signature',
                        Pointer(span=item.loc, message='second `...` here'),
                        hint='a function signature may contain at most one `...` divider/rest parameter')
                saw_rest = True
            case p0.Block(kind='<>', inner=[inner]):
                if saw_rest:
                    user_error(ctx.srcfile, 'position-only parameter after `...`',
                        Pointer(span=item.loc, message='position-only parameters must be before the keyword-only divider'))
                pos_or_kw_args.append(collect_param(inner, position_only=True))
            case p0.Block(kind='<>'):
                user_error(ctx.srcfile, 'invalid position-only parameter',
                    Pointer(span=item.loc, message='`<>` must contain exactly one named parameter'))
            case (
                p0.Atom(item=t1.Identifier())
                | p0.Prefix(op=t1.Operator(symbol='@'))
                | p0.BinOp(op=t1.Operator(symbol=':'|'='))
            ):
                (kw_only_args if saw_rest else pos_or_kw_args).append(collect_param(item))
            case p0.BinOp(op=t2.EllipsisJuxtapose(), left=p0.Atom(item=t1.Identifier(name='...')), right=p0.Atom(item=t1.Identifier(name=name))):
                if saw_rest:
                    user_error(ctx.srcfile, 'multiple `...` in function signature',
                        Pointer(span=item.loc, message='second `...` here'),
                        hint='a function signature may contain at most one `...` divider/rest parameter')
                saw_rest = True
                rest_args = hir.Param(name, type=ty.INFERRED_TYPE)
            # case ...name:type
            # case ...name=value
            # case ...name:type=value
            # etc. etc. many other cases... namely dict/object/array unpacking
            case _:
                not_implemented(ctx.srcfile, item.loc, f'{type(item).__name__} in function signature')

    return pos_or_kw_args, kw_only_args, rest_args


def parse_call_arguments(
    right: p0.AST,
    *,
    ctx: Context,
    method: ty.FunctionType | None = None,
) -> tuple[list[hir.AST], dict[str, hir.AST], list[str | None]]:
    """Typecheck call args while retaining their left-to-right binding order."""
    if isinstance(right, p0.Block):
        items = list(right.inner)
    else:
        items = [right]

    pos_args: list[hir.AST] = []
    kw_args: dict[str, hir.AST] = {}
    order: list[str | None] = []
    bound_positional_indices: set[int] = set()
    argument_ctx = replace(ctx, allow_place_expression=True)
    for item in items:
        match item:
            case p0.BinOp(op=t1.Operator(symbol='='), left=p0.Atom(item=t1.Identifier(name=name)) as target, right=value):
                if name in kw_args:
                    user_error(ctx.srcfile, f'duplicate keyword argument `{name}`',
                        Pointer(span=target.loc, message='already given earlier in this call'))
                param = next((p for p in method.pos_or_kw if p.name == name), None) if method is not None else None
                if param is None and method is not None:
                    param = next((p for p in method.kw_only if p.name == name), None)
                expected_arg = param.type if param is not None else None
                arg = typecheck_and_resolve_inner(
                    value,
                    ctx=argument_ctx,
                    expected=expected_arg,
                )
                if _contains_place(arg) and not isinstance(arg, hir.Place):
                    user_error(
                        ctx.srcfile,
                        'a place must be a complete call argument',
                        Pointer(
                            span=arg.loc,
                            message='pass `@name` directly without wrapping it in an expression',
                        ),
                    )
                kw_args[name] = (
                    arg
                    if isinstance(arg, hir.Place) or expected_arg is None
                    else check_against(arg, expected_arg, ctx=ctx)
                )
                order.append(name)
                if method is not None:
                    index = next(
                        (i for i, candidate in enumerate(method.pos_or_kw) if candidate.name == name),
                        None,
                    )
                    if index is not None:
                        bound_positional_indices.add(index)
            case _:
                index = next(
                    (
                        i for i in range(len(method.pos_or_kw))
                        if i not in bound_positional_indices
                    ),
                    None,
                ) if method is not None else None
                expected_arg = method.pos_or_kw[index].type if method is not None and index is not None else None
                arg = typecheck_and_resolve_inner(
                    item,
                    ctx=argument_ctx,
                    expected=expected_arg,
                )
                if _contains_place(arg) and not isinstance(arg, hir.Place):
                    user_error(
                        ctx.srcfile,
                        'a place must be a complete call argument',
                        Pointer(
                            span=arg.loc,
                            message='pass `@name` directly without wrapping it in an expression',
                        ),
                    )
                pos_args.append(
                    arg
                    if isinstance(arg, hir.Place) or expected_arg is None
                    else check_against(arg, expected_arg, ctx=ctx)
                )
                order.append(None)
                if index is not None:
                    bound_positional_indices.add(index)
    return pos_args, kw_args, order


def _contains_place(value: object) -> bool:
    if isinstance(value, hir.Place):
        return True
    if isinstance(value, (list, tuple)):
        return any(_contains_place(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_place(item) for item in value.values())
    if is_dataclass(value) and isinstance(value, hir.AST):
        return any(
            _contains_place(getattr(value, item.name))
            for item in fields(value)
            if item.name not in {'loc', 'type'}
        )
    return False


def _validate_place_call_arguments(
    method: ty.FunctionType,
    pos_args: list[hir.AST],
    kw_args: dict[str, hir.AST],
    *,
    ctx: Context,
) -> None:
    """Require `@` on both sides and reject overlapping mutable places."""

    supplied: list[tuple[ty.PosOrKwArg | ty.KwOnlyArg, hir.AST]] = []
    supplied.extend(zip(method.pos_or_kw, pos_args))
    parameters_by_name = {
        parameter.name: parameter
        for parameter in [*method.pos_or_kw, *method.kw_only]
        if parameter.name is not None
    }
    supplied.extend(
        (parameters_by_name[name], argument)
        for name, argument in kw_args.items()
        if name in parameters_by_name
    )

    seen_places: list[hir.Place] = []
    for parameter, argument in supplied:
        place = argument if isinstance(argument, hir.Place) else None
        if parameter.place and place is None:
            user_error(
                ctx.srcfile,
                'place argument requires `@`',
                Pointer(
                    span=argument.loc,
                    message='this parameter can write the caller binding',
                ),
                hint='pass a mutable named binding as `@name`',
            )
        if not parameter.place and place is not None:
            user_error(
                ctx.srcfile,
                'value parameter does not accept a place',
                Pointer(
                    span=place.loc,
                    message='remove `@` to pass an independent value',
                ),
            )
        if place is None:
            continue
        if place.target.type != parameter.type:
            type_error(
                ctx.srcfile,
                'place parameter types are invariant',
                Pointer(
                    span=place.loc,
                    message=(
                        f'place has type `{type_to_dewy(place.target.type)}`, '
                        f'but parameter requires exactly '
                        f'`{type_to_dewy(parameter.type)}`'
                    ),
                ),
            )
        previous = next(
            (
                candidate
                for candidate in seen_places
                if _place_routes_may_overlap(candidate.target, place.target)
            ),
            None,
        )
        if previous is not None:
            user_error(
                ctx.srcfile,
                'overlapping mutable places in one call',
                Pointer(span=previous.loc, message='first use of this place'),
                Pointer(span=place.loc, message='same place passed again here'),
            )
        seen_places.append(place)


PlaceRouteComponent = tuple[Literal['field'], str] | tuple[Literal['index'], int | None]


def _place_route(
    target: hir.ExpressedIdentifier | hir.MemberAccess | hir.Index,
) -> tuple[int, tuple[PlaceRouteComponent, ...]]:
    if isinstance(target, hir.ExpressedIdentifier):
        if target.binding_id is None:
            raise ValueError('INTERNAL ERROR: place target has no binding identity')
        return target.binding_id, ()
    if isinstance(target, hir.MemberAccess):
        binding_id, route = _place_route(target.value)
        return binding_id, (*route, ('field', target.name))
    binding_id, route = _place_route(target.array)
    return binding_id, (*route, ('index', target.constant_index))


def _place_routes_may_overlap(
    left: hir.ExpressedIdentifier | hir.MemberAccess | hir.Index,
    right: hir.ExpressedIdentifier | hir.MemberAccess | hir.Index,
) -> bool:
    left_binding, left_route = _place_route(left)
    right_binding, right_route = _place_route(right)
    if left_binding != right_binding:
        return False
    for left_part, right_part in zip(left_route, right_route):
        if left_part[0] != right_part[0]:
            return False
        if left_part[0] == 'field' and left_part[1] != right_part[1]:
            return False
        if (
            left_part[0] == 'index'
            and left_part[1] is not None
            and right_part[1] is not None
            and left_part[1] != right_part[1]
        ):
            return False
    # An identical route or a prefix route can select the same storage. Dynamic
    # indices are conservatively assumed equal unless bounds prove otherwise.
    return True


def _arguments_in_source_order(
    pos_args: list[hir.AST],
    kw_args: dict[str, hir.AST],
    order: list[str | None],
) -> list[tuple[str | None, hir.AST]]:
    positional = iter(pos_args)
    return [
        (name, next(positional) if name is None else kw_args[name])
        for name in order
    ]


def _bind_ordered_call_arguments(
    method: ty.FunctionType,
    arguments: list[tuple[str | None, hir.AST]],
) -> tuple[list[hir.AST], dict[str, hir.AST]] | None:
    """Apply Dewy's left-to-right parameter binding rule to one method."""

    remaining_indices = list(range(len(method.pos_or_kw)))
    bound_slots: dict[int, hir.AST] = {}
    bound_keywords: dict[str, hir.AST] = {}
    extra_positional: list[hir.AST] = []
    pos_by_name = {
        param.name: index
        for index, param in enumerate(method.pos_or_kw)
        if param.name is not None
    }
    kw_names = {param.name for param in method.kw_only}

    for name, argument in arguments:
        if name is None:
            if remaining_indices:
                index = remaining_indices.pop(0)
                bound_slots[index] = argument
            elif method.rest is not None:
                extra_positional.append(argument)
            else:
                return None
            continue

        if name in pos_by_name:
            index = pos_by_name[name]
            if index in bound_slots:
                return None
            bound_slots[index] = argument
            if index in remaining_indices:
                remaining_indices.remove(index)
            continue
        if name in kw_names:
            if name in bound_keywords:
                return None
            bound_keywords[name] = argument
            continue
        if method.rest is not None:
            bound_keywords[name] = argument
            continue
        return None

    if any(method.pos_or_kw[index].required for index in remaining_indices):
        return None
    if any(param.required and param.name not in bound_keywords for param in method.kw_only):
        return None

    canonical_pos: list[hir.AST] = []
    canonical_kw = dict(bound_keywords)
    saw_gap = False
    for index, param in enumerate(method.pos_or_kw):
        argument = bound_slots.get(index)
        if argument is None:
            saw_gap = True
            continue
        if not saw_gap:
            canonical_pos.append(argument)
        elif param.name is not None:
            canonical_kw[param.name] = argument
        else:
            return None
    canonical_pos.extend(extra_positional)
    return canonical_pos, canonical_kw


def _contextualize_flow_result(
    node: hir.AST,
    expected: ty.TypeExpr,
    *,
    ctx: Context,
) -> hir.AST:
    """Record the concrete representation selected for a scalar flow value."""
    if isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
        item = _contextualize_flow_result(node.items[0], expected, ctx=ctx)
        if item is not node.items[0]:
            return replace(node, type=item.type, items=[item])
        return node
    if (
        isinstance(node, hir.Flow)
        and node.type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE)
        and ctx.type_system.is_subtype(node.type, expected)
    ):
        return replace(node, type=expected)
    return node


def _unwrap_literal_value(node: hir.AST) -> hir.AST:
    while isinstance(node, (hir.ValueCast, hir.RepresentationCast)):
        node = node.expr
    if isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
        return _unwrap_literal_value(node.items[0])
    return node


def _literal_path_call_result(
    left: hir.AST,
    pos_args: list[hir.AST],
    kw_args: dict[str, hir.AST],
    *,
    ctx: Context,
) -> ty.PathLiteralType | None:
    if not isinstance(left, hir.ExpressedIdentifier) or left.binding_id is None:
        return None
    binding = ctx.binding_registry.by_id[left.binding_id]
    parameter_name = binding.literal_path_parameter
    if parameter_name is None or not isinstance(left.type, ty.FunctionType):
        return None
    params = [*left.type.pos_or_kw, *left.type.kw_only]
    param = next((param for param in params if param.name == parameter_name), None)
    if param is None:
        return None
    positional_index = next(
        (
            index
            for index, candidate in enumerate(left.type.pos_or_kw)
            if candidate.name == parameter_name
        ),
        None,
    )
    argument = (
        pos_args[positional_index]
        if positional_index is not None and positional_index < len(pos_args)
        else kw_args.get(parameter_name)
    )
    if argument is None:
        return None
    argument = _unwrap_literal_value(argument)
    if not isinstance(argument.type, ty.StringLiteralType):
        return None
    return ty.PathLiteralType(argument.type.value)


def _checked_single_argument_call(
    func: hir.AST,
    argument: hir.AST,
    *,
    loc: Span,
    ctx: Context,
) -> hir.FunctionCall:
    """Build one ordinary checked call from an already-checked argument."""

    methods: list[ty.FunctionType]
    if isinstance(func.type, ty.FunctionType):
        methods = [func.type]
    elif isinstance(func.type, ty.OverloadType):
        methods = func.type.methods
    else:
        type_error(
            ctx.srcfile,
            'call target is not a function',
            Pointer(
                span=func.loc,
                message=f'this has type `{type_to_dewy(func.type)}`, which is not callable',
            ),
        )
    try:
        result = ctx.type_system.match_best_function(
            methods,
            [require_valued(
                argument.type,
                ctx.srcfile,
                argument.loc,
                'function call argument',
            )],
            {},
        )
    except ty.DispatchError as error:
        type_error(
            ctx.srcfile,
            'no string conversion available for interpolation field',
            Pointer(span=argument.loc, message=str(error)),
        )
    contextual = check_against(
        argument,
        result.method.pos_or_kw[0].type,
        ctx=ctx,
    )
    promoted = apply_promotions([contextual], result.promote_pos)
    return hir.FunctionCall(
        loc,
        result.method.ret,
        func,
        promoted,
        {},
        result.method_index if isinstance(func.type, ty.OverloadType) else None,
    )


def _specialize_interpolated_output(
    call: hir.FunctionCall,
    *,
    ctx: Context,
) -> hir.AST:
    """Rewrite interpolated ``print``/``printl`` calls into streaming writes."""

    if (
        not isinstance(call.func, hir.ExpressedIdentifier)
        or call.func.name not in {'print', 'printl'}
        or len(call.pos_args) != 1
        or call.kw_args
        or not isinstance(call.pos_args[0], hir.InterpolatedString)
    ):
        return call

    print_func = tcr_identifier(
        t1.Identifier(call.func.loc, 'print'),
        ctx=ctx,
    )
    statements = [
        _checked_single_argument_call(
            print_func,
            part,
            loc=part.loc,
            ctx=ctx,
        )
        for part in call.pos_args[0].parts
    ]
    if call.func.name == 'printl':
        newline = hir.String(
            call.loc,
            ty.StringLiteralType('\n'),
            '\n',
        )
        statements.append(
            _checked_single_argument_call(
                print_func,
                newline,
                loc=call.loc,
                ctx=ctx,
            )
        )
    return hir.Block(call.loc, ty.VOID_TYPE, statements, False)


def tcr_function_call(left: hir.AST, right: p0.AST, *, ctx: Context, expected: ty.Type|None=None) -> hir.AST:
    if isinstance(left, hir.Block) and not left.scoped and len(left.items) == 1:
        left = left.items[0]

    methods: list[ty.FunctionType]
    if isinstance(left.type, ty.FunctionType):
        methods = [left.type]
    elif isinstance(left.type, ty.OverloadType):
        methods = left.type.methods
    else:
        type_error(ctx.srcfile, 'call target is not a function',
            Pointer(span=left.loc, message=f'this has type `{type_to_dewy(left.type)}`, which is not callable'))

    contextual_method = methods[0] if len(methods) == 1 and not methods[0].type_params else None
    pos_args, kw_args, argument_order = parse_call_arguments(
        right,
        ctx=ctx,
        method=contextual_method,
    )
    for name, arg in kw_args.items():
        if not any(
            method.rest is not None
            or any(param.name == name for param in method.pos_or_kw)
            or any(param.name == name for param in method.kw_only)
            for method in methods
        ):
            user_error(ctx.srcfile, f'unknown keyword argument `{name}`',
                Pointer(span=arg.loc, message='no method has a parameter with this name'))
    ordered_arguments = _arguments_in_source_order(pos_args, kw_args, argument_order)
    interleaved = any(
        name is None and any(previous is not None for previous in argument_order[:index])
        for index, name in enumerate(argument_order)
    )
    pos_types = [require_valued(a.type, ctx.srcfile, a.loc, 'function call argument') for a in pos_args]
    kw_types = {k: require_valued(v.type, ctx.srcfile, v.loc, f'keyword argument `{k}`') for k, v in kw_args.items()}
    try:
        expected_return = expected if expected not in (None, ty.VOID_TYPE, ty.INFERRED_TYPE) else None
        if not interleaved:
            result = ctx.type_system.match_best_function(
                methods,
                pos_types,
                kw_types,
                expected_return=expected_return,
            )
        else:
            applicable: list[
                tuple[
                    int,
                    ty.FunctionType,
                    list[hir.AST],
                    dict[str, hir.AST],
                    list[ty.TypeExpr | None],
                ]
            ] = []
            for method_index, method in enumerate(methods):
                bound = _bind_ordered_call_arguments(method, ordered_arguments)
                if bound is None:
                    continue
                candidate_pos, candidate_kw = bound
                candidate_pos_types = [
                    require_valued(arg.type, ctx.srcfile, arg.loc, 'function call argument')
                    for arg in candidate_pos
                ]
                candidate_kw_types = {
                    name: require_valued(
                        arg.type,
                        ctx.srcfile,
                        arg.loc,
                        f'keyword argument `{name}`',
                    )
                    for name, arg in candidate_kw.items()
                }
                instantiated = ctx.type_system.try_instantiate_for_call(
                    method,
                    candidate_pos_types,
                    candidate_kw_types,
                    expected_return,
                )
                if instantiated is not None:
                    applicable.append((
                        method_index,
                        instantiated,
                        candidate_pos,
                        candidate_kw,
                        [None] * len(candidate_pos),
                    ))
            if not applicable:
                for method_index, method in enumerate(methods):
                    bound = _bind_ordered_call_arguments(method, ordered_arguments)
                    if bound is None:
                        continue
                    candidate_pos, candidate_kw = bound
                    candidate_pos_types = [
                        require_valued(
                            arg.type,
                            ctx.srcfile,
                            arg.loc,
                            'function call argument',
                        )
                        for arg in candidate_pos
                    ]
                    if not candidate_pos_types or not all(
                        isinstance(type_, str) for type_ in candidate_pos_types
                    ):
                        continue
                    common: str | None = candidate_pos_types[0]  # type: ignore[assignment]
                    for type_ in candidate_pos_types[1:]:
                        assert common is not None
                        common = ctx.type_system.promote_type(common, type_)
                        if common is None:
                            break
                    if common is None:
                        continue
                    promoted_types = [common] * len(candidate_pos_types)
                    candidate_kw_types = {
                        name: require_valued(
                            arg.type,
                            ctx.srcfile,
                            arg.loc,
                            f'keyword argument `{name}`',
                        )
                        for name, arg in candidate_kw.items()
                    }
                    instantiated = ctx.type_system.try_instantiate_for_call(
                        method,
                        promoted_types,
                        candidate_kw_types,
                        expected_return,
                    )
                    if instantiated is not None:
                        applicable.append((
                            method_index,
                            instantiated,
                            candidate_pos,
                            candidate_kw,
                            [
                                None if type_ == common else common
                                for type_ in candidate_pos_types
                            ],
                        ))
            winners = [
                candidate
                for candidate in applicable
                if not any(
                    ctx.type_system.more_specific(other[1], candidate[1])
                    for other in applicable
                    if other[0] != candidate[0]
                )
            ]
            if len(winners) != 1:
                detail = (
                    'no matching method for arguments in this order'
                    if not winners
                    else f'ambiguous call among {len(applicable)} applicable methods'
                )
                raise ty.DispatchError(detail)
            method_index, selected, pos_args, kw_args, promote_pos = winners[0]
            result = ty.DispatchResult(
                selected,
                method_index,
                promote_pos,
            )
    except ty.DispatchError as e:
        type_error(ctx.srcfile, 'no matching method for call',
            Pointer(span=left.loc, message='calling this'),
            Pointer(span=right.loc, message=str(e)))

    if interleaved:
        # Re-bind once against the selected signature so generic instantiation
        # cannot leave the HIR call in source-order form.
        bound = _bind_ordered_call_arguments(result.method, ordered_arguments)
        if bound is None:
            raise ValueError('INTERNAL ERROR: selected method no longer accepts ordered call')
        pos_args, kw_args = bound

    _validate_place_call_arguments(
        result.method,
        pos_args,
        kw_args,
        ctx=ctx,
    )

    contextual_pos_args = [
        arg
        if isinstance(arg, hir.Place)
        else check_against(
            _contextualize_flow_result(
                arg,
                result.method.pos_or_kw[index].type,
                ctx=ctx,
            ),
            result.method.pos_or_kw[index].type,
            ctx=ctx,
        )
        if index < len(result.method.pos_or_kw)
        else arg
        for index, arg in enumerate(pos_args)
    ]
    parameter_types = {
        param.name: param.type
        for param in [*result.method.pos_or_kw, *result.method.kw_only]
    }
    contextual_kw_args = {
        name: argument
        if isinstance(argument, hir.Place)
        else check_against(
            _contextualize_flow_result(
                argument,
                parameter_types[name],
                ctx=ctx,
            ),
            parameter_types[name],
            ctx=ctx,
        )
        for name, argument in kw_args.items()
    }
    return_type = result.method.ret
    literal_path_type = _literal_path_call_result(
        left,
        pos_args,
        kw_args,
        ctx=ctx,
    )
    if literal_path_type is not None:
        return_type = literal_path_type
    call = hir.FunctionCall(
        Span(left.loc.start, right.loc.stop),
        return_type,
        left,
        apply_promotions(contextual_pos_args, result.promote_pos),
        contextual_kw_args,
        result.method_index if isinstance(left.type, ty.OverloadType) else None,
    )
    return _specialize_interpolated_output(call, ctx=ctx)


def _is_string_type(type_: ty.Type) -> bool:
    if isinstance(type_, (ty.StringLiteralType, ty.StringType)):
        return True
    return isinstance(type_, str) and type_ in {'string', 'grapheme', 'char'}


def _refine_binary_materialization_target(
    source: ty.Type,
    target: ty.Type,
) -> ty.Type:
    if (
        isinstance(source, ty.BinaryLiteralType)
        and isinstance(target, ty.ArrayType)
        and target.element == 'uint8'
        and target.length is None
    ):
        return ty.ArrayType('uint8', len(source.value))
    return target


def _explicit_value_conversion(
    node: hir.AST,
    target: ty.Type,
    loc: Span,
    *,
    ctx: Context,
) -> hir.AST:
    source = node.type
    target = _refine_binary_materialization_target(source, target)
    target = _refine_string_materialization_target(source, target)
    if source == target:
        return node
    if isinstance(source, ty.BinaryLiteralType):
        if ctx.type_system.is_subtype(source, target):
            return hir.RepresentationCast(loc, target, node)
        if _is_string_type(target):
            type_error(
                ctx.srcfile,
                'binary data is not Unicode text',
                Pointer(
                    span=loc,
                    message=(
                        f'cannot convert `{type_to_dewy(source)}` to '
                        f'`{type_to_dewy(target)}`'
                    ),
                ),
                hint='based strings only materialize as `array<uint8>`',
            )
    if isinstance(source, ty.StringLiteralType) and ctx.type_system.is_subtype(
        source,
        target,
    ):
        return hir.RepresentationCast(loc, target, node)
    if _is_string_type(source):
        if isinstance(target, ty.ArrayType) and target.element in {
            'uint8',
            'uint32',
            'grapheme',
            'char',
        }:
            return hir.RepresentationCast(loc, target, node)
        if target in {'string', 'grapheme', 'char'}:
            if ctx.type_system.is_subtype(source, target):
                return hir.RepresentationCast(loc, target, node)
    if isinstance(source, ty.ArrayType):
        if target in {'string', 'grapheme', 'char'}:
            if source.element in {'uint8', 'uint32'}:
                type_error(
                    ctx.srcfile,
                    'string conversion requires a validity proof',
                    Pointer(
                        span=loc,
                        message=(
                            f'`{type_to_dewy(source)}` does not prove that its '
                            'contents form valid Unicode text'
                        ),
                    ),
                    hint='validation-backed refinement types are not implemented yet',
                )
            if (
                source.element in {'grapheme', 'char'}
                or isinstance(source.element, ty.StringType)
                and source.element.length == 1
            ) and target == 'string':
                return hir.RepresentationCast(loc, target, node)
    if isinstance(source, ty.ObjectType) and isinstance(target, ty.ObjectType):
        if (
            len(source.fields) == len(target.fields)
            and all(
                source_field.name == target_field.name
                and source_field.mutable == target_field.mutable
                and ctx.type_system.is_subtype(
                    source_field.type,
                    target_field.type,
                )
                for source_field, target_field in zip(
                    source.fields,
                    target.fields,
                )
            )
        ):
            return hir.RepresentationCast(loc, target, node)
    if ctx.type_system.is_subtype(source, target):
        return node
    if ctx.type_system.promote_type(source, target) == target:
        return hir.ValueCast(loc, target, node)
    type_error(
        ctx.srcfile,
        'unsupported value conversion',
        Pointer(
            span=loc,
            message=(
                f'cannot convert `{type_to_dewy(source)}` to '
                f'`{type_to_dewy(target)}`'
            ),
        ),
    )


def _transmute_compatible(source: ty.Type, target: ty.Type) -> bool:
    """Whether source and target have the same one-word udewy value shape."""

    if source in (ty.VOID_TYPE, ty.INFERRED_TYPE) or target in (
        ty.VOID_TYPE,
        ty.INFERRED_TYPE,
    ):
        return False
    if isinstance(source, ty.BinaryLiteralType) or isinstance(
        target,
        ty.BinaryLiteralType,
    ):
        return False
    source_string = _is_string_type(source)
    target_string = _is_string_type(target)
    source_array = isinstance(source, ty.ArrayType)
    target_array = isinstance(target, ty.ArrayType)
    if (source_string and target_array) or (source_array and target_string):
        return False
    return True


def _refine_string_materialization_target(
    source: ty.Type,
    target: ty.Type,
) -> ty.Type:
    if not isinstance(source, ty.StringLiteralType):
        return target
    if not isinstance(target, ty.ArrayType) or target.length is not None:
        return target
    byte_count, scalar_count, grapheme_count = ty.string_literal_lengths(source.value)
    length = {
        'uint8': byte_count,
        'uint32': scalar_count,
        'grapheme': grapheme_count,
        'char': grapheme_count,
        'string': grapheme_count,
    }.get(target.element) if isinstance(target.element, str) else None
    return ty.ArrayType(target.element, length) if length is not None else target


def check_against(node: hir.AST, expected: ty.Type, *, ctx: Context) -> hir.AST:
    """Check a synthesized node against an expected type (bidirectional checking's checking mode).

    Subsumption passes the node through unchanged; a legal numeric promotion wraps it in a
    ValueCast; anything else is a type error.
    """
    if node.type == expected:
        return node
    if node.type == ty.BOTTOM_TYPE:
        return node  # unreachable; vacuously satisfies any expectation
    if node.type == ty.VOID_TYPE or node.type == ty.INFERRED_TYPE or expected == ty.VOID_TYPE:
        expected_str = type_to_dewy(expected) if expected != ty.VOID_TYPE else 'void'
        type_error(ctx.srcfile, 'type mismatch',
            Pointer(span=node.loc, message=f'expected `{expected_str}`, got `{node.type}`'))
    if isinstance(node.type, ty.BinaryLiteralType):
        target = _refine_binary_materialization_target(node.type, expected)
        if ctx.type_system.is_subtype(node.type, target):
            return hir.RepresentationCast(node.loc, target, node)
    if isinstance(node.type, ty.StringLiteralType) and ctx.type_system.is_subtype(
        node.type,
        expected,
    ):
        target = _refine_string_materialization_target(node.type, expected)
        return hir.RepresentationCast(node.loc, target, node)
    if ctx.type_system.is_subtype(node.type, expected):
        return node
    if ctx.type_system.promote_type(node.type, expected) == expected:
        return hir.ValueCast(node.loc, expected, node)
    type_error(ctx.srcfile, 'type mismatch',
        Pointer(span=node.loc, message=f'expected `{type_to_dewy(expected)}`, got `{type_to_dewy(node.type)}`'))


def apply_promotions(args: list[hir.AST], promote_pos: list[ty.TypeExpr | None]) -> list[hir.AST]:
    """Wrap args that need promotion in Cast nodes. `promote_pos` is parallel to `args`."""
    out: list[hir.AST] = []
    for arg, target in zip(args, promote_pos):
        if target is None:
            out.append(arg)
        else:
            out.append(hir.ValueCast(arg.loc, target, arg))
    return out


def typecheck_partial_eval(left: hir.AST, right: hir.AST) -> hir.Partial:
    raise NotImplementedError('typecheck_partial_eval')

def tcr_identifier(
    id: t1.Identifier,
    *,
    ctx: Context,
    expected: ty.Type | None = None,
    refined: bool = True,
) -> hir.AST:
    if (module := ctx.module_namespaces.get(id.name)) is not None:
        return hir.ModuleNamespace(
            id.loc,
            ty.ModuleType(tuple(
                ty.ModuleField(
                    name,
                    binding.type or ty.TOP_TYPE,
                    binding.id,
                    binding.type_value,
                )
                for name, binding in module.exports.items()  # type: ignore[attr-defined]
            )),
            id.name,
        )
    if id.name in ctx.declarations:
        binding = ctx.binding_scopes.get(id.name)
        declared_type = ctx.declarations[id.name]
        if declared_type == ty.TYPE_TYPE or (
            binding is not None and binding.type_value is not None
        ):
            not_implemented(ctx.srcfile, id.loc, 'runtime type values')
        resolved_type = (
            ctx.refinements.get(binding.id, declared_type)
            if refined and binding is not None
            else declared_type
        )
        return hir.ExpressedIdentifier(
            id.loc,
            resolved_type,
            id.name,
            binding_id=binding.id if binding is not None else None,
        )

    user_error(ctx.srcfile, f'undefined identifier `{id.name}`',
        Pointer(span=id.loc, message='not found in this scope'))





def test():
    from argparse import ArgumentParser
    from pathlib import Path
    parser = ArgumentParser()
    parser.add_argument('path', type=Path, help='path to file to tokenize')
    args = parser.parse_args()
    path: Path = args.path
    src = path.read_text()
    srcfile = SrcFile(path, src)
    try:
        ast = typecheck_and_resolve(srcfile)
    except ReportException as e:
        print(e.report)
        exit(1)
    
    print(repr(ast))
    print()
    print(str(ast))
    
if __name__ == '__main__':
    test()
