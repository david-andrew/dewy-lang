"""
semantic analysis pass 0: 
- type checking
- ambiguity resolution
"""
from dataclasses import dataclass, replace, field
from collections import ChainMap
from ..parser import p0, t2, t1, t0
from . import hir, ty, builtins
from .errors import TypeCheckError, NotImplementedYet, type_error, user_error, not_implemented, require_valued
from .hir_display import type_to_dewy
from ..reporting import SrcFile, ReportException, Pointer, Span


@dataclass
class Catcher:
    """non-local exits bound for one boundary. 
    E.g. top level return is illegal because there is nothing to catch it. Inside a function body return is valid"""
    returns: list[tuple[Span, ty.Type]] = field(default_factory=list)
    expected: ty.Type | None = None  # the boundary's annotated `:>` type, checked at each return site

@dataclass
class Context:
    """global context for the typechecker"""
    srcfile: SrcFile
    declarations: ChainMap[str, ty.Type] = field(default_factory=ChainMap) #TODO: handling different scopes...
    type_system: ty.TypeSystem = field(default_factory=ty.TypeSystem)
    catcher: Catcher | None = None  # installed by the nearest enclosing return boundary
    # TODO: etc stuff

def typecheck_and_resolve(srcfile: SrcFile) -> hir.AST:
    # set up the base type system/builtins
    type_system = ty.TypeSystem()
    builtins.apply_builtin_promote_rules(type_system)
    declarations = ChainMap(builtins.builtin_types)
    
    ctx = Context(srcfile, declarations, type_system)
    block = p0.parse(srcfile)
    return tcr_block(block, ctx=ctx)

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
            if ctx.catcher is not None:
                assert fork.catcher is not None
                ctx.catcher.returns[:] = fork.catcher.returns
            return result

        
        case p0.KeywordExpr(parts=[t1.Keyword(name='let'|'const'), *_]):
            return tcr_declare(ast, ctx=ctx)

        case p0.KeywordExpr(parts=[t1.Keyword(name='import'|'from'), *_]):
            return tcr_import(ast, ctx=ctx)
        
        case p0.KeywordExpr(parts=[t1.Keyword(name='return'), *_]):
            return tcr_return(ast, ctx=ctx, expected=expected)

        # etc. keyword cases as outlined in t2
        case p0.KeywordExpr(parts=[t1.Keyword(name=name), *_]):
            not_implemented(ctx.srcfile, ast.loc, f'`{name}` expression')
        case p0.KeywordExpr():
            raise ValueError(f'INTERNAL ERROR: unrecognized keyword expression structure: {ast=}')

        case p0.BinOp(op=t1.Operator(symbol=':='|'='|'::')):
            return tcr_assign(ast, ctx=ctx)

        case p0.Block(): return tcr_block(ast, ctx=ctx, expected=expected)
        case p0.BinOp(): return tcr_binop(ast, ctx=ctx, type_block=type_block, expected=expected)
        case p0.Atom(item=t1.Identifier(name='..')): return hir.Range(ast.item.loc, 'range', bounds=None, step_pair=None, left=None, right=None)
        case p0.Atom(item=t1.Identifier()): return tcr_identifier(ast.item, ctx=ctx)
        case p0.Atom(item=t1.String(content=content)): return hir.String(ast.item.loc, 'string', content)
        case p0.Atom(item=t1.Integer(value=value)):
            # integer literals adopt a compatible expected numeric type directly
            # (e.g. `let x:float = 1` makes a float literal, not a cast on an int literal)
            t = 'int'
            if isinstance(expected, str) and expected != 'int' and ctx.type_system.is_subtype(expected, 'number'):
                t = expected
            return hir.Integer(ast.item.loc, t, value.prefix, t0.parse_integer(value.src, value.prefix))
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
                op=t1.Operator(symbol='='|'::'|':=' as op),
                right=p0.AST() as right)
            ]:
            expr = typecheck_and_resolve_inner(right, ctx=ctx)
            #TODO: perhaps special handling if expr.type is VOID_TYPE.
            #      also it shouldn't be possible for it to be inferred type, but may need to check/handle...

            # if this declaration was pre-bound by the two-phase pass, verify the checked
            # type matches the pre-bound signature rather than silently overwriting it
            prebound = ctx.declarations.maps[0].get(name)
            if isinstance(prebound, ty.FunctionType) and isinstance(expr.type, ty.FunctionType):
                assert ctx.type_system.function_subtype(expr.type, prebound) and ctx.type_system.function_subtype(prebound, expr.type), \
                    f'INTERNAL ERROR: checked function type {expr.type} does not match the pre-bound signature {prebound} for `{name}`'

            # use the type directly from the expression since no type annotation was provided
            ctx.declarations[name] = expr.type

            return hir.Declare(ast.loc, ty.VOID_TYPE, keyword, name, None, expr)
        
        case [
            t1.Keyword(name='let'|'const' as keyword),
            p0.BinOp(
                left=p0.BinOp(
                    left=p0.Atom(item=t1.Identifier(name=name)),
                    op=t1.Operator(symbol=':'),
                    right=p0.AST() as typeexpr),
                op=t1.Operator(symbol='='|'::'|':=' as op),
                right=p0.AST() as right)
            ]:
            # decl assign + type annotation: check the expression against the annotation
            annotation = ast_to_type(typeexpr, ctx=ctx)
            expr = typecheck_and_resolve_inner(right, ctx=ctx, expected=annotation)
            expr = check_against(expr, annotation, ctx=ctx)
            ctx.declarations[name] = annotation
            return hir.Declare(ast.loc, ty.VOID_TYPE, keyword, name, annotation, expr)
        
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
    not_implemented(ctx.srcfile, ast.loc, 'assignment')

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

