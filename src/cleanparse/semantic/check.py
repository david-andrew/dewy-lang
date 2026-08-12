"""
semantic analysis pass 0: 
- type checking
- ambiguity resolution
"""
from dataclasses import dataclass, replace, field
from collections import ChainMap
from typing import Literal, cast
from ..parser import p0, t2, t1, t0
from . import bindings as sb
from . import builtins, hir, initialization, ty
from .errors import TypeCheckError, NotImplementedYet, type_error, user_error, not_implemented, require_valued
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
    # TODO: etc stuff

def typecheck_and_resolve(srcfile: SrcFile) -> hir.AST:
    # set up the base type system/builtins
    type_system = ty.TypeSystem()
    builtins.apply_builtin_promote_rules(type_system)
    declarations = ChainMap(builtins.builtin_types)
    
    ctx = Context(srcfile, declarations, type_system)
    block = p0.parse(srcfile)
    checked = tcr_block(block, ctx=ctx)
    initialization.validate_initialization(checked, ctx.binding_registry, srcfile)
    return checked

def typecheck_and_resolve_inner(ast: p0.AST, *, ctx: Context, type_block:bool=False, expected: ty.Type|None=None) -> hir.AST:
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
                    catcher=Catcher(list(ctx.catcher.returns), ctx.catcher.expected) if ctx.catcher is not None else None)
                try:
                    passes.append((typecheck_and_resolve_inner(candidate, ctx=fork, type_block=type_block, expected=expected), fork))
                except (TypeCheckError, NotImplementedYet) as e:
                    # NotImplementedYet prunes too so an unimplemented reading doesn't block a
                    # valid one, but it is reported preferentially when nothing survives since
                    # the failure may be a compiler gap rather than a user error
                    rejections.append(e)
            if len(passes) == 0:
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

        case p0.Block(): return tcr_block(ast, ctx=ctx, expected=expected)
        case p0.Prefix(): return tcr_prefix(ast, ctx=ctx, expected=expected)
        case p0.BinOp(): return tcr_binop(ast, ctx=ctx, type_block=type_block, expected=expected)
        case p0.Atom(item=t1.Identifier(name='..')): return hir.Range(ast.item.loc, 'range', bounds=None, step_pair=None, left=None, right=None)
        case p0.Atom(item=t1.Identifier(name='void')): return hir.Void(ast.item.loc, ty.VOID_TYPE)
        case p0.Atom(item=t1.Identifier()): return tcr_identifier(ast.item, ctx=ctx)
        case p0.Atom(item=t1.String(content=content)): return hir.String(ast.item.loc, 'string', content)
        case p0.Atom(item=t1.Integer(value=value)):
            parsed = t0.parse_integer(value.src, value.prefix)
            return hir.Integer(ast.item.loc, ty.IntegerLiteralType(parsed), value.prefix, parsed)
        case p0.Atom(item=t1.Metatag(name=name)):
            return tcr_scope_metatag(ast, name=name, ctx=ctx)
        # case p0.Atom(item=t1.Real()): ...
        # case p0.Atom(item=t1.BasedString()): ...
        # case p0.Atom(item=t1.Semicolon()): ...
        # case p0.Atom(item=t1.Metatag()): ...
        # case p0.Atom(item=t1.Integer()): ...
        case p0.Atom(item=t1.Bool(value=value)): return hir.Bool(ast.item.loc, 'bool', value)
        # case p0.Atom(item=t2.OpFn()): ...
        # case p0.Atom(item=t2.Placeholder()): ...
        case p0.Flat(op=t2.RangeJuxtapose()): return tcr_bare_range(ast, ctx=ctx)
        case _:
            not_implemented(ctx.srcfile, ast.loc, f'{type(ast).__name__} expression')