def tcr_block(block: p0.Block, *, ctx: Context, expected: ty.Type|None=None) -> hir.AST:
    # TODO: if kind=='<>' then typecheck and resolve needs to behave differently, e.g. because `|` means `type union`, not regular `or`

    # open a new scope if the block is a scoped block
    type_block = block.kind == '<>'
    if block.kind == '{}': ctx = replace(ctx, declarations=ctx.declarations.new_child())

    # pass 1: pre-bind fully annotated function declarations before checking anything,
    # so bodies checked in pass 2 can refer to them (buys mutual and self recursion)
    if not type_block:
        for item in block.inner:
            match item:
                case p0.KeywordExpr(parts=[
                        t1.Keyword(name='let'|'const'),
                        p0.BinOp(
                            left=p0.Atom(item=t1.Identifier(name=name)),
                            op=t1.Operator(symbol='='|'::'|':='),
                            right=p0.BinOp(op=t1.Operator(symbol='=>')) as fn_ast)]):
                    try:
                        sig = signature_of(fn_ast, ctx=ctx)
                    except ReportException:
                        continue  # pass 2 will report the problem with full context
                    if sig is not None:
                        ctx.declarations[name] = sig

    # pass 2: typecheck and resolve the inner items.
    # `()` / `{}` are non-semantic (aside from `{}` opening a scope), so an expected type
    # must flow through them. For now only the single-item wrapper case forwards it —
    # enough for `():>float => {1}` / `(1)` to match bare `1`.
    # TODO: full generality — push expected into the expressed-value slots of a multi-item
    # block (skipping void/never items like declarations), and when expected is a
    # SequenceType distribute it pointwise across those slots. Can't forward expected to
    # every item blindly: `{ let x = 1; x }` must not shove the outer expected into the decl.
    if expected is not None and len(block.inner) == 1:
        results = [typecheck_and_resolve_inner(block.inner[0], ctx=ctx, type_block=type_block, expected=expected)]
    else:
        results = [typecheck_and_resolve_inner(item, ctx=ctx, type_block=type_block) for item in block.inner]

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
        return tcr_function_call(left, binop.right, ctx=ctx)

    # Special cases that don't just typecheck both sides
    symbol = binop.op.symbol if isinstance(binop.op, t1.Operator) else None
    if symbol == '=>': return tcr_function_literal(binop, ctx=ctx, expected=expected)

    if symbol in ('=','::',':='):
        #TODO: determine if assignment or declaration based on if the right already declared
        right = typecheck_and_resolve_inner(binop.right, ctx=ctx)
        target = tcr_assignment_target(binop.left, right, ctx=ctx)
        not_implemented(ctx.srcfile, binop.loc, 'bare assignment')

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
        case t2.CombinedAssignmentOp(): not_implemented(ctx.srcfile, binop.loc, 'combined assignment operator')
        case t2.InvertedComparisonOp(): not_implemented(ctx.srcfile, binop.loc, 'inverted comparison operator')
        case t2.BroadcastOp(): not_implemented(ctx.srcfile, binop.loc, 'broadcast operator')
    
    # TODO: eventually should be able to remove this check once all the arms of the above match are implemented
    assert isinstance(binop.op, t1.Operator), f'INTERNAL ERROR: unexpected operator type: {binop.op}'


    # general case, delegate to the builtin __dunder__ method
    if binop.op.symbol in builtins.BINOP_DUNDER_MAP:
        fname = builtins.BINOP_DUNDER_MAP[binop.op.symbol]
        ftype = ctx.declarations[fname]
        assert isinstance(ftype, (ty.FunctionType, ty.OverloadType)), f'INTERNAL ERROR: builtin function type expected, got {type(ftype)}'
        methods = ftype.methods if isinstance(ftype, ty.OverloadType) else [ftype]
        try:
            result = ctx.type_system.match_best_function(methods, [left.type, right.type])
        except ty.DispatchError as e:
            type_error(ctx.srcfile, f'no matching overload for operator `{binop.op.symbol}`',
                Pointer(span=binop.op.loc, message=str(e)),
                Pointer(span=left.loc, message=f'left operand is `{type_to_dewy(left.type)}`'),
                Pointer(span=right.loc, message=f'right operand is `{type_to_dewy(right.type)}`'))

        # special case for `&`/`and` function overloading
        # preserve the operands and their precise methods instead of emitting a runtime __and__ call.
        # TODO: eventually have a more general path for similar cases
        if _is_overload_constructor(fname, result.method):
            combined = ty.OverloadType(_function_methods(left.type) + _function_methods(right.type))
            return hir.OverloadedFunction(
                Span(left.loc.start, right.loc.stop),
                combined,
                _function_alternates(left) + _function_alternates(right),
            )

        left_arg, right_arg = apply_promotions([left, right], result.promote_pos)
        return hir.FunctionCall(
            Span(left.loc.start, right.loc.stop),
            result.method.ret,
            hir.ExpressedIdentifier(binop.op.loc, result.method, fname),
            [left_arg, right_arg],
            {},
        )
    

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




def tcr_assignment_target(target: p0.AST, right: hir.AST, *, ctx: Context):  # -> UndeclaredIdentifier|Identifier|Unpack|ArrayRangeTarget|etc.
    """
    verify that the assignment target is valid and can receive the right-hand side expression
    """
    not_implemented(ctx.srcfile, target.loc, 'assignment target')

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
    for param in pos_or_kw_args:
        inner_scope[param.name] = param.type
    for param in kw_only_args:
        inner_scope[param.name] = param.type
    if rest_args is not None:
        inner_scope[rest_args.name] = rest_args.type
    annotated = rettype if rettype != ty.INFERRED_TYPE else None
    catcher = Catcher(expected=annotated)
    inner_ctx = replace(ctx, declarations=inner_scope, catcher=catcher)
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

def ast_to_type(ast: p0.AST, *, ctx: Context) -> ty.Type:
    """convert an AST from a position that is expected to be a type into a type"""
    match ast:
        case p0.Atom(item=t1.Identifier(name=name)):
            return name
        
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


def parse_call_arguments(right: p0.AST, *, ctx: Context) -> tuple[list[hir.AST], dict[str, hir.AST]]:
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
                kw_args[name] = typecheck_and_resolve_inner(value, ctx=ctx)
            case _:
                pos_args.append(typecheck_and_resolve_inner(item, ctx=ctx))
    return pos_args, kw_args


def tcr_function_call(left: hir.AST, right: p0.AST, *, ctx: Context, expected: ty.Type|None=None) -> hir.FunctionCall:
    methods: list[ty.FunctionType]
    if isinstance(left.type, ty.FunctionType):
        methods = [left.type]
    elif isinstance(left.type, ty.OverloadType):
        methods = left.type.methods
    else:
        type_error(ctx.srcfile, 'call target is not a function',
            Pointer(span=left.loc, message=f'this has type `{type_to_dewy(left.type)}`, which is not callable'))

    pos_args, kw_args = parse_call_arguments(right, ctx=ctx)
    pos_types = [require_valued(a.type, ctx.srcfile, a.loc, 'function call argument') for a in pos_args]
    kw_types = {k: require_valued(v.type, ctx.srcfile, v.loc, f'keyword argument `{k}`') for k, v in kw_args.items()}
    try:
        result = ctx.type_system.match_best_function(methods, pos_types, kw_types)
    except ty.DispatchError as e:
        type_error(ctx.srcfile, 'no matching method for call',
            Pointer(span=left.loc, message='calling this'),
            Pointer(span=right.loc, message=str(e)))

    return hir.FunctionCall(
        Span(left.loc.start, right.loc.stop),
        result.method.ret,
        left,
        apply_promotions(pos_args, result.promote_pos),
        kw_args,
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
        return hir.ExpressedIdentifier(id.loc, ctx.declarations[id.name], id.name)

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