def _complete_binding(
    ast: p0.KeywordExpr,
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
    declaration = replace(declaration, binding_id=binding.id)
    binding.declaration = declaration
    if isinstance(declaration.expr, hir.FunctionLiteral):
        binding.function = declaration.expr
    ctx.binding_scopes[declaration.name] = binding
    return declaration


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
            expr = typecheck_and_resolve_inner(right, ctx=ctx, expected=annotation)
            expr = check_against(expr, annotation, ctx=ctx)
            ctx.declarations[name] = annotation
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

    target = tcr_assignment_target(ast.left, ctx=ctx)
    value = typecheck_and_resolve_inner(ast.right, ctx=ctx, expected=target.type)
    value = check_against(value, target.type, ctx=ctx)
    return hir.Assign(ast.loc, ty.VOID_TYPE, target, '=', value)


def tcr_combined_assign(ast: p0.BinOp, *, ctx: Context) -> hir.Assign:
    """Typecheck a simple compound assignment while retaining its source operator."""
    assert isinstance(ast.op, t2.CombinedAssignmentOp)
    if not isinstance(ast.op.op, t1.Operator):
        not_implemented(ctx.srcfile, ast.op.loc, 'broadcast compound assignment')
    symbol = ast.op.op.symbol
    if symbol not in builtins.BINOP_DUNDER_MAP:
        not_implemented(ctx.srcfile, ast.op.loc, f'compound assignment operator `{symbol}=`')

    target = tcr_assignment_target(ast.left, ctx=ctx)
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
    not_implemented(ctx.srcfile, ast.loc, 'import')

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
        for arm in ast.arms:
            if len(arm.parts) != 3:
                raise ValueError(f'INTERNAL ERROR: malformed if arm: {arm.parts!r}')
            _, condition_ast, body_ast = arm.parts
            assert isinstance(condition_ast, p0.AST)
            assert isinstance(body_ast, p0.AST)
            condition = _check_flow_condition(condition_ast, ctx=ctx)
            body = typecheck_and_resolve_inner(body_ast, ctx=ctx, expected=branch_expected)
            if branch_expected is not None:
                body = check_against(body, branch_expected, ctx=ctx)
            arms.append(hir.IfArm(arm.loc, body.type, condition, body))
            bodies.append(body)

        default = None
        if ast.default is not None:
            default = typecheck_and_resolve_inner(ast.default, ctx=ctx, expected=branch_expected)
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
        condition = _check_flow_condition(condition_ast, ctx=ctx)
        if not ctx.label_scopes:
            raise ValueError('INTERNAL ERROR: loop has no containing lexical label scope')
        boundary = LoopBoundary(ctx.label_scopes[-1])
        body = typecheck_and_resolve_inner(
            body_ast,
            ctx=replace(
                ctx,
                loop_boundaries=(*ctx.loop_boundaries, boundary),
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


def tcr_block(block: p0.Block, *, ctx: Context, expected: ty.Type|None=None) -> hir.AST:
    # TODO: if kind=='<>' then typecheck and resolve needs to behave differently, e.g. because `|` means `type union`, not regular `or`

    # open a new scope if the block is a scoped block
    type_block = block.kind == '<>'
    if block.kind == '{}':
        ctx = replace(
            ctx,
            declarations=ctx.declarations.new_child(),
            binding_scopes=ctx.binding_scopes.new_child(),
            label_scopes=(*ctx.label_scopes, _collect_label_scope(block, ctx=ctx)),
        )

    _collect_block_bindings(block, ctx=ctx)

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
            deferred_functions.add(id(item))
            try:
                signature = signature_of(expression, ctx=ctx)
            except ReportException:
                continue
            if signature is None:
                continue
            binding = ctx.binding_registry.by_syntax[id(item)]
            binding.type = signature
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
        item_expected = expected if expected is not None and len(block.inner) == 1 else None
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
            # otherwise it may be an array. also arrays should handle multi-dimensions via spacing, nested arrays, ;, etc.
            # might also be a generator...
            not_implemented(ctx.srcfile, block.loc, 'array literal')
        case '[)' | '(]':
            if len(results) != 1 or not isinstance(results[0], hir.Range) or results[0].bounds is not None:
                user_error(ctx.srcfile, f'invalid contents for `{block.kind}` range delimiters',
                    Pointer(span=block.loc, message=f'`{block.kind}` may only contain a single bare range expression, got {len(results)} expressions'),
                    hint='e.g. `[1..10)`. use `[]` for arrays or `()` for grouping')
            return replace(results[0], loc=block.loc, bounds=block.kind)
        case '<>':
            # return hir.TypeBlock(block.loc, type..., results) #TODO: handling type of type block based on contained inner items
            not_implemented(ctx.srcfile, block.loc, 'type block')
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
    ftype = ctx.declarations[fname]
    assert isinstance(ftype, (ty.FunctionType, ty.OverloadType)), (
        f'INTERNAL ERROR: builtin function type expected, got {type(ftype)}'
    )
    methods = ftype.methods if isinstance(ftype, ty.OverloadType) else [ftype]
    arg_types = [require_valued(arg.type, ctx.srcfile, arg.loc, f'operand of `{source_name}`') for arg in args]
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
        _contextualize_flow_result(arg, param.type, ctx=ctx)
        for arg, param in zip(args, result.method.pos_or_kw)
    ]
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
    if prefix.op.symbol not in builtins.UNARY_PREFIX_DUNDER_MAP:
        not_implemented(ctx.srcfile, prefix.op.loc, f'prefix operator `{prefix.op.symbol}`')

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


def tcr_binop(binop: p0.BinOp, *, ctx: Context, type_block:bool=False, expected: ty.Type|None=None) -> hir.AST:
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
        left = typecheck_and_resolve_inner(binop.left, ctx=ctx, type_block=type_block)
        return tcr_function_call(left, binop.right, ctx=ctx, expected=expected)

    if isinstance(binop.op, t2.CombinedAssignmentOp):
        return tcr_combined_assign(binop, ctx=ctx)

    # Special cases that don't just typecheck both sides
    symbol = binop.op.symbol if isinstance(binop.op, t1.Operator) else None
    if symbol == '=>': return tcr_function_literal(binop, ctx=ctx, expected=expected)

    if symbol == '|>':
        callable_value = typecheck_and_resolve_inner(binop.right, ctx=ctx)
        return tcr_function_call(callable_value, binop.left, ctx=ctx, expected=expected)

    if symbol == 'transmute':
        item = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        require_valued(item.type, ctx.srcfile, item.loc, 'transmute operand')
        target = ast_to_type(binop.right, ctx=ctx)
        return hir.Transmute(binop.loc, target, item)

    if symbol == 'as':
        not_implemented(ctx.srcfile, binop.op.loc, 'value conversion with `as`')

    if symbol in ('=','::',':='):
        return tcr_assign(binop, ctx=ctx, expected=expected)

    if isinstance(binop.op, t2.InvertedComparisonOp):
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
    right = typecheck_and_resolve_inner(binop.right, ctx=ctx, type_block=type_block)
    
    match binop.op:
        case t2.QJuxtapose():
            not_implemented(ctx.srcfile, binop.loc, 'quantum juxtapose')
        case t2.IndexJuxtapose():
            not_implemented(ctx.srcfile, binop.loc, 'index juxtapose')
        case t2.MultiplyJuxtapose():
            # TODO: need table for binop compatibility
            not_implemented(ctx.srcfile, binop.loc, 'multiply juxtapose')
        case t2.RangeJuxtapose(): not_implemented(ctx.srcfile, binop.loc, 'range juxtapose')
        case t2.EllipsisJuxtapose(): not_implemented(ctx.srcfile, binop.loc, 'ellipsis juxtapose')
        case t2.TypeParamJuxtapose(): not_implemented(ctx.srcfile, binop.loc, 'type parameterization')
        case t2.SemicolonJuxtapose(): not_implemented(ctx.srcfile, binop.loc, 'semicolon juxtapose')
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




def tcr_assignment_target(target: p0.AST, *, ctx: Context) -> hir.ExpressedIdentifier:
    """Resolve a Stage 1 assignment target, currently limited to declared identifiers."""
    if not isinstance(target, p0.Atom) or not isinstance(target.item, t1.Identifier):
        not_implemented(ctx.srcfile, target.loc, 'non-identifier assignment target')
    resolved = tcr_identifier(target.item, ctx=ctx)
    assert isinstance(resolved, hir.ExpressedIdentifier)
    return resolved

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
    
    left = typecheck_and_resolve_inner(left, ctx=ctx) if left is not None else None
    right = typecheck_and_resolve_inner(right, ctx=ctx) if right is not None else None
    #TODO: handle if left or right have comma, split out step pair
    return hir.Range(ast.loc, 'range', bounds=None, step_pair=None, left=left, right=right)



def typefunc_from_hir_params(
    pos_or_kw_args: list[hir.Param],
    kw_only_args: list[hir.Param | hir.BoundParam],
    rest_args: hir.Param | hir.BoundParam | None,
    rettype: ty.Type,
) -> ty.FunctionType:
    pos = [ty.PosOrKwArg(p.name, p.type if p.type != ty.INFERRED_TYPE else ty.TOP_TYPE) for p in pos_or_kw_args]
    kw: list[ty.KwOnlyArg] = []
    for p in kw_only_args:
        ptype = p.type if p.type != ty.INFERRED_TYPE else ty.TOP_TYPE
        required = not isinstance(p, hir.BoundParam)
        kw.append(ty.KwOnlyArg(p.name, ptype, required))
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
    """Parse the required positional slots to the left of a function type's `:>`."""
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
        else:
            args.append(ty.PosOrKwArg(None, ast_to_type(item, ctx=ctx)))
    return args


def ast_to_type(ast: p0.AST, *, ctx: Context) -> ty.Type:
    """convert an AST from a position that is expected to be a type into a type"""
    match ast:
        case p0.Atom(item=t1.Identifier(name=name)):
            return name

        case p0.Block(kind='<>'|'()', inner=[inner]):
            return ast_to_type(inner, ctx=ctx)

        case p0.BinOp(op=t1.Operator(symbol=':>')):
            return ty.FunctionType(
                _function_type_args(ast.left, ctx=ctx),
                [],
                None,
                ast_to_type(ast.right, ctx=ctx),
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

def collect_function_signature_args(signature: p0.AST, *, ctx: Context) -> tuple[list[hir.Param], list[hir.Param|hir.BoundParam], hir.Param|hir.BoundParam|None]:
    """
    collect the parameters from a function signature
    
    Returns:
        list of positional or keyword parameters (all unbound)
        list of keyword only parameters (bound or unbound)
        ...rest parameter (if any) or None (bound or unbound)
    """

    # make sure we are operating on a block at the top level
    if not isinstance(signature, p0.Block): return collect_function_signature_args(p0.Block(signature.loc, [signature], kind='()'))

    pos_or_kw_args: list[hir.Param] = []
    kw_only_args: list[hir.Param|hir.BoundParam] = []
    saw_rest: bool = False
    rest_args: hir.Param|hir.BoundParam|None = None
    for item in signature.inner:
        match item:
            case p0.Atom(item=t1.Identifier(name='...')):
                if saw_rest:
                    user_error(ctx.srcfile, 'multiple `...` in function signature',
                        Pointer(span=item.loc, message='second `...` here'),
                        hint='a function signature may contain at most one `...` divider/rest parameter')
                saw_rest = True
            case p0.Atom(item=t1.Identifier(name=name)):
                (kw_only_args if saw_rest else pos_or_kw_args).append(hir.Param(name, type=ty.INFERRED_TYPE))
            case p0.BinOp(op=t1.Operator(symbol=':'), left=p0.Atom(item=t1.Identifier(name=name))):
                (kw_only_args if saw_rest else pos_or_kw_args).append(hir.Param(name, type=ast_to_type(item.right, ctx=ctx)))
            case p0.BinOp(op=t1.Operator(symbol='='), left=p0.Atom(item=t1.Identifier(name=name)), right=p0.AST() as right):
                kw_only_args.append(hir.BoundParam(name, type=ty.INFERRED_TYPE, value=typecheck_and_resolve_inner(right, ctx=ctx)))
            case p0.BinOp(op=t1.Operator(symbol='='), left=p0.BinOp(op=t1.Operator(symbol=':'), left=p0.Atom(item=t1.Identifier(name=name)), right=p0.AST() as typeexpr), right=p0.AST() as right):
                kw_only_args.append(hir.BoundParam(name, type=ast_to_type(typeexpr, ctx=ctx), value=typecheck_and_resolve_inner(right, ctx=ctx)))
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
) -> tuple[list[hir.AST], dict[str, hir.AST]]:
    """Typecheck call args from p0, splitting positional vs `name=value` keywords."""
    if isinstance(right, p0.Block):
        items = list(right.inner)
    else:
        items = [right]

    pos_args: list[hir.AST] = []
    kw_args: dict[str, hir.AST] = {}
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
                arg = typecheck_and_resolve_inner(value, ctx=ctx, expected=expected_arg)
                kw_args[name] = check_against(arg, expected_arg, ctx=ctx) if expected_arg is not None else arg
            case _:
                index = len(pos_args)
                expected_arg = method.pos_or_kw[index].type if method is not None and index < len(method.pos_or_kw) else None
                arg = typecheck_and_resolve_inner(item, ctx=ctx, expected=expected_arg)
                pos_args.append(check_against(arg, expected_arg, ctx=ctx) if expected_arg is not None else arg)
    return pos_args, kw_args


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


def tcr_function_call(left: hir.AST, right: p0.AST, *, ctx: Context, expected: ty.Type|None=None) -> hir.FunctionCall:
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
    pos_args, kw_args = parse_call_arguments(right, ctx=ctx, method=contextual_method)
    pos_types = [require_valued(a.type, ctx.srcfile, a.loc, 'function call argument') for a in pos_args]
    kw_types = {k: require_valued(v.type, ctx.srcfile, v.loc, f'keyword argument `{k}`') for k, v in kw_args.items()}
    try:
        expected_return = expected if expected not in (None, ty.VOID_TYPE, ty.INFERRED_TYPE) else None
        result = ctx.type_system.match_best_function(
            methods,
            pos_types,
            kw_types,
            expected_return=expected_return,
        )
    except ty.DispatchError as e:
        type_error(ctx.srcfile, 'no matching method for call',
            Pointer(span=left.loc, message='calling this'),
            Pointer(span=right.loc, message=str(e)))

    contextual_pos_args = [
        _contextualize_flow_result(arg, param.type, ctx=ctx)
        for arg, param in zip(pos_args, result.method.pos_or_kw)
    ]
    parameter_types = {
        param.name: param.type
        for param in [*result.method.pos_or_kw, *result.method.kw_only]
    }
    contextual_kw_args = {
        name: _contextualize_flow_result(arg, parameter_types[name], ctx=ctx)
        for name, arg in kw_args.items()
    }
    return hir.FunctionCall(
        Span(left.loc.start, right.loc.stop),
        result.method.ret,
        left,
        apply_promotions(contextual_pos_args, result.promote_pos),
        contextual_kw_args,
        result.method_index if isinstance(left.type, ty.OverloadType) else None,
    )


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

def tcr_identifier(id: t1.Identifier, *, ctx: Context, expected: ty.Type|None=None) -> hir.AST:
    if id.name in ctx.declarations:
        binding = ctx.binding_scopes.get(id.name)
        return hir.ExpressedIdentifier(
            id.loc,
            ctx.declarations[id.name],
            id.name,
            binding_id=binding.id if binding is not None else None,
        )

    user_error(ctx.srcfile, f'undefined identifier `{id.name}`',
        Pointer(span=id.loc, message='not found in this scope'))





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
    
    print(repr(ast))
    print()
    print(str(ast))
    
if __name__ == '__main__':
    test()