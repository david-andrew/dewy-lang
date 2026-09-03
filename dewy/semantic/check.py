"""
semantic analysis pass 0: 
- type checking
- ambiguity resolution
"""
import copy
import os
from pathlib import Path
from dataclasses import dataclass, replace, field, fields, is_dataclass
from fractions import Fraction
from collections import ChainMap
from itertools import count
from typing import Callable, Literal, NoReturn, cast
from ..parser import p0, t2, t1, t0
from . import bindings as sb
from . import builtins, hir, ty
from .errors import TypeCheckError, UserError, NotImplementedYet, type_error, user_error, user_warning, not_implemented, require_valued
from .hir_display import type_to_dewy
from ..reporting import SrcFile, ReportException, Pointer, Span, Error


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
    refinement_subject: str | None = None
    """The name being annotated (`d:int64<d not=? 0>`): inside its type's
    parameterize blocks a comparison on that name is a refinement of the value."""
    length_bounds: dict[int, int] = field(default_factory=dict)  # proven minimum lengths of runtime-length arrays
    key_facts: dict[tuple[int, tuple[str, object]], tuple[str | None, int | None]] = field(default_factory=dict)
    """Proven dictionary keys: (dictionary route id, key identity) -> (position local, literal entry index)."""
    type_alias_asts: dict[int, p0.AST] = field(default_factory=dict)
    resolving_type_aliases: set[int] = field(default_factory=set)
    named_types: dict[int, ty.NamedType] = field(default_factory=dict)  # recursive alias references, by alias binding id
    generic_instances: list[hir.Declare] = field(default_factory=list)  # hoisted instantiations of generic functions (shared list)
    module: 'Context | None' = None  # the module-level context (methods are declared in it)
    pending_methods: list[tuple[sb.Binding, ty.ObjectType]] = field(default_factory=list)  # aliases whose methods are not declared yet (shared list)
    synthesized: list[object] = field(default_factory=list)
    """Syntax the checker synthesizes (assert directives, constructor literals,
    method bodies) is kept alive for the whole compile: bindings are keyed by
    `id(node)`, and a freed node's id could otherwise be reused."""
    object_strings: dict[str, sb.Binding] = field(default_factory=dict)
    """The hidden field-by-field `as string` conversions, by object type (shared)."""
    hoisted: list[hir.AST] | None = None
    """Statements a loop capture (`[loop …]`) inside the statement being checked
    needs before it: the capture array's declaration and the loop that fills it."""
    module_loader: object | None = None
    module_namespaces: ChainMap[str, object] = field(default_factory=ChainMap)
    module_declared_names: set[str] = field(default_factory=set)
    grown_array_names: frozenset[str] = frozenset()  # names some `.push`/`.pop`/... targets
    target: str = 'x86_64'  # backend target: `$target`
    allow_place_expression: bool = False
    # TODO: etc stuff

def typecheck_and_resolve(
    srcfile: SrcFile,
    *,
    include_prelude: bool | None = None,
    target: str = 'x86_64',
    test: bool = False,
) -> hir.AST:
    """Check a program; with ``test``, the entry module's `$test` functions get a generated runner as its entry."""
    from .modules import typecheck_program

    return typecheck_program(
        srcfile,
        include_prelude=(
            srcfile.path is not None
            if include_prelude is None
            else include_prelude
        ),
        target=target,
        test=test,
    )


_parsed_modules: dict[tuple[str, str], p0.Block] = {}
"""Parse trees of path-backed modules, keyed by path and exact contents.

Parsing the prelude dominates the cost of compiling a small program, and the
checker never mutates a parse tree (every rewrite builds new nodes), so the
same tree serves every compilation of an unchanged file. In-memory sources
are not cached: each is parsed once per compilation anyway.
"""


def _parse_cache_path(srcfile: SrcFile) -> Path | None:
    """Where a module's parsed AST is cached on disk, keyed by its text and the parser's source.

    Parsing the prelude dominates every compile (the tokenizer's class
    dispatch is slow in Python); the pickled AST loads ~30× faster. The key
    covers the module text and the parser modules' own text, so a grammar
    change invalidates every entry.
    """
    if srcfile.path is None or os.environ.get('DEWY_NO_PARSE_CACHE'):
        return None
    import hashlib
    digest = hashlib.sha256()
    digest.update(_PARSER_SOURCE_DIGEST)
    digest.update(srcfile.body.encode('utf-8'))
    return Path('__dewycache__') / 'parse' / f'{Path(str(srcfile.path)).stem}-{digest.hexdigest()[:24]}.pickle'


def _parser_source_digest() -> bytes:
    import hashlib
    from ..parser import t0, t2
    digest = hashlib.sha256()
    for module in (t0, t1, t2, p0):
        digest.update(Path(module.__file__).read_bytes())
    return digest.digest()


_PARSER_SOURCE_DIGEST = _parser_source_digest()


@dataclass(frozen=True)
class ModuleDirectives:
    """The file-level metatags stripped from a module before checking."""

    no_prelude: bool
    prototype: bool
    prototype_warnings: bool


def _parse_module(srcfile: SrcFile, *, target: str = 'x86_64') -> tuple[p0.Block, ModuleDirectives]:
    key = (str(srcfile.path), srcfile.body) if srcfile.path is not None else None
    block = _parsed_modules.get(key) if key is not None else None
    if block is None:
        import pickle
        cache_path = _parse_cache_path(srcfile)
        if cache_path is not None and cache_path.is_file():
            try:
                block = pickle.loads(cache_path.read_bytes())
            except Exception:
                block = None   # a stale or corrupt entry: parse and rewrite it
        if block is None:
            block = p0.parse(srcfile)
            if cache_path is not None:
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = cache_path.with_suffix('.tmp')
                    tmp.write_bytes(pickle.dumps(block, protocol=pickle.HIGHEST_PROTOCOL))
                    tmp.replace(cache_path)
                except OSError:
                    pass   # an unwritable cache only costs the parse
        if key is not None:
            _parsed_modules[key] = block
    no_prelude: bool | None = None
    prototype: bool | None = None
    prototype_warnings: bool | None = None
    items: list[p0.AST] = []
    for item in block.inner:
        if (
            isinstance(item, p0.BinOp)
            and isinstance(item.op, t1.Operator)
            and item.op.symbol == '='
            and isinstance(item.left, p0.Atom)
            and isinstance(item.left.item, t1.Metatag)
            and item.left.item.name == 'supported_targets'
        ):
            _check_supported_targets(item, srcfile, target)
            continue
        if isinstance(item, p0.Atom) and isinstance(item.item, t1.Metatag) and item.item.name == 'prototype':
            prototype = True   # the bare spelling: `$prototype`
            continue
        if (
            isinstance(item, p0.BinOp)
            and isinstance(item.op, t1.Operator)
            and item.op.symbol == '='
            and isinstance(item.left, p0.Atom)
            and isinstance(item.left.item, t1.Metatag)
            and item.left.item.name in ('prototype', 'prototype_warnings')
        ):
            if not isinstance(item.right, p0.Atom) or not isinstance(item.right.item, t1.Bool):
                user_error(
                    srcfile,
                    f'`${item.left.item.name}` must be a boolean literal',
                    Pointer(span=item.right.loc, message='expected `true` or `false`'),
                )
            if item.left.item.name == 'prototype':
                prototype = item.right.item.value
            else:
                prototype_warnings = item.right.item.value
            continue
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
    return replace(block, inner=items), ModuleDirectives(
        bool(no_prelude),
        bool(prototype),
        prototype_warnings is None or prototype_warnings,
    )


def _check_supported_targets(item: p0.BinOp, srcfile: SrcFile, target: str) -> None:
    """`$supported_targets = ["x86_64" ...]` rejects compilation for other targets."""
    supported: list[str] = []
    entries = item.right.inner if isinstance(item.right, p0.Block) else [item.right]
    for entry in entries:
        if not (isinstance(entry, p0.Atom) and isinstance(entry.item, t1.String)):
            user_error(
                srcfile,
                '`$supported_targets` must list string target names',
                Pointer(span=entry.loc, message='expected a string such as `"x86_64"`'),
            )
        supported.append(entry.item.content)
    if target not in supported:
        user_error(
            srcfile,
            f'module does not support target `{target}`',
            Pointer(span=item.loc, message='supported: ' + ', '.join(supported)),
        )


def _typecheck_module(
    srcfile: SrcFile,
    *,
    block: p0.Block | None = None,
    type_system: ty.TypeSystem | None = None,
    registry: sb.BindingRegistry | None = None,
    module_loader: object | None = None,
    prelude_bindings: dict[str, sb.Binding] | None = None,
    target: str = 'x86_64',
    test: bool = False,
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
    for type_name, attribute in ((RATIONAL_TYPE_NAME, 'rational_object'), (FIXED_TYPE_NAME, 'fixed_object'), (BIGINT_TYPE_NAME, 'bigint_object')):
        prelude_type = prelude_bindings.get(type_name)
        if prelude_type is not None and prelude_type.type_value is not None:
            # `BigInt = 0 | [...]`: the object member is the representation constants materialize into
            setattr(type_system, attribute, _union_object_member(prelude_type.type_value))
    declarations = ChainMap(prelude_declarations, builtins.builtin_types)

    if block is None:
        block, _ = _parse_module(srcfile)
    block, tests = _extract_tests(block, srcfile=srcfile)
    if test:
        runner, srcfile = _synthesize_test_runner(tests, block, srcfile=srcfile)
        block = replace(block, inner=[*block.inner, *runner])
    ctx = Context(
        srcfile,
        declarations,
        type_system,
        binding_scopes=ChainMap(prelude_bindings),
        binding_registry=registry or sb.BindingRegistry(),
        module_loader=module_loader,
        module_declared_names=set(),
        grown_array_names=_grown_array_names(block),
        target=target,
    )
    seen_names: set[str] = set()
    for item in block.inner:
        declaration = _block_declaration_parts(item, seen_names, ctx=ctx)   # `let x = …` and a bare `x = …` alike
        if declaration is not None:
            ctx.module_declared_names.add(declaration[0])
    checked = tcr_block(block, ctx=ctx)
    if not isinstance(checked, hir.Block):
        raise TypeError('INTERNAL ERROR: source module did not produce a block')
    # A module-level array the module grows is a runtime-length array to
    # every other module too (its binding otherwise exports the initializer's
    # exact type, and `loop b in buffer` elsewhere would iterate zero times).
    for item in checked.items:
        if isinstance(item, hir.Declare) and item.name in ctx.grown_array_names and item.binding_id is not None:
            binding = ctx.binding_registry.by_id[item.binding_id]
            if isinstance(binding.type, ty.ArrayType) and binding.type.length is not None:
                binding.type = replace(binding.type, length=None)
    _declare_pending_methods(ctx=ctx.module if ctx.module is not None else ctx)  # methods never called still get checked
    if ctx.generic_instances:
        # instantiations of generic functions, methods, and constructor
        # overloads are ordinary module-level functions; they carry no state,
        # so they are declared first and module-level code may call them
        checked = replace(checked, items=[*ctx.generic_instances, *checked.items])
    return checked, ctx

# ---------------------------------------------------------------- `$test`
TEST_ENTRY_NAME = hir.TEST_ENTRY_NAME

_TEST_PARAMETERS = ('cases',)


@dataclass
class _TestSpec:
    """One `$test` annotation and the function declaration it marks."""

    loc: Span                     # the annotation, where problems with the test's setup are reported
    name: str                     # the declared function
    cases: p0.AST | None          # `cases=` — an array (or tuple) of arguments, one call per element
    takes_parameters: bool        # the function's parameter list is not `()`


def _test_annotation(item: p0.AST) -> tuple[Span, p0.Block | None] | None:
    """`$test` or `$test(parameters)` as a statement: its span and its parameter block."""
    if isinstance(item, p0.Atom) and isinstance(item.item, t1.Metatag) and item.item.name == 'test':
        return item.loc, None
    if (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, (t2.QJuxtapose, t2.CallJuxtapose))
        and isinstance(item.left, p0.Atom)
        and isinstance(item.left.item, t1.Metatag)
        and item.left.item.name == 'test'
        and isinstance(item.right, p0.Block)
    ):
        return item.loc, item.right
    return None


def _extract_tests(block: p0.Block, *, srcfile: SrcFile) -> tuple[p0.Block, list[_TestSpec]]:
    """Take the `$test` annotations out of a module and pair each with the declaration after it.

    The annotation is a statement of its own (like a scope metatag), so this
    is adjacency: `$test` (or `$test(cases=…)`) marks the next item, which
    must declare a function. Tests are ordinary functions otherwise — they
    are checked and callable like any other — and the annotation only feeds
    the generated runner (see `_synthesize_test_runner`).
    """
    items: list[p0.AST] = []
    tests: list[_TestSpec] = []
    index = 0
    while index < len(block.inner):
        item = block.inner[index]
        annotation = _test_annotation(item)
        if annotation is None:
            items.append(item)
            index += 1
            continue
        loc, parameters = annotation
        following = block.inner[index + 1] if index + 1 < len(block.inner) else None
        declaration = _declaration_parts(following) if following is not None else None
        if (
            following is None
            or declaration is None
            or not (
                isinstance(declaration[1], p0.BinOp)
                and isinstance(declaration[1].op, t1.Operator)
                and declaration[1].op.symbol == '=>'
            )
        ):
            user_error(
                srcfile,
                '`$test` must mark a function declaration',
                Pointer(span=loc, message='expected `let name = (…) => …` after the annotation'),
                hint='`$test` (or `$test(cases=…)`) goes on the line before the test function',
            )
        name, function = declaration
        assert isinstance(function, p0.BinOp)
        params = function.left
        takes_parameters = not (isinstance(params, p0.Block) and params.kind == '()' and not params.inner)
        cases: p0.AST | None = None
        if parameters is not None:
            seen: set[str] = set()
            for parameter in parameters.inner:
                if not (
                    isinstance(parameter, p0.BinOp)
                    and isinstance(parameter.op, t1.Operator)
                    and parameter.op.symbol == '='
                    and isinstance(parameter.left, p0.Atom)
                    and isinstance(parameter.left.item, t1.Identifier)
                ):
                    user_error(
                        srcfile,
                        '`$test` parameters are `name=value` pairs',
                        Pointer(span=parameter.loc, message='this is not a named parameter'),
                        hint=f'the parameters are: {", ".join(f"`{p}`" for p in _TEST_PARAMETERS)}',
                    )
                key = parameter.left.item.name
                if key not in _TEST_PARAMETERS:
                    user_error(
                        srcfile,
                        f'unknown `$test` parameter `{key}`',
                        Pointer(span=parameter.left.loc, message='not a test parameter'),
                        hint=f'the parameters are: {", ".join(f"`{p}`" for p in _TEST_PARAMETERS)}',
                    )
                if key in seen:
                    user_error(srcfile, f'`$test` parameter `{key}` is given twice', Pointer(span=parameter.left.loc, message='second occurrence'))
                seen.add(key)
                cases = parameter.right
        if takes_parameters and cases is None:
            user_error(
                srcfile,
                'this test takes parameters but `$test` gives no cases',
                Pointer(span=params.loc, message='the runner would not know what to pass here'),
                hint='`$test(cases=(1 2 3))` calls the test once per element; `$test(cases=[[a=1 b=2] [a=3 b=4]])` passes each object\'s fields by name',
            )
        if not takes_parameters and cases is not None:
            user_error(
                srcfile,
                'this test takes no parameters, but `$test` gives cases',
                Pointer(span=cases.loc, message='nothing to pass these to'),
                hint='give the test a parameter for each case value, or drop `cases=`',
            )
        tests.append(_TestSpec(loc, name, cases, takes_parameters))
        items.append(following)
        index += 2
    return replace(block, inner=items), tests


def _case_arguments(cases: p0.AST, block: p0.Block, *, srcfile: SrcFile) -> list[str] | None:
    """The argument text of each call when the cases are written out: `[[a=1 b=2] …]` or `(1 2 3)`.

    An object literal passes its fields by name (`a=1 b=2`), any other
    element is the single argument, both spliced from the source as the
    user wrote them. A module constant bound to a literal counts as written
    out; anything else (a computed array) is `None` and is looped over.
    """
    if isinstance(cases, p0.Atom) and isinstance(cases.item, t1.Identifier):
        for item in block.inner:
            declaration = _declaration_parts(item)
            if declaration is not None and declaration[0] == cases.item.name:
                return _case_arguments(declaration[1], block, srcfile=srcfile)
        return None
    if not isinstance(cases, p0.Block) or cases.kind not in ('[]', '()') or not cases.inner:
        return None
    text = srcfile.body
    calls: list[str] = []
    for case in cases.inner:
        if (
            isinstance(case, p0.Block)
            and case.kind == '[]'
            and case.inner
            and all(
                isinstance(field, p0.BinOp)
                and isinstance(field.op, t1.Operator)
                and field.op.symbol == '='
                and isinstance(field.left, p0.Atom)
                and isinstance(field.left.item, t1.Identifier)
                for field in case.inner
            )
        ):
            calls.append(' '.join(
                f'{field.left.item.name}={text[field.right.loc.start:field.right.loc.stop]}'
                for field in case.inner
            ))
        else:
            calls.append(text[case.loc.start:case.loc.stop])
    return calls


def _synthesize_test_runner(tests: list[_TestSpec], block: p0.Block, *, srcfile: SrcFile) -> tuple[list[p0.AST], SrcFile]:
    """The module's test entry, as parsed Dewy appended to the module.

    `__dewy_test_main(args)` calls every `$test` function — once per case,
    passing an object case's fields by name and any other case as the single
    argument — between `_test_begin`/`_test_end` (`library/testing.dewy`),
    and returns the failure count. `--json` selects one JSON object per
    line; `--brief` (from `dewy test dir`) leaves out the summary line. Cases written out as a literal are spliced into the calls as the
    user wrote them; a computed cases array is looped over. The runner's text
    is appended to the module's source (the returned `SrcFile`), so a problem
    in it — a call that does not fit the test's signature — is reported on
    the generated line that makes the call.
    """
    lines: list[str] = [
        '',
        f'# ---- generated by `dewy --test`: the runner for the `$test` functions above',
        f'let {TEST_ENTRY_NAME} = (__dewy_test_args:array<string>):>int64 => {{',
        '    let __dewy_test_json:bool = false',
        '    let __dewy_test_brief:bool = false',
        '    loop __dewy_test_arg in __dewy_test_args {',
        '        if __dewy_test_arg =? "--json" { __dewy_test_json = true }',
        '        if __dewy_test_arg =? "--brief" { __dewy_test_brief = true }',
        '    }',
        '    _test_init(__dewy_test_json)',
    ]
    for number, spec in enumerate(tests, start=1):
        if spec.cases is None:
            lines += [
                '    _test_begin(__dewy_test_json)',
                f'    {spec.name}()',
                f'    _test_end("{spec.name}" (-1) __dewy_test_json)',
            ]
            continue
        arguments = _case_arguments(spec.cases, block, srcfile=srcfile)
        if arguments is not None:
            for index, argument in enumerate(arguments):
                lines += [
                    '    _test_begin(__dewy_test_json)',
                    f'    {spec.name}({argument})',
                    f'    _test_end("{spec.name}" {index} __dewy_test_json)',
                ]
            continue
        cases_text = srcfile.body[spec.cases.loc.start:spec.cases.loc.stop]
        lines += [
            f'    let __dewy_test_index_{number}:int64 = 0',
            f'    loop __dewy_test_case in ({cases_text}) {{',
            '        _test_begin(__dewy_test_json)',
            f'        {spec.name}(__dewy_test_case)',
            f'        _test_end("{spec.name}" __dewy_test_index_{number} __dewy_test_json)',
            f'        __dewy_test_index_{number} += 1',
            '    }',
        ]
    lines += ['    return _test_summary(__dewy_test_json __dewy_test_brief)', '}']
    text = '\n'.join(lines) + '\n'
    # parsed with its offsets already in place after the module's own text
    runner = p0.parse(SrcFile(None, ' ' * len(srcfile.body) + text))
    return list(runner.inner), SrcFile(srcfile.path, srcfile.body + text)


def _sink_ambiguity(ast: p0.AST) -> p0.AST:
    """Push a statement-level parse ambiguity below the operators its readings share.

    `x = load(id).name` parses as two readings of the whole statement (call
    vs. product inside), which the declaration forms cannot match. When every
    reading is the same binary operator over the same left operand, the
    ambiguity belongs to the right operand only.
    """
    if isinstance(ast, p0.KeywordExpr) and len(ast.parts) == 2 and isinstance(ast.parts[1], p0.Ambiguous):
        return replace(ast, parts=[ast.parts[0], _sink_ambiguity(ast.parts[1])])
    if not isinstance(ast, p0.Ambiguous):
        return ast
    candidates = ast.candidates
    first = candidates[0]
    if (
        isinstance(first, p0.BinOp)
        and all(
            isinstance(candidate, p0.BinOp)
            and type(candidate.op) is type(first.op)
            and getattr(candidate.op, 'symbol', None) == getattr(first.op, 'symbol', None)
            and candidate.left == first.left
            for candidate in candidates[1:]
        )
    ):
        right = _sink_ambiguity(p0.Ambiguous(ast.loc, [candidate.right for candidate in candidates]))
        return replace(first, right=right)
    return ast


_ASSERT_LOGICAL_OPERATORS = {'and', 'or', 'nand', 'nor', 'xor', 'xnor'}
_ASSERT_COMPARISON_OPERATORS = {'=?', '>?', '<?', '>=?', '<=?', 'is?', 'isnt?', 'in?'}


_SHAPE_REJECTION_TITLES = ('index target is not an array or string', 'function followed by parentheses is a call', 'call target is not a function')


def _is_shape_rejection(error: ReportException) -> bool:
    """Whether a reading of an ambiguous expression failed only for its shape."""
    title = error.report.title or ''
    return title in _SHAPE_REJECTION_TITLES or title.endswith('needs arguments')


def typecheck_and_resolve_inner(ast: p0.AST, *, ctx: Context, type_block:bool=False, expected: ty.Type|None=None, call_target: bool=False) -> hir.AST:
    ast = _sink_ambiguity(ast)
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
                    length_bounds=dict(ctx.length_bounds),
                    key_facts=dict(ctx.key_facts),
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
                # a reading rejected for its shape (`f x` read as an index, a
                # call read as juxtaposition) says nothing; when one reading got
                # past its shape, its error is the report
                substantive = [r for r in rejections if not _is_shape_rejection(r)]
                if len(substantive) == 1:
                    raise UserError(substantive[0].report)   # definite, like the summary it replaces
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
            ctx.length_bounds.clear()
            ctx.length_bounds.update(fork.length_bounds)
            ctx.key_facts.clear()
            ctx.key_facts.update(fork.key_facts)
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
        case p0.Postfix(op=t1.Operator(symbol='or_throw')): return tcr_or_throw(ast, ctx=ctx)
        case p0.BinOp() if _include_bytes_call(ast) is not None:
            return _tcr_include_bytes(ast.loc, _include_bytes_call(ast), ctx=ctx)   # `$include_bytes(p"…")`
        case p0.BinOp(): return tcr_binop(ast, ctx=ctx, type_block=type_block, expected=expected, call_target=call_target)
        case p0.Atom(item=t1.Identifier(name='..')): return hir.Range(ast.item.loc, 'range', bounds=None, step_pair=None, left=None, right=None)
        case p0.Atom(item=t1.Identifier(name='void')): return hir.Void(ast.item.loc, ty.VOID_TYPE)
        case p0.Atom(item=t1.Identifier(name='none')):
            return hir.NoneValue(ast.item.loc, 'none')
        case p0.Atom(item=t1.Identifier()):
            resolved = tcr_identifier(ast.item, ctx=ctx)
            if call_target or type_block:
                return resolved
            return _auto_call_function_value(resolved, ctx=ctx, expected=expected)
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
        case p0.AssertDirective():
            return tcr_assert(ast, ctx=ctx)
        case p0.Atom(item=t1.Metatag(name='target')):
            # Compile-time string (udewy's `$target`); comparisons against
            # literals fold, so `if $target =? "x86_64" { ... }` resolves
            # during checking.
            return hir.TargetString(ast.loc, ty.StringLiteralType(ctx.target), ctx.target)
        case p0.Atom(item=t1.Metatag(name=name)):
            return tcr_scope_metatag(ast, name=name, ctx=ctx)
        case p0.Atom(item=t1.Real() as real):
            return _real_literal(real, loc=ast.loc, ctx=ctx)
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


def _hoisted_union_field(value: hir.AST, *, ctx: Context) -> hir.AST | None:
    """A union-valued interpolation field that is not a name: bound to a
    hidden local hoisted before the current statement (see `Context.hoisted`),
    so the member flow reads a name. None outside a block body."""
    if ctx.hoisted is None:
        return None
    loc = value.loc
    name = f'__dewy_field_{ctx.binding_registry.next_id}'
    binding = ctx.binding_registry.allocate(_fresh_syntax(ctx), name, 'value', loc)
    binding.type = value.type
    declaration = hir.Declare(loc, ty.VOID_TYPE, 'let', name, value.type, value, binding_id=binding.id)
    binding.declaration = declaration
    ctx.declarations[name] = value.type
    ctx.binding_scopes[name] = binding
    ctx.hoisted.append(declaration)
    return _optional_field_flow(hir.ExpressedIdentifier(loc, value.type, name, binding_id=binding.id), ctx=ctx)


def _readable_object(value: hir.AST, *, ctx: Context) -> hir.AST | None:
    """The value as something read once per arm without effects: itself when it
    is a name or a field, else a hidden local hoisted before the statement
    (None where nothing can be hoisted)."""
    if isinstance(value, (hir.ExpressedIdentifier, hir.MemberAccess)):
        return value
    if ctx.hoisted is None:
        return None
    loc = value.loc
    name = f'__dewy_field_{ctx.binding_registry.next_id}'
    binding = ctx.binding_registry.allocate(_fresh_syntax(ctx), name, 'value', loc)
    binding.type = value.type
    declaration = hir.Declare(loc, ty.VOID_TYPE, 'let', name, value.type, value, binding_id=binding.id)
    binding.declaration = declaration
    ctx.declarations[name] = value.type
    ctx.binding_scopes[name] = binding
    ctx.hoisted.append(declaration)
    return hir.ExpressedIdentifier(loc, value.type, name, binding_id=binding.id)


def _brand_dispatch(value: hir.AST, loc: Span, per_brand: 'Callable[[hir.AST, ty.ObjectType], hir.AST]', otherwise: 'Callable[[hir.AST], hir.AST]', *, ctx: Context) -> hir.AST | None:
    """A string-valued flow over the brands a value may carry at runtime (a
    mint's descendants; the mints minted from a plain structure): one `is?`
    arm per brand, deepest first, reading the value narrowed to it; else the
    static form. None when the value has no such alternatives."""
    plain = ty.unfold(ty.strip_refinement(value.type))
    if isinstance(plain, ty.MetaType):
        alternatives = ty.brand_alternatives(plain.family)
        narrowed_type = lambda brand: ty.MetaType(ty.USER_BRAND_TYPES[brand])
    elif isinstance(plain, ty.ObjectType):
        alternatives = ty.brand_alternatives(plain)
        narrowed_type = lambda brand: ty.USER_BRAND_TYPES[brand]
    else:
        return None
    if not alternatives:
        return None
    readable = _readable_object(value, ctx=ctx)
    if readable is None:
        return None
    arms = [
        hir.IfArm(loc, ty.StringType(), hir.TypeTest(loc, 'bool', readable, ty.USER_BRAND_TYPES[brand], False), per_brand(replace(readable, type=narrowed_type(brand)), ty.USER_BRAND_TYPES[brand]))
        for brand in alternatives
    ]
    return hir.Flow(loc, ty.StringType(), arms, otherwise(readable))


def _typename(value: hir.AST, loc: Span, *, ctx: Context) -> hir.AST:
    """`value.typename`: the minted name a value carries (read from its brand
    word when its static type has descendants), else its structural spelling."""
    def own(node: hir.AST) -> hir.AST:
        plain = ty.unfold(ty.strip_refinement(node.type))
        if isinstance(plain, ty.MetaType):
            plain = plain.family   # a type value names its family's type
        text = plain.brand if isinstance(plain, ty.ObjectType) and ty.user_branded(plain) and plain.brand is not None else type_to_dewy(plain)
        return hir.String(loc, ty.StringLiteralType(text), text)
    dispatched = _brand_dispatch(value, loc, lambda narrowed, _child: own(narrowed), own, ctx=ctx)
    return dispatched if dispatched is not None else own(value)


def _optional_field_flow(value: hir.AST, *, ctx: Context) -> hir.AST | None:
    """A union-typed value (an optional, or a container union of words,
    strings, `none`, and objects) as a string: a flow with one arm per
    member — the text `none`, a member's one-part interpolation, or an
    object member's literal syntax. The value must be a name or a field, so
    reading it once per arm is free of effects."""
    if not isinstance(value, (hir.ExpressedIdentifier, hir.MemberAccess)):
        return None
    plain = ty.strip_refinement(value.type)
    if _optional_container_element(plain):
        payload = ty.optional_payload(plain)
        assert payload is not None
        members: tuple[ty.TypeExpr, ...] = ('none', payload)
    elif _union_container_element(plain):
        found = ty.runtime_union_members(plain)
        assert found is not None
        members = found
    else:
        return None
    loc = value.loc

    def member_text(member: ty.TypeExpr) -> hir.AST:
        if member == 'none':
            return hir.String(loc, ty.StringLiteralType('none'), 'none')
        narrowed = replace(value, type=member)
        structural = _structure_string(narrowed, loc, ctx=ctx)   # an object member: its literal syntax
        if structural is not None:
            return structural
        # a word or string member: a one-part interpolation materializes its text
        return hir.InterpolatedString(loc, ty.StringType(), [_prepared_single_argument(narrowed, ctx=ctx)])

    arms = [
        hir.IfArm(loc, ty.StringType(), hir.TypeTest(loc, 'bool', value, member, False), member_text(member))
        for member in members[:-1]
    ]
    return hir.Flow(loc, ty.StringType(), arms, member_text(members[-1]))


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
        spelled = _spelling_string(value, ctx=ctx)
        if spelled is not None:
            parts.append(spelled)   # a type or a function: its spelling
            continue
        if isinstance(ty.unfold(ty.strip_refinement(value.type)), ty.MetaType):
            parts.append(_typename(value, value.loc, ctx=ctx))   # a type value: its name
            continue
        if value.type == 'none':
            parts.append(hir.String(value.loc, ty.StringLiteralType('none'), 'none'))   # the text of `none`
            continue
        optional_flow = _optional_field_flow(value, ctx=ctx)
        if optional_flow is not None:
            parts.append(optional_flow)   # `none`, or the payload's text
            continue
        if _optional_container_element(ty.strip_refinement(value.type)) or _union_container_element(ty.strip_refinement(value.type)):
            # any other union-valued expression (`xs[i]`, a call): evaluate it
            # once into a hidden local declared before the statement, then the
            # flow tests and reads the local
            named = _hoisted_union_field(value, ctx=ctx)
            if named is not None:
                parts.append(named)
                continue
            user_error(
                ctx.srcfile,
                'a union value in an interpolation must be a name here',
                Pointer(span=value.loc, message=f'this has type `{type_to_dewy(value.type)}`; its member is tested and read separately, and there is no statement to evaluate it before'),
                hint='bind it first: `let item = xs[i]` then `"{item}"`',
            )
        require_valued(
            value.type,
            ctx.srcfile,
            value.loc,
            'string interpolation field',
        )
        # an object interpolates through its own conversion when it declares
        # one: `p"{root}/{name}"` is the join because `Path` declares
        # `__as__ = ():>string => path` (quantities and the number objects
        # print through their own paths; anything else is rejected where the
        # field is printed or materialized)
        converted = _brand_dispatch(
            value, value.loc,
            lambda narrowed, _child: _static_string_conversion(narrowed, value.loc, ctx=ctx),
            lambda readable: _static_string_conversion(readable, value.loc, ctx=ctx),
            ctx=ctx,
        )   # a value carrying a child's brand converts as that child
        if converted is None:
            converted = _conversion_method_call(value, ty.StringType(), value.loc, ctx=ctx)
        if converted is None:
            # a container or a plain object: its literal syntax (`[1 2 3]`, `[x=1 y="a"]`)
            converted = _structure_string(value, value.loc, ctx=ctx)
        if converted is not None:
            value = converted
        parts.append(value)
    return hir.InterpolatedString(ast.loc, ty.StringType(), parts)


def _conversion_method_call(value: hir.AST, target: ty.Type, loc: Span, *, ctx: Context) -> hir.AST | None:
    """`value as target` through the value's type, when it declares `__as__` with a result that fits ``target``.

    The conversion protocol for declared types: a zero-argument method
    `__as__ = ():>T => …` says how a value converts to `T`; `x as T` and
    string interpolation (`T` = `string`) call it. Nothing about a type's
    name or shape is special — `Path` converts to its text this way.
    """
    unfolded = ty.unfold(ty.strip_refinement(value.type))
    if not isinstance(unfolded, ty.ObjectType):
        return None
    function_binding = _conversion_method_binding(unfolded, target, loc, ctx=ctx)
    if function_binding is None:
        return None
    function_type = function_binding.type
    assert isinstance(function_type, ty.FunctionType)
    receiver = replace(value, type=unfolded) if isinstance(value.type, ty.NamedType) else value
    function = hir.ExpressedIdentifier(loc, function_type, function_binding.name, binding_id=function_binding.id)
    method = unfolded.method('__as__')
    if method is not None and method.static:
        return tcr_function_call(function, p0.Block(loc, [], '()', None), ctx=ctx)   # reads nothing of the value
    bound = hir.BoundMethod(loc, replace(function_type, pos_or_kw=function_type.pos_or_kw[1:]), function, receiver)
    return tcr_function_call(bound, p0.Block(loc, [], '()', None), ctx=ctx)


def _conversion_method_binding(unfolded: ty.ObjectType, target: ty.Type, loc: Span, *, ctx: Context) -> sb.Binding | None:
    """The `__as__` method of an object type whose result fits ``target``, else None."""
    conversions = [method for method in unfolded.methods if method.name == '__as__']
    if not conversions:
        return None
    if any(method.binding_id is None for method in conversions):
        _declare_pending_methods(ctx=ctx, for_type=unfolded)
    function_binding = None
    for method in conversions:
        if method.binding_id is None:
            continue
        candidate = ctx.binding_registry.by_id[method.binding_id]
        candidate_type = candidate.type
        expected_params = 0 if method.static else 1   # the receiver, unless the conversion reads nothing of the value
        if not isinstance(candidate_type, ty.FunctionType) or len(candidate_type.pos_or_kw) != expected_params or candidate_type.kw_only:
            user_error(
                ctx.srcfile,
                '`__as__` takes no arguments',
                Pointer(span=loc, message='the conversion of this value is declared with parameters'),
                hint='a conversion is `__as__ = ():>T => …`; the target type is its result type (`__as__ &= …` adds one for another target)',
            )
        if ctx.type_system.is_subtype(candidate_type.ret, target) or (_is_string_type(candidate_type.ret) and _is_string_type(target)):
            function_binding = candidate
            break
    return function_binding


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
    _seed_container_facts(declaration, ctx=ctx)
    return declaration


def _seed_container_facts(declaration: hir.Declare, *, ctx: Context) -> None:
    """A dictionary or set declared from a literal starts with its members proven at their entries."""
    if declaration.binding_id is None:
        return
    literal = _unwrap_parens(declaration.expr)
    while isinstance(literal, (hir.RepresentationCast, hir.ValueCast)):
        literal = literal.expr
    if not (isinstance(literal, hir.ObjectLiteral) and ty.container_entry_types(literal.type) is not None):
        return
    declared = ty.strip_refinement(declaration.annotation) if declaration.annotation is not None else literal.type
    _seed_field_routes(declaration.binding_id, declared, literal, (), ctx=ctx)
    dictionary = hir.ExpressedIdentifier(declaration.loc, literal.type, declaration.name, binding_id=declaration.binding_id)
    keys_literal = literal.fields[0].value
    while isinstance(keys_literal, (hir.RepresentationCast, hir.ValueCast)):
        keys_literal = keys_literal.expr
    if isinstance(keys_literal, hir.ArrayLiteral):
        for index, key in enumerate(keys_literal.items):
            _record_key_fact(dictionary, key, ctx=ctx, static_position=index)


def _widen_inferred_let_value(expr: hir.AST, *, ctx: Context) -> hir.AST:
    if isinstance(expr, hir.Integer) and isinstance(expr.type, ty.IntegerLiteralType):
        return replace(expr, type='int')
    if (
        isinstance(expr, hir.Integer)
        and isinstance(expr.type, ty.QuantityType)
        and isinstance(expr.type.number, ty.IntegerLiteralType)
    ):
        # `let distance = 120m` is a runtime integer quantity, like `let x = 5`.
        return replace(expr, type=ty.QuantityType('int', expr.type.dimension))
    if _is_compile_time_rational(expr.type):
        # `let` bindings are runtime values; exact rationals materialize here.
        return _materialize_rational(expr, ctx=ctx)
    return expr


def _tcr_annotated_declaration(
    ast: p0.AST,
    keyword: str,
    name: str,
    typeexpr: p0.AST,
    right: p0.AST,
    *,
    ctx: Context,
) -> hir.AST:
    """`let name:T = value` (and the keyword-less `name:T = value`)."""
    # decl assign + type annotation: check the expression against the annotation
    annotation = _value_type(ast_to_type(typeexpr, ctx=replace(ctx, refinement_subject=name)), loc=typeexpr.loc, ctx=ctx)
    refined_annotation = annotation if isinstance(annotation, ty.RefinedType) else None
    annotation = ty.strip_refinement(annotation)
    if annotation == ty.TYPE_TYPE:
        binding = ctx.binding_registry.by_syntax.get(id(ast))
        prebound = _prebound_alias_value(binding, ctx=ctx)
        type_value = prebound if prebound is not None else _type_alias_value(right, ctx=ctx)
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
    if (
        ty.dict_key_value(annotation) is not None
        and isinstance(right, p0.Block)
        and right.kind == '[]'
        and (not right.inner or _dict_literal_block(right) is not None)
    ):
        return _tcr_dict_declare(name, ast.loc, right, ctx=ctx, annotation=annotation, keyword=keyword)
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
    expr = check_against(expr, refined_annotation or annotation, ctx=ctx)
    optional_annotation_payload = ty.optional_payload(annotation)
    growable = (
        keyword == 'let'
        and isinstance(annotation, ty.ArrayType)
        and annotation.length is None
        and isinstance(expr.type, ty.ArrayType)
        and expr.type.length is not None
        # grown somewhere in this module, or declared runtime-length and
        # started empty (`let buffer:array<uint8> = []`): an empty exact array
        # is useless unless grown, often by a callee through `@buffer`
        and (name in ctx.grown_array_names or expr.type.length == 0)
    )
    # an object or array annotation takes the value's exact shape (field
    # refinements, exact lengths) — but a minted child stored under its parent's
    # annotation (`let t:Token = Name(…)`) is a parent value: the annotation governs
    ctx.declarations[name] = (
        annotation
        if growable
        else expr.type
        if isinstance(annotation, (ty.ArrayType, ty.ObjectType))
        and isinstance(expr.type, type(annotation))
        and not ty.user_brand_descends(expr.type, annotation)
        else ty.optional(expr.type)
        if isinstance(optional_annotation_payload, (ty.ArrayType, ty.ObjectType))
        and isinstance(expr.type, type(optional_annotation_payload))
        and not ty.user_brand_descends(expr.type, optional_annotation_payload)
        else annotation
    )
    declaration = _complete_binding(
        ast,
        hir.Declare(ast.loc, ty.VOID_TYPE, keyword, name, refined_annotation or annotation, expr),
        ctx=ctx,
    )
    if refined_annotation is not None and declaration.binding_id is not None:
        _record_refinement_facts(declaration.binding_id, refined_annotation, ctx=ctx)
    if declaration.binding_id is not None:
        _seed_field_routes(declaration.binding_id, annotation, expr, (), ctx=ctx)
    if growable and declaration.binding_id is not None:
        # A runtime-length binding initialized from an exact-length
        # value keeps that exact length as a refinement until a
        # length-changing operation invalidates it, so index proofs
        # still work while the length is known.
        ctx.refinements[declaration.binding_id] = expr.type
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
    - expr vs none

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
            alias_binding = ctx.binding_registry.by_syntax.get(id(ast))
            alias_value = _prebound_alias_value(alias_binding, ctx=ctx)
            if alias_value is not None:
                # `let MyType = type of ...`: prebound as a minting type alias
                expr = hir.TypeValue(right.loc, ty.TYPE_TYPE, alias_value)
                ctx.declarations[name] = ty.TYPE_TYPE
                return _complete_binding(
                    ast,
                    hir.Declare(ast.loc, ty.VOID_TYPE, keyword, name, ty.TYPE_TYPE, expr),
                    ctx=ctx,
                )
            dict_block = _dict_literal_block(right)
            if dict_block is not None:
                return _tcr_dict_declare(name, ast.loc, dict_block, ctx=ctx, keyword=keyword)
            generic = _generic_signature(right, ctx=ctx) if isinstance(right, p0.BinOp) else None
            if generic is not None:
                signature, params = generic
                expr = hir.GenericFunction(right.loc, signature, name, hir.GenericSource(right, params, ctx))
                ctx.declarations[name] = signature
                return _complete_binding(ast, hir.Declare(ast.loc, ty.VOID_TYPE, keyword, name, None, expr), ctx=ctx)
            expr = typecheck_and_resolve_inner(right, ctx=ctx)
            expr = _unit_inhabitant(expr, None, ctx=ctx) or expr   # `let w = Whitespace`
            if isinstance(expr, hir.TypeValue) and isinstance(right, p0.Atom):
                # a type read by name is a value only where it converts to its
                # spelling; a binding holding one would need types at runtime
                # (`const Index = <int64>` declares an alias)
                not_implemented(ctx.srcfile, right.loc, 'runtime type values')
            require_valued(expr.type, ctx.srcfile, expr.loc, 'declaration initializer')
            if keyword == 'let':
                expr = _widen_inferred_let_value(expr, ctx=ctx)

            # if this declaration was pre-bound by the two-phase pass, verify the checked
            # type matches the pre-bound signature rather than silently overwriting it
            prebound = ctx.declarations.maps[0].get(name)
            if isinstance(prebound, ty.FunctionType) and isinstance(expr.type, ty.FunctionType):
                assert ctx.type_system.function_subtype(expr.type, prebound) and ctx.type_system.function_subtype(prebound, expr.type), \
                    f'INTERNAL ERROR: checked function type {expr.type} does not match the pre-bound signature {prebound} for `{name}`'

            # use the type directly from the expression since no type annotation was provided
            grown_annotation = _grown_array_annotation(name, keyword, expr.type, ctx=ctx)
            ctx.declarations[name] = grown_annotation or expr.type

            declaration = _complete_binding(
                ast,
                hir.Declare(ast.loc, ty.VOID_TYPE, keyword, name, grown_annotation, expr),
                ctx=ctx,
            )
            if grown_annotation is not None and declaration.binding_id is not None:
                ctx.refinements[declaration.binding_id] = expr.type
            return declaration
        
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
            return _tcr_annotated_declaration(ast, keyword, name, typeexpr, right, ctx=ctx)
        
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
        isinstance(ast.left, p0.BinOp)
        and isinstance(ast.left.op, t1.Operator)
        and ast.left.op.symbol == ':'
        and isinstance(ast.left.left, p0.Atom)
        and isinstance(ast.left.left.item, t1.Identifier)
        and ast.left.left.item.name not in ctx.declarations
    ):
        # `score:Positive = 42` declares like `let score:Positive = 42`
        return _tcr_annotated_declaration(
            ast, 'let', ast.left.left.item.name, ast.left.right, ast.right, ctx=ctx,
        )

    alias_binding = ctx.binding_registry.by_syntax.get(id(ast))
    if (
        alias_binding is not None
        and (
            isinstance(ast.left, p0.Atom) and isinstance(ast.left.item, t1.Identifier)
            or _annotated_type_alias_rhs(ast) is not None
        )
        and _prebound_alias_value(alias_binding, ctx=ctx) is not None
    ):
        # `Positive = int< i => i >? 0 >` / `Context:type = [...]`: prebound as a type alias
        name = (
            ast.left.item.name
            if isinstance(ast.left, p0.Atom) and isinstance(ast.left.item, t1.Identifier)
            else ast.left.left.item.name   # type: ignore[union-attr]
        )
        expr = hir.TypeValue(ast.right.loc, ty.TYPE_TYPE, alias_binding.type_value)
        ctx.declarations[name] = ty.TYPE_TYPE
        return _complete_binding(
            ast,
            hir.Declare(ast.loc, ty.VOID_TYPE, 'let', name, ty.TYPE_TYPE, expr),
            ctx=ctx,
        )

    if (
        isinstance(ast.left, p0.Atom)
        and isinstance(ast.left.item, t1.Identifier)
        and (
            ast.left.item.name not in ctx.declarations
            or ctx.binding_registry.by_syntax.get(id(ast)) is not None   # collected as this block's declaration (its signature may already be known)
        )
    ):
        name = ast.left.item.name
        dict_block = _dict_literal_block(ast.right)
        if dict_block is not None:
            return _tcr_dict_declare(name, ast.loc, dict_block, ctx=ctx)   # an implicit declaration is a `let`
        value = typecheck_and_resolve_inner(ast.right, ctx=ctx)
        require_valued(value.type, ctx.srcfile, value.loc, 'declaration initializer')
        value = _widen_inferred_let_value(value, ctx=ctx)
        grown_annotation = _grown_array_annotation(name, 'let', value.type, ctx=ctx)
        ctx.declarations[name] = grown_annotation or value.type
        declaration = _complete_binding(
            ast,
            hir.Declare(
                ast.loc,
                ty.VOID_TYPE,
                'let',
                name,
                grown_annotation,
                value,
            ),
            ctx=ctx,
        )
        if grown_annotation is not None and declaration.binding_id is not None:
            ctx.refinements[declaration.binding_id] = value.type
        return declaration

    dict_store = _tcr_dict_store(ast, ctx=ctx)
    if dict_store is not None:
        return dict_store
    target = tcr_assignment_target(ast.left, ctx=ctx)
    if isinstance(target, hir.ForwardingAccess):
        user_error(
            ctx.srcfile,
            'assignment through a union route',
            Pointer(span=target.value.loc, message=f'this has type `{type_to_dewy(target.value.type)}`, so `{target.field}` is not one definite place'),
            hint='narrow the receiver with `is?` (or propagate with `or_throw`) before assigning',
        )
    declared: ty.ObjectField | None = None
    if isinstance(target, hir.MemberAccess) and isinstance(target.value.type, ty.ObjectType):
        # a store accepts the field's declared type; an `is?` narrowing of the
        # route is forgotten below, not enforced on the new value
        declared = target.value.type.field(target.name)
        if declared is not None:
            target = replace(target, type=declared.type)
    store_expected = _field_expectation(declared) if isinstance(target, hir.MemberAccess) and declared is not None else target.type
    value = typecheck_and_resolve_inner(ast.right, ctx=ctx, expected=ty.strip_refinement(store_expected))
    value = check_against(value, store_expected, ctx=ctx)
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
        assigned = sb.member_path(target)
        if assigned is not None:
            root_id, path = assigned
            _invalidate_routes(root_id, ctx=ctx, prefix=path)
        return hir.MemberAssign(ast.loc, ty.VOID_TYPE, target, value)
    if _is_range_type(target.type):
        # Range bindings resolve to their initializer at compile time, so a
        # reassignment would silently be ignored by earlier resolutions.
        not_implemented(ctx.srcfile, ast.loc, 'reassigning a range value')
    if target.binding_id is not None:
        ctx.refinements.pop(target.binding_id, None)
        ctx.length_bounds.pop(target.binding_id, None)
        _invalidate_routes(target.binding_id, ctx=ctx)
        _drop_key_facts(ctx, dictionary_id=target.binding_id)
        _drop_key_facts(ctx, key_id=target.binding_id)
    return hir.Assign(ast.loc, ty.VOID_TYPE, target, '=', value)


def _seed_field_routes(
    root_id: int,
    declared: ty.Type,
    expr: hir.AST,
    path: tuple[str, ...],
    *,
    ctx: Context,
) -> None:
    """Record exact lengths of growable array fields initialized by an object literal.

    `let bag:Bag = [items = [1 2]]` gives the route `bag.items` the same
    exact-length refinement a named growable array gets from its initializer.
    """
    declared = ty.strip_refinement(declared)
    literal = _unwrap_parens(expr)
    while isinstance(literal, (hir.RepresentationCast, hir.ValueCast)):
        literal = literal.expr
    if not (isinstance(declared, ty.ObjectType) and isinstance(literal, hir.ObjectLiteral)):
        return
    for field_value in literal.fields:
        field = declared.field(field_value.name)
        if field is None:
            continue
        field_path = (*path, field_value.name)
        if (
            isinstance(field.type, ty.ArrayType)
            and field.type.length is None
            and isinstance(field_value.value.type, ty.ArrayType)
            and field_value.value.type.length is not None
        ):
            route_id = ctx.binding_registry.route_id(root_id, field_path, field.type, field_value.loc)
            ctx.refinements[route_id] = ty.ArrayType(field.type.element, field_value.value.type.length)
            ctx.length_bounds[route_id] = field_value.value.type.length
        elif isinstance(field.type, ty.ObjectType):
            _seed_field_routes(root_id, field.type, field_value.value, field_path, ctx=ctx)


def _invalidate_routes(root_id: int, *, ctx: Context, prefix: tuple[str, ...] = ()) -> None:
    """Drop length facts of the member routes under a reassigned binding or field."""
    for route_id in ctx.binding_registry.routes_under(root_id, prefix):
        ctx.refinements.pop(route_id, None)
        ctx.length_bounds.pop(route_id, None)
        _drop_key_facts(ctx, dictionary_id=route_id)
    if not prefix:
        _drop_key_facts(ctx, dictionary_id=root_id)


def _drop_key_facts(ctx: Context, *, dictionary_id: int | None = None, key_id: int | None = None) -> None:
    """Forget proven keys of a reassigned dictionary, or facts about a reassigned key binding."""
    for fact_key in list(ctx.key_facts):
        route_id, identity = fact_key
        if dictionary_id is not None and route_id == dictionary_id:
            del ctx.key_facts[fact_key]
        elif key_id is not None and identity == ('b', key_id):
            del ctx.key_facts[fact_key]


_key_position_counter = count(1)


def _new_key_position_name() -> str:
    return f'__dewy_key_pos_{next(_key_position_counter)}'


def _key_identity(key: hir.AST, *, ctx: Context) -> tuple[str, object] | None:
    """How a key expression is tracked in facts: a binding or a constant."""
    key = _unwrap_parens(key)
    while isinstance(key, (hir.RepresentationCast, hir.ValueCast)):
        key = key.expr
    if isinstance(key, hir.ExpressedIdentifier) and key.binding_id is not None:
        return ('b', key.binding_id)
    if isinstance(key, hir.String):
        return ('c', key.content)
    if isinstance(key.type, ty.StringLiteralType):
        return ('c', key.type.value)
    constant = _constant_integer(key, ctx=ctx)
    if constant is not None:
        return ('c', constant)
    return None


def _dictionary_fact_id(dictionary: hir.AST, *, ctx: Context) -> int | None:
    return sb.array_route_id(dictionary, ctx.binding_registry)


def _const_key_facts(ctx: Context) -> dict:
    """The proven keys of `const` dictionaries, which a function body inherits:
    a `const` is never stored into, so its literal's entries stay where they are."""
    inherited: dict = {}
    for fact_key, fact in ctx.key_facts.items():
        dictionary_id = fact_key[0]
        binding = ctx.binding_registry.by_id.get(dictionary_id)
        if binding is None and dictionary_id in ctx.binding_registry.route_paths:
            continue   # a member route: its root may be reassigned
        if binding is not None and binding.declaration is not None and binding.declaration.decltype == 'const':
            inherited[fact_key] = fact
    return inherited


def _record_key_fact(
    dictionary: hir.AST,
    key: hir.AST,
    *,
    ctx: Context,
    position: str | None = None,
    static_position: int | None = None,
) -> None:
    dictionary_id = _dictionary_fact_id(dictionary, ctx=ctx)
    identity = _key_identity(key, ctx=ctx)
    if dictionary_id is None or identity is None:
        return
    ctx.key_facts[(dictionary_id, identity)] = (position, static_position)


def _proven_key(dictionary: hir.AST, key: hir.AST, *, ctx: Context) -> tuple[str | None, int | None] | None:
    dictionary_id = _dictionary_fact_id(dictionary, ctx=ctx)
    identity = _key_identity(key, ctx=ctx)
    if dictionary_id is None or identity is None:
        return None
    return ctx.key_facts.get((dictionary_id, identity))


def _dict_index_binding(left: p0.AST, *, ctx: Context) -> sb.Binding | None:
    """The dictionary binding of an assignment target spelled `d[key]`, else None."""
    if not isinstance(left, p0.BinOp):
        return None
    op = left.op
    if isinstance(op, t2.QJuxtapose):
        op = next((option for option in op.options if isinstance(option, t2.IndexJuxtapose)), op)
    if not isinstance(op, t2.IndexJuxtapose):
        return None
    if not (isinstance(left.left, p0.Atom) and isinstance(left.left.item, t1.Identifier)):
        return None
    binding = ctx.binding_scopes.get(left.left.item.name)
    if binding is None or ty.dict_key_value(binding.type) is None:
        return None  # (a set target falls through to the index-assignment error)
    return binding


def _tcr_dict_store(ast: p0.BinOp, *, ctx: Context) -> hir.DictStore | None:
    """Check `d[key] = value` when `d` names a dictionary."""
    left = ast.left
    binding = _dict_index_binding(left, ctx=ctx)
    if binding is None:
        return None
    assert isinstance(left, p0.BinOp)
    if not isinstance(left.right, p0.Block) or len(left.right.inner) != 1:
        user_error(
            ctx.srcfile,
            'dictionary store takes one key',
            Pointer(span=left.right.loc, message='expected exactly one key expression'),
        )
    if (reason := _read_only_reason(binding)) is not None:
        user_error(
            ctx.srcfile,
            'cannot store into a const dictionary',
            Pointer(span=left.left.loc, message=f'`{binding.name}` {reason}'),
        )
    dictionary = tcr_identifier(left.left.item, ctx=ctx)
    found = _dict_value(dictionary)
    assert found is not None and found[2] is not None
    dictionary, key_type, value_type = found
    key = check_against(
        typecheck_and_resolve_inner(left.right.inner[0], ctx=ctx, expected=key_type),
        key_type,
        ctx=ctx,
    )
    value = check_against(
        typecheck_and_resolve_inner(ast.right, ctx=ctx, expected=value_type),
        value_type,
        ctx=ctx,
    )
    keys, values = _dict_arrays(dictionary, ast.loc, ctx=ctx)
    _invalidate_dict_lengths(dictionary, ctx=ctx)
    _forget_positions(dictionary, ctx=ctx)  # a store may resize, which compacts entries
    position = _new_key_position_name()
    _record_key_fact(dictionary, key, ctx=ctx, position=position)
    return hir.DictStore(ast.loc, ty.VOID_TYPE, keys, values, key, value, position=position)


def tcr_combined_assign(ast: p0.BinOp, *, ctx: Context) -> hir.AST:
    """Typecheck a simple compound assignment while retaining its source operator.

    `Type &= (…) => …` is not an assignment: it adds a constructor overload to
    an object type (see `_declare_constructor_overload`).
    """
    assert isinstance(ast.op, t2.CombinedAssignmentOp)
    if not isinstance(ast.op.op, t1.Operator):
        not_implemented(ctx.srcfile, ast.op.loc, 'broadcast compound assignment')
    symbol = ast.op.op.symbol
    if symbol == '&' and (constructor := _type_constructor_target(ast.left, ctx=ctx)) is not None:
        return _declare_constructor_overload(constructor, ast.right, ctx=ctx)
    if symbol == '=':
        user_error(
            ctx.srcfile,
            '`==` is not an operator',
            Pointer(span=ast.op.loc, message='this reads as the compound assignment `=` `=`'),
            hint='equality is `=?` (and inequality `not =?`); assignment is a single `=`',
        )
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

    if (dict_binding := _dict_index_binding(ast.left, ctx=ctx)) is not None:
        # `d[k] op= v` is `d[k] = d[k] op v`: the key must be proven present
        # (the lookup says so otherwise), and the store replaces its value
        if (reason := _read_only_reason(dict_binding)) is not None:
            user_error(
                ctx.srcfile,
                'cannot store into a const dictionary',
                Pointer(span=ast.left.loc, message=f'`{dict_binding.name}` {reason}'),
            )
        assert isinstance(ast.left, p0.BinOp)
        lookup = _tcr_index(ast.left, ctx=ctx)
        assert isinstance(lookup, hir.DictLookup)
        value = typecheck_and_resolve_inner(ast.right, ctx=ctx, expected=lookup.type)
        result = _dispatch_builtin(
            builtins.BINOP_DUNDER_MAP[symbol],
            [lookup, value],
            loc=ast.loc,
            op_loc=ast.op.loc,
            source_name=symbol,
            ctx=ctx,
            expected=lookup.type,
        )
        result = check_against(result, lookup.type, ctx=ctx)
        return hir.DictStore(ast.loc, ty.VOID_TYPE, lookup.keys, lookup.values, lookup.key, result)

    target = tcr_assignment_target(ast.left, ctx=ctx, refined=True)
    if isinstance(target, hir.Index):
        not_implemented(
            ctx.srcfile,
            ast.left.loc,
            'compound indexed assignment',
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
    result = check_against(result, target.type, ctx=ctx)
    if isinstance(target, hir.MemberAccess):
        # `obj.field += v` is `obj.field = obj.field + v`
        assigned = sb.member_path(target)
        if assigned is not None:
            root_id, path = assigned
            _invalidate_routes(root_id, ctx=ctx, prefix=path)
        return hir.MemberAssign(ast.loc, ty.VOID_TYPE, target, result)
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


def tcr_or_throw(ast: p0.Postfix, *, ctx: Context) -> hir.AST:
    """`value or_throw`: propagate the exception alternatives (`error`
    subtypes and `none`) out of the enclosing function; the expression
    continues as the ordinary alternatives."""
    value = typecheck_and_resolve_inner(ast.item, ctx=ctx)
    require_valued(value.type, ctx.srcfile, value.loc, '`or_throw` operand')
    members = list(value.type.items) if isinstance(value.type, ty.TypeOr) else [value.type]
    exceptions = [m for m in members if ctx.type_system.is_subtype(m, ty.EXCEPTION_TYPE)]
    ordinary = [m for m in members if m not in exceptions]
    if not exceptions:
        user_error(
            ctx.srcfile,
            'nothing to propagate',
            Pointer(span=value.loc, message=f'this has type `{type_to_dewy(value.type)}`, which has no `error` or `none` alternative'),
        )
    if not ordinary:
        user_error(
            ctx.srcfile,
            '`or_throw` always returns',
            Pointer(span=value.loc, message=f'every alternative of `{type_to_dewy(value.type)}` is propagated'),
            hint='write `return value` instead',
        )
    if ctx.catcher is None:
        user_error(ctx.srcfile, '`or_throw` outside a function', Pointer(span=ast.op.loc, message='nothing here catches the propagated value'))
    expected = ctx.catcher.expected
    if expected is None or expected == ty.VOID_TYPE:
        user_error(
            ctx.srcfile,
            'the enclosing function has no declared result type to propagate into',
            Pointer(span=ast.op.loc, message='annotate the function result with `:>T | ...` including the propagated alternatives'),
        )
    for member in exceptions:
        if not ctx.type_system.is_subtype(member, expected):
            user_error(
                ctx.srcfile,
                f'the enclosing function does not return `{type_to_dewy(member)}`',
                Pointer(span=ast.op.loc, message=f'`or_throw` would propagate `{type_to_dewy(member)}`, but the result type is `{type_to_dewy(expected)}`'),
                hint=f'add `| {type_to_dewy(member)}` to the function result type, or handle it with `is?` first',
            )
    binding = ctx.binding_registry.allocate(ast, f'__dewy_or_throw_{ctx.binding_registry.next_id}', 'value', ast.loc)
    binding.type = value.type
    exception_type = ty.union(*exceptions)
    tested = hir.ExpressedIdentifier(ast.loc, exception_type, binding.name, binding_id=binding.id)
    if exception_type == 'none':
        propagated: hir.AST = hir.NoneValue(ast.loc, 'none')
    else:
        propagated = tested
    propagated = check_against(propagated, expected, ctx=ctx)
    ctx.catcher.returns.append((ast.op.loc, propagated.type))
    return hir.OrThrow(ast.loc, ty.union(*ordinary), value, binding.name, binding.id, exception_type, propagated)


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


@dataclass
class _FlowArmSpec:
    """One arm of a flow chain: how to check its condition and body in the arm's context."""

    loc: Span
    condition: Callable[[Context], hir.AST]
    body: Callable[[Context, ty.Type | None], hir.AST]
    body_ast: p0.AST | None = None   # the `if` arm's syntax (target-gated arms splice it)


def _if_arm_spec(loc: Span, condition_ast: p0.AST, body_ast: p0.AST) -> _FlowArmSpec:
    return _FlowArmSpec(
        loc,
        lambda arm_ctx: _check_flow_condition(condition_ast, ctx=arm_ctx),
        lambda body_ctx, branch_expected: typecheck_and_resolve_inner(body_ast, ctx=body_ctx, expected=branch_expected),
        body_ast,
    )


# --- match ------------------------------------------------------------------
# See `dewy/semantic/match.md`. An arm's left side is a parameter signature;
# the arm matches when the scrutinee satisfies it.

@dataclass
class _Pattern:
    kind: str                                   # 'type' | 'any' | 'object' | 'sequence'
    loc: Span
    name: str | None = None                     # the binding a `name:T` / `name` / field introduces
    type_ast: p0.AST | None = None              # `T` of `name:T` / `<T>`
    fields: list[tuple[str, '_Pattern | None']] = field(default_factory=list)   # object shape
    items: list['_Pattern'] = field(default_factory=list)                         # sequence


def _parse_pattern(ast: p0.AST, *, ctx: Context) -> _Pattern:
    """The left side of a match arm as a pattern."""
    if isinstance(ast, p0.Atom) and isinstance(ast.item, t1.Identifier):
        # a bare name is the catch-all and binds the whole value, shadowing
        # whatever the name meant (as a parameter would); `_` is the idiom
        # and any other name warns, saying what it shadows
        name = ast.item.name
        if name != '_':
            existing = ctx.binding_scopes.get(name)
            if existing is not None and existing.type_value is not None:
                what = f'`{name}` names a type here; this arm matches everything and binds the value as `{name}`'
                hint = f'write `<{name}>` to match the type, `value:{name}` to bind it, or `_` for the catch-all'
            elif existing is not None:
                what = f'`{name}` shadows the enclosing `{name}`; this arm matches everything'
                hint = f'write `{name}:T` to bind with a type, or `_` for the catch-all'
            else:
                what = f'`{name}` matches everything'
                hint = f'the idiomatic catch-all is `_`; write `{name}:T` to bind with a type, or `<{name}>` to match a type'
            user_warning(ctx.srcfile, 'bare name in a match arm binds the whole value', Pointer(span=ast.loc, message=what), hint=hint)
        return _Pattern('any', ast.loc, name=name)
    if isinstance(ast, p0.Block) and ast.kind == '<>':
        if len(ast.inner) != 1:
            user_error(ctx.srcfile, 'match arm type block holds one type', Pointer(span=ast.loc, message='write `<T>`'))
        return _Pattern('type', ast.loc, type_ast=ast.inner[0])
    if (
        isinstance(ast, p0.BinOp)
        and isinstance(ast.op, t1.Operator)
        and ast.op.symbol == ':'
        and isinstance(ast.left, p0.Atom)
        and isinstance(ast.left.item, t1.Identifier)
    ):
        return _Pattern('type', ast.loc, name=ast.left.item.name, type_ast=ast.right)
    if isinstance(ast, p0.Block) and ast.kind == '[]':
        fields: list[tuple[str, _Pattern | None]] = []
        for item in ast.inner:
            if isinstance(item, p0.Atom) and isinstance(item.item, t1.Identifier):
                fields.append((item.item.name, None))
                continue
            if (
                isinstance(item, p0.BinOp)
                and isinstance(item.op, t1.Operator)
                and item.op.symbol == ':'
                and isinstance(item.left, p0.Atom)
                and isinstance(item.left.item, t1.Identifier)
            ):
                fields.append((item.left.item.name, _Pattern('type', item.loc, name=item.left.item.name, type_ast=item.right)))
                continue
            user_error(ctx.srcfile, 'object pattern fields are `name` or `name:type`', Pointer(span=item.loc, message='not a field pattern'))
        return _Pattern('object', ast.loc, fields=fields)
    if isinstance(ast, p0.Block) and ast.kind == '()':
        return _Pattern('sequence', ast.loc, items=[_parse_pattern(item, ctx=ctx) for item in ast.inner])
    user_error(
        ctx.srcfile,
        'unsupported match pattern',
        Pointer(span=ast.loc, message='patterns are `name:T`, `<T>`, `name`, `[fields]`, or `(patterns)`'),
        hint='see `dewy/semantic/match.md`',
    )


def _identifier_atom(loc: Span, name: str) -> p0.Atom:
    return p0.Atom(loc, t1.Identifier(loc, name))


def _member_ast(loc: Span, base: p0.AST, name: str) -> p0.BinOp:
    return p0.BinOp(loc, t1.Operator(loc, '.'), base, _identifier_atom(loc, name))


def _let_ast(loc: Span, name: str, value: p0.AST) -> p0.KeywordExpr:
    return p0.KeywordExpr(loc, [t1.Keyword(loc, 'let'), p0.BinOp(loc, t1.Operator(loc, '='), _identifier_atom(loc, name), value)])


_PROPOSITION_DUNDERS = {'>?': '__gt__', '>=?': '__ge__', '<?': '__lt__', '<=?': '__le__', '=?': '__eq__', 'not=?': '__ne__'}


def _proposition_condition(subject_ast: p0.AST, proposition: ty.Proposition, *, ctx: Context, loc: Span) -> hir.AST:
    """A refinement proposition as a runtime test of the subject (a match guard)."""
    target: p0.AST = subject_ast
    if proposition.field is not None:
        for part in proposition.field.split('.'):
            target = _member_ast(loc, target, part)
    if proposition.is_length:
        target = _member_ast(loc, target, 'length')
    value = typecheck_and_resolve_inner(target, ctx=ctx)
    constant = hir.Integer(loc, ty.IntegerLiteralType(proposition.value), '0d', proposition.value)
    return _dispatch_builtin(_PROPOSITION_DUNDERS[proposition.op], [value, constant], loc=loc, op_loc=loc, source_name=proposition.op, ctx=ctx)


def _conjoin(conditions: list[hir.AST], loc: Span) -> hir.AST | None:
    combined: hir.AST | None = None
    for condition in conditions:
        combined = condition if combined is None else hir.ShortCircuit(loc, 'bool', 'and', combined, condition)
    return combined


def _pattern_condition(subject_ast: p0.AST, pattern: _Pattern, *, ctx: Context) -> tuple[list[hir.AST], Context]:
    """The tests that make ``subject`` satisfy ``pattern``, and the context they establish.

    Each test is checked in the context narrowed by the previous ones (a
    guard reads the value narrowed by its type test).
    """
    loc = pattern.loc
    if pattern.kind == 'any':
        return [], ctx
    if pattern.kind == 'type':
        assert pattern.type_ast is not None
        declared = ast_to_type(pattern.type_ast, ctx=replace(ctx, refinement_subject=pattern.name))
        base = ty.strip_refinement(declared)
        value = typecheck_and_resolve_inner(subject_ast, ctx=ctx)
        require_valued(value.type, ctx.srcfile, value.loc, 'match scrutinee')
        conditions: list[hir.AST] = []
        current = ctx
        value_number = ty.strip_refinement(_number_and_dimension(value.type)[0])
        if not ctx.type_system.is_subtype(value_number, base):
            test = _integer_singleton_test(value, base, negated=False, loc=loc, op_loc=loc, ctx=ctx)
            if test is None:
                test = hir.TypeTest(loc, 'bool', value, base, False)
            conditions.append(test)
            current = _refine_condition_context(ctx, test, truth=True)
        if isinstance(declared, ty.RefinedType):
            for proposition in declared.propositions:
                guard = _proposition_condition(subject_ast, proposition, ctx=current, loc=loc)
                conditions.append(guard)
                current = _refine_condition_context(current, guard, truth=True)
        return conditions, current
    if pattern.kind == 'object':
        value = typecheck_and_resolve_inner(subject_ast, ctx=ctx)
        names = [name for name, _ in pattern.fields]
        member = _object_member_with_fields(value.type, names, loc=loc, ctx=ctx)
        conditions = []
        current = ctx
        value_number = ty.strip_refinement(_number_and_dimension(value.type)[0])
        if not ctx.type_system.is_subtype(value_number, member):
            test = hir.TypeTest(loc, 'bool', value, member, False)
            conditions.append(test)
            current = _refine_condition_context(ctx, test, truth=True)
        for name, sub in pattern.fields:
            if sub is None:
                continue
            sub_conditions, current = _pattern_condition(_member_ast(loc, subject_ast, name), sub, ctx=current)
            conditions.extend(sub_conditions)
        return conditions, current
    user_error(ctx.srcfile, 'a sequence pattern needs a sequence scrutinee', Pointer(span=loc, message='the scrutinee is one value'))


def _object_member_with_fields(type_: ty.Type, names: list[str], *, loc: Span, ctx: Context) -> ty.ObjectType:
    """The object type an object pattern tests for: the scrutinee's object, or the union member with those fields."""
    number = ty.strip_refinement(_number_and_dimension(type_)[0])
    candidates = list(number.items) if isinstance(number, ty.TypeOr) else [number]
    objects = [
        ty.unfold(member) for member in candidates
        if isinstance(ty.unfold(member), ty.ObjectType) and all(ty.unfold(member).field(name) is not None for name in names)
    ]
    if len(objects) != 1:
        user_error(
            ctx.srcfile,
            'object pattern does not select one member',
            Pointer(span=loc, message=f'`{type_to_dewy(type_)}` has {len(objects)} object members with fields {", ".join(names)}'),
        )
    return objects[0]


def _pattern_bindings(subject_ast: p0.AST, pattern: _Pattern, loc: Span) -> list[p0.AST]:
    """The `let` declarations a matched pattern introduces, reading the (narrowed) subject."""
    if pattern.kind in ('any', 'type'):
        return [_let_ast(loc, pattern.name, subject_ast)] if pattern.name is not None else []
    if pattern.kind == 'object':
        declarations: list[p0.AST] = []
        for name, sub in pattern.fields:
            member = _member_ast(loc, subject_ast, name)
            if sub is None:
                declarations.append(_let_ast(loc, name, member))
            else:
                declarations.extend(_pattern_bindings(member, sub, loc))
        return declarations
    return []


class _ValueSet:
    """A set of integers as sorted disjoint inclusive intervals (None = unbounded)."""

    def __init__(self, intervals: list[tuple[int | None, int | None]] | None = None) -> None:
        self.intervals: list[tuple[int | None, int | None]] = []
        for interval in intervals or []:
            self.add(interval)

    def add(self, interval: tuple[int | None, int | None]) -> None:
        lower, upper = interval
        if lower is not None and upper is not None and lower > upper:
            return
        merged: list[tuple[int | None, int | None]] = []
        for e_lower, e_upper in self.intervals:
            disjoint_left = e_upper is not None and lower is not None and e_upper + 1 < lower
            disjoint_right = upper is not None and e_lower is not None and upper + 1 < e_lower
            if disjoint_left or disjoint_right:
                merged.append((e_lower, e_upper))
                continue
            lower = None if lower is None or e_lower is None else min(lower, e_lower)
            upper = None if upper is None or e_upper is None else max(upper, e_upper)
        merged.append((lower, upper))
        merged.sort(key=lambda item: (item[0] is not None, item[0] if item[0] is not None else 0))
        self.intervals = merged

    def union(self, other: '_ValueSet') -> '_ValueSet':
        result = _ValueSet(self.intervals)
        for interval in other.intervals:
            result.add(interval)
        return result

    def intersect(self, other: '_ValueSet') -> '_ValueSet':
        result = _ValueSet()
        for a_lower, a_upper in self.intervals:
            for b_lower, b_upper in other.intervals:
                lower = a_lower if b_lower is None else (b_lower if a_lower is None else max(a_lower, b_lower))
                upper = a_upper if b_upper is None else (b_upper if a_upper is None else min(a_upper, b_upper))
                result.add((lower, upper))
        return result

    def contains_interval(self, lower: int | None, upper: int | None) -> bool:
        return any(
            (e_lower is None or (lower is not None and e_lower <= lower))
            and (e_upper is None or (upper is not None and upper <= e_upper))
            for e_lower, e_upper in self.intervals
        )

    def covers(self, other: '_ValueSet') -> bool:
        """Whether every interval of ``other`` lies inside one of ours."""
        return all(self.contains_interval(lower, upper) for lower, upper in other.intervals)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _ValueSet) and self.intervals == other.intervals

    def first_uncovered(self, domain: '_ValueSet') -> int | None:
        """The least value of ``domain`` not in this set (finite domains and lower-bounded ones)."""
        for lower, upper in domain.intervals:
            probe = lower if lower is not None else (0 if upper is None else min(0, upper))
            while upper is None or probe <= upper:
                if not self.contains_interval(probe, probe):
                    return probe
                # jump past the covering interval
                jump = next(e_upper for e_lower, e_upper in self.intervals if (e_lower is None or e_lower <= probe) and (e_upper is None or probe <= e_upper))
                if jump is None:
                    break
                probe = jump + 1
        return None


def _propositions_value_set(propositions: tuple[ty.Proposition, ...] | list[ty.Proposition], domain: _ValueSet) -> _ValueSet:
    """The values of ``domain`` a set of `self` propositions admits."""
    lower: int | None = None
    upper: int | None = None
    holes: list[int] = []
    for proposition in propositions:
        if proposition.subject != 'self':
            continue
        p_lower, p_upper = proposition.lower_bound(), proposition.upper_bound()
        if p_lower is not None:
            lower = p_lower if lower is None else max(lower, p_lower)
        if p_upper is not None:
            upper = p_upper if upper is None else min(upper, p_upper)
        if proposition.op == 'not=?':
            holes.append(proposition.value)
    result = _ValueSet()
    for d_lower, d_upper in domain.intervals:
        r_lower = d_lower if lower is None else (lower if d_lower is None else max(lower, d_lower))
        r_upper = d_upper if upper is None else (upper if d_upper is None else min(upper, d_upper))
        pieces = [(r_lower, r_upper)]
        for hole in sorted(holes):
            next_pieces = []
            for piece_lower, piece_upper in pieces:
                inside = (piece_lower is None or piece_lower <= hole) and (piece_upper is None or hole <= piece_upper)
                if not inside:
                    next_pieces.append((piece_lower, piece_upper))
                    continue
                next_pieces.append((piece_lower, hole - 1))
                next_pieces.append((hole + 1, piece_upper))
            pieces = next_pieces
        for piece in pieces:
            result.add(piece)
    return result


def _integer_domain(type_: ty.Type) -> _ValueSet | None:
    """The value set of an integer-like type, or None for a non-integer type."""
    stripped = ty.strip_refinement(type_)
    if isinstance(stripped, ty.IntegerLiteralType):
        return _ValueSet([(stripped.value, stripped.value)])
    if stripped == 'bool':
        return _ValueSet([(0, 1)])
    if isinstance(stripped, str):
        layout = ty.fixed_integer_layout(stripped)
        if layout is not None:
            bounds = ty.fixed_integer_bounds(stripped)
            assert bounds is not None
            domain = _ValueSet([bounds])
        elif stripped == 'int':
            domain = _ValueSet([(None, None)])
        elif stripped == 'uint':
            domain = _ValueSet([(0, None)])
        else:
            return None
        if isinstance(type_, ty.RefinedType):
            domain = _propositions_value_set(type_.propositions, domain)
        return domain
    return None


@dataclass
class _MemberCoverage:
    """What the arms so far cover of one member of the scrutinee's type."""

    member: ty.TypeExpr
    domain: _ValueSet | None                       # integer members: their values; else None (atomic)
    covered: _ValueSet = field(default_factory=_ValueSet)
    full: bool = False
    fields: dict[str, tuple[_ValueSet, _ValueSet]] = field(default_factory=dict)   # object members: field -> (domain, covered)
    brands: set[str] | None = None                 # a minted member: the concrete brands under it (its children, itself unless abstract)
    covered_brands: set[str] = field(default_factory=set)

    def is_full(self) -> bool:
        if self.full:
            return True
        if self.brands is not None:
            return bool(self.brands) and self.brands <= self.covered_brands
        if self.domain is not None:
            return self.covered.covers(self.domain)
        return any(covered.covers(domain) for domain, covered in self.fields.values())

    def uncovered(self) -> str:
        if self.brands is not None:
            missing = sorted(self.brands - self.covered_brands)
            if missing:
                own = ty.unfold(self.member)
                if isinstance(own, ty.ObjectType) and missing[0] == own.brand:
                    return f'`{missing[0]}` itself (it is not `$abstract`, so it has values of its own)'
                return f'`{missing[0]}` (a `{type_to_dewy(self.member)}`)'
        if self.domain is not None and self.covered.intervals:
            probe = self.covered.first_uncovered(self.domain)
            if probe is not None:
                return f'value `{probe}` of `{type_to_dewy(self.member)}`'
        return f'`{type_to_dewy(self.member)}`'


def _concrete_brands_under(brand: str) -> set[str]:
    return {name for name in ty.brand_descendants(brand) if ty.brand_concrete(name)}


def _brand_family(type_: ty.TypeExpr) -> ty.ObjectType | None:
    """The minted type a value's brand ranges over: itself for a minted object, its family for a `type<Family>` value."""
    unfolded = ty.unfold(ty.strip_refinement(type_))
    if isinstance(unfolded, ty.MetaType):
        return unfolded.family
    return unfolded if isinstance(unfolded, ty.ObjectType) and ty.user_branded(unfolded) else None


def _brand_member_domain(member: ty.TypeExpr) -> set[str] | None:
    """A minted member's value set as brands: every concrete brand minted under it so far
    (the closed world is confirmed once every module is loaded)."""
    family = _brand_family(member)
    if family is None:
        return None
    assert family.brand is not None
    return _concrete_brands_under(family.brand)


@dataclass
class PendingBrandMatch:
    """A match over a minted type accepted as exhaustive by the brands minted so far;
    re-checked against the whole program once every module is loaded."""
    srcfile: SrcFile
    loc: Span
    brand: str
    covered: set[str]


pending_brand_matches: list[PendingBrandMatch] = []


def _pattern_coverage(pattern: _Pattern, coverage: list[_MemberCoverage], *, ctx: Context) -> bool:
    """Add a pattern's coverage; True when it covered something new (else the arm is unreachable)."""
    progressed = False
    if pattern.kind == 'any':
        for member in coverage:
            if not member.is_full():
                progressed = True
            member.full = True
        return progressed
    if pattern.kind == 'type':
        assert pattern.type_ast is not None
        declared = ast_to_type(pattern.type_ast, ctx=replace(ctx, refinement_subject=pattern.name))
        base = ty.strip_refinement(declared)
        propositions = declared.propositions if isinstance(declared, ty.RefinedType) else ()
        pattern_domain = _integer_domain(declared)
        for member in coverage:
            if member.is_full():
                continue
            member_base = ty.strip_refinement(member.member)
            if member.brands is not None and ty.user_branded(ty.unfold(base)) and not propositions:
                # an arm for a minted type covers it and every brand under it
                pattern_brand = ty.unfold(base).brand
                assert pattern_brand is not None
                family = _brand_family(member_base)
                assert family is not None
                if ctx.type_system.is_subtype(family, base):
                    member.full = True
                    progressed = True
                    continue
                if ctx.type_system.is_subtype(base, family):
                    admitted = _concrete_brands_under(pattern_brand)
                    if not admitted <= member.covered_brands:
                        member.covered_brands |= admitted
                        progressed = True
                continue
            related = ctx.type_system.is_subtype(member_base, base) or ctx.type_system.is_subtype(base, member_base)
            if member.domain is not None and pattern_domain is not None:
                # integer-like on both sides: the arm admits the values its
                # type denotes (a singleton, a guarded range, a whole width)
                if not related and not isinstance(base, ty.IntegerLiteralType):
                    continue
                admitted = member.domain.intersect(pattern_domain)
                new = member.covered.union(admitted)
                if new != member.covered:
                    member.covered = new
                    progressed = True
                continue
            if not ctx.type_system.is_subtype(member_base, base):
                continue
            if propositions:
                continue   # a guard on a non-integer member covers nothing for totality
            member.full = True
            progressed = True
        return progressed
    if pattern.kind == 'object':
        names = [name for name, _ in pattern.fields]
        for member in coverage:
            unfolded = ty.unfold(member.member)
            if not isinstance(unfolded, ty.ObjectType) or not all(unfolded.field(name) is not None for name in names):
                continue
            if member.is_full():
                continue
            constrained = [(name, sub) for name, sub in pattern.fields if sub is not None and sub.type_ast is not None]
            if not constrained:
                member.full = True
                progressed = True
                continue
            if len(constrained) != 1:
                continue   # several constrained fields: conservative (covers nothing)
            name, sub = constrained[0]
            field_declared = unfolded.field(name)
            assert field_declared is not None
            field_type = _refined(field_declared.type, list(field_declared.refinement)) if field_declared.refinement else field_declared.type
            domain = _integer_domain(field_type)
            if domain is None:
                continue
            assert sub.type_ast is not None
            sub_domain = _integer_domain(ast_to_type(sub.type_ast, ctx=replace(ctx, refinement_subject=sub.name)))
            if sub_domain is None:
                continue
            existing_domain, existing_covered = member.fields.get(name, (domain, _ValueSet()))
            new = existing_covered.union(sub_domain)
            if new != existing_covered:
                member.fields[name] = (existing_domain, new)
                progressed = True
        return progressed
    return False


def _match_arm_specs(
    arm: p0.KeywordExpr,
    scrutinee_ast: p0.AST,
    clause_ast: p0.AST,
    *,
    ctx: Context,
) -> tuple[list[_FlowArmSpec], list[hir.AST], bool, str | None]:
    """Expand one `match` arm into flow arm specs.

    Returns the specs, the scrutinee prelude (a hidden local for a
    non-identifier scrutinee), whether the arms cover the scrutinee's type,
    and a description of the first uncovered member or value.
    """
    loc = arm.loc
    # --- the scrutinee(s): identifiers are matched in place, other expressions bound once
    prelude: list[hir.AST] = []
    element_asts = (
        list(scrutinee_ast.inner)
        if isinstance(scrutinee_ast, p0.Block) and scrutinee_ast.kind == '()' and len(scrutinee_ast.inner) != 1
        else [scrutinee_ast]
    )
    subjects: list[p0.AST] = []
    subject_types: list[ty.Type] = []
    for element in element_asts:
        if isinstance(element, p0.Atom) and isinstance(element.item, t1.Identifier) and ctx.binding_scopes.get(element.item.name) is not None:
            value = typecheck_and_resolve_inner(element, ctx=ctx)
            subjects.append(element)
            subject_types.append(value.type)
            continue
        value = typecheck_and_resolve_inner(element, ctx=ctx)
        require_valued(value.type, ctx.srcfile, value.loc, 'match scrutinee')
        value = _widen_inferred_let_value(value, ctx=ctx)
        local = ctx.binding_registry.allocate(_fresh_syntax(ctx), f'__dewy_match_{ctx.binding_registry.next_id}', 'value', element.loc)
        local.type = value.type
        declaration = hir.Declare(element.loc, ty.VOID_TYPE, 'let', local.name, value.type, value, binding_id=local.id)
        local.declaration = declaration
        ctx.binding_scopes[local.name] = local
        ctx.declarations[local.name] = value.type   # resolution consults the declaration map first
        prelude.append(declaration)
        subjects.append(_identifier_atom(element.loc, local.name))
        subject_types.append(value.type)
    sequence = len(subjects) > 1
    # --- the arms
    arm_asts = list(clause_ast.inner) if isinstance(clause_ast, p0.Block) and clause_ast.kind == '{}' else [clause_ast]
    if not arm_asts:
        user_error(ctx.srcfile, 'match needs at least one arm', Pointer(span=clause_ast.loc, message='empty arm group'))
    coverage_sets: list[list[_MemberCoverage]] = []
    for subject_type in subject_types:
        number = ty.strip_refinement(_number_and_dimension(subject_type)[0])
        members = list(number.items) if isinstance(number, ty.TypeOr) else [number]
        coverage_sets.append([
            _MemberCoverage(
                member,
                _integer_domain(subject_type if len(members) == 1 and isinstance(subject_type, ty.RefinedType) else member),
                brands=_brand_member_domain(member),
            )
            for member in members
        ])
    specs: list[_FlowArmSpec] = []
    total = False
    for arm_ast in arm_asts:
        if not (isinstance(arm_ast, p0.BinOp) and isinstance(arm_ast.op, t1.Operator) and arm_ast.op.symbol == '=>'):
            user_error(ctx.srcfile, 'match arm must be `pattern => body`', Pointer(span=arm_ast.loc, message='not an arm'))
        pattern = _parse_pattern(arm_ast.left, ctx=ctx)
        body_ast = arm_ast.right
        if sequence:
            if pattern.kind != 'sequence' or len(pattern.items) != len(subjects):
                user_error(ctx.srcfile, 'sequence match arm arity', Pointer(span=pattern.loc, message=f'the scrutinee has {len(subjects)} values'))
            element_patterns = pattern.items
        else:
            if pattern.kind == 'sequence':
                if len(pattern.items) != 1:
                    user_error(ctx.srcfile, 'a sequence pattern needs a sequence scrutinee', Pointer(span=pattern.loc, message='the scrutinee is one value'))
                pattern = pattern.items[0]
            element_patterns = [pattern]
        # coverage and reachability, on the pattern types alone
        if total:
            user_error(ctx.srcfile, 'unreachable match arm', Pointer(span=pattern.loc, message='earlier arms already cover every value'))
        progressed = [
            _pattern_coverage(element_pattern, coverage, ctx=ctx)
            for element_pattern, coverage in zip(element_patterns, coverage_sets)
        ]
        if not any(progressed):
            user_error(ctx.srcfile, 'unreachable match arm', Pointer(span=pattern.loc, message='earlier arms already cover these values'))
        if sequence:
            # a sequence is total only when one arm covers every element on its own
            whole = all(
                element_pattern.kind == 'any'
                or (element_pattern.kind == 'type' and element_pattern.type_ast is not None
                    and not isinstance(ast_to_type(element_pattern.type_ast, ctx=replace(ctx, refinement_subject=element_pattern.name)), ty.RefinedType))
                or (element_pattern.kind == 'object' and all(sub is None for _, sub in element_pattern.fields))
                for element_pattern in element_patterns
            )
            total = whole and all(all(member.is_full() for member in coverage) for coverage in coverage_sets)
        else:
            total = all(member.is_full() for member in coverage_sets[0])

        def make_condition(element_patterns: list[_Pattern] = element_patterns) -> Callable[[Context], hir.AST]:
            def condition(arm_ctx: Context) -> hir.AST:
                conditions: list[hir.AST] = []
                current = arm_ctx
                for subject, element_pattern in zip(subjects, element_patterns):
                    element_conditions, current = _pattern_condition(subject, element_pattern, ctx=current)
                    conditions.extend(element_conditions)
                combined = _conjoin(conditions, loc)
                return combined if combined is not None else hir.Bool(loc, 'bool', True)
            return condition

        def make_body(element_patterns: list[_Pattern] = element_patterns, body_ast: p0.AST = body_ast) -> Callable[[Context, ty.Type | None], hir.AST]:
            def body(body_ctx: Context, branch_expected: ty.Type | None) -> hir.AST:
                declarations: list[p0.AST] = []
                for subject, element_pattern in zip(subjects, element_patterns):
                    declarations.extend(_pattern_bindings(subject, element_pattern, element_pattern.loc))
                if not declarations:
                    return typecheck_and_resolve_inner(body_ast, ctx=body_ctx, expected=branch_expected)
                # the bindings open the arm's scope; a braced body's items
                # join that scope rather than nesting a block statement
                body_items = list(body_ast.inner) if isinstance(body_ast, p0.Block) and body_ast.kind == '{}' else [body_ast]
                block = p0.Block(body_ast.loc, [*declarations, *body_items], '{}', None)
                return typecheck_and_resolve_inner(block, ctx=body_ctx, expected=branch_expected)
            return body

        specs.append(_FlowArmSpec(arm_ast.loc, make_condition(), make_body()))
    uncovered: str | None = None
    if not total:
        for coverage in coverage_sets:
            for member in coverage:
                if not member.is_full():
                    uncovered = member.uncovered()
                    break
            if uncovered is not None:
                break
    if total:
        # exhaustive over the brands minted so far: confirmed against the
        # whole program by `validate_brand_matches` (a child minted in a later
        # module would be uncovered)
        for coverage in coverage_sets:
            for member in coverage:
                if member.brands is not None and not member.full:
                    family = _brand_family(member.member)
                    assert family is not None and family.brand is not None
                    pending_brand_matches.append(PendingBrandMatch(ctx.srcfile, arm.loc, family.brand, set(member.covered_brands)))
    return specs, prelude, total, uncovered


def validate_brand_matches() -> None:
    """Every module loaded: a match accepted over the brands known then must cover the brands minted since."""
    for pending in pending_brand_matches:
        missing = sorted(_concrete_brands_under(pending.brand) - pending.covered)
        if missing:
            user_error(
                pending.srcfile,
                'match is not exhaustive',
                Pointer(span=pending.loc, message=f'`{missing[0]}` (a `{pending.brand}` minted elsewhere in the program) is not handled by any arm'),
                hint='add an arm for it, a catch-all arm (`value => …`), or an `else` branch',
            )


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
    if any(value != values[0] for value in values) and all(isinstance(value, ty.IntegerLiteralType) for value in values):
        # integer singleton branches are an `int64` word (`if flag 100 else
        # 0`), as singleton unions are at every value boundary; string
        # singletons keep their union — `'A' | 'B'` is an enum value
        return 'int64'
    return ty.union(*values)


def _unhandled_type_test_members(
    arms: list[hir.IfArm | hir.LoopArm],
    fall_through: Context,
    *,
    ctx: Context,
) -> ty.Type | None:
    """For a chain of `is?` tests on one union binding, the members no arm handles.

    Returns None when the arms are not such a chain; `ty.BOTTOM_TYPE` when the
    chain is exhaustive.
    """
    binding_id: int | None = None
    for arm in arms:
        if not isinstance(arm, hir.IfArm):
            return None
        condition = arm.condition
        if not (
            isinstance(condition, hir.TypeTest)
            and not condition.negated
            and isinstance(condition.value, hir.ExpressedIdentifier)
            and condition.value.binding_id is not None
        ):
            return None
        if binding_id is None:
            binding_id = condition.value.binding_id
        elif binding_id != condition.value.binding_id:
            return None
    if binding_id is None or binding_id not in fall_through.refinements:
        return None
    residual = fall_through.refinements[binding_id]
    if isinstance(residual, ty.TypeOr) and not residual.items:
        return ty.BOTTOM_TYPE
    return residual


def _in_declared_order(joined: ty.Type, binding_id: int, *, ctx: Context) -> ty.Type:
    """A joined union in the binding's declared member order.

    Union tags are physical (the declared union's numbering), so a join of
    per-path narrowings — `[...]` on one path, `0` on the other — must spell
    the declared `0 | [...]` again, not a reordered union of the same members.
    """
    if not isinstance(joined, ty.TypeOr):
        return joined
    binding = ctx.binding_registry.by_id.get(binding_id)
    declared = ty.strip_refinement(binding.type) if binding is not None and binding.type is not None else None
    declared = _number_and_dimension(declared)[0] if declared is not None else None
    if not isinstance(declared, ty.TypeOr):
        return joined
    if all(item in declared.items for item in joined.items):
        ordered = [item for item in declared.items if item in joined.items]
        return declared if len(ordered) == len(declared.items) else ty.TypeOr(ordered)
    return joined


def _tcr_typeof(binop: p0.BinOp, *, ctx: Context) -> hir.AST:
    """`typeof(value)`: the minted type a value carries, as a `type<Family>`
    value — read from its brand word when the static type has types under it,
    else that type itself."""
    arguments = binop.right.inner if isinstance(binop.right, p0.Block) else [binop.right]
    if len(arguments) != 1:
        user_error(ctx.srcfile, '`typeof` takes one value', Pointer(span=binop.right.loc, message='the value whose type is wanted'))
    value = typecheck_and_resolve_inner(arguments[0], ctx=ctx)
    require_valued(value.type, ctx.srcfile, value.loc, '`typeof` operand')
    plain = ty.unfold(ty.strip_refinement(value.type))
    if isinstance(plain, ty.MetaType):
        return value   # a type value's type is itself
    if not (isinstance(plain, ty.ObjectType) and ty.user_branded(plain)):
        # not a minted value: its static type, as a compile-time type value
        return hir.TypeValue(binop.loc, ty.TYPE_TYPE, plain)
    return hir.TypeOf(binop.loc, ty.MetaType(plain), value)


def _metatype_test(value: hir.AST, test: ty.TypeExpr, *, negated: bool, loc: Span, ctx: Context) -> hir.AST | None:
    """`kind is? Whitespace` on a `type<Token>` value: whether the type it names is
    `Whitespace` or minted under it — the brand range test on the value itself."""
    metatype = ty.unfold(ty.strip_refinement(value.type))
    if not isinstance(metatype, ty.MetaType):
        return None
    tested = ty.unfold(test)
    if not (isinstance(tested, ty.ObjectType) and ty.user_branded(tested)):
        return hir.DecidedBool(loc, 'bool', negated)   # a type value is never a string, a number, …: decided
    if tested == metatype.family or ty.user_brand_descends(metatype.family, tested):
        return hir.DecidedBool(loc, 'bool', not negated)   # every type under the family is under the test
    if not ty.user_brand_descends(tested, metatype.family):
        return hir.DecidedBool(loc, 'bool', negated)       # unrelated families
    return hir.TypeTest(loc, 'bool', value, tested, negated)


def _decided_type_test(value_type: ty.Type, test: ty.TypeExpr, *, ctx: Context) -> bool | None:
    """The result of `value is? T` when the value's static type settles it —
    every alternative is a `T` (true) or none can be (false) — else None
    (a runtime test). `any` says nothing, so it is never decided."""
    variants = list(value_type.items) if isinstance(value_type, ty.TypeOr) else [value_type]
    if any(ty.strip_refinement(variant) in (ty.TOP_TYPE, ty.INFERRED_TYPE) for variant in variants):
        return None
    if all(ctx.type_system.is_subtype(variant, test) for variant in variants):
        return True
    if all(_disjoint_types(variant, test, ctx=ctx) for variant in variants):
        return False
    return None


def _disjoint_types(a: ty.TypeExpr, b: ty.TypeExpr, *, ctx: Context) -> bool:
    """Whether no value has both types (`int64` and `string`; not `string` and
    `'0x'`). Objects are exact — a value has one field list — so two object
    types are disjoint unless one is the other's subtype."""
    def members(type_: ty.TypeExpr) -> list[ty.TypeExpr]:
        plain = ty.strip_refinement(type_)
        return list(plain.items) if isinstance(plain, ty.TypeOr) else [plain]

    def disjoint(x: ty.TypeExpr, y: ty.TypeExpr) -> bool:
        x, y = ty.unfold(ty.strip_refinement(x)), ty.unfold(ty.strip_refinement(y))
        if isinstance(x, ty.ObjectType) and isinstance(y, ty.ObjectType):
            return not (ctx.type_system.is_subtype(x, y) or ctx.type_system.is_subtype(y, x))
        if isinstance(x, ty.ObjectType) or isinstance(y, ty.ObjectType):
            return True
        return ctx.type_system.is_empty(ty.intersect(x, y))

    return all(disjoint(x, y) for x in members(a) for y in members(b))


def _refine_type_test(
    current: ty.Type,
    test: ty.TypeExpr,
    *,
    matches: bool,
    ctx: Context,
) -> ty.Type:
    if isinstance(current, ty.MetaType):
        # `kind is? Whitespace`: the type value names a type under `Whitespace`
        tested = ty.unfold(test)
        if matches and isinstance(tested, ty.ObjectType) and ty.user_branded(tested):
            return ty.MetaType(tested)
        return current
    variants: list[ty.TypeExpr] = (
        list(current.items)
        if isinstance(current, ty.TypeOr)
        else [cast(ty.TypeExpr, current)]
    )
    selected: list[ty.TypeExpr] = []
    for variant in variants:
        if ctx.type_system.is_subtype(variant, test):
            if matches:
                selected.append(variant)
        elif ctx.type_system.is_subtype(test, ty.strip_refinement(variant)):
            # a runtime membership test (`s is? '0b' | '0x'` on a string):
            # the value is one of the members when it passes, and stays a
            # string when it fails
            selected.append(test if matches else variant)
        elif not _disjoint_types(variant, test, ctx=ctx):
            selected.append(variant)   # overlapping: the test decides nothing statically
        elif not matches:
            selected.append(variant)
    return ty.union(*selected)


def _length_bound_fact(
    condition: hir.AST,
    truth: bool,
    *,
    ctx: Context,
) -> tuple[int, int] | None:
    """A proven minimum length from `xs.length <op> k` (or `k <op> xs.length`)."""
    if not (
        isinstance(condition, hir.FunctionCall)
        and isinstance(condition.func, hir.ExpressedIdentifier)
        and condition.func.name in {'__gt__', '__ge__', '__lt__', '__le__', '__eq__', '__ne__'}
        and len(condition.pos_args) == 2
    ):
        return None
    left, right = condition.pos_args
    name = condition.func.name

    def length_binding(node: hir.AST) -> int | None:
        if isinstance(node, hir.ArrayLength) and isinstance(node.array.type, ty.ArrayType):
            return sb.array_route_id(node.array, ctx.binding_registry)
        return None

    binding_id = length_binding(left)
    if binding_id is not None:
        constant = _constant_integer(right, ctx=ctx)
        if constant is None:
            return None
        relation = name
    else:
        binding_id = length_binding(right)
        if binding_id is None:
            return None
        constant = _constant_integer(left, ctx=ctx)
        if constant is None:
            return None
        # `k op len` mirrors to `len op' k`.
        relation = {
            '__gt__': '__lt__', '__lt__': '__gt__',
            '__ge__': '__le__', '__le__': '__ge__',
            '__eq__': '__eq__', '__ne__': '__ne__',
        }[name]
    if not truth:
        relation = {
            '__gt__': '__le__', '__le__': '__gt__',
            '__ge__': '__lt__', '__lt__': '__ge__',
            '__eq__': '__ne__', '__ne__': '__eq__',
        }[relation]
    # relation now holds `len <relation> constant` as a true fact.
    if relation == '__gt__':
        return binding_id, max(constant + 1, 0)
    if relation in {'__ge__', '__eq__'}:
        return binding_id, max(constant, 0)
    if relation == '__ne__' and constant == 0:
        return binding_id, 1
    return None


def _refine_condition_context(
    ctx: Context,
    condition: hir.AST,
    *,
    truth: bool,
) -> Context:
    refinements = dict(ctx.refinements)
    key_facts = dict(ctx.key_facts)  # facts are path-sensitive: every refined context owns its copy
    if isinstance(condition, hir.DictContains) and truth:
        # `key in? d` proves the key; when the test directly guards an `if`
        # arm the found position is reused by the guarded lookup
        dictionary = condition.keys.value if isinstance(condition.keys, hir.MemberAccess) else None
        if dictionary is not None:
            refined = replace(ctx, refinements=refinements, key_facts=key_facts)
            _record_key_fact(
                dictionary, condition.key, ctx=refined,
                position=condition.position if getattr(condition, 'hoisted', False) else None,
            )
            return refined
    if isinstance(condition, hir.TypeTest):
        value = condition.value
        fact_id: int | None = None
        if isinstance(value, hir.ExpressedIdentifier) and value.binding_id is not None:
            fact_id = value.binding_id
        elif isinstance(value, hir.MemberAccess):
            # `node.next is? Node` narrows the field's route, like a binding
            fact_id = sb.array_route_id(value, ctx.binding_registry)
        if fact_id is not None:
            current = refinements.get(fact_id, value.type)
            refinements[fact_id] = _refine_type_test(
                current,
                condition.test_type,
                matches=truth != condition.negated,
                ctx=ctx,
            )
        return replace(ctx, refinements=refinements, key_facts=key_facts)
    length_fact = _length_bound_fact(condition, truth, ctx=ctx)
    if length_fact is not None:
        binding_id, minimum = length_fact
        length_bounds = dict(ctx.length_bounds)
        length_bounds[binding_id] = max(length_bounds.get(binding_id, 0), minimum)
        return replace(ctx, refinements=refinements, length_bounds=length_bounds, key_facts=key_facts)
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
    return replace(ctx, refinements=refinements, key_facts=key_facts)


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


def _is_range_type(type_: ty.TypeExpr | None) -> bool:
    return type_ == 'range' or (
        isinstance(type_, ty.TypeParameterize) and type_.t == 'range'
    )


def _resolve_range_value(
    node: hir.AST,
    *,
    ctx: Context,
    _seen: frozenset[int] = frozenset(),
) -> hir.Range | None:
    """Resolve a range-typed expression to its compile-time range literal.

    Range bindings are compile-time values: iterating or testing membership
    against a stored range inlines the literal it was initialized with. Only
    ranges whose anchors are compile-time constants resolve, because inlining
    runtime anchor expressions at the use site could observe mutations made
    after the binding was initialized. Range bindings cannot be reassigned.
    """
    while (
        isinstance(node, hir.Block)
        and not node.scoped
        and len(node.items) == 1
    ):
        node = node.items[0]
    if isinstance(node, hir.Range):
        for anchor in [node.left, node.right, *(node.step_pair or ())]:
            if anchor is None:
                continue
            if _is_string_type(anchor.type):
                if _constant_scalar_grapheme(anchor) is None:
                    return None
            elif _constant_integer(anchor, ctx=ctx) is None:
                return None
        return node
    if (
        isinstance(node, hir.ExpressedIdentifier)
        and node.binding_id is not None
        and node.binding_id not in _seen
    ):
        binding = ctx.binding_registry.by_id.get(node.binding_id)
        if binding is not None and binding.declaration is not None:
            return _resolve_range_value(
                binding.declaration.expr,
                ctx=ctx,
                _seen=_seen | {node.binding_id},
            )
    return None


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


def _tcr_dict_unpack_iterators(
    condition_ast: p0.AST,
    *,
    ctx: Context,
) -> tuple[tuple[hir.IteratorExpression, hir.IteratorExpression], Context] | None:
    """Check a `loop [key value] in dictionary` unpacking condition.

    Dictionaries are hidden parallel arrays, so the unpacking desugars to a
    lockstep pair of array iterators combined with `and`.
    """
    if not (
        isinstance(condition_ast, p0.BinOp)
        and isinstance(condition_ast.op, t1.Operator)
        and condition_ast.op.symbol == 'in'
        and isinstance(condition_ast.left, p0.Block)
        and condition_ast.left.kind == '[]'
    ):
        return None
    targets = condition_ast.left.inner
    if not all(
        isinstance(item, p0.Atom) and isinstance(item.item, t1.Identifier)
        for item in targets
    ):
        return None
    iterable = typecheck_and_resolve_inner(condition_ast.right, ctx=ctx)
    found_dict = _dict_value(iterable)
    if found_dict is None:
        not_implemented(
            ctx.srcfile,
            condition_ast.loc,
            'iterator target unpacking over non-dictionary values',
        )
    if len(targets) != 2:
        user_error(
            ctx.srcfile,
            'dictionary unpacking takes exactly two targets',
            Pointer(
                span=condition_ast.left.loc,
                message='use `[key value]` to unpack dictionary entries',
            ),
        )
    names = [
        item.item.name
        for item in targets
        if isinstance(item, p0.Atom) and isinstance(item.item, t1.Identifier)
    ]
    dictionary, key_type, value_type = found_dict
    # iteration compacts away removed entries, which moves entries: forget
    # remembered positions and exact lengths
    _forget_positions(dictionary, ctx=ctx)
    _invalidate_dict_lengths(dictionary, ctx=ctx)
    keys: hir.AST = hir.DictEntries(condition_ast.loc, ty.ArrayType(key_type, None), dictionary, 'keys')
    values: hir.AST = hir.DictEntries(condition_ast.loc, ty.ArrayType(value_type, None), dictionary, 'values')
    key_iterator, ctx_after_key = _array_expression_iterator(
        names[0], targets[0].loc, keys, condition_ast.loc, ctx=ctx,
    )
    value_iterator, ctx_after_value = _array_expression_iterator(
        names[1], targets[1].loc, values, condition_ast.loc, ctx=ctx_after_key,
    )
    ctx_after_value = replace(ctx_after_value, key_facts=dict(ctx_after_value.key_facts))
    _record_key_fact(found_dict[0], key_iterator.target, ctx=ctx_after_value)
    return (key_iterator, value_iterator), ctx_after_value


def _array_expression_iterator(
    target_name: str,
    target_loc: Span,
    iterable: hir.AST,
    loc: Span,
    *,
    ctx: Context,
) -> tuple[hir.IteratorExpression, Context]:
    """Build an iterator over an array-typed expression (a dictionary's entry arrays)."""
    array_type = iterable.type
    assert isinstance(array_type, ty.ArrayType)
    element_type = array_type.element
    binding = ctx.binding_registry.allocate_param(target_name, element_type, target_loc)
    iterator_ctx = replace(
        ctx,
        declarations=ctx.declarations.new_child({target_name: element_type}),
        binding_scopes=ctx.binding_scopes.new_child({target_name: binding}),
    )
    target = hir.ExpressedIdentifier(target_loc, element_type, target_name, binding_id=binding.id)
    return (
        hir.IteratorExpression(
            loc,
            ty.TypeParameterize('iterator', [element_type]),
            target,
            iterable,
            0,
            1,
            None if array_type.length is None else array_type.length - 1,
            array_type.length,
        ),
        iterator_ctx,
    )


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
        resolved_range = _resolve_range_value(iterable, ctx=ctx)
        if resolved_range is not None:
            iterable = resolved_range
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
                    (ty.FunctionType, ty.StringLiteralType, ty.StringType, ty.ObjectType, ty.MetaType),
                )
                or isinstance(element_type, str)
                and element_type in {'string', 'grapheme', 'char'}
                or ty.string_valued(element_type)
                or _optional_container_element(element_type)
                or _union_container_element(element_type)
            ):
                not_implemented(
                    ctx.srcfile,
                    condition_ast.right.loc,
                    'array iteration over elements with unsettled identity semantics',
                )
            target_type = element_type
            count = iterable.type.length
        elif ty.set_element(iterable.type) is not None:
            # a set iterates its live members in insertion order (compacting
            # first when removals left tombstones)
            target_type = ty.set_element(iterable.type)
            count = None
            _forget_positions(iterable, ctx=ctx)
            _invalidate_dict_lengths(iterable, ctx=ctx)
            iterable = hir.DictEntries(iterable.loc, ty.ArrayType(target_type, None), iterable, 'keys')
        if target_type is not None:
            binding = ctx.binding_registry.allocate_param(
                identifier.name,
                target_type,
                identifier.loc,
            )
            if isinstance(target_type, ty.ObjectType):
                # the loop variable borrows the element (no copy per iteration)
                binding.read_only_reason = 'borrows the array element, so it is read-only (copy it with `let` to change it)'
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
            if isinstance(iterable, hir.DictEntries):
                iterator_ctx = replace(iterator_ctx, key_facts=dict(iterator_ctx.key_facts))
                _record_key_fact(iterable.dictionary, target, ctx=iterator_ctx)
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


def _and_operands(ast: p0.AST) -> list[p0.AST]:
    """The operands of a word-`and` chain (one item for anything else)."""
    if isinstance(ast, p0.BinOp) and isinstance(ast.op, t1.Operator) and ast.op.symbol == 'and':
        return [*_and_operands(ast.left), *_and_operands(ast.right)]
    return [ast]


def _join_and(operands: list[p0.AST]) -> p0.AST:
    joined = operands[0]
    for operand in operands[1:]:
        joined = p0.BinOp(Span(joined.loc.start, operand.loc.stop), t1.Operator(Span(joined.loc.stop, operand.loc.start), 'and'), joined, operand)
    return joined


def _runtime_range_parts(iterable: p0.AST) -> tuple[p0.AST, p0.AST, str] | None:
    """A range spelling whose end is a runtime expression: the open range that
    replaces it, the end expression, and the comparison that guards it
    (`0..argv.length` -> `0..`, `argv.length`, `<=?`; `[0..n)` -> `<?`)."""
    bounds = '[]'
    flat = iterable
    if isinstance(flat, p0.Block) and flat.kind in ('[)', '[]') and len(flat.inner) == 1:
        bounds = flat.kind
        flat = flat.inner[0]
    if not (isinstance(flat, p0.Flat) and isinstance(flat.op, t2.RangeJuxtapose) and len(flat.items) == 3):
        return None
    start, dots, end = flat.items
    if _refinement_bound_ast(start) is None or _literal_integer_ast(start) is None and _refinement_bound_ast(start) is None:
        return None   # a runtime start still needs the general runtime range representation
    if _refinement_bound_ast(end) is not None:
        return None   # a constant end stays on the normalized path
    open_range = p0.Flat(Span(start.loc.start, dots.loc.stop), flat.op, [start, dots])
    return open_range, end, ('<?' if bounds == '[)' else '<=?')


def _rewrite_runtime_range_ends(condition_ast: p0.AST) -> p0.AST:
    """`loop i in 0..argv.length` (or `[0..n)`) iterates the open range under a
    guard: the end becomes the predicate `i <=? end` (`<?` when exclusive),
    joining any written predicates. The guard bounds the counter the way an
    explicit `i <? n` does."""
    operands = _and_operands(condition_ast)
    rewritten: list[p0.AST] = []
    changed = False
    for operand in operands:
        if (
            isinstance(operand, p0.BinOp)
            and isinstance(operand.op, t1.Operator)
            and operand.op.symbol == 'in'
            and isinstance(operand.left, p0.Atom)
            and isinstance(operand.left.item, t1.Identifier)
        ):
            parts = _runtime_range_parts(operand.right)
            if parts is not None:
                open_range, end, comparison = parts
                rewritten.append(replace(operand, right=open_range))
                rewritten.append(p0.BinOp(
                    Span(operand.left.loc.start, end.loc.stop),
                    t1.Operator(end.loc, comparison),
                    operand.left,
                    end,
                ))
                changed = True
                continue
        rewritten.append(operand)
    return _join_and(rewritten) if changed else condition_ast


def _rewrite_nested_unpack_targets(condition_ast: p0.AST, *, ctx: Context) -> tuple[p0.AST, list[tuple[str, list[tuple[str, Span]], Span]]]:
    """`loop [prefix [digits ci]] in specs`: a nested unpack target becomes a
    hidden binding, and the body opens by declaring each written name as the
    matching field of that binding (by position)."""
    unpacks: list[tuple[str, list[tuple[str, Span]], Span]] = []
    operands = _and_operands(condition_ast)
    rewritten: list[p0.AST] = []
    changed = False
    for operand in operands:
        if (
            isinstance(operand, p0.BinOp)
            and isinstance(operand.op, t1.Operator)
            and operand.op.symbol == 'in'
            and isinstance(operand.left, p0.Block)
            and operand.left.kind == '[]'
            and any(isinstance(item, p0.Block) for item in operand.left.inner)
        ):
            targets: list[p0.AST] = []
            for item in operand.left.inner:
                if isinstance(item, p0.Block) and item.kind == '[]' and all(
                    isinstance(inner, p0.Atom) and isinstance(inner.item, t1.Identifier) for inner in item.inner
                ):
                    hidden = f'__dewy_unpack_{ctx.binding_registry.next_id}_{len(unpacks)}'
                    names = [(inner.item.name, inner.loc) for inner in item.inner]   # type: ignore[union-attr]
                    unpacks.append((hidden, names, item.loc))
                    targets.append(p0.Atom(item.loc, t1.Identifier(item.loc, hidden)))
                    changed = True
                else:
                    targets.append(item)
            rewritten.append(replace(operand, left=replace(operand.left, inner=targets)))
            continue
        rewritten.append(operand)
    return (_join_and(rewritten) if changed else condition_ast), unpacks


def _declare_nested_unpacks(
    unpacks: list[tuple[str, list[tuple[str, Span]], Span]],
    body_ctx: Context,
    *,
    ctx: Context,
) -> tuple[list[hir.AST], Context]:
    """The per-iteration declarations of a nested unpack: each written name is a
    copy of the hidden binding's field at the same position."""
    declares: list[hir.AST] = []
    additions: dict[str, ty.Type] = {}
    bindings: dict[str, sb.Binding] = {}
    for hidden, names, loc in unpacks:
        hidden_binding = body_ctx.binding_scopes.get(hidden)
        hidden_type = ty.unfold(ty.strip_refinement(body_ctx.declarations.get(hidden) or ty.TOP_TYPE))
        if not isinstance(hidden_type, ty.ObjectType):
            user_error(
                ctx.srcfile,
                'nested unpacking needs an object element',
                Pointer(span=loc, message=f'the iterated element has type `{type_to_dewy(body_ctx.declarations.get(hidden) or ty.TOP_TYPE)}`'),
            )
        if len(names) != len(hidden_type.fields):
            user_error(
                ctx.srcfile,
                'nested unpacking must name every field',
                Pointer(span=loc, message=f'{len(names)} name{"s" if len(names) != 1 else ""} for {len(hidden_type.fields)} field{"s" if len(hidden_type.fields) != 1 else ""} ({", ".join(field.name for field in hidden_type.fields)})'),
            )
        source = hir.ExpressedIdentifier(loc, hidden_type, hidden, binding_id=hidden_binding.id if hidden_binding is not None else None)
        for (name, name_loc), field in zip(names, hidden_type.fields):
            binding = ctx.binding_registry.allocate_param(name, field.type, name_loc)
            declares.append(hir.Declare(
                name_loc,
                ty.VOID_TYPE,
                'let',
                name,
                field.type,
                hir.MemberAccess(name_loc, field.type, source, field.name, field.mutable),
                binding_id=binding.id,
            ))
            additions[name] = field.type
            bindings[name] = binding
    return declares, replace(
        body_ctx,
        declarations=body_ctx.declarations.new_child(additions),
        binding_scopes=body_ctx.binding_scopes.new_child(bindings),
    )


def _split_loop_condition(condition_ast: p0.AST) -> tuple[list[p0.AST], list[p0.AST]]:
    """`loop i in 0.. and i <? n and src[i] in? ws`: the iterator clauses of the
    top-level `and` chain, and the Boolean predicates that guard each iteration."""
    iterators: list[p0.AST] = []
    predicates: list[p0.AST] = []
    for operand in _and_operands(condition_ast):
        (iterators if _contains_iterator_syntax(operand) else predicates).append(operand)
    return iterators, predicates


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

        unpack = _tcr_dict_unpack_iterators(ast, ctx=current_ctx)
        if unpack is not None:
            pair, iterator_ctx = unpack
            formula: list[hir.IteratorFormulaToken] = []
            for iterator in pair:
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
                formula.append(len(iterators))
                iterators.append(iterator)
            formula.append('and')
            return formula, iterator_ctx

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
    # Runtime-length arrays advance at runtime against their length. That is
    # supported for pure `and` (zip-shortest) formulas, whose all-exhausted
    # truth is false, so the loop cannot repeat forever.
    lockstep_dynamic = dynamic_array is not None and all(
        isinstance(token, int) or token == 'and' for token in formula
    )
    if dynamic_array is not None and not lockstep_dynamic:
        not_implemented(
            ctx.srcfile,
            dynamic_array.iterable.loc,
            'dynamic-length arrays in multiiterator formulas other than `and`',
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
    repeats = stop is None and not lockstep_dynamic
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


def tcr_flow(ast: p0.Flow, *, ctx: Context, expected: ty.Type | None = None) -> hir.AST:
    """Typecheck supported structured `if` and while-style `loop` flows."""
    if not ast.arms:
        raise ValueError('INTERNAL ERROR: Flow has no arms')

    keywords: list[str] = []
    for arm in ast.arms:
        if not arm.parts or not isinstance(arm.parts[0], t1.Keyword):
            raise ValueError(f'INTERNAL ERROR: malformed flow arm: {arm.parts!r}')
        keywords.append(arm.parts[0].name)

    unsupported = next(
        (keyword for keyword in keywords if keyword not in {'if', 'loop', 'match'}),
        None,
    )
    if unsupported is not None:
        not_implemented(ctx.srcfile, ast.loc, f'`{unsupported}` flow')

    if all(keyword in ('if', 'match') for keyword in keywords):
        branch_expected = _flow_expected(expected)
        if isinstance(branch_expected, ty.SequenceType):
            not_implemented(ctx.srcfile, ast.loc, 'multi-value conditional result')
        # Every arm is a spec: an `if` arm checks its condition and body
        # syntax; a `match` arm expands to one spec per pattern (see
        # `match.md`), with its scrutinee declared before the flow.
        specs: list[_FlowArmSpec] = []
        match_prelude: list[hir.AST] = []
        match_total = False
        match_present = False
        match_uncovered: str | None = None
        for arm in ast.arms:
            if len(arm.parts) != 3:
                raise ValueError(f'INTERNAL ERROR: malformed flow arm: {arm.parts!r}')
            keyword, condition_ast, body_ast = arm.parts
            assert isinstance(keyword, t1.Keyword)
            assert isinstance(condition_ast, p0.AST)
            assert isinstance(body_ast, p0.AST)
            if keyword.name == 'match':
                match_present = True
                pending_before = len(pending_brand_matches)
                arm_specs, prelude, total, uncovered = _match_arm_specs(arm, condition_ast, body_ast, ctx=ctx)
                if ast.default is not None:
                    del pending_brand_matches[pending_before:]   # `else` takes whatever is minted later
                specs.extend(arm_specs)
                match_prelude.extend(prelude)
                match_total = match_total or total
                if uncovered is not None and match_uncovered is None:
                    match_uncovered = uncovered
                continue
            specs.append(_if_arm_spec(arm.loc, condition_ast, body_ast))
        if match_present and ast.default is None and not match_total:
            user_error(
                ctx.srcfile,
                'match is not exhaustive',
                Pointer(span=ast.loc, message=f'{match_uncovered} is not handled by any arm' if match_uncovered else 'the arms do not cover the scrutinee'),
                hint='add an arm for it, a catch-all arm (`value => …`), or an `else` branch',
            )
        arms: list[hir.IfArm | hir.LoopArm] = []
        bodies: list[hir.AST] = []
        # Refinement state at the end of every path that can reach the code
        # after the flow; the continuation keeps their join.
        continuing_paths: list[dict[int, ty.Type]] = []
        continuing_bounds: list[dict[int, int]] = []
        continuing_keys: list[dict] = []
        arm_ctx = ctx
        constant_true = False
        for arm in specs:
            body_ast = arm.body_ast
            condition = arm.condition(arm_ctx)
            if isinstance(condition, hir.DictContains):
                condition.hoisted = True  # its search runs right before the flow: the position is in scope
            if isinstance(condition, (hir.TargetBool, hir.DecidedBool)):
                # Target queries (`$target =? "..."`) select arms during
                # checking: dead arms are not checked at all (they may import
                # files for other targets), and the live arm's `{}` body is
                # spliced into the enclosing scope so gated imports and
                # declarations bind there. A type test the static types
                # decide (`DecidedBool`) selects arms the same way — in a
                # generic instance, the arm written for this type — but the
                # live body keeps its own scope. Plain literal conditions keep
                # the ordinary flow semantics (every arm checked).
                if not condition.value:
                    continue
                constant_true = True
                if (
                    isinstance(condition, hir.TargetBool)
                    and branch_expected is None
                    and isinstance(body_ast, p0.Block)
                    and body_ast.kind == '{}'
                ):
                    spliced = [
                        typecheck_and_resolve_inner(item, ctx=arm_ctx)
                        for item in body_ast.inner
                    ]
                    # ``scoped=False`` lets the enclosing block flatten it.
                    return hir.Block(body_ast.loc, ty.VOID_TYPE, spliced, False)
                else:
                    body = arm.body(arm_ctx, branch_expected)
                    if branch_expected is not None:
                        body = check_against(body, branch_expected, ctx=ctx)
                    if not arms:
                        return body   # the first arm is always taken: the flow is its body
                arms.append(hir.IfArm(arm.loc, body.type, condition, body))
                bodies.append(body)
                if body.type != ty.BOTTOM_TYPE:
                    continuing_paths.append(dict(arm_ctx.refinements))
                    continuing_bounds.append(dict(arm_ctx.length_bounds))
                    continuing_keys.append(dict(arm_ctx.key_facts))
                break
            body_ctx = _refine_condition_context(
                arm_ctx,
                condition,
                truth=True,
            )
            body = arm.body(body_ctx, branch_expected)
            if branch_expected is not None:
                body = check_against(body, branch_expected, ctx=ctx)
            arms.append(hir.IfArm(arm.loc, body.type, condition, body))
            bodies.append(body)
            if body.type != ty.BOTTOM_TYPE:
                continuing_paths.append(dict(body_ctx.refinements))
                continuing_bounds.append(dict(body_ctx.length_bounds))
                continuing_keys.append(dict(body_ctx.key_facts))
            arm_ctx = _refine_condition_context(
                arm_ctx,
                condition,
                truth=False,
            )

        default = None
        # An `is?` chain that rules out every member of the tested union is
        # exhaustive: the last arm becomes the default (its condition can only
        # be true on that path), so downstream passes see an ordinary if/else.
        unhandled = _unhandled_type_test_members(arms, arm_ctx, ctx=ctx) if ast.default is None and not constant_true else None
        chain_exhaustive = (unhandled is not None and unhandled == ty.BOTTOM_TYPE) or (match_total and ast.default is None and not constant_true)
        if constant_true:
            # later arms and the default are dead; a type test decided true
            # after other arms (`… else if v is? string`, the last member) is
            # the chain's default, so downstream passes see an ordinary if/else
            if len(arms) > 1 and isinstance(arms[-1].condition, hir.DecidedBool):
                last = arms.pop()
                assert isinstance(last, hir.IfArm)
                default = last.body
        elif chain_exhaustive:
            last = arms.pop()
            assert isinstance(last, hir.IfArm)
            default = last.body
        elif ast.default is not None:
            default = typecheck_and_resolve_inner(
                ast.default,
                ctx=arm_ctx,
                expected=branch_expected,
            )
            if branch_expected is not None:
                default = check_against(default, branch_expected, ctx=ctx)
            bodies.append(default)
            if default.type != ty.BOTTOM_TYPE:
                continuing_paths.append(dict(arm_ctx.refinements))
                continuing_bounds.append(dict(arm_ctx.length_bounds))
                continuing_keys.append(dict(arm_ctx.key_facts))
        elif not constant_true:
            # No else: falling through means every condition was false.
            continuing_paths.append(dict(arm_ctx.refinements))
            continuing_bounds.append(dict(arm_ctx.length_bounds))
            continuing_keys.append(dict(arm_ctx.key_facts))
        if chain_exhaustive and not arms and default is not None:
            # a single-arm chain covering the whole union is just its body
            arms.append(hir.IfArm(specs[0].loc, default.type, hir.Bool(ast.loc, 'bool', True), default))
            default = None
        if constant_true and not arms:
            raise ValueError('INTERNAL ERROR: constant-true flow without arms')
        if not arms and default is not None:
            # every arm was a compile-time false: the flow is its `else`
            return default
        if not arms:
            # Every arm was a compile-time false: nothing remains.
            return hir.Void(ast.loc, ty.VOID_TYPE)
        if continuing_paths:
            # ``ctx.refinements`` is the dict shared by the enclosing block's
            # items, so updating it in place narrows the code after the flow.
            # A binding stays refined only when every continuing path refines
            # it; the joined type is the union of the per-path types.
            joined: dict[int, ty.Type] = {}
            length_minimums: dict[int, int] = {}
            for binding_id in set.intersection(*(set(path) for path in continuing_paths)):
                types = [path[binding_id] for path in continuing_paths]
                if all(isinstance(item, ty.ArrayType) for item in types):
                    # exact-length refinements join to one exact length, or
                    # to a proven minimum when the paths disagree
                    arrays = cast(list[ty.ArrayType], types)
                    lengths = {array.length for array in arrays}
                    if len(lengths) == 1:
                        joined[binding_id] = arrays[0]
                    elif None not in lengths:
                        length_minimums[binding_id] = min(cast(set[int], lengths))
                    continue
                joined[binding_id] = _in_declared_order(ty.union(*types), binding_id, ctx=ctx)
            ctx.refinements.clear()
            ctx.refinements.update(joined)
            joined_bounds: dict[int, int] = {}
            for binding_id in set.intersection(*(set(path) for path in continuing_bounds)):
                joined_bounds[binding_id] = min(path[binding_id] for path in continuing_bounds)
            for binding_id, minimum in length_minimums.items():
                joined_bounds[binding_id] = max(joined_bounds.get(binding_id, 0), minimum)
            ctx.length_bounds.clear()
            ctx.length_bounds.update(joined_bounds)
            # a key stays proven only on every path; a shared position only
            # when every path found it at the same local
            joined_keys: dict = {}
            for fact_key in set.intersection(*(set(path) for path in continuing_keys)):
                positions = {path[fact_key] for path in continuing_keys}
                joined_keys[fact_key] = positions.pop() if len(positions) == 1 else (None, None)
            ctx.key_facts.clear()
            ctx.key_facts.update(joined_keys)
        else:
            # Everything diverges: the continuation is unreachable, keep the
            # all-conditions-false state.
            ctx.refinements.clear()
            ctx.refinements.update(arm_ctx.refinements)
            ctx.length_bounds.clear()
            ctx.length_bounds.update(arm_ctx.length_bounds)
            ctx.key_facts.clear()
            ctx.key_facts.update(arm_ctx.key_facts)
        if ast.default is None and not constant_true and not chain_exhaustive and (
            branch_expected is not None
            and any(body.type != ty.BOTTOM_TYPE for body in bodies)
        ):
            missing = (
                f'`{type_to_dewy(unhandled)}` is not handled by any `is?` arm'
                if unhandled is not None
                else 'this conditional is not exhaustive'
            )
            user_error(
                ctx.srcfile,
                'value-producing conditional requires a default branch',
                Pointer(span=ast.loc, message=missing),
                hint='add an `else` branch that produces the missing value' if unhandled is None
                else 'add an arm for the unhandled member, or an `else` branch',
            )

        result_type = _flow_value_type(
            bodies,
            exhaustive=default is not None or chain_exhaustive,   # a single covering arm has no default left
            ctx=ctx,
            loc=ast.loc,
        )
        if (
            branch_expected is not None
            and result_type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE)
        ):
            result_type = branch_expected
        flow = hir.Flow(ast.loc, result_type, arms, default)
        if match_prelude:
            # the scrutinee's hidden local precedes the flow; ``scoped=False``
            # lets the enclosing block flatten it so narrowing after the
            # match still reaches the enclosing scope
            return hir.Block(ast.loc, result_type, [*match_prelude, flow], False)
        return flow

    if len(ast.arms) == 1 and keywords == ['loop'] and ast.default is None:
        arm = ast.arms[0]
        if len(arm.parts) != 3:
            not_implemented(ctx.srcfile, arm.loc, 'iterator or generator loop form')
        _, condition_ast, body_ast = arm.parts
        assert isinstance(condition_ast, p0.AST)
        assert isinstance(body_ast, p0.AST)
        # iterator clauses mixed with Boolean predicates (`loop i in 0.. and
        # i <? n and src[i] in? ws`): the iterators advance, then the
        # predicates are tested with the targets bound — the loop ends at the
        # first false — and their truth refines the body
        condition_ast = _rewrite_runtime_range_ends(condition_ast)
        condition_ast, nested_unpacks = _rewrite_nested_unpack_targets(condition_ast, ctx=ctx)
        predicates: list[p0.AST] = []
        iterator_ast = condition_ast
        if _contains_iterator_syntax(condition_ast):
            iterator_parts, predicates = _split_loop_condition(condition_ast)
            if predicates and iterator_parts:
                iterator_ast = _join_and(iterator_parts)
        iterator_result = _tcr_loop_iterator(iterator_ast, ctx=ctx)
        guard: hir.AST | None = None
        unpack_declares: list[hir.AST] = []
        if iterator_result is None:
            if nested_unpacks:
                not_implemented(ctx.srcfile, condition_ast.loc, 'nested unpacking in this loop condition')
            condition = _check_flow_condition(condition_ast, ctx=ctx)
            body_ctx = _refine_condition_context(ctx, condition, truth=True)
        else:
            condition, body_ctx = iterator_result
            if nested_unpacks:
                unpack_declares, body_ctx = _declare_nested_unpacks(nested_unpacks, body_ctx, ctx=ctx)
            if predicates:
                predicate_ast = _join_and(predicates)
                predicate = _check_flow_condition(predicate_ast, ctx=body_ctx)
                body_ctx = _refine_condition_context(body_ctx, predicate, truth=True)
                # `loop i in 0.. and i <? n`: the guard bounds the counter
                from .analyze.bounds import predicate_bounds_counter

                def guarded(iterator: hir.IteratorExpression) -> hir.IteratorExpression:
                    beyond_word = iterator.count is None or (iterator.last is not None and not ty.integer_literal_fits(iterator.last, 'int64'))
                    if beyond_word and iterator.target.binding_id is not None and predicate_bounds_counter(predicate, iterator.target.binding_id):
                        return replace(iterator, guarded=True)
                    return iterator

                if isinstance(condition, hir.IteratorExpression):
                    condition = guarded(condition)
                elif isinstance(condition, hir.MultiIteratorExpression):
                    condition = replace(condition, iterators=[guarded(iterator) for iterator in condition.iterators])
                guard = hir.Flow(
                    predicate_ast.loc,
                    ty.VOID_TYPE,
                    [hir.IfArm(predicate_ast.loc, ty.VOID_TYPE, predicate, hir.Void(predicate_ast.loc, ty.VOID_TYPE))],
                    hir.Break(predicate_ast.loc, ty.BOTTOM_TYPE, None, 0),
                )
        # A refinement established before the loop is only sound inside the
        # body if nothing in the body can invalidate it on a later iteration,
        # so drop refinements of every binding the body assigns or grows.
        iterated_containers = _iterated_container_names(condition)
        for mutated_name in _mutated_binding_names(body_ast):
            if mutated_name in iterated_containers:
                # Python raises "changed size during iteration" at runtime;
                # entries may move (compaction, resize), so it is rejected here
                user_error(
                    ctx.srcfile,
                    f'cannot mutate `{mutated_name}` while iterating it',
                    Pointer(span=body_ast.loc, message=f'this loop body changes `{mutated_name}`, the container it iterates'),
                    hint='collect the changes and apply them after the loop',
                )
            mutated_binding = ctx.binding_scopes.get(mutated_name)
            if mutated_binding is not None:
                invalidated = [
                    mutated_binding.id,
                    *ctx.binding_registry.routes_under(mutated_binding.id),
                ]
                for invalidated_id in invalidated:
                    ctx.refinements.pop(invalidated_id, None)
                    body_ctx.refinements.pop(invalidated_id, None)
                    ctx.length_bounds.pop(invalidated_id, None)
                    body_ctx.length_bounds.pop(invalidated_id, None)
                    _drop_key_facts(ctx, dictionary_id=invalidated_id)
                    _drop_key_facts(body_ctx, dictionary_id=invalidated_id)
                    _drop_key_facts(ctx, key_id=invalidated_id)
                    _drop_key_facts(body_ctx, key_id=invalidated_id)
        if iterator_result is None:
            # The condition is re-evaluated before every iteration, so the
            # facts it establishes hold at the top of the body even when the
            # body mutates the tested bindings; only facts inherited from
            # before the loop were dropped above.
            body_ctx = _refine_condition_context(ctx, condition, truth=True)
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
        if guard is not None or unpack_declares:
            body = hir.Block(body.loc, body.type, [*unpack_declares, *([guard] if guard is not None else []), body], False)
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
        if metatag is None or metatag.name == 'test':
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


def _operator_symbol(op: object) -> str | None:
    """The source operator of a p0 operator token (`not=?` reports its base comparison)."""
    symbol = getattr(op, 'symbol', None)
    return symbol if symbol is not None else getattr(op, 'op', None)


def _is_literal_atom(node: p0.AST) -> bool:
    return isinstance(node, p0.Atom) and isinstance(
        node.item, (t1.Integer, t1.Real, t1.String, t1.BasedString, t1.Bool)
    )


def _assert_operands(node: p0.AST) -> list[p0.AST]:
    """The non-literal operands of the comparisons inside a condition, for the failure report."""
    node = _sink_ambiguity(node)
    if isinstance(node, p0.BinOp):
        symbol = _operator_symbol(node.op)
        if symbol in _ASSERT_LOGICAL_OPERATORS:
            return [*_assert_operands(node.left), *_assert_operands(node.right)]
        if symbol in _ASSERT_COMPARISON_OPERATORS:
            return [side for side in (node.left, node.right) if not _is_literal_atom(side)]
        return []
    if isinstance(node, p0.Prefix) and _operator_symbol(node.op) == 'not':
        return _assert_operands(node.item)
    if isinstance(node, p0.Block) and node.kind == '()' and len(node.inner) == 1:
        return _assert_operands(node.inner[0])
    return []


def _assert_source(node: p0.AST, *, ctx: Context) -> str:
    return ' '.join(ctx.srcfile.body[node.loc.start:node.loc.stop].split())


def _report_refuted_assertion(loc: Span, source: str, message: str | None, *, dimmed: Span | None, ctx: Context) -> NoReturn:
    user_error(
        ctx.srcfile,
        'assertion refuted',
        Pointer(span=loc, message=message if message is not None else 'this condition is false at compile time'),
        notes=[f'`{source}` folds to `false`'],
        dimmed=[dimmed] if dimmed is not None else None,
    )


def tcr_assert(ast: p0.AssertDirective, *, ctx: Context) -> hir.AST:
    """`$assert` is a compile-time obligation; `$runtime_assert` checks at runtime and diverges on failure.

    Both take `condition` or `condition, message`. A condition the checker
    already folds is decided here; otherwise `$assert` leaves a `hir.Assert`
    for the bounds analysis to prove (or refute), and `$runtime_assert`
    becomes `if condition {} else { report; _exit(101) }` whose failure body
    diverges, so the code after it keeps the condition's facts exactly as
    code after an early-return guard does.
    """
    if ast.name == 'fail':
        return _tcr_fail(ast, ctx=ctx)
    if ast.name == 'abstract':
        user_error(
            ctx.srcfile,
            '`$abstract` marks a `type of` mint',
            Pointer(span=ast.loc, message='it belongs on the value of a type alias'),
            hint='`Context = $abstract type of any & [...]`',
        )
    assert ast.condition is not None
    condition_ast, message_ast = _sink_ambiguity(ast.condition), ast.message
    condition = _check_flow_condition(condition_ast, ctx=ctx)
    if isinstance(condition, hir.DictContains):
        condition.hoisted = True
    source = _assert_source(condition_ast, ctx=ctx)
    # the `, message` tail is greyed out in reports so the condition stands out
    dimmed = Span(condition_ast.loc.stop, message_ast.loc.stop) if message_ast is not None else None
    if ast.name == 'assert':
        message: str | None = None
        if message_ast is not None:
            checked = typecheck_and_resolve_inner(message_ast, ctx=ctx)
            if not isinstance(checked, hir.String):
                user_error(
                    ctx.srcfile,
                    'a compile-time assertion message must be a string literal',
                    Pointer(span=message_ast.loc, message='the message is reported at compile time, so it cannot depend on runtime values'),
                    hint='`$runtime_assert` messages may interpolate values',
                )
            message = checked.content
        if isinstance(condition, hir.Bool):
            if not condition.value:
                _report_refuted_assertion(condition_ast.loc, source, message, dimmed=dimmed, ctx=ctx)
            return hir.Void(ast.loc, ty.VOID_TYPE)
        return hir.Assert(ast.loc, ty.VOID_TYPE, condition, source, message, dimmed=dimmed)

    if ast.name == 'expect':
        return _tcr_expect(ast, condition_ast, message_ast, condition, source, dimmed=dimmed, ctx=ctx)

    if isinstance(condition, hir.Bool):
        if not condition.value:
            _report_refuted_assertion(condition_ast.loc, source, None, dimmed=dimmed, ctx=ctx)
        if message_ast is not None:
            typecheck_and_resolve_inner(message_ast, ctx=ctx)
        return hir.Void(ast.loc, ty.VOID_TYPE)
    failure_ctx = _refine_condition_context(ctx, condition, truth=False)
    failure = hir.Block(
        ast.loc,
        ty.BOTTOM_TYPE,
        _assert_failure_report(ast, condition_ast, message_ast, source, ctx=failure_ctx),
        True,
    )
    flow = hir.Flow(
        ast.loc,
        ty.VOID_TYPE,
        [hir.IfArm(ast.loc, ty.VOID_TYPE, condition, hir.Void(ast.loc, ty.VOID_TYPE))],
        failure,
    )
    # the analyses still reject a condition they can refute outright
    obligation = hir.Assert(ast.loc, ty.VOID_TYPE, condition, source, None, runtime=True, dimmed=dimmed)
    # The code after the assertion runs only when the condition held (the
    # failure path diverges), like the continuation of an early-return guard.
    held = _refine_condition_context(ctx, condition, truth=True)
    refinements, bounds, keys = dict(held.refinements), dict(held.length_bounds), dict(held.key_facts)
    ctx.refinements.clear()
    ctx.refinements.update(refinements)
    ctx.length_bounds.clear()
    ctx.length_bounds.update(bounds)
    ctx.key_facts.clear()
    ctx.key_facts.update(keys)
    return hir.Block(ast.loc, ty.VOID_TYPE, [obligation, flow], False)


def _tcr_fail(ast: p0.AssertDirective, *, ctx: Context) -> hir.AST:
    """`$fail message` / `$fail`: an expectation that always fails — the deliberate "fail here" of a test."""
    _require_expectation_site(ast, ctx=ctx)
    ctx.catcher.returns.append((ast.loc, ty.VOID_TYPE))
    return hir.Block(
        ast.loc,
        ty.BOTTOM_TYPE,
        _assert_failure_report(ast, ast, ast.message, 'fail', ctx=ctx, expect=True),
        True,
    )


def _require_expectation_site(ast: p0.AssertDirective, *, ctx: Context) -> None:
    """`$expect`/`$fail` return from the enclosing function on failure: it must exist and return `void`."""
    if ctx.catcher is None:
        user_error(
            ctx.srcfile,
            f'`${ast.name}` outside a function',
            Pointer(span=ast.loc, message='a failed expectation returns from the enclosing function, and nothing here catches that'),
            hint='put the expectation in a `$test` function (or a helper it calls); module-level facts are `$assert`',
        )
    if ctx.catcher.expected is not None and ctx.catcher.expected != ty.VOID_TYPE:
        user_error(
            ctx.srcfile,
            f'`${ast.name}` in a function that returns a value',
            Pointer(span=ast.loc, message=f'a failed expectation returns from this function without a value, but it returns `{type_to_dewy(ctx.catcher.expected)}`'),
            hint='expectations belong in `void` functions; a helper that computes a value can return it to the test that checks it',
        )


def _tcr_expect(
    ast: p0.AssertDirective,
    condition_ast: p0.AST,
    message_ast: p0.AST | None,
    condition: hir.AST,
    source: str,
    *,
    dimmed: Span | None,
    ctx: Context,
) -> hir.AST:
    """`$expect condition, message`: a test expectation.

    Like `$runtime_assert`, the failure path reports the condition, its
    message and the operands' values; unlike it, failing is not fatal — the
    failure is recorded (`_expect_failed`) and the enclosing function
    *returns*, so the code after an expectation may assume it exactly as the
    code after an assertion does, and a test stops at its first failure. A
    condition the compiler refutes is a warning, not an error: the test still
    builds and fails when it runs (a literal `false` is the deliberate
    "fail here" and is not warned about).
    """
    _require_expectation_site(ast, ctx=ctx)
    ctx.catcher.returns.append((ast.loc, ty.VOID_TYPE))
    if isinstance(condition, hir.Bool):
        if condition.value:
            if message_ast is not None:
                typecheck_and_resolve_inner(message_ast, ctx=ctx)
            return hir.Void(ast.loc, ty.VOID_TYPE)
        if not (isinstance(condition_ast, p0.Atom) and isinstance(condition_ast.item, t1.Bool)):
            user_warning(
                ctx.srcfile,
                'expectation refuted at compile time',
                Pointer(span=condition_ast.loc, message='this condition is false'),
                hint='the test will fail when it runs',
            )
        return hir.Block(
            ast.loc,
            ty.BOTTOM_TYPE,
            _assert_failure_report(ast, condition_ast, message_ast, source, ctx=ctx, expect=True),
            True,
        )
    failure_ctx = _refine_condition_context(ctx, condition, truth=False)
    failure = hir.Block(
        ast.loc,
        ty.BOTTOM_TYPE,
        _assert_failure_report(ast, condition_ast, message_ast, source, ctx=failure_ctx, expect=True),
        True,
    )
    flow = hir.Flow(
        ast.loc,
        ty.VOID_TYPE,
        [hir.IfArm(ast.loc, ty.VOID_TYPE, condition, hir.Void(ast.loc, ty.VOID_TYPE))],
        failure,
    )
    obligation = hir.Assert(ast.loc, ty.VOID_TYPE, condition, source, None, runtime=True, dimmed=dimmed, expect=True)
    held = _refine_condition_context(ctx, condition, truth=True)
    refinements, bounds, keys = dict(held.refinements), dict(held.length_bounds), dict(held.key_facts)
    ctx.refinements.clear()
    ctx.refinements.update(refinements)
    ctx.length_bounds.clear()
    ctx.length_bounds.update(bounds)
    ctx.key_facts.clear()
    ctx.key_facts.update(keys)
    return hir.Block(ast.loc, ty.VOID_TYPE, [obligation, flow], False)


def _checked_call(func: hir.AST, arguments: list[hir.AST], *, loc: Span, ctx: Context) -> hir.FunctionCall:
    """A positional call to a single-method function with already-checked arguments."""
    if not isinstance(func.type, ty.FunctionType):
        raise ValueError(f'INTERNAL ERROR: `{getattr(func, "name", func)}` is not a single function')
    params = func.type.pos_or_kw
    if len(params) != len(arguments):
        raise ValueError(f'INTERNAL ERROR: `{getattr(func, "name", func)}` takes {len(params)} arguments, got {len(arguments)}')
    checked = [
        argument if isinstance(argument, hir.Place) else check_against(argument, param.type, ctx=ctx)
        for argument, param in zip(arguments, params)
    ]
    return hir.FunctionCall(loc, func.type.ret, func, checked, {})


def _assert_failure_report(
    ast: p0.AssertDirective,
    condition_ast: p0.AST,
    message_ast: p0.AST | None,
    source: str,
    *,
    ctx: Context,
    expect: bool = False,
) -> list[hir.AST]:
    """The failure path of a `$runtime_assert` (or, with ``expect``, a `$expect`).

    Fills the report model of `library/reporting.dewy` — the condition as the
    pointer with the message as its text, the `, message` tail dimmed, the
    operands' values as notes — renders it over the condition's source line,
    then `_exit(101)`; an expectation records the failure and returns instead.
    """
    loc = ast.loc

    def text(content: str) -> hir.String:
        return hir.String(loc, ty.StringLiteralType(content), content)

    def integer(value: int) -> hir.Integer:
        return hir.Integer(loc, ty.IntegerLiteralType(value), '0d', value)

    def call(name: str, *arguments: hir.AST) -> hir.FunctionCall:
        return _checked_call(tcr_identifier(t1.Identifier(loc, name), ctx=ctx), list(arguments), loc=loc, ctx=ctx)

    body = ctx.srcfile.body
    line_start = body.rfind('\n', 0, condition_ast.loc.start) + 1
    line_end = body.find('\n', condition_ast.loc.start)
    if line_end < 0:
        line_end = len(body)
    row = body.count('\n', 0, condition_ast.loc.start) + 1
    line = body[line_start:line_end]

    def byte_offset(index: int) -> int:
        """A source index on the line as a byte offset into the excerpt."""
        return len(line[:max(0, min(index, line_end) - line_start)].encode('utf-8'))

    condition_start = byte_offset(condition_ast.loc.start)
    condition_stop = byte_offset(condition_ast.loc.stop)
    path = 'input' if ctx.srcfile.path is None else str(ctx.srcfile.path)
    if message_ast is not None:
        message = typecheck_and_resolve_inner(message_ast, ctx=ctx)
    elif ast.name == 'fail':
        message = text('the test reached `$fail`')
    else:
        message = text('this condition was false')
    dim_stop = byte_offset(message_ast.loc.stop) if message_ast is not None else condition_stop
    report_alias = ctx.binding_scopes.get('Report')
    if report_alias is None or report_alias.type_value is None:
        not_implemented(ctx.srcfile, loc, f'`${ast.name}` without the prelude (`Report` is not available)')
    report_type = ty.unfold(report_alias.type_value)
    assert isinstance(report_type, ty.ObjectType)
    # the report lives in a hidden local of the failure block
    local = ctx.binding_registry.allocate(_fresh_syntax(ctx), f'__dewy_assert_report_{ctx.binding_registry.next_id}', 'value', loc)
    local.type = report_type
    report = hir.ExpressedIdentifier(loc, report_type, local.name, binding_id=local.id)
    declaration = hir.Declare(
        loc, ty.VOID_TYPE, 'let', local.name, report_type,
        call('_expectation_report' if expect else '_assertion_report', integer(condition_start), integer(condition_stop), integer(dim_stop), message),
        binding_id=local.id,
    )
    local.declaration = declaration
    statements: list[hir.AST] = [declaration]
    seen: set[str] = set()
    for operand_ast in _assert_operands(condition_ast):
        operand_source = _assert_source(operand_ast, ctx=ctx)
        if operand_source in seen:
            continue
        seen.add(operand_source)
        try:
            value = typecheck_and_resolve_inner(operand_ast, ctx=ctx)  # re-evaluated on the failure path
        except ReportException:
            continue
        if not _assert_note_value_supported(value.type, ctx=ctx):
            continue  # values interpolation cannot show are left out
        note = hir.InterpolatedString(loc, ty.StringType(), [text(f'`{operand_source}` is '), value])
        statements.append(call('_assertion_note', hir.Place(loc, report_type, report), note))
    statements.append(call('_assertion_render', report, text(path), integer(row), text(line)))
    if expect:
        statements.append(call('_expect_failed'))
        statements.append(hir.Return(loc, ty.BOTTOM_TYPE, None))
    else:
        statements.append(call('_exit', integer(101)))
    return statements


def _assert_note_value_supported(type_: ty.Type, *, ctx: Context) -> bool:
    """Types a materialized interpolated string renders: fixed-width integers, booleans, strings."""
    if _is_string_type(type_) or type_ == 'bool' or isinstance(type_, ty.IntegerLiteralType):
        return True
    return isinstance(type_, str) and type_ not in ('int', 'uint') and ctx.type_system.is_subtype(type_, 'int')


_MUTATING_METHODS = {'push', 'pop', 'insert', 'clear', 'truncate', 'reserve', 'sort', 'add'}


def _method_row(item: p0.AST, *, symbol: str = '=') -> tuple[str, p0.AST] | None:
    """`name = (params) => body` inside an object type: a method (`&=`: one more of the same name)."""
    if symbol == '&=':
        # a compound assignment token wraps its base operator
        matches = isinstance(item, p0.BinOp) and isinstance(item.op, t2.CombinedAssignmentOp) and _operator_symbol(item.op.op) == '&'
    else:
        matches = isinstance(item, p0.BinOp) and _operator_symbol(item.op) == symbol
    if (
        matches
        and isinstance(item, p0.BinOp)
        and isinstance(item.left, p0.Atom)
        and isinstance(item.left.item, t1.Identifier)
        and isinstance(item.right, p0.BinOp)
        and _operator_symbol(item.right.op) == '=>'
    ):
        return item.left.item.name, item.right
    return None


def _function_literal_parts(literal: p0.BinOp) -> tuple[p0.Block, p0.AST | None, p0.AST]:
    """(parameter block, result annotation, body) of a `(params):>ret => body` literal."""
    signature = literal.left
    result: p0.AST | None = None
    if isinstance(signature, p0.BinOp) and _operator_symbol(signature.op) == ':>':
        result = signature.right
        signature = signature.left
    if not isinstance(signature, p0.Block):
        signature = p0.Block(signature.loc, [signature], '()', None)  # `x => …`
    return signature, result, literal.right


def _parameter_names(params: p0.Block) -> set[str]:
    names: set[str] = set()
    for item in params.inner:
        node: p0.AST = item
        if isinstance(node, p0.BinOp) and _operator_symbol(node.op) == '=':
            node = node.left
        if isinstance(node, p0.BinOp) and _operator_symbol(node.op) == ':':
            node = node.left
        if isinstance(node, p0.Prefix):
            node = node.item
        if isinstance(node, p0.Atom) and isinstance(node.item, t1.Identifier):
            names.add(node.item.name)
    return names


def _local_names(body: p0.AST) -> set[str]:
    """Names declared inside a method body (`let`/`const`, loop targets): they shadow members."""
    names: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if isinstance(node, p0.KeywordExpr):
            parts = _declaration_parts(node)
            if parts is not None:
                names.add(parts[0])
            walk([part for part in node.parts if isinstance(part, (p0.AST, list))])
            return
        if isinstance(node, p0.BinOp):
            if _operator_symbol(node.op) == 'in' and isinstance(node.left, p0.Atom) and isinstance(node.left.item, t1.Identifier):
                names.add(node.left.item.name)
            walk(node.left)
            walk(node.right)
            return
        if isinstance(node, p0.AST):
            for field_info in fields(node):
                value = getattr(node, field_info.name)
                if isinstance(value, (p0.AST, list)):
                    walk(value)

    walk(body)
    return names


# the hidden receiver parameter of a compiled method: not a spellable name, so
# a method body reaches its instance only through bare field and method names
_RECEIVER = '__dewy_receiver'


def _rewrite_members_to_self(node: p0.AST, members: set[str]) -> p0.AST:
    """Bare references to fields/methods inside a method body become reads of the hidden receiver."""

    def self_access(atom: p0.Atom) -> p0.AST:
        return p0.BinOp(atom.loc, t1.Operator(atom.loc, '.'), p0.Atom(atom.loc, t1.Identifier(atom.loc, _RECEIVER)), atom)

    def rewrite(value: object) -> object:
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, p0.Atom):
            if isinstance(value.item, t1.Identifier) and value.item.name in members:
                return self_access(value)
            return value
        if isinstance(value, p0.BinOp) and _operator_symbol(value.op) == '.':
            return replace(value, left=rewrite(value.left))  # the member name on the right stays
        if isinstance(value, p0.Block) and value.kind == '[]':
            # an object literal's keys are field names, not member reads:
            # `[path = _path_parent(path)]` rewrites only the value
            items = []
            for item in value.inner:
                if (
                    isinstance(item, p0.BinOp)
                    and _operator_symbol(item.op) == '='
                    and isinstance(item.left, p0.Atom)
                    and isinstance(item.left.item, t1.Identifier)
                ):
                    items.append(replace(item, right=rewrite(item.right)))
                else:
                    items.append(rewrite(item))
            return replace(value, inner=items)
        if isinstance(value, p0.AST):
            changes = {}
            for field_info in fields(value):
                current = getattr(value, field_info.name)
                if isinstance(current, (p0.AST, list)):
                    changes[field_info.name] = rewrite(current)
            return replace(value, **changes) if changes else value
        return value

    result = rewrite(node)
    assert isinstance(result, p0.AST)
    return result


def _referenced_members(body: p0.AST, members: set[str]) -> set[str]:
    """The bare member names a method body reads (the ones `_rewrite_members_to_self` would rewrite)."""
    found: set[str] = set()

    def walk(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if isinstance(value, p0.Atom):
            if isinstance(value.item, t1.Identifier) and value.item.name in members:
                found.add(value.item.name)
            return
        if isinstance(value, p0.BinOp) and _operator_symbol(value.op) == '.':
            walk(value.left)   # the member name on the right is not a bare read
            return
        if isinstance(value, p0.Block) and value.kind == '[]':
            for item in value.inner:
                if isinstance(item, p0.BinOp) and _operator_symbol(item.op) == '=' and isinstance(item.left, p0.Atom) and isinstance(item.left.item, t1.Identifier):
                    walk(item.right)   # an object literal's keys are field names
                else:
                    walk(item)
            return
        if is_dataclass(value) and not isinstance(value, type):
            for field_ in fields(value):
                walk(getattr(value, field_.name))

    walk(body)
    return found


def _rewrite_static_calls(node: p0.AST, statics: set[str], alias: str) -> p0.AST:
    """In a static method, bare names of the type's other static methods become `Alias.name`."""

    def type_access(atom: p0.Atom) -> p0.AST:
        return p0.BinOp(atom.loc, t1.Operator(atom.loc, '.'), p0.Atom(atom.loc, t1.Identifier(atom.loc, alias)), atom)

    def rewrite(value: object) -> object:
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, p0.Atom):
            if isinstance(value.item, t1.Identifier) and value.item.name in statics:
                return type_access(value)
            return value
        if isinstance(value, p0.BinOp) and _operator_symbol(value.op) == '.':
            return replace(value, left=rewrite(value.left))
        if isinstance(value, (t1.Token, t2.Operator, t1.Operator)):
            return value   # tokens and operators carry no member reads
        if is_dataclass(value) and not isinstance(value, type):
            return replace(value, **{field_.name: rewrite(getattr(value, field_.name)) for field_ in fields(value) if field_.init and field_.name != 'loc'})
        return value

    result = rewrite(node)
    assert isinstance(result, p0.AST)
    return result


def _body_mutates_members(body: p0.AST, members: set[str]) -> bool:
    """Whether a method body assigns a field, mutates one in place, or takes its place."""

    def root_name(node: p0.AST) -> str | None:
        while isinstance(node, p0.BinOp) and (
            _operator_symbol(node.op) == '.' or isinstance(node.op, (t2.IndexJuxtapose, t2.QJuxtapose))
        ):
            node = node.left
        if isinstance(node, p0.Atom) and isinstance(node.item, t1.Identifier):
            return node.item.name
        return None

    found = False

    def walk(value: object) -> None:
        nonlocal found
        if found:
            return
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if isinstance(value, p0.BinOp):
            symbol = _operator_symbol(value.op)
            if (symbol == '=' or isinstance(value.op, t2.CombinedAssignmentOp)) and root_name(value.left) in members:
                found = True
                return
            if isinstance(value.op, (t2.CallJuxtapose, t2.QJuxtapose)) and isinstance(value.left, p0.BinOp) and _operator_symbol(value.left.op) == '.':
                right = value.left.right
                if isinstance(right, p0.Atom) and isinstance(right.item, t1.Identifier) and right.item.name in _MUTATING_METHODS and root_name(value.left.left) in members:
                    found = True
                    return
        if isinstance(value, p0.Prefix) and _operator_symbol(value.op) == '@' and root_name(value.item) in members:
            found = True
            return
        if isinstance(value, p0.Block) and value.kind == '[]':
            # an object literal's keys are field names, not member writes:
            # `[path = _path_parent(path)]` builds a new value
            for item in value.inner:
                if (
                    isinstance(item, p0.BinOp)
                    and _operator_symbol(item.op) == '='
                    and isinstance(item.left, p0.Atom)
                    and isinstance(item.left.item, t1.Identifier)
                ):
                    walk(item.right)
                else:
                    walk(item)
            return
        if isinstance(value, p0.AST):
            for field_info in fields(value):
                current = getattr(value, field_info.name)
                if isinstance(current, (p0.AST, list)):
                    walk(current)

    walk(body)
    return found


def _hoist_hidden_function(name: str, literal: p0.BinOp, *, ctx: Context) -> sb.Binding:
    """Typecheck a synthesized function literal as a module-level function (like a generic instance)."""
    binding = ctx.binding_registry.allocate(_fresh_syntax(ctx), name, 'function', literal.loc)
    checked = tcr_function_literal(literal, ctx=ctx)
    binding.type = checked.type
    declaration = hir.Declare(literal.loc, ty.VOID_TYPE, 'let', name, None, checked, binding_id=binding.id)
    binding.declaration = declaration
    binding.function = checked
    # the module's own scope (`ctx` is the module root block context)
    ctx.declarations.maps[0][name] = checked.type
    ctx.binding_scopes.maps[0][name] = binding
    ctx.generic_instances.append(declaration)
    return binding


def _declare_pending_methods(*, ctx: Context, for_type: ty.ObjectType | None = None) -> None:
    """Declare the methods of every pending alias (or of one type) in the module context."""
    module_ctx = ctx.module if ctx.module is not None else ctx
    pending = list(ctx.pending_methods)
    for alias, object_type in pending:
        if for_type is not None and object_type is not for_type:
            continue
        ctx.pending_methods.remove((alias, object_type))
        _declare_type_methods(alias, object_type, ctx=module_ctx)


def _declare_type_methods(alias: sb.Binding, object_type: ty.ObjectType, *, ctx: Context) -> None:
    """Compile a type's methods as hidden functions `Type__method(self …)`.

    Inside a method, bare names of the type's fields and methods mean
    `self.name`; `self` is a place parameter when the body assigns or
    mutates fields, so the call site passes the receiver as a place.
    """
    if alias.name not in ctx.module_declared_names:
        not_implemented(ctx.srcfile, alias.loc, 'methods on a type declared inside a function')
    members = {f.name for f in object_type.fields} | {m.name for m in object_type.methods}
    field_names = {f.name for f in object_type.fields}
    for method in object_type.methods:
        if method.binding_id is None and method.owner not in (None, alias.name):
            # inherited: its declaring type compiles it (now, if that is still pending)
            owner_entry = next(((a, t) for a, t in ctx.pending_methods if a.name == method.owner), None)
            if owner_entry is not None:
                ctx.pending_methods.remove(owner_entry)
                _declare_type_methods(owner_entry[0], owner_entry[1], ctx=ctx)
    own = [method for method in object_type.methods if method.binding_id is None and method.owner in (None, alias.name)]
    # a method is static when it reads no field and calls no method that does
    # (transitively; an inherited method's verdict is its declaring type's)
    parts = {}
    for method in own:
        literal = method.literal
        assert isinstance(literal, p0.BinOp)
        params, result, body = _function_literal_parts(literal)
        visible = (members | {'typename'}) - _parameter_names(params) - _local_names(body)   # `typename` reads the instance's, like a field
        parts[method.name] = (params, result, body, visible, _referenced_members(body, visible))
    instance_level = {name for name, (_p, _r, _b, _v, refs) in parts.items() if refs & (field_names | {'typename'})}
    instance_level |= {m.name for m in object_type.methods if m.binding_id is not None and not m.static}
    changed = True
    while changed:
        changed = False
        for name, (_p, _r, _b, _v, refs) in parts.items():
            if name not in instance_level and refs & instance_level:
                instance_level.add(name)
                changed = True
    statics = {name for name in parts if name not in instance_level}
    # callees before callers, so a call to another method resolves to a declared function
    ordered: list = []
    remaining = list(own)
    while remaining:
        progressed = False
        for method in list(remaining):
            refs = parts[method.name][4]
            if any(other.name in refs for other in remaining if other is not method):
                continue
            ordered.append(method)
            remaining.remove(method)
            progressed = True
        if not progressed:
            ordered.extend(remaining)   # mutually recursive methods: declared in order (the later one is unresolved)
            break
    for method in ordered:
        literal = method.literal
        assert isinstance(literal, p0.BinOp)
        params, result, body, visible, _refs = parts[method.name]
        loc = literal.loc
        if method.name in statics:
            method.static = True
            rewritten = _rewrite_static_calls(body, statics - {method.name}, alias.name)
            signature: p0.AST = params if result is None else p0.BinOp(loc, t1.Operator(loc, ':>'), params, result)
        else:
            self_name: p0.AST = p0.Atom(loc, t1.Identifier(loc, _RECEIVER))
            method.place_self = _body_mutates_members(body, visible)
            if method.place_self:
                self_name = p0.Prefix(loc, t1.Operator(loc, '@'), self_name)
            self_param = p0.BinOp(loc, t1.Operator(loc, ':'), self_name, p0.Atom(loc, t1.Identifier(loc, alias.name)))
            new_params = replace(params, inner=[self_param, *params.inner])
            signature = new_params if result is None else p0.BinOp(loc, t1.Operator(loc, ':>'), new_params, result)
            rewritten = _rewrite_members_to_self(body, visible)
        new_literal = replace(literal, left=signature, right=rewritten)
        ctx.synthesized.append(new_literal)
        ordinal = sum(1 for earlier in object_type.methods[:object_type.methods.index(method)] if earlier.name == method.name)
        hidden_name = f'{alias.name}__{method.name}' + (f'_{ordinal + 1}' if ordinal else '')
        method.binding_id = _hoist_hidden_function(hidden_name, new_literal, ctx=ctx).id


def _declare_constructor_overload(constructor: hir.TypeValue, literal: p0.AST, *, ctx: Context) -> hir.AST:
    """`Type &= (…) => …` adds an ordinary function to the type's constructor overload set."""
    object_type = _constructed_object_type(constructor)
    assert object_type is not None and constructor.name is not None
    if constructor.name not in ctx.module_declared_names:
        not_implemented(ctx.srcfile, constructor.loc, 'constructor overloads on a type declared inside a function')
    if not (isinstance(literal, p0.BinOp) and _operator_symbol(literal.op) == '=>'):
        user_error(
            ctx.srcfile,
            'a constructor overload must be a function literal',
            Pointer(span=literal.loc, message='expected `(params):>Type => …`'),
        )
    binding = _hoist_hidden_function(f'{constructor.name}__new_{len(object_type.constructors) + 1}', literal, ctx=ctx)
    object_type.constructors.append(binding.id)
    return hir.Void(constructor.loc, ty.VOID_TYPE)


def _select_constructor_overload(
    left: hir.TypeValue,
    object_type: ty.ObjectType,
    right: p0.AST,
    *,
    ctx: Context,
) -> hir.ExpressedIdentifier | None:
    """Dispatch a constructor call over the field-wise signature and the `&=` overloads.

    Returns the overload to call, or None when the field-wise constructor
    (or none of them) applies — the literal path then reports its errors.
    """
    if not object_type.constructors:
        return None
    pos_args, kw_args, _order = parse_call_arguments(right, ctx=ctx, method=None)
    pos_types = [require_valued(a.type, ctx.srcfile, a.loc, 'constructor argument') for a in pos_args]
    kw_types = {k: require_valued(v.type, ctx.srcfile, v.loc, f'keyword argument `{k}`') for k, v in kw_args.items()}
    field_wise = ty.FunctionType(
        [ty.PosOrKwArg(f.name, f.type, f.default is None) for f in object_type.fields],
        [],
        None,
        object_type,
        [],
    )
    overloads = [ctx.binding_registry.by_id[binding_id] for binding_id in object_type.constructors]
    methods: list[ty.FunctionType] = [field_wise]
    for overload in overloads:
        assert isinstance(overload.type, ty.FunctionType)
        methods.append(overload.type)
    try:
        result = ctx.type_system.match_best_function(methods, pos_types, kw_types)
    except ty.DispatchError:
        return None
    if result.method_index == 0:
        return None
    chosen = overloads[result.method_index - 1]
    assert isinstance(chosen.type, ty.FunctionType)
    return hir.ExpressedIdentifier(left.loc, chosen.type, chosen.name, binding_id=chosen.id)


def _fresh_syntax(ctx: Context) -> object:
    """A stand-in syntax object for a hidden binding, kept alive so its `id()` is never reused."""
    sentinel = object()
    ctx.synthesized.append(sentinel)
    return sentinel


def _declaration_pointers(binding: sb.Binding) -> list[Pointer]:
    """The `const declaration is here` pointer, when the binding has a declaration."""
    if binding.declaration is None:
        return []
    return [Pointer(span=binding.declaration.loc, message='const declaration is here')]


def _read_only_reason(binding: sb.Binding | None) -> str | None:
    """Why a binding rejects writes: `const` declarations and borrowed loop variables."""
    if binding is None:
        return None
    if binding.declaration is not None and binding.declaration.decltype == 'const':
        return 'is declared const'
    return binding.read_only_reason


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


def _implicit_declaration_parts(item: p0.AST, seen: set[str], *, ctx: Context) -> tuple[str, p0.AST] | None:
    """`name = value` at block level declares `name` when nothing outer has it
    and it is the block's first `name` (later ones assign): the same
    declaration `let name = value` would make, so it is collected and
    deferred like one — a function body may call a function written after it."""
    if not (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol == '='
        and isinstance(item.left, p0.Atom)
        and isinstance(item.left.item, t1.Identifier)
    ):
        return None
    name = item.left.item.name
    if name in ctx.declarations or name in seen:
        return None
    seen.add(name)
    return name, item.right


def _block_declaration_parts(item: p0.AST, seen: set[str], *, ctx: Context) -> tuple[str, p0.AST] | None:
    """A block item's declaration: `let`/`const`, or the block's first bare `name = value`
    (``seen`` holds the names the block has declared so far, either way)."""
    declaration = _declaration_parts(item)
    if declaration is not None:
        seen.add(declaration[0])
        return declaration
    return _implicit_declaration_parts(item, seen, ctx=ctx)


def _collect_block_bindings(block: p0.Block, *, ctx: Context) -> None:
    seen: set[str] = set()
    for item in block.inner:
        declaration = _block_declaration_parts(item, seen, ctx=ctx)
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
        and _is_type_of_expression(expression.right)
    ):
        return expression.left.item.name, expression.right
    if (
        isinstance(expression.left, p0.Atom)
        and isinstance(expression.left.item, t1.Identifier)
        and isinstance(expression.right, p0.Block)
        and expression.right.kind == '<>'
        and len(expression.right.inner) == 1
    ):
        return expression.left.item.name, expression.right
    return None


def _is_type_of_prefix(ast: p0.AST) -> bool:
    return isinstance(ast, p0.Prefix) and isinstance(ast.op, t1.Operator) and ast.op.symbol == 'type of'


def _intersection_operands(ast: p0.AST) -> list[p0.AST]:
    """The operands of an `&` chain (one item for anything else)."""
    if isinstance(ast, p0.BinOp) and isinstance(ast.op, t1.Operator) and ast.op.symbol == '&':
        return [*_intersection_operands(ast.left), *_intersection_operands(ast.right)]
    return [ast]


def _abstract_mint(ast: p0.AST) -> tuple[p0.AST, bool]:
    """`$abstract type of any & [...]`: the mint under the directive, and whether it was marked."""
    if isinstance(ast, p0.AssertDirective) and ast.name == 'abstract' and ast.condition is not None:
        return ast.condition, True
    return ast, False


def _is_type_of_expression(ast: p0.AST) -> bool:
    """A declaration value that mints: `type of X`, or an intersection holding
    one (`type of Token & [text:string]` is `(type of Token) & [...]`), either
    under `$abstract`."""
    ast, _abstract = _abstract_mint(ast)
    return any(_is_type_of_prefix(item) for item in _intersection_operands(ast))


def _type_expression_root(ast: p0.AST) -> str | None:
    """The identifier a would-be type expression is rooted at (`int`, `array<...>`,
    alias names, the left of `Context & [...]`)."""
    if isinstance(ast, p0.Atom) and isinstance(ast.item, t1.Identifier):
        return ast.item.name
    if isinstance(ast, p0.BinOp) and isinstance(ast.op, t2.TypeParamJuxtapose):
        return _type_expression_root(ast.left)
    if isinstance(ast, p0.BinOp) and isinstance(ast.op, t1.Operator) and ast.op.symbol in ('&', '|'):
        return _type_expression_root(ast.left)
    return None


def _annotated_type_alias_rhs(item: p0.AST) -> tuple[str, p0.AST] | None:
    """`Name:type = <expr>` without `let` declares a type alias too."""
    if (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol in {'=', '::', ':='}
        and isinstance(item.left, p0.BinOp)
        and isinstance(item.left.op, t1.Operator)
        and item.left.op.symbol == ':'
        and isinstance(item.left.left, p0.Atom)
        and isinstance(item.left.left.item, t1.Identifier)
        and isinstance(item.left.right, p0.Atom)
        and isinstance(item.left.right.item, t1.Identifier)
        and item.left.right.item.name == 'type'
    ):
        return item.left.left.item.name, item.right
    return None


def _implicit_type_alias_rhs(item: p0.AST, known_aliases: set[str], *, ctx: Context) -> tuple[str, p0.AST] | None:
    """`Name = <type expression>` (with or without `let`) declares a type alias."""
    if _is_top_level_declare(item) and isinstance(item, p0.KeywordExpr) and len(item.parts) == 2 and isinstance(item.parts[1], p0.AST):
        inner = item.parts[1]
        if (
            isinstance(inner, p0.BinOp)
            and isinstance(inner.op, t1.Operator)
            and inner.op.symbol == '='
            and isinstance(inner.right, p0.Atom)
            and isinstance(inner.right.item, t1.Identifier)
        ):
            # `let e = NotFound` / `let w = Space`: a bare name stays a value
            # use — the error value or the empty mint's inhabitant — not an alias
            return None
        return _implicit_type_alias_rhs(inner, known_aliases, ctx=ctx)
    if not (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol == '='
        and isinstance(item.left, p0.Atom)
        and isinstance(item.left.item, t1.Identifier)
    ):
        return None
    if item.left.item.name in ctx.declarations:
        return None  # an assignment to an existing binding
    if _is_type_of_expression(item.right):
        return item.left.item.name, item.right
    root = _type_expression_root(item.right)
    if root is None or root in {'none', 'void', 'end', 'new', 'ellipsis'}:
        return None  # value keywords that also name types
    binding = ctx.binding_scopes.get(root)
    if not (
        root in known_aliases
        or (binding is not None and binding.type_value is not None)
        or (binding is None and root not in ctx.declarations and root in ctx.type_system._named_types)
    ):
        return None
    return item.left.item.name, item.right


def _record_refinement_facts(binding_id: int, refined: ty.RefinedType, *, ctx: Context) -> None:
    """Keep proven length facts where the checker's own proofs look."""
    for proposition in refined.propositions:
        lower = proposition.lower_bound()
        if proposition.subject == 'length' and lower is not None:
            ctx.length_bounds[binding_id] = max(ctx.length_bounds.get(binding_id, 0), lower)


def _prebind_type_aliases(block: p0.Block, *, ctx: Context) -> list[sb.Binding]:
    """Bind the block's type aliases by name; each resolves at its first use
    (or, for one never used, after the block's items — by then the imports
    it may refer to have run)."""
    aliases: list[sb.Binding] = []
    known_aliases: set[str] = set()
    for item in block.inner:
        alias = _type_alias_rhs(item) or _annotated_type_alias_rhs(item) or _implicit_type_alias_rhs(item, known_aliases, ctx=ctx)
        if alias is None:
            continue
        name, rhs = alias
        known_aliases.add(name)
        binding = ctx.binding_registry.by_syntax.get(id(item))
        if binding is None:
            binding = ctx.binding_registry.allocate(item, name, 'value', item.loc)
        binding.type = ty.TYPE_TYPE
        ctx.type_alias_asts[binding.id] = rhs
        ctx.declarations[name] = ty.TYPE_TYPE
        ctx.binding_scopes[name] = binding
        aliases.append(binding)
    return aliases


def _mint_nominal_type(binding: sb.Binding, rhs: p0.AST, *, ctx: Context) -> ty.TypeExpr | None:
    """`let NotFound:type = type of error` mints a fresh nominal type named
    after the alias, a subtype of the `of` operand. Only the `error` family is
    supported so far; its canonical inhabitant is written with the type's name."""
    rhs, abstract = _abstract_mint(rhs)
    operands = _intersection_operands(rhs)
    mints = [item for item in operands if _is_type_of_prefix(item)]
    if not mints:
        if abstract:
            user_error(ctx.srcfile, '`$abstract` marks a `type of` mint', Pointer(span=rhs.loc, message='an alias of an existing type cannot be abstract'))
        return None
    if len(mints) > 1:
        user_error(
            ctx.srcfile,
            'an alias mints once',
            Pointer(span=mints[1].loc, message='a second `type of` in the same intersection'),
        )
    mint = mints[0]
    assert isinstance(mint, p0.Prefix)
    parent = ast_to_type(mint.item, ctx=ctx)
    extras = [ast_to_type(item, ctx=ctx) for item in operands if item is not mint]
    name = binding.name
    if ty.user_branded(parent) and isinstance(parent, ty.ObjectType) and parent.brand in ty.USER_NOMINAL_TYPES:
        # `type of TokenError & [...]`: a child of an error carrying fields is
        # one too, nominally under its parent
        child = _mint_branded_object(binding, rhs, parent, extras, ctx=ctx, nominal_parent=parent.brand, abstract=abstract)
        ty.USER_NOMINAL_TYPES[name] = parent.brand
        ctx.type_system.register_user_nominals()
        return child
    if not (isinstance(parent, str) and ctx.type_system.is_subtype(parent, 'error')):
        return _mint_branded_object(binding, rhs, parent, extras, ctx=ctx, abstract=abstract)
    if abstract:
        user_error(ctx.srcfile, '`$abstract` marks an object mint', Pointer(span=rhs.loc, message='error types are not abstract'))
    if extras:
        # an error carrying fields (`type of error & Report`, `& [code:int64]`):
        # a branded object whose brand is registered as a nominal error, so it
        # is constructed and read like any minted object and sits in the
        # `error` family for `is? error`, `or_throw`, and forwarding
        carrying = _mint_branded_object(binding, rhs, 'any', extras, ctx=ctx, nominal_parent=parent)
        ty.USER_NOMINAL_TYPES[name] = parent
        ctx.type_system.register_user_nominals()
        return carrying
    known = ty.USER_NOMINAL_TYPES.get(name)
    if known is not None and known != parent:
        user_error(
            ctx.srcfile,
            f'error type `{name}` is already minted with a different parent',
            Pointer(span=binding.loc, message=f'this one descends from `{parent}`; the earlier one from `{known}`'),
        )
    if known is None and name in ctx.type_system._named_types:
        user_error(
            ctx.srcfile,
            f'`{name}` is already a type name',
            Pointer(span=binding.loc, message='choose another name for this error type'),
        )
    ty.USER_NOMINAL_TYPES[name] = parent
    ctx.type_system.register_user_nominals()
    return name


def _intersect_object_types(operands: list[ty.TypeExpr], *, loc: Span, ctx: Context) -> ty.ObjectType | None:
    """`Context & [tag:string='root']`: intersecting object types strengthens the
    structure — fields merge, a later same-name field must fit and replaces —
    and never mints identity (a branded operand keeps its nominal kind)."""
    flattened: list[ty.TypeExpr] = []
    for operand in operands:
        flattened.extend(ty.unfold(item) for item in (operand.items if isinstance(operand, ty.TypeAnd) else [operand]))
    if not flattened or not all(isinstance(item, ty.ObjectType) for item in flattened):
        return None
    branded = [item for item in flattened if isinstance(item, ty.ObjectType) and item.brand is not None]
    if len(branded) > 1 or any(item.brand is not None and not ty.user_branded(item) for item in branded):
        return None
    fields: list[ty.ObjectField] = []
    methods: list[ty.MethodSpec] = []
    for item in flattened:
        assert isinstance(item, ty.ObjectType)
        for field_ in item.fields:
            existing_index = next((index for index, existing in enumerate(fields) if existing.name == field_.name), None)
            if existing_index is None:
                fields.append(field_)
                continue
            if not ctx.type_system.is_subtype(field_.type, fields[existing_index].type):
                type_error(
                    ctx.srcfile,
                    'intersection weakens a field',
                    Pointer(span=loc, message=f'`{field_.name}: {type_to_dewy(field_.type)}` does not fit the earlier `{type_to_dewy(fields[existing_index].type)}`'),
                )
            fields[existing_index] = field_
        methods.extend(item.methods)
    brand = branded[0].brand if branded else None
    return ty.ObjectType(tuple(fields), brand=brand, methods=tuple(methods))


def _mint_branded_object(binding: sb.Binding, rhs: p0.AST, parent: ty.TypeExpr, extras: list[ty.TypeExpr], *, ctx: Context, nominal_parent: str | None = None, abstract: bool = False) -> ty.ObjectType:
    """`let Number:type = type of any & [value:int64]` — `(type of any) & [...]` —
    mints a nominal object type: the parent's structure (`any` contributes
    nothing) strengthened by the intersected objects, distinct from every
    other type — including a structurally identical one — printed and
    constructed by its name. `type of` is the sole generative type
    expression; `&` alone never mints identity."""
    operands = [*(parent.items if isinstance(parent, ty.TypeAnd) else [parent]), *extras]
    fields: list[ty.ObjectField] = []
    methods: list[ty.MethodSpec] = []
    ancestor: str | None = None
    for item in operands:
        if ty.user_branded(item):
            # `type of Token`: a nominal child — the parent's fields lead, so a
            # child value is a parent value with more behind it
            assert isinstance(item, ty.ObjectType) and item.brand is not None
            if ancestor is not None:
                not_implemented(ctx.srcfile, rhs.loc, f'`type of {type_to_dewy(parent)}` (a minted type with two nominal parents)')
            ancestor = item.brand
            for field_ in item.fields:
                if any(field_.name == existing.name for existing in fields):
                    user_error(
                        ctx.srcfile,
                        f'minted type `{binding.name}` declares field `{field_.name}` twice',
                        Pointer(span=rhs.loc, message=f'`{ancestor}` already carries it'),
                    )
            fields[:0] = item.fields
            methods[:0] = item.methods   # inherited: compiled once by their declaring type, a child receiver being a subtype
            continue
    for item in operands:
        if item == 'any' or ty.user_branded(item):
            continue
        if isinstance(item, ty.ObjectType) and item.brand is None:
            for field_ in item.fields:
                existing_index = next((index for index, existing in enumerate(fields) if existing.name == field_.name), None)
                if existing_index is None:
                    fields.append(field_)
                    continue
                # strengthening an inherited field (`type of Report & [severity='error']`):
                # the type must still fit, and the new default replaces the old
                if not ctx.type_system.is_subtype(field_.type, fields[existing_index].type):
                    user_error(
                        ctx.srcfile,
                        f'minted type `{binding.name}` weakens field `{field_.name}`',
                        Pointer(span=rhs.loc, message=f'`{type_to_dewy(field_.type)}` does not fit the inherited `{type_to_dewy(fields[existing_index].type)}`'),
                    )
                fields[existing_index] = field_
            for method in item.methods:
                slot = next((index for index, existing in enumerate(fields) if existing.name == method.name), None)
                if slot is not None and isinstance(fields[slot].type, ty.FunctionType):
                    # `type of Protocol & [eat = (…) => …]`: a method named like an
                    # inherited function-typed field is that field's value — the
                    # child implements the protocol's slot; the default is the
                    # compiled static method `Child.eat` (so its body may call
                    # the child's other static methods by bare name)
                    literal = method.literal
                    assert isinstance(literal, p0.BinOp)
                    fields[slot] = replace(fields[slot], default=_slot_forwarder(literal, binding.name, method.name, ctx=ctx))
                inherited = next((index for index, existing in enumerate(methods) if existing.name == method.name), None)
                if method.owner is None:
                    method.owner = binding.name   # declared here (an aliased structure's methods keep their owner)
                if inherited is not None:
                    methods[inherited] = method   # a child's method overrides the parent's
                else:
                    methods.append(method)
            continue
        not_implemented(
            ctx.srcfile,
            rhs.loc,
            f'`type of {type_to_dewy(parent)}` (mintable so far: error types, and object types — possibly intersected with `any`)',
        )
    name = binding.name
    reminted = nominal_parent is not None and ty.USER_NOMINAL_TYPES.get(name) == nominal_parent   # the same error minted again (another compile in this process)
    if (name in ty.USER_NOMINAL_TYPES or name in ctx.type_system._named_types) and name not in ty.USER_BRANDS and not reminted:
        user_error(
            ctx.srcfile,
            f'`{name}` is already a type name',
            Pointer(span=binding.loc, message='choose another name for this minted type'),
        )
    ty.USER_BRANDS.add(name)
    if ancestor is not None:
        ty.USER_BRAND_PARENTS[name] = ancestor
    else:
        ty.USER_BRAND_PARENTS.pop(name, None)
    minted = ty.ObjectType(tuple(fields), brand=name, methods=tuple(methods))
    ty.USER_BRAND_TYPES[name] = minted
    if abstract:
        ty.USER_ABSTRACT_BRANDS.add(name)   # `$abstract`: values only of its children
    else:
        ty.USER_ABSTRACT_BRANDS.discard(name)
    return minted


def _slot_forwarder(literal: p0.BinOp, alias: str, method: str, *, ctx: Context) -> p0.AST:
    """A field's default forwarding to a static method: `(params) => Alias.method(params)`.
    A function stored in a field is called with the object first (a field literal
    may read its siblings), a static method without — so the slot holds a literal
    in the field's convention that calls the method, whose body keeps its own."""
    params_ast, _result, _body = _function_literal_parts(literal)
    signature_text = ctx.srcfile.body[literal.left.loc.start:literal.left.loc.stop]   # the parameter list as written, its types with it
    names = [name for name in _parameter_names_in_order(params_ast)]
    text = f'{signature_text} => {alias}.{method}({" ".join(names)})'
    parsed = p0.parse(SrcFile(None, ' ' * literal.loc.start + text + '\n'))
    forwarder = parsed.inner[0]
    assert isinstance(forwarder, p0.BinOp)
    ctx.synthesized.append(forwarder)
    return forwarder


def _parameter_names_in_order(params: p0.Block) -> list[str]:
    names: list[str] = []
    for item in params.inner:
        node: p0.AST = item
        if isinstance(node, p0.BinOp) and _operator_symbol(node.op) == '=':
            node = node.left
        if isinstance(node, p0.BinOp) and _operator_symbol(node.op) == ':':
            node = node.left
        if isinstance(node, p0.Prefix):
            node = node.item
        if isinstance(node, p0.Atom) and isinstance(node.item, t1.Identifier):
            names.append(node.item.name)
    return names


def _validate_recursive_alias(
    binding: sb.Binding,
    value: ty.TypeAliasValue,
    named: ty.NamedType,
    *,
    ctx: Context,
) -> None:
    """A recursive reference is only allowed as a union member of an object field.

    That is the one position with a finite representation: the member lives
    behind a handle in the union cell. A required field of the alias's own
    type would be an infinite value; an alias that is merely a union of itself
    has no base case.
    """
    if isinstance(value, ty.GenericTypeAlias):
        not_implemented(ctx.srcfile, binding.loc, 'recursive generic type aliases')
    if isinstance(value, ty.NamedType):
        # `let A:type = B` / `let B:type = A`: aliases of each other and nothing else
        user_error(
            ctx.srcfile,
            f'cyclic type alias involving `{binding.name}`',
            Pointer(span=binding.loc, message='this alias is part of the cycle'),
        )
    if not isinstance(value, ty.ObjectType):
        user_error(
            ctx.srcfile,
            f'recursive type `{binding.name}` must be an object type',
            Pointer(span=binding.loc, message='the recursion has no object to carry it'),
            hint=f'write `{binding.name}` as `[... {binding.name} | none ...]`: the self-reference lives in a field and is optional or one of several members',
        )

    def check(type_: object, in_union: bool) -> None:
        if isinstance(type_, ty.NamedType):
            if not in_union:
                user_error(
                    ctx.srcfile,
                    f'recursive type `{binding.name}` refers to itself without a union',
                    Pointer(span=binding.loc, message=f'a field typed exactly `{type_.name}` would be an infinite value'),
                    hint=f'make the recursive field a union such as `{type_.name} | none`',
                )
            return
        if isinstance(type_, ty.TypeOr):
            if all(isinstance(item, ty.NamedType) for item in type_.items):
                user_error(
                    ctx.srcfile,
                    f'recursive type `{binding.name}` has no base case',
                    Pointer(span=binding.loc, message='every member of this union is the recursive type itself'),
                )
            for item in type_.items:
                check(item, True)
            return
        if isinstance(type_, ty.ObjectType):
            for field_ in type_.fields:
                check(field_.type, False)
            return
        if isinstance(type_, ty.ArrayType):
            # `children:array<Node>` is finite (the elements live behind the
            # array's descriptor) but the lowering does not unfold a recursive
            # element yet (every element-kind decision reads the object type)
            if ty.mentions_named_type(type_.element):
                not_implemented(ctx.srcfile, binding.loc, f'`array<{binding.name}>` inside `{binding.name}` (arrays of the recursive type; hold the children in a separate array keyed by index for now)')
            return
        if isinstance(type_, ty.ArrayType):
            check(type_.element, False)
            return
        if isinstance(type_, ty.RefinedType):
            check(type_.base, in_union)

    check(value, False)


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
    params, alias_ctx = _declare_generic_parameters(parameters, ctx=ctx)
    if not params:
        user_error(
            ctx.srcfile,
            'generic type alias requires at least one parameter',
            Pointer(span=parameters.loc, message='this parameter list is empty'),
        )
    return ty.GenericTypeAlias(params, ast_to_type(body, ctx=alias_ctx))


def _declare_generic_parameters(parameters: p0.Block, *, ctx: Context) -> tuple[list[ty.GenericParam], Context]:
    """`<T U of Bound>`: the parameters, and a context in which each is a type variable."""
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
    return params, alias_ctx


def _generic_function_parts(fn_ast: p0.AST) -> tuple[p0.Block, p0.AST, p0.AST | None] | None:
    """`<T…>(params):>Ret => body`: the type-parameter block, the parameter
    block, and the result type (None when unannotated), else None."""
    if not (isinstance(fn_ast, p0.BinOp) and isinstance(fn_ast.op, t1.Operator) and fn_ast.op.symbol == '=>'):
        return None
    signature = fn_ast.left
    rettype: p0.AST | None = None
    if isinstance(signature, p0.BinOp) and isinstance(signature.op, t1.Operator) and signature.op.symbol == ':>':
        rettype = signature.right
        signature = signature.left
    if (
        isinstance(signature, p0.BinOp)
        and isinstance(signature.op, t2.TypeParamJuxtapose)
        and isinstance(signature.left, p0.Block)
        and signature.left.kind == '<>'
    ):
        return signature.left, signature.right, rettype
    return None


def _generic_signature(fn_ast: p0.BinOp, *, ctx: Context) -> tuple[ty.FunctionType, list[ty.GenericParam]] | None:
    """The FunctionType (with type parameters) of a generic literal, else None."""
    parts = _generic_function_parts(fn_ast)
    if parts is None:
        return None
    type_block, params_block, rettype_ast = parts
    if rettype_ast is None:
        user_error(
            ctx.srcfile,
            'a generic function needs a declared result type',
            Pointer(span=type_block.loc, message='annotate the result with `:>T`, `:>array<T>`, …'),
        )
    params, generic_ctx = _declare_generic_parameters(type_block, ctx=ctx)
    if not params:
        user_error(ctx.srcfile, 'a generic function needs at least one type parameter', Pointer(span=type_block.loc, message='this parameter list is empty'))
    rettype = ast_to_type(rettype_ast, ctx=generic_ctx)
    pos_or_kw_args, kw_only_args, rest_args = collect_function_signature_args(params_block, ctx=generic_ctx)
    all_params = [*pos_or_kw_args, *kw_only_args, *([rest_args] if rest_args is not None else [])]
    if any(p.type == ty.INFERRED_TYPE for p in all_params):
        user_error(ctx.srcfile, 'a generic function needs every parameter type declared', Pointer(span=params_block.loc, message='annotate each parameter'))
    signature = typefunc_from_hir_params(pos_or_kw_args, kw_only_args, rest_args, rettype)
    return replace(signature, type_params=params), params


def _instantiation_name(name: str, bindings: dict[str, ty.TypeExpr], params: list[ty.GenericParam]) -> str:
    rendered = '_'.join(type_to_dewy(bindings[param.name]) for param in params)
    cleaned = ''.join(ch if ch.isalnum() else '_' for ch in rendered).strip('_')
    while '__' in cleaned:
        cleaned = cleaned.replace('__', '_')
    return f'{name}__{cleaned}'


def _widen_type_argument(type_: ty.TypeExpr, *, loc: Span, ctx: Context) -> ty.TypeExpr:
    """A type parameter bound from a literal takes the literal's ordinary type
    (`1` → `int64`, `"a"` → `string`, `1/2` → the runtime rational), as `let`
    would give the value."""
    if isinstance(type_, ty.RationalLiteralType):
        return _rational_type(ctx, loc)
    if isinstance(type_, ty.IntegerLiteralType):
        return 'int64' if ty.integer_literal_fits(type_.value, 'int64') else _bigint_type(ctx, loc)
    if type_ == 'int':
        return 'int64'  # two integer literals meet at the abstract `int`: the instance is word-sized
    if isinstance(type_, ty.StringLiteralType) or (isinstance(type_, ty.StringType) and type_.length is not None):
        return ty.StringType()
    if isinstance(type_, ty.BinaryLiteralType):
        return ty.ArrayType('uint8', len(type_.value))
    return ty.strip_refinement(type_)


def _instantiate_generic_call(
    left: hir.AST,
    result: ty.DispatchResult,
    pos_types: list[ty.TypeExpr],
    kw_types: dict[str, ty.TypeExpr],
    expected_return: ty.TypeExpr | None,
    *,
    ctx: Context,
) -> tuple[hir.AST, ty.DispatchResult]:
    """Replace a generic callee by (a reference to) its instance for these
    arguments; the dispatch result becomes the instance's concrete signature."""
    if not (isinstance(left, hir.ExpressedIdentifier) and left.binding_id is not None):
        return left, result
    binding = ctx.binding_registry.by_id.get(left.binding_id)
    declaration = binding.declaration if binding is not None else None
    if declaration is None or not isinstance(declaration.expr, hir.GenericFunction):
        return left, result
    generic = declaration.expr
    assert isinstance(generic.type, ty.FunctionType)
    bindings = ctx.type_system.infer_type_args(generic.type, pos_types, kw_types, expected_return)
    if bindings is None:
        user_error(
            ctx.srcfile,
            f'cannot infer the type parameters of `{generic.name}` from this call',
            Pointer(span=left.loc, message='the arguments do not determine every type parameter'),
        )
    bindings = {name: _widen_type_argument(value, loc=left.loc, ctx=ctx) for name, value in bindings.items()}
    source = generic.source
    key = tuple((param.name, repr(bindings[param.name])) for param in source.params)
    instance = source.instances.get(key)
    if instance is None:
        instance = _instantiate_generic_function(generic, bindings, ctx=ctx, call_loc=left.loc)
    assert isinstance(instance.type, ty.FunctionType)
    callee = hir.ExpressedIdentifier(left.loc, instance.type, instance.name, binding_id=instance.id)
    return callee, ty.DispatchResult(instance.type, result.method_index, result.promote_pos)


def _instantiate_generic_function(generic: hir.GenericFunction, bindings: dict[str, ty.TypeExpr], *, ctx: Context, call_loc: Span | None = None) -> sb.Binding:
    """Check the generic body with its type parameters bound to concrete types
    and hoist the result as an ordinary module-level function. A body that
    does not check for these types is reported at the use inside it, or — for
    a generic from another module, whose source the caller is not looking
    at — at the call, with the same title and reason."""
    source = generic.source
    defining: Context = source.context  # type: ignore[assignment]
    instance_ctx = replace(
        defining,
        declarations=defining.declarations.new_child(),
        binding_scopes=defining.binding_scopes.new_child(),
        # what the body instantiates or synthesizes is hoisted into the module
        # being compiled (the caller's), after it — callees come first
        module=ctx.module,
        generic_instances=ctx.generic_instances,
        pending_methods=ctx.pending_methods,   # the caller's types' methods, declared on first use
        object_strings=ctx.object_strings,
        synthesized=ctx.synthesized,
    )
    for param in source.params:
        alias = instance_ctx.binding_registry.allocate_param(param.name, ty.TYPE_TYPE, generic.loc)
        alias.type_value = bindings[param.name]
        instance_ctx.declarations[param.name] = ty.TYPE_TYPE
        instance_ctx.binding_scopes[param.name] = alias
    assert isinstance(generic.type, ty.FunctionType)
    instance_type = ty.instantiate_method(generic.type, bindings)
    name = _instantiation_name(generic.name, bindings, source.params)
    taken = {instance.name for instance in source.instances.values()}
    if name in taken:
        # two object types with the same fields spell the same (their methods differ)
        name = next(f'{name}_{ordinal}' for ordinal in count(2) if f'{name}_{ordinal}' not in taken)
    key = tuple((param.name, repr(bindings[param.name])) for param in source.params)
    binding = ctx.binding_registry.allocate(_fresh_syntax(ctx), name, 'function', generic.loc)
    binding.type = instance_type
    binding.generic_instance = (generic, dict(bindings), ctx)
    source.instances[key] = binding  # registered first, so a recursive call finds it
    # the instance is visible under its own name in the defining scope (recursion, other instances)
    defining.declarations.maps[0][name] = instance_type
    defining.binding_scopes.maps[0][name] = binding
    literal_ast = source.literal
    assert isinstance(literal_ast, p0.BinOp)
    # check the literal without its `<T…>` prefix, under the instance bindings
    signature = literal_ast.left
    if isinstance(signature, p0.BinOp) and isinstance(signature.op, t1.Operator) and signature.op.symbol == ':>':
        plain = replace(literal_ast, left=replace(signature, left=signature.left.right))
    else:
        plain = replace(literal_ast, left=signature.right)
    try:
        literal = tcr_function_literal(plain, ctx=instance_ctx)
    except (TypeCheckError, UserError) as error:
        if call_loc is None or defining.srcfile is ctx.srcfile:
            raise
        report = error.report
        reason = next((pointer.message for pointer in report.pointer_messages), None)
        arguments = ', '.join(f'`{param.name}` = `{type_to_dewy(bindings[param.name])}`' for param in source.params)
        raise type(error)(Error(
            srcfile=ctx.srcfile,
            title=report.title,
            message=report.message,
            pointer_messages=[Pointer(span=call_loc, message=f'in `{generic.name}` for {arguments}' + (f': {reason}' if reason else ''))],
            hint=report.hint,
            notes=report.notes,
        )) from None
    declaration = hir.Declare(generic.loc, ty.VOID_TYPE, 'let', name, None, literal, binding_id=binding.id)
    binding.declaration = declaration
    binding.function = literal
    ctx.generic_instances.append(declaration)
    return binding


def _type_alias_value(ast: p0.AST, *, ctx: Context) -> ty.TypeAliasValue:
    generic = _generic_type_alias_parts(ast)
    if generic is not None:
        parameters, body = generic
        return _generic_type_alias(parameters, body, ctx=ctx)
    return ast_to_type(ast, ctx=ctx)


def _prebound_alias_value(binding: sb.Binding | None, *, ctx: Context) -> ty.TypeAliasValue | None:
    """A prebound alias's value at its own declaration: resolved now if nothing referred to it yet."""
    if binding is None:
        return None
    if binding.type_value is not None:
        return binding.type_value
    if binding.id in ctx.type_alias_asts:
        return _resolve_type_alias(binding, ctx=ctx)
    return None


def _resolve_type_alias(binding: sb.Binding, *, ctx: Context) -> ty.TypeAliasValue:
    if binding.type_value is not None:
        return binding.type_value
    if binding.id in ctx.resolving_type_aliases:
        # a recursive alias: the inner occurrence is a by-name reference that
        # unfolds to the alias once it has resolved
        named = ctx.named_types.get(binding.id)
        if named is None:
            named = ty.NamedType(binding.name, binding.id)
            ctx.named_types[binding.id] = named
        return named
    rhs = ctx.type_alias_asts[binding.id]
    ctx.resolving_type_aliases.add(binding.id)   # a mint too: a cycle through it is a recursive reference, not a re-entry
    try:
        minted = _mint_nominal_type(binding, rhs, ctx=ctx)
        value = minted if minted is not None else _type_alias_value(rhs, ctx=ctx)
    finally:
        ctx.resolving_type_aliases.remove(binding.id)
    named = ctx.named_types.get(binding.id)
    if named is not None:
        _validate_recursive_alias(binding, value, named, ctx=ctx)
        named.resolve(value)
    if minted is not None:
        binding.type_value = minted
        if isinstance(minted, ty.ObjectType) and minted.methods:
            ctx.pending_methods.append((binding, minted))
        return minted
    binding.type_value = value
    if isinstance(value, ty.ObjectType):
        for method in value.methods:
            if method.owner is None:
                method.owner = binding.name
    if isinstance(value, ty.ObjectType) and value.methods:
        # declared at first use (or at the end of the module): the bodies may
        # call functions declared after the alias
        ctx.pending_methods.append((binding, value))
    return binding.type_value


_dict_literal_counter = count(1)


def _dict_literal_block(ast: p0.AST) -> p0.Block | None:
    """Match a `[]` block whose items are all `->` dictionary entries."""
    if (
        isinstance(ast, p0.Block)
        and ast.kind == '[]'
        and ast.inner
        and all(
            isinstance(item, p0.BinOp)
            and isinstance(item.op, t1.Operator)
            and item.op.symbol == '->'
            for item in ast.inner
        )
    ):
        return ast
    return None


def _dict_value(node: hir.AST) -> tuple[hir.AST, ty.TypeExpr, ty.TypeExpr | None] | None:
    """`(container, K, V)` for a runtime dictionary, `(container, T, None)` for a set."""
    while isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
        node = node.items[0]
    entry_types = ty.container_entry_types(node.type)
    if entry_types is None:
        return None
    return node, entry_types[0], entry_types[1]


def _container_fields(dictionary: hir.AST) -> list[tuple[str, ty.TypeExpr]]:
    entry_types = ty.container_entry_types(dictionary.type)
    assert entry_types is not None
    fields = [('keys', entry_types[0])]
    if entry_types[1] is not None:
        fields.append(('values', entry_types[1]))
    return fields


def _dict_arrays(dictionary: hir.AST, loc: Span, *, ctx: Context) -> tuple[hir.AST, hir.AST | None]:
    """The `keys` (and `values`) member routes of a container, with exact lengths when known."""
    result: list[hir.AST] = []
    for field, element in _container_fields(dictionary):
        member = hir.MemberAccess(loc, ty.ArrayType(element, None), dictionary, field)
        route_id = sb.array_route_id(member, ctx.binding_registry)
        refined = ctx.refinements.get(route_id) if route_id is not None else None
        if isinstance(refined, ty.ArrayType):
            member = replace(member, type=refined)
        result.append(member)
    return result[0], (result[1] if len(result) > 1 else None)


def _invalidate_dict_lengths(dictionary: hir.AST, *, ctx: Context) -> None:
    """A store may append: the entry arrays' exact lengths are no longer known."""
    for field, element in _container_fields(dictionary):
        member = hir.MemberAccess(dictionary.loc, ty.ArrayType(element, None), dictionary, field)
        route_id = sb.array_route_id(member, ctx.binding_registry)
        if route_id is not None:
            ctx.refinements.pop(route_id, None)
            ctx.length_bounds.pop(route_id, None)


def _tcr_dict_literal(
    block: p0.Block,
    *,
    expected: ty.Type | None,
    ctx: Context,
) -> hir.ObjectLiteral:
    """Check `[k -> v ...]` (or `[]` against a dictionary type) as the object `[keys values]`."""
    entries = [item for item in block.inner if isinstance(item, p0.BinOp)]
    keys_block = p0.Block(block.loc, [item.left for item in entries], '[]', None)
    values_block = p0.Block(block.loc, [item.right for item in entries], '[]', None)
    expected_keys = expected_values = None
    annotation = ty.strip_refinement(expected) if expected is not None else None
    key_value = ty.dict_key_value(annotation) if annotation is not None else None
    if key_value is not None:
        expected_keys = ty.ArrayType(key_value[0], len(entries))
        expected_values = ty.ArrayType(key_value[1], len(entries))
    elif not entries:
        user_error(
            ctx.srcfile,
            'empty dictionary literal needs a dictionary type',
            Pointer(span=block.loc, message='annotate it, for example `let d:dict<string int64> = []`'),
        )
    keys = typecheck_and_resolve_inner(keys_block, ctx=ctx, expected=expected_keys)
    values = typecheck_and_resolve_inner(values_block, ctx=ctx, expected=expected_values)
    if not isinstance(keys.type, ty.ArrayType) or not isinstance(values.type, ty.ArrayType):
        not_implemented(
            ctx.srcfile,
            block.loc,
            'dictionary entries without homogeneous key and value types',
        )
    dict_object = annotation if key_value is not None else ty.dict_type(keys.type.element, values.type.element)
    assert isinstance(dict_object, ty.ObjectType)
    count = len(entries)
    return hir.ObjectLiteral(
        block.loc,
        dict_object,
        [
            hir.ObjectField(keys.loc, 'keys', keys),
            hir.ObjectField(values.loc, 'values', values),
            # hashes and the probe table are built lazily on first use
            hir.ObjectField(block.loc, 'hashes', hir.ArrayLiteral(block.loc, ty.ArrayType('int64', 0), [])),
            hir.ObjectField(block.loc, 'indices', hir.ArrayLiteral(block.loc, ty.ArrayType('int64', 0), [])),
            hir.ObjectField(block.loc, 'live', hir.Integer(block.loc, ty.IntegerLiteralType(count), '0d', count)),
        ],
    )


def _loop_flow(ast: p0.AST) -> p0.Flow | None:
    """A `loop …` flow (the only arm is a loop), else None."""
    if isinstance(ast, p0.Flow) and ast.default is None and len(ast.arms) == 1:
        arm = ast.arms[0]
        if arm.parts and isinstance(arm.parts[0], t1.Keyword) and arm.parts[0].name == 'loop':
            return ast
    return None


def _capture_values(node: hir.AST) -> list[hir.AST]:
    """The expressed values of a loop body: the last item of a block, every
    arm of a conditional, a nested loop's body — the positions a capture
    collects. Statements (void or diverging) express nothing."""
    if isinstance(node, hir.Block):
        return _capture_values(node.items[-1]) if node.items else []
    if isinstance(node, hir.Flow):
        values: list[hir.AST] = []
        for arm in node.arms:
            values.extend(_capture_values(arm.body))
        if node.default is not None:
            values.extend(_capture_values(node.default))
        return values
    if node.type in (ty.VOID_TYPE, ty.BOTTOM_TYPE):
        return []
    return [node]


def _replace_capture_values(node: hir.AST, push: Callable[[hir.AST], hir.AST]) -> hir.AST:
    """The loop body with each expressed value replaced by its push."""
    if isinstance(node, hir.Block):
        if not node.items:
            return node
        items = [*node.items[:-1], _replace_capture_values(node.items[-1], push)]
        return replace(node, type=ty.VOID_TYPE, items=items)
    if isinstance(node, hir.Flow):
        arms = [replace(arm, type=ty.VOID_TYPE, body=_replace_capture_values(arm.body, push)) for arm in node.arms]
        default = _replace_capture_values(node.default, push) if node.default is not None else None
        return replace(node, type=ty.VOID_TYPE, arms=arms, default=default)
    if node.type in (ty.VOID_TYPE, ty.BOTTOM_TYPE):
        return node
    return push(node)


_CAPTURE_KEY, _CAPTURE_VALUE = '__dewy_key', '__dewy_value'


def _capture_positions(ast: p0.AST) -> list[p0.AST]:
    """The syntax at a loop body's value positions (see `_capture_values`)."""
    if isinstance(ast, p0.Block) and ast.kind in ('{}', '()'):
        return _capture_positions(ast.inner[-1]) if ast.inner else []
    if isinstance(ast, p0.Flow):
        positions: list[p0.AST] = []
        for arm in ast.arms:
            if len(arm.parts) == 3 and isinstance(arm.parts[2], p0.AST):
                positions.extend(_capture_positions(arm.parts[2]))
        if ast.default is not None:
            positions.extend(_capture_positions(ast.default))
        return positions
    return [ast]


def _rewrite_capture_pairs(ast: p0.AST) -> p0.AST:
    """`k -> v` at a value position as the object literal `[__dewy_key=k __dewy_value=v]`, so the pair checks as one value."""
    if isinstance(ast, p0.Block) and ast.kind in ('{}', '()') and ast.inner:
        return replace(ast, inner=[*ast.inner[:-1], _rewrite_capture_pairs(ast.inner[-1])])
    if isinstance(ast, p0.Flow):
        arms = [
            replace(arm, parts=[*arm.parts[:2], _rewrite_capture_pairs(arm.parts[2])])
            if len(arm.parts) == 3 and isinstance(arm.parts[2], p0.AST) else arm
            for arm in ast.arms
        ]
        default = _rewrite_capture_pairs(ast.default) if ast.default is not None else None
        return replace(ast, arms=arms, default=default)
    if isinstance(ast, p0.BinOp) and _operator_symbol(ast.op) == '->':
        loc = ast.loc
        def field(name: str, value: p0.AST) -> p0.AST:
            return p0.BinOp(loc, t1.Operator(loc, '='), p0.Atom(loc, t1.Identifier(loc, name)), value)
        return p0.Block(loc, [field(_CAPTURE_KEY, ast.left), field(_CAPTURE_VALUE, ast.right)], '[]', None)
    return ast


def _tcr_loop_capture(block: p0.Block, *, kind: Literal['array', 'set'], expected: ty.Type | None, ctx: Context) -> hir.AST:
    """`[loop i in xs f(i)]` / `set[loop …]` / `[loop … k -> v]`: the array,
    set, or dictionary of the values the loop body expresses, in order — an
    iteration whose body expresses nothing (an `if` without a match, a bare
    statement) adds nothing, so `[loop i in xs if keep(i) i]` filters. The
    container is declared before the statement (`let name:array<T> = []`,
    synthesized) and filled by the loop through `_capture_push` /
    `_capture_add` / `_capture_store`; the literal is then the container."""
    if ctx.hoisted is None:
        not_implemented(ctx.srcfile, block.loc, 'a loop capture outside a block body (in an expression-bodied function or a default)')
    flow = _loop_flow(block.inner[0])
    assert flow is not None
    body_ast = flow.arms[0].parts[2]
    assert isinstance(body_ast, p0.AST)
    positions = _capture_positions(body_ast)
    arrows = [position for position in positions if isinstance(position, p0.BinOp) and _operator_symbol(position.op) in ('->', '<->')]
    if arrows and kind == 'set':
        user_error(ctx.srcfile, 'a set capture takes members, not pairs', Pointer(span=arrows[0].loc, message='`->` builds a dictionary: write `[loop …]`'))
    if arrows and len(arrows) != len(positions):
        other = next(position for position in positions if position not in arrows)
        user_error(ctx.srcfile, 'a capture mixes pairs and values', Pointer(span=arrows[0].loc, message='this is a pair'), Pointer(span=other.loc, message='this is a value'))
    if any(_operator_symbol(arrow.op) == '<->' for arrow in arrows):
        not_implemented(ctx.srcfile, arrows[0].loc, 'bidirectional dictionary literals')
    if arrows:
        kind = 'dict'
        flow = replace(flow, arms=[replace(flow.arms[0], parts=[*flow.arms[0].parts[:2], _rewrite_capture_pairs(body_ast)])])
        ctx.synthesized.append(flow)
    loop = typecheck_and_resolve_inner(flow, ctx=ctx)
    if not isinstance(loop, hir.Flow) or len(loop.arms) != 1 or not isinstance(loop.arms[0], hir.LoopArm):
        raise TypeError('INTERNAL ERROR: loop capture did not check to a loop')
    values = _capture_values(loop.arms[0].body)
    if not values:
        user_error(
            ctx.srcfile,
            'this loop expresses no value to capture',
            Pointer(span=block.loc, message='every path through the body is a statement'),
            hint='end the body with the value to collect, for example `[loop i in xs i * 2]`',
        )

    def common_type(nodes: list[hir.AST], what: str) -> ty.TypeExpr:
        widened = [_widen_type_argument(cast(ty.TypeExpr, node.type), loc=node.loc, ctx=ctx) for node in nodes]
        chosen = widened[0]
        for index, other in enumerate(widened[1:], start=1):
            if other == chosen or ctx.type_system.is_subtype(other, chosen):
                continue
            if ctx.type_system.is_subtype(chosen, other):
                chosen = other
                continue
            type_error(
                ctx.srcfile,
                f'loop capture {what} differ in type',
                Pointer(span=nodes[0].loc, message=f'this has type `{type_to_dewy(chosen)}`'),
                Pointer(span=nodes[index].loc, message=f'this has type `{type_to_dewy(other)}`'),
                hint='a container holds one type; annotate the binding to choose it',
            )
        return chosen

    plain_expected = ty.unfold(ty.strip_refinement(expected)) if expected is not None else None
    loc = block.loc
    name = f'__dewy_capture_{ctx.binding_registry.next_id}'
    if kind == 'dict':
        pairs = [value for value in values if isinstance(value, hir.ObjectLiteral) and [f.name for f in value.fields] == [_CAPTURE_KEY, _CAPTURE_VALUE]]
        if len(pairs) != len(values):
            raise TypeError('INTERNAL ERROR: a dictionary capture value is not a pair')
        expected_entries = ty.dict_key_value(plain_expected) if plain_expected is not None else None
        key_type = expected_entries[0] if expected_entries is not None else common_type([pair.fields[0].value for pair in pairs], 'keys')
        value_type = expected_entries[1] if expected_entries is not None else common_type([pair.fields[1].value for pair in pairs], 'values')
        text = f'let {name}:dict<{type_to_dewy(key_type)} {type_to_dewy(value_type)}> = []\n'
    else:
        expected_element = (
            plain_expected.element if kind == 'array' and isinstance(plain_expected, ty.ArrayType)
            else ty.set_element(plain_expected) if kind == 'set' and plain_expected is not None
            else None
        )
        element = expected_element if expected_element is not None else common_type(values, 'values')
        spelled = type_to_dewy(element)
        text = f'let {name}:array<{spelled}> = []\n' if kind == 'array' else f'let {name}:set<{spelled}> = set[]\n'
        if kind == 'array':
            # declared the way a grown array is written by hand, so it takes the runtime-length representation
            ctx.grown_array_names = ctx.grown_array_names | {name}
    parsed = p0.parse(SrcFile(None, ' ' * loc.start + text))
    declaration_ast = parsed.inner[0]
    ctx.synthesized.append(declaration_ast)
    declaration = typecheck_and_resolve_inner(declaration_ast, ctx=ctx)
    binding = ctx.binding_scopes.get(name)
    declared = ctx.declarations.get(name)   # the runtime-length type reads see (the binding keeps the exact one)
    if binding is None or declared is None:
        raise TypeError('INTERNAL ERROR: loop capture container was not declared')
    container_type = cast(ty.TypeExpr, declared)

    def push(value: hir.AST) -> hir.AST:
        place = hir.Place(value.loc, container_type, hir.ExpressedIdentifier(value.loc, container_type, name, binding_id=binding.id))
        if kind == 'dict':
            assert isinstance(value, hir.ObjectLiteral)
            return _library_call('_capture_store', [place, value.fields[0].value, value.fields[1].value], value.loc, ctx=ctx)
        return _library_call('_capture_push' if kind == 'array' else '_capture_add', [place, value], value.loc, ctx=ctx)

    arm = loop.arms[0]
    filled = replace(loop, type=ty.VOID_TYPE, arms=[replace(arm, type=ty.VOID_TYPE, body=_replace_capture_values(arm.body, push))])
    ctx.hoisted.extend([declaration, filled])
    return hir.ExpressedIdentifier(loc, container_type, name, binding_id=binding.id)


def _tcr_set_from(operand_ast: p0.AST, loc: Span, *, ctx: Context) -> hir.AST:
    """`set"0123"` / `set(values)`: the set of a string's graphemes or an array's elements (`library/strings.dewy`)."""
    if isinstance(operand_ast, p0.Block) and operand_ast.kind == '()' and len(operand_ast.inner) == 1:
        operand_ast = operand_ast.inner[0]
    operand = typecheck_and_resolve_inner(operand_ast, ctx=ctx)
    require_valued(operand.type, ctx.srcfile, operand.loc, '`set` operand')
    if _is_string_type(operand.type):
        return _library_call('_set_of_graphemes', [operand], loc, ctx=ctx)
    if isinstance(ty.unfold(ty.strip_refinement(operand.type)), ty.ArrayType):
        return _library_call('_set_of_array', [operand], loc, ctx=ctx)
    type_error(
        ctx.srcfile,
        '`set` takes a string or an array',
        Pointer(span=operand.loc, message=f'this has type `{type_to_dewy(operand.type)}`'),
        hint='`set[a b c]` lists members; `set"abc"` takes a string\'s graphemes and `set(values)` an array\'s elements',
    )


def _tcr_set_literal(
    block: p0.Block,
    loc: Span,
    *,
    expected: ty.Type | None,
    ctx: Context,
) -> hir.ObjectLiteral:
    """`set[a b c]`: the set object over the distinct members, in first-seen order."""
    annotation = ty.strip_refinement(expected) if expected is not None else None
    element = ty.set_element(annotation) if annotation is not None else None
    if element is None and not block.inner:
        user_error(
            ctx.srcfile,
            'empty set literal needs a set type',
            Pointer(span=loc, message='annotate it, for example `let s:set<string> = set[]`'),
        )
    members = typecheck_and_resolve_inner(
        block, ctx=ctx, expected=ty.ArrayType(element, len(block.inner)) if element is not None else None,
    )
    if not isinstance(members, hir.ArrayLiteral) or not isinstance(members.type, ty.ArrayType):
        not_implemented(ctx.srcfile, block.loc, 'set literals from non-literal member lists')
    # duplicates collapse at compile time, so `live` is exact; members must
    # be constants for that (runtime members dedupe at the first table build)
    seen: dict[object, int] = {}
    distinct: list[hir.AST] = []
    for item in members.items:
        identity = _key_identity(item, ctx=ctx)
        if identity is None or identity[0] != 'c':
            not_implemented(ctx.srcfile, item.loc, 'set literal members that are not constants')
        if identity[1] in seen:
            continue
        seen[identity[1]] = len(distinct)
        distinct.append(item)
    set_object = annotation if element is not None else ty.set_type(members.type.element)
    assert isinstance(set_object, ty.ObjectType)
    keys = replace(members, items=distinct, type=ty.ArrayType(members.type.element, len(distinct)))
    count = len(distinct)
    return hir.ObjectLiteral(
        loc,
        set_object,
        [
            hir.ObjectField(keys.loc, 'keys', keys),
            hir.ObjectField(loc, 'hashes', hir.ArrayLiteral(loc, ty.ArrayType('int64', 0), [])),
            hir.ObjectField(loc, 'indices', hir.ArrayLiteral(loc, ty.ArrayType('int64', 0), [])),
            hir.ObjectField(loc, 'live', hir.Integer(loc, ty.IntegerLiteralType(count), '0d', count)),
        ],
    )


def _tcr_dict_declare(
    name: str,
    loc: Span,
    block: p0.Block,
    *,
    ctx: Context,
    annotation: ty.ObjectType | None = None,
    keyword: str = 'let',
) -> hir.AST:
    """Declare a dictionary: the runtime object `[keys values]` (insertion order).

    The literal's entries become the exact-length initializers of the two
    growable arrays; their exact lengths are kept as route refinements
    (`d.keys`, `d.values`) until a store may append.
    """
    literal = _tcr_dict_literal(block, expected=annotation, ctx=ctx)
    dict_object = literal.type
    assert isinstance(dict_object, ty.ObjectType)
    binding = ctx.binding_registry.allocate(block, name, 'value', loc)
    binding.type = dict_object
    declaration = hir.Declare(loc, ty.VOID_TYPE, keyword, name, dict_object, literal, binding_id=binding.id)   # a `const` keeps its literal's keys proven everywhere
    binding.declaration = declaration
    ctx.declarations[name] = dict_object
    ctx.binding_scopes[name] = binding
    _seed_field_routes(binding.id, dict_object, literal, (), ctx=ctx)
    dictionary = hir.ExpressedIdentifier(loc, dict_object, name, binding_id=binding.id)
    keys_literal = literal.fields[0].value
    while isinstance(keys_literal, (hir.RepresentationCast, hir.ValueCast)):
        keys_literal = keys_literal.expr
    if isinstance(keys_literal, hir.ArrayLiteral):
        for index, key in enumerate(keys_literal.items):
            _record_key_fact(dictionary, key, ctx=ctx, static_position=index)
    return declaration


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


def _spread_operand(item: p0.AST) -> p0.AST | None:
    """The operand of a spread item `x...`, else None."""
    if isinstance(item, p0.Ambiguous):
        # `f(x)...` also reads as `f * (x)...`; in a literal item position the
        # spread reading is the one meant
        for candidate in item.candidates:
            operand = _spread_operand(candidate)
            if operand is not None:
                return operand
        return None
    if (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t2.EllipsisJuxtapose)
        and isinstance(item.right, p0.Atom)
        and isinstance(item.right.item, t1.Identifier)
        and item.right.item.name == '...'
    ):
        return item.left
    return None


def _spread_source(operand: p0.AST, *, ctx: Context) -> hir.AST:
    """Check a spread operand: a named place, so reading it several times is one evaluation."""
    value = typecheck_and_resolve_inner(operand, ctx=ctx)
    if isinstance(value, hir.Place):
        value = value.target
    if not isinstance(value, (hir.ExpressedIdentifier, hir.MemberAccess)):
        not_implemented(ctx.srcfile, operand.loc, 'spreading a computed value (bind it to a name first)')
    require_valued(value.type, ctx.srcfile, value.loc, 'spread operand')
    if isinstance(value.type, ty.TypeOr):
        user_error(
            ctx.srcfile,
            'cannot spread a union-typed value',
            Pointer(span=value.loc, message=f'this has type `{type_to_dewy(value.type)}`'),
            hint='narrow it with `is?` first',
        )
    return replace(value, type=ty.unfold(value.type))


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


def _accepts_no_arguments(type_: ty.Type) -> bool:
    """Whether a callable type has some method every parameter of which is optional."""
    methods = type_.methods if isinstance(type_, ty.OverloadType) else [type_]
    return any(
        isinstance(method, ty.FunctionType)
        and all(not param.required for param in method.pos_or_kw)
        and all(not param.required for param in method.kw_only)
        for method in methods
    )


def _auto_call_function_value(node: hir.AST, *, ctx: Context, expected: ty.Type | None = None) -> hir.AST:
    """A bare function name is a call. `@name` is the way to mean the function itself."""
    if not isinstance(node, hir.ExpressedIdentifier) or not isinstance(node.type, (ty.FunctionType, ty.OverloadType)):
        return node
    if _accepts_no_arguments(node.type):
        return tcr_function_call(node, p0.Block(node.loc, [], '()', None), ctx=ctx, expected=expected)
    type_error(
        ctx.srcfile,
        f'`{node.name}` needs arguments',
        Pointer(span=node.loc, message='a bare function name calls the function, and this one has required parameters'),
        hint=f'call it with its arguments, or write `@{node.name}` to mean the function itself',
    )


# `text.contains(x)`, `text.trim`, …: methods of `string`, implemented in
# `library/strings.dewy` as `_string_<name>(text …)` and bound like a type's methods.
_STRING_METHODS = frozenset({
    'contains', 'startswith', 'endswith', 'find', 'rfind', 'split', 'lines',
    'trim', 'trim_start', 'trim_end', 'replace', 'casefold',
})


def _string_method(receiver: hir.AST, name: str, binop: p0.BinOp, *, ctx: Context) -> hir.BoundMethod:
    binding = ctx.binding_scopes.get(f'_string_{name}')
    if binding is None or not isinstance(binding.type, ty.FunctionType):
        user_error(
            ctx.srcfile,
            f'`.{name}` needs the prelude',
            Pointer(span=binop.right.loc, message='string methods are implemented in the prelude\'s `strings.dewy`'),
        )
    function = hir.ExpressedIdentifier(binop.right.loc, binding.type, binding.name, binding_id=binding.id)
    bound_type = replace(binding.type, pos_or_kw=binding.type.pos_or_kw[1:])
    return hir.BoundMethod(binop.loc, bound_type, function, receiver)


def _maybe_auto_call_member(node: hir.AST, *, ctx: Context) -> hir.AST:
    if isinstance(node, hir.BoundMethod):
        if ty.is_zero_arg_function(node.type):
            return tcr_function_call(node, p0.Block(node.loc, [], '()', None), ctx=ctx)
        if node.receiver is None:
            return node.function   # a static method with parameters is its function, an ordinary value
        type_error(ctx.srcfile, 'a method must be called', Pointer(span=node.loc, message='this method takes arguments; methods are not values yet'))
    if not isinstance(node, (hir.MemberAccess, hir.ArrayMethod, hir.DictMethod)):
        return node
    if isinstance(node, hir.DictMethod) and isinstance(node.type, ty.FunctionType) and not node.type.pos_or_kw:
        call = hir.FunctionCall(node.loc, node.type.ret, node, [], {})
        return _dict_method_call(node, call, ctx=ctx)
    optional_only = (
        isinstance(node, hir.ArrayMethod)
        and isinstance(node.type, ty.FunctionType)
        and all(not param.required for param in node.type.pos_or_kw)
        and all(not param.required for param in node.type.kw_only)
    )
    if ty.is_zero_arg_function(node.type) or optional_only:
        # `xs.pop` calls with every optional argument left to its default
        assert isinstance(node.type, ty.FunctionType)
        call = hir.FunctionCall(node.loc, node.type.ret, node, [], {})
        if isinstance(node, hir.ArrayMethod):
            _apply_array_method_transition(node, node.loc, ctx=ctx)
        return call
    if isinstance(node.type, (ty.FunctionType, ty.OverloadType)):
        not_implemented(
            ctx.srcfile,
            node.loc,
            'extracting an object method as a function value',
        )
    return node


def _positional_object_literal(block: p0.Block, object_type: ty.ObjectType, *, ctx: Context) -> p0.Block | None:
    """`[set'01' false []]` where a plain object type is expected: the items
    fill the fields in declaration order (a field left out takes its
    default), as a constructor call does; None when any item is named."""
    if (object_type.brand is not None and not ty.user_branded(object_type)) or not block.inner:
        return None
    for item in block.inner:
        if isinstance(item, p0.BinOp) and _operator_symbol(item.op) in ('=', '->', '<->'):
            return None
        if _spread_operand(item) is not None:
            return None
    if len(block.inner) > len(object_type.fields):
        user_error(
            ctx.srcfile,
            'too many values for this object',
            Pointer(span=block.inner[len(object_type.fields)].loc, message=f'the expected type has {len(object_type.fields)} fields'),
        )
    items: list[p0.AST] = []
    for index, field_ in enumerate(object_type.fields):
        if index < len(block.inner):
            value: p0.AST = block.inner[index]
        elif field_.default is not None:
            value = cast(p0.AST, field_.default)
        else:
            user_error(
                ctx.srcfile,
                f'missing value for field `{field_.name}`',
                Pointer(span=block.loc, message=f'the expected type needs `{field_.name}:{type_to_dewy(field_.type)}`'),
                hint='give the fields in order, or name them (`[name=value …]`)',
            )
        loc = value.loc
        items.append(p0.BinOp(loc, t1.Operator(loc, '='), p0.Atom(loc, t1.Identifier(loc, field_.name)), value))
    literal = p0.Block(block.loc, items, '[]', None)
    ctx.synthesized.append(literal)
    return literal


def _tcr_object_literal(
    block: p0.Block,
    *,
    expected: ty.Type | None,
    ctx: Context,
) -> hir.ObjectLiteral:
    expected = ty.unfold(ty.strip_refinement(expected)) if expected is not None else None
    expected_object = expected if isinstance(expected, ty.ObjectType) else None
    if expected_object is not None:
        positional = _positional_object_literal(block, expected_object, ctx=ctx)
        if positional is not None:
            block = positional
    if expected_object is None and isinstance(expected, ty.TypeOr):
        # A literal checked against a union targets the union's unique
        # object member, if there is exactly one.
        # a recursive member unfolds to its object type for the literal
        candidates = [ty.unfold(item) for item in expected.items if isinstance(ty.unfold(item), ty.ObjectType)]
        if len(candidates) > 1:
            # several object members: the literal's field names choose
            written = {
                item.left.item.name
                for item in block.inner
                if isinstance(item, p0.BinOp)
                and isinstance(item.op, t1.Operator)
                and item.op.symbol == '='
                and isinstance(item.left, p0.Atom)
                and isinstance(item.left.item, t1.Identifier)
            }
            matching = [candidate for candidate in candidates if {field.name for field in candidate.fields} == written]
            if len(matching) == 1:
                candidates = matching
        if len(candidates) == 1:
            expected_object = candidates[0]
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
    # An entry is a written field or one copied in by a spread `obj...`
    # (already checked: a member read of the spread source). Names repeat in
    # the Python splat sense — the later entry wins, at the position of the
    # first — except that two *written* fields with one name are a mistake.
    entries: list[tuple[tuple[str, p0.AST | None, p0.AST | None, Span, bool], object, hir.AST | None]] = []
    for item in block.inner:
        operand = _spread_operand(item)
        if operand is None:
            entries.append((_object_field_syntax(item, ctx=ctx), item, None))
            continue
        source = _spread_source(operand, ctx=ctx)
        if not isinstance(source.type, ty.ObjectType) or (source.type.brand is not None and not ty.user_branded(source.type)):
            user_error(
                ctx.srcfile,
                'object spread requires an object',
                Pointer(span=source.loc, message=f'this has type `{type_to_dewy(source.type)}`'),
            )
        for field in source.type.fields:
            read = hir.MemberAccess(item.loc, field.type, source, field.name, field.mutable)
            entries.append(((field.name, None, None, item.loc, field.mutable), object(), read))
    ordered: dict[str, int] = {}
    merged: list[tuple[tuple[str, p0.AST | None, p0.AST | None, Span, bool], object, hir.AST | None]] = []
    for entry in entries:
        name, _annotation, _value, loc, _mutable = entry[0]
        position = ordered.get(name)
        if position is None:
            ordered[name] = len(merged)
            merged.append(entry)
            continue
        if entry[2] is None and merged[position][2] is None:
            user_error(
                ctx.srcfile,
                f'duplicate object field `{name}`',
                Pointer(span=loc, message='this field repeats a name'),
                Pointer(span=merged[position][0][3], message='the earlier field is here'),
            )
        merged[position] = entry  # later wins
    entries = merged
    specs = [entry[0] for entry in entries]

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
        binding = ctx.binding_registry.allocate(entries[index][1], name, kind, loc)
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
            field_expected = _field_expectation(expected_object.fields[index])
        prechecked = entries[index][2]
        if prechecked is not None:
            value = prechecked  # a field copied in by a spread
        else:
            assert value_ast is not None
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
            field_expected = _field_expectation(expected_object.fields[index])
        value = typecheck_and_resolve_inner(value_ast, ctx=ctx, expected=field_expected)
        require_valued(value.type, ctx.srcfile, value.loc, 'object field')
        if field_expected is not None:
            value = check_against(value, field_expected, ctx=ctx)
            field_type = ty.strip_refinement(field_expected)
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
        types.append(ty.ObjectField(name, ty.strip_refinement(binding.type or value.type), mutable))  # a field invariant is not part of the literal's shape
    object_type = ty.ObjectType(tuple(types))
    if expected_object is not None:
        check_against(
            hir.ObjectLiteral(block.loc, object_type, fields),
            # a literal in a minted type's context is its construction form:
            # the fields are checked structurally and the value takes the brand
            ty.ObjectType(expected_object.fields, methods=expected_object.methods) if ty.user_branded(expected_object) else expected_object,
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


_ARRAY_METHOD_NAMES = frozenset({'push', 'pop', 'clear', 'reserve', 'insert', 'truncate', 'sort', 'join'})
_READ_ONLY_ARRAY_METHOD_NAMES = frozenset({'join'})


def _apply_array_method_transition(
    method: hir.ArrayMethod,
    loc: Span,
    *,
    ctx: Context,
    index: hir.AST | None = None,
) -> None:
    """Update length facts after a growth method call, proving `pop` first.

    An exact-length refinement steps by one on `push`/`insert`/`pop` and
    resets on `clear`; `truncate(n)` caps it; otherwise a proven minimum
    length (from guards such as `xs.length >? 0`) steps the same way. `pop`
    without an index requires one of them to prove the array is non-empty;
    constant indexes for `pop`/`insert` are checked here and runtime ones by
    the bounds analysis.
    """
    receiver = method.array
    binding_id = sb.array_route_id(receiver, ctx.binding_registry)
    if binding_id is None:
        return
    assert isinstance(receiver.type, ty.ArrayType)
    element = receiver.type.element
    current = ctx.refinements.get(binding_id)
    exact = current.length if isinstance(current, ty.ArrayType) else None
    minimum = ctx.length_bounds.get(binding_id, 0) if exact is None else exact
    index_value = _constant_integer(_unwrap_parens(index), ctx=ctx) if index is not None else None
    if method.name == 'pop':
        if index is None:
            if exact == 0:
                user_error(
                    ctx.srcfile,
                    'pop on an empty array',
                    Pointer(span=loc, message='this array has length 0 here'),
                )
            if exact is None and minimum < 1:
                user_error(
                    ctx.srcfile,
                    'cannot prove the array is non-empty',
                    Pointer(span=loc, message='`pop` needs a proven positive length'),
                    hint='guard the call with `if xs.length >? 0 { ... }`, or pop while the length is known',
                )
        elif index_value is not None:
            # a constant index is proven here; runtime indexes are proven by
            # the bounds analysis from intervals and `i <? xs.length` facts
            if index_value < 0 or (exact is not None and index_value >= exact):
                user_error(
                    ctx.srcfile,
                    'pop index is out of bounds',
                    Pointer(span=index.loc, message=f'index {index_value} into an array of length {exact}'),
                )
        new_exact = None if exact is None else exact - 1
        new_minimum = minimum - 1
    elif method.name == 'push':
        new_exact = None if exact is None else exact + 1
        new_minimum = minimum + 1
    elif method.name == 'insert':
        if index_value is not None and (index_value < 0 or (exact is not None and index_value > exact)):
            user_error(
                ctx.srcfile,
                'insert index is out of bounds',
                Pointer(span=index.loc, message=f'index {index_value} into an array of length {exact} (the end, {exact}, is allowed)'),
            )
        new_exact = None if exact is None else exact + 1
        new_minimum = minimum + 1
    elif method.name == 'truncate':
        if index_value is not None and index_value < 0:
            user_error(
                ctx.srcfile,
                'truncate length cannot be negative',
                Pointer(span=index.loc, message=f'got {index_value}'),
            )
        if index_value is None:
            new_exact = None
            new_minimum = 0
        else:
            new_exact = None if exact is None else min(exact, index_value)
            new_minimum = min(minimum, index_value)
    elif method.name == 'clear':
        new_exact = 0
        new_minimum = 0
    else:  # reserve, sort: the length is unchanged
        new_exact = exact
        new_minimum = minimum
    if new_exact is not None:
        ctx.refinements[binding_id] = ty.ArrayType(element, new_exact)
    else:
        ctx.refinements.pop(binding_id, None)
    ctx.length_bounds[binding_id] = max(new_minimum, 0)


def _grown_array_annotation(
    name: str,
    keyword: str,
    value_type: ty.Type,
    *,
    ctx: Context,
) -> ty.ArrayType | None:
    """The runtime-length type for an unannotated `let` array that gets grown."""
    if (
        keyword == 'let'
        and name in ctx.grown_array_names
        and isinstance(value_type, ty.ArrayType)
        and value_type.length is not None
    ):
        return ty.ArrayType(value_type.element, None)
    return None


def _grown_array_names(ast: p0.AST) -> frozenset[str]:
    """Names that are receivers of a growth method anywhere in ``ast``.

    A `let` array whose name is never grown keeps its initializer's exact
    type everywhere (including inside functions); one that is grown somewhere
    is checked as a runtime-length array with a local exact-length refinement.
    Name-based matching over-approximates under shadowing, which only costs
    precision.
    """
    names: set[str] = set()

    def walk(node: object) -> None:
        if (
            isinstance(node, p0.BinOp)
            and isinstance(node.op, t1.Operator)
            and node.op.symbol == '.'
            and isinstance(node.left, p0.Atom)
            and isinstance(node.left.item, t1.Identifier)
            and isinstance(node.right, p0.Atom)
            and isinstance(node.right.item, t1.Identifier)
            and node.right.item.name in _ARRAY_METHOD_NAMES
        ):
            names.add(node.left.item.name)
        if is_dataclass(node) and not isinstance(node, type):
            for field_ in fields(node):
                walk(getattr(node, field_.name))
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(ast)
    return frozenset(names)


def _iterated_container_names(condition: hir.AST) -> set[str]:
    """Names of dictionaries and sets a loop condition iterates."""
    iterators: list[hir.IteratorExpression] = []
    if isinstance(condition, hir.IteratorExpression):
        iterators.append(condition)
    elif isinstance(condition, hir.MultiIteratorExpression):
        iterators.extend(condition.iterators)
    names: set[str] = set()
    for iterator in iterators:
        iterable = iterator.iterable
        if isinstance(iterable, hir.DictEntries):
            root = iterable.dictionary
            while isinstance(root, hir.MemberAccess):
                root = root.value
            if isinstance(root, hir.ExpressedIdentifier):
                names.add(root.name)
    return names


_MUTATING_METHOD_NAMES = frozenset({*(_ARRAY_METHOD_NAMES - _READ_ONLY_ARRAY_METHOD_NAMES), 'add'})  # arrays, dictionaries, sets


def _mutated_binding_names(ast: p0.AST) -> set[str]:
    """Names a syntax tree may assign or grow (a conservative pre-scan)."""
    names: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, p0.BinOp):
            left_name = (
                node.left.item.name
                if isinstance(node.left, p0.Atom) and isinstance(node.left.item, t1.Identifier)
                else None
            )
            if left_name is not None and (
                (isinstance(node.op, t1.Operator) and node.op.symbol in {'=', ':=', '::'})
                or isinstance(node.op, t2.CombinedAssignmentOp)
            ):
                names.add(left_name)
            if (
                left_name is None
                and isinstance(node.op, t1.Operator)
                and node.op.symbol == '='
                and isinstance(node.left, p0.BinOp)
                and isinstance(node.left.left, p0.Atom)
                and isinstance(node.left.left.item, t1.Identifier)
            ):
                # `d[k] = v` mutates the indexed binding (a dictionary or array).
                names.add(node.left.left.item.name)
            if (
                left_name is not None
                and isinstance(node.op, t1.Operator)
                and node.op.symbol == '.'
                and isinstance(node.right, p0.Atom)
                and isinstance(node.right.item, t1.Identifier)
                and node.right.item.name in _MUTATING_METHOD_NAMES
            ):
                names.add(left_name)
        if is_dataclass(node) and not isinstance(node, type):
            for field_ in fields(node):
                walk(getattr(node, field_.name))
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(ast)
    return names


def _tcr_array_method(
    value: hir.AST,
    name: str,
    loc: Span,
    *,
    ctx: Context,
) -> hir.ArrayMethod:
    """Bind a compiler-provided growth method to a named array binding.

    Conceptually ``array`` is an ordinary Dewy object type whose methods are
    ``push``, ``pop``, ``clear``, and ``reserve``; container mutation is only
    ever reached through the container value.
    """
    assert isinstance(value.type, ty.ArrayType)
    if name in _READ_ONLY_ARRAY_METHOD_NAMES:
        # `xs.join`: reads any array value, named or not, of any length
        return _bind_array_method(value, value.type, name, loc, ctx=ctx)
    if isinstance(value, hir.MemberAccess):
        # `bag.items.push(x)`: a growable array field of a named object. Length
        # and index facts are keyed by the member route (see `array_route_id`).
        root = _member_root_binding(value, ctx=ctx)
        if root is None:
            not_implemented(ctx.srcfile, loc, 'array methods on an unnamed array value')
        if (reason := _read_only_reason(root)) is not None:
            user_error(
                ctx.srcfile,
                'cannot mutate a field of a const binding',
                Pointer(span=value.loc, message=f'`{root.name}` {reason}'),
            )
        if value.type.length is not None:
            user_error(
                ctx.srcfile,
                'exact-length arrays cannot change length',
                Pointer(span=value.loc, message=f'this field has type `{type_to_dewy(value.type)}`'),
                hint='declare the field as `array<T>` to allow growth',
            )
        declared = value.type
        return _bind_array_method(value, declared, name, loc, ctx=ctx)
    if not isinstance(value, hir.ExpressedIdentifier) or value.binding_id is None:
        not_implemented(ctx.srcfile, loc, 'array methods on an unnamed array value')
    binding = ctx.binding_registry.by_id[value.binding_id]
    declared = (
        binding.declaration.annotation
        if binding.declaration is not None and binding.declaration.annotation is not None
        else binding.type
    )
    if not isinstance(declared, ty.ArrayType) or declared.length is not None:
        user_error(
            ctx.srcfile,
            'exact-length arrays cannot change length',
            Pointer(
                span=value.loc,
                message=f'this is declared as `{type_to_dewy(declared)}`',
            ),
            hint='declare the binding as `array<T>` to allow growth',
        )
    return _bind_array_method(value, declared, name, loc, ctx=ctx)


def _bind_array_method(
    value: hir.AST,
    declared: ty.ArrayType,
    name: str,
    loc: Span,
    *,
    ctx: Context,
) -> hir.ArrayMethod:
    value = replace(value, type=declared)
    element = declared.element
    signatures: dict[str, ty.FunctionType] = {
        'push': ty.FunctionType([ty.PosOrKwArg('value', element)], [], None, ty.VOID_TYPE),
        # `xs.pop` removes the last element; `xs.pop(idx)` removes and returns
        # the element at `idx`, shifting the rest down.
        'pop': ty.FunctionType([ty.PosOrKwArg('idx', 'int64', required=False)], [], None, element),
        'insert': ty.FunctionType([ty.PosOrKwArg('value', element), ty.PosOrKwArg('idx', 'int64')], [], None, ty.VOID_TYPE),
        'truncate': ty.FunctionType([ty.PosOrKwArg('count', 'int64')], [], None, ty.VOID_TYPE),
        'clear': ty.FunctionType([], [], None, ty.VOID_TYPE),
        'reserve': ty.FunctionType([ty.PosOrKwArg('count', 'int64')], [], None, ty.VOID_TYPE),
        # ascending in-place sort of integer elements (comparators later)
        'sort': ty.FunctionType([], [], None, ty.VOID_TYPE),
        # `xs.join` concatenates string elements; `xs.join(sep)` / `xs.join"sep"`
        # puts the separator between them. The result is a new string.
        'join': ty.FunctionType([ty.PosOrKwArg('sep', 'string', required=False)], [], None, ty.StringType()),
    }
    if name == 'sort' and not (isinstance(element, str) and element in ty.FIXED_INTEGER_TYPES):
        not_implemented(ctx.srcfile, loc, f'`sort` on `{type_to_dewy(element)}` elements')
    if name == 'join' and not _is_string_type(element):
        user_error(
            ctx.srcfile,
            '`join` requires string elements',
            Pointer(span=value.loc, message=f'this array has `{type_to_dewy(element)}` elements'),
            hint='build the pieces as strings first, e.g. push `"{x}"` into an `array<string>`',
        )
    return hir.ArrayMethod(loc, signatures[name], value, name)


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
        and binop.left.item.name not in ctx.declarations
        and (bounds := ty.fixed_integer_bounds(binop.left.item.name)) is not None
    ):
        if name not in {'min', 'max'}:
            type_error(
                ctx.srcfile,
                f'fixed-width integer type has no property `{name}`',
                Pointer(span=binop.right.loc, message='unknown type property'),
                hint='available properties: min, max',
            )
        value = bounds[0] if name == 'min' else bounds[1]
        return hir.Integer(binop.loc, ty.IntegerLiteralType(value), '0d', value)
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
    if name in _ARRAY_METHOD_NAMES:
        value = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        if isinstance(value.type, ty.ArrayType):
            return _tcr_array_method(value, name, binop.loc, ctx=ctx)
    if name in {'keys', 'values'}:
        value = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        found_dict = _dict_value(value)
        if found_dict is not None:
            # fresh values, never the entry arrays themselves (which hold tombstones)
            dictionary, key_type, value_type = found_dict
            if value_type is None and name == 'keys':
                user_error(
                    ctx.srcfile,
                    'sets have no keys',
                    Pointer(span=binop.right.loc, message='use `.values` for the members as an array'),
                )
            view_type: ty.Type = (
                ty.set_type(key_type) if name == 'keys'
                else ty.ArrayType(value_type if value_type is not None else key_type, None)
            )
            return hir.DictView(binop.loc, view_type, dictionary, name)
    if name in {'get', 'pop', 'clear', 'add'}:
        value = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        found_dict = _dict_value(value)
        dict_methods = {'get', 'pop', 'clear'}
        set_methods = {'add', 'pop', 'clear'}
        if found_dict is not None and name in (set_methods if found_dict[2] is None else dict_methods):
            dictionary, key_type, value_type = found_dict
            if name == 'get':
                assert value_type is not None
                signature = ty.FunctionType(
                    [ty.PosOrKwArg('key', key_type), ty.PosOrKwArg('default', value_type, required=False)],
                    [], None, ty.optional(value_type),
                )
            elif name == 'pop' and value_type is not None:
                # `default` is name-only: with it the key need not be proven present
                signature = ty.FunctionType(
                    [ty.PosOrKwArg('key', key_type)],
                    [ty.PosOrKwArg('default', value_type, required=False)],
                    None,
                    value_type,
                )
            elif name == 'pop':
                # a set's pop removes a proven member and yields it; with the
                # name-only `default` (any value, e.g. `none`) no proof is needed
                signature = ty.FunctionType(
                    [ty.PosOrKwArg('key', key_type)],
                    [ty.PosOrKwArg('default', ty.optional(key_type), required=False)],
                    None,
                    key_type,
                )
            elif name == 'add':
                signature = ty.FunctionType([ty.PosOrKwArg('key', key_type)], [], None, ty.VOID_TYPE)
            else:
                signature = ty.FunctionType([], [], None, ty.VOID_TYPE)
            if name != 'get':
                root = _member_root_binding(dictionary, ctx=ctx)
                if (reason := _read_only_reason(root)) is not None:
                    user_error(
                        ctx.srcfile,
                        'cannot mutate a const dictionary',
                        Pointer(span=binop.left.loc, message=f'`{root.name}` {reason}'),
                    )
            return hir.DictMethod(binop.loc, signature, dictionary, name)
    if name == 'length':
        value = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        found_dict = _dict_value(value)
        if found_dict is not None:
            # the live entry count (removed entries stay as tombstones)
            return hir.MemberAccess(binop.loc, 'int64', found_dict[0], 'live')
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
    if isinstance(value.type, ty.NamedType):
        value = replace(value, type=ty.unfold(value.type))
    if isinstance(value.type, ty.TypeOr) and source_place is None:
        forwarding = _forwarding_member_access(value, name, binop, ctx=ctx)
        if forwarding is not None:
            return forwarding
    if _is_string_type(value.type) and name in _STRING_METHODS:
        return _string_method(value, name, binop, ctx=ctx)
    if isinstance(ty.unfold(ty.strip_refinement(value.type)), ty.MetaType):
        return _metatype_member(value, name, binop, ctx=ctx)
    if isinstance(value, hir.TypeValue) and isinstance(ty.unfold(value.value), ty.ObjectType):
        return _type_name_member(value, name, binop, ctx=ctx)
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
    if field is None and name == 'typename' and value.type.method(name) is None:
        return _typename(value, binop.loc, ctx=ctx)
    if field is None:
        method = value.type.method(name)
        if method is not None and method.binding_id is None:
            _declare_pending_methods(ctx=ctx, for_type=value.type)
        if method is not None and method.binding_id is not None:
            function_binding = ctx.binding_registry.by_id[method.binding_id]
            assert isinstance(function_binding.type, ty.FunctionType)
            function = hir.ExpressedIdentifier(binop.right.loc, function_binding.type, function_binding.name, binding_id=function_binding.id)
            if method.static:
                return hir.BoundMethod(binop.loc, function_binding.type, function, None)   # needs no receiver; still only ever called
            bound_type = replace(function_binding.type, pos_or_kw=function_binding.type.pos_or_kw[1:])
            return hir.BoundMethod(binop.loc, bound_type, function, value)
        user_error(
            ctx.srcfile,
            f'unknown object field `{name}`',
            Pointer(span=binop.right.loc, message='this field is not present'),
            hint=f'available fields: {", ".join(item.name for item in value.type.fields) or "(none)"}',
        )
    access = hir.MemberAccess(binop.loc, field.type, value, name, field.mutable)
    if isinstance(field.type, ty.TypeOr):
        # a union field narrowed by an earlier `is?` on this route reads as
        # the narrowed member (the route's refinement, dropped on assignment)
        route_id = sb.array_route_id(access, ctx.binding_registry)
        refined = ctx.refinements.get(route_id) if route_id is not None else None
        if refined is not None:
            access = replace(access, type=ty.unfold(refined))
    if source_place is None:
        return access
    if not field.mutable:
        user_error(
            ctx.srcfile,
            f'cannot take the place of const object field `{name}`',
            Pointer(span=binop.loc, message='this field is const'),
        )
    return hir.Place(binop.loc, field.type, access)


def _static_method(object_type: ty.ObjectType, name: str, *, ctx: Context) -> sb.Binding | None:
    """The hidden function of a static method of the type (declared now if pending), else None."""
    method = object_type.method(name)
    if method is None:
        return None
    if method.binding_id is None:
        _declare_pending_methods(ctx=ctx, for_type=object_type)
        if method.binding_id is None and method.owner is not None:
            owner = ctx.binding_scopes.get(method.owner)
            owner_type = owner.type_value if owner is not None else None
            if isinstance(owner_type, ty.ObjectType):
                _declare_pending_methods(ctx=ctx, for_type=owner_type)
    if method.binding_id is None or not method.static:
        return None
    return ctx.binding_registry.by_id[method.binding_id]


def _type_name_member(value: hir.TypeValue, name: str, binop: p0.BinOp, *, ctx: Context) -> hir.AST:
    """`Whitespace.eat`: a static method off the type's name; `Whitespace.typename` its name."""
    object_type = ty.unfold(value.value)
    assert isinstance(object_type, ty.ObjectType)
    if name == 'typename':
        text = object_type.brand if ty.user_branded(object_type) and object_type.brand is not None else type_to_dewy(object_type)
        return hir.String(binop.loc, ty.StringLiteralType(text), text)
    function_binding = _static_method(object_type, name, ctx=ctx)
    if function_binding is not None:
        assert isinstance(function_binding.type, ty.FunctionType)
        function = hir.ExpressedIdentifier(binop.right.loc, function_binding.type, function_binding.name, binding_id=function_binding.id)
        return hir.BoundMethod(binop.loc, function_binding.type, function, None)
    spelled = value.name or type_to_dewy(object_type)
    if object_type.method(name) is not None:
        type_error(
            ctx.srcfile,
            f'`{name}` needs an instance',
            Pointer(span=binop.right.loc, message=f'it reads a field of `{spelled}` (directly or through a method that does)'),
            hint=f'call it on a value: `{spelled}(…).{name}`',
        )
    if object_type.field(name) is not None:
        type_error(
            ctx.srcfile,
            f'`{name}` is a field of `{spelled}`',
            Pointer(span=binop.right.loc, message='a type has no field values; a value of it does'),
        )
    type_error(
        ctx.srcfile,
        f'`{spelled}` has no member `{name}`',
        Pointer(span=binop.right.loc, message='not a method or field of the type'),
    )


def _family_signature(family: ty.ObjectType, name: str, *, ctx: Context) -> ty.FunctionType | None:
    """The signature a family declares for `name`: a static method's, or a function-typed slot's."""
    function_binding = _static_method(family, name, ctx=ctx)
    if function_binding is not None and isinstance(function_binding.type, ty.FunctionType):
        return function_binding.type
    slot = family.field(name)
    if slot is not None and isinstance(slot.type, ty.FunctionType):
        return slot.type
    return None


def _brand_dispatcher(family: ty.ObjectType, name: str, loc: Span, *, ctx: Context) -> sb.Binding:
    """The hidden function `Family__dispatch__name(kind args…)` calling the static
    method `name` of whichever type under the family `kind` names — synthesized
    as Dewy: a `match` over the family's concrete types, each arm a static call."""
    assert family.brand is not None
    key = f'dispatch:{family.brand}:{name}'
    existing = ctx.object_strings.get(key)
    if existing is not None:
        return existing
    module_ctx = ctx.module if ctx.module is not None else ctx
    signature = _family_signature(family, name, ctx=ctx)
    if signature is None:
        type_error(
            ctx.srcfile,
            f'`{family.brand}` declares no `{name}` for its types',
            Pointer(span=loc, message=f'dispatching `{name}` through a `type<{family.brand}>` needs a static method or a function-typed slot on `{family.brand}`'),
        )
    brands = sorted(_concrete_brands_under(family.brand))
    missing = [brand for brand in brands if _static_method(ty.USER_BRAND_TYPES[brand], name, ctx=ctx) is None and not _slot_filled(ty.USER_BRAND_TYPES[brand], name)]
    if missing:
        type_error(
            ctx.srcfile,
            f'`{missing[0]}` has no static `{name}`',
            Pointer(span=loc, message=f'every type under `{family.brand}` needs one to dispatch `{name}` through a type value'),
        )
    params = ' '.join(f'{p.name or f"__dewy_p{i}"}:{type_to_dewy(p.type)}' for i, p in enumerate(signature.pos_or_kw))
    args = ' '.join(p.name or f'__dewy_p{i}' for i, p in enumerate(signature.pos_or_kw))
    result = f':>{type_to_dewy(signature.ret)}' if signature.ret not in (ty.VOID_TYPE, ty.INFERRED_TYPE) else ''
    arms = '\n'.join(f'    <{brand}> => return {brand}.{name}({args})' for brand in brands)
    text = f'(__dewy_kind:type<{family.brand}> {params}){result} => {{ match __dewy_kind {{\n{arms}\n}} }}'
    parsed = p0.parse(SrcFile(None, ' ' * loc.start + text + '\n'))
    literal = parsed.inner[0]
    assert isinstance(literal, p0.BinOp)
    ctx.synthesized.append(literal)
    binding = _hoist_hidden_function(f'{family.brand}__dispatch__{name}', literal, ctx=module_ctx)
    ctx.object_strings[key] = binding
    return binding


def _brand_constructor(family: ty.ObjectType, loc: Span, *, ctx: Context) -> sb.Binding:
    """The hidden function `Family__construct(kind fields…)` constructing whichever
    type under the family `kind` names, with the family's own required fields
    (a function-typed slot is the child's; a child's extra fields default)."""
    assert family.brand is not None
    key = f'construct:{family.brand}'
    existing = ctx.object_strings.get(key)
    if existing is not None:
        return existing
    module_ctx = ctx.module if ctx.module is not None else ctx
    given = [f for f in family.fields if f.default is None and not isinstance(f.type, ty.FunctionType)]
    brands = sorted(_concrete_brands_under(family.brand))
    for brand in brands:
        child = ty.USER_BRAND_TYPES[brand]
        extra = [f.name for f in child.fields if f.default is None and family.field(f.name) is None and not isinstance(f.type, ty.FunctionType)]
        if extra:
            type_error(
                ctx.srcfile,
                f'`{brand}` cannot be constructed through a `type<{family.brand}>` value',
                Pointer(span=loc, message=f'its field `{extra[0]}` has no default, and only `{family.brand}`\'s fields are given here'),
            )
        unfilled = [f.name for f in child.fields if f.default is None and isinstance(f.type, ty.FunctionType)]
        if unfilled:
            type_error(
                ctx.srcfile,
                f'`{brand}` leaves the slot `{unfilled[0]}` unfilled',
                Pointer(span=loc, message=f'every type constructed through a `type<{family.brand}>` value fills its function-typed slots with a method'),
            )
    params = ' '.join(f'{f.name}:{type_to_dewy(f.type)}' for f in given)
    args = ' '.join(f'{f.name}={f.name}' for f in given)
    arms = '\n'.join(f'    <{brand}> => return {brand}({args})' for brand in brands)
    text = f'(__dewy_kind:type<{family.brand}> {params}):>{family.brand} => {{ match __dewy_kind {{\n{arms}\n}} }}'
    parsed = p0.parse(SrcFile(None, ' ' * loc.start + text + '\n'))
    literal = parsed.inner[0]
    assert isinstance(literal, p0.BinOp)
    ctx.synthesized.append(literal)
    binding = _hoist_hidden_function(f'{family.brand}__construct', literal, ctx=module_ctx)
    ctx.object_strings[key] = binding
    return binding


def _slot_filled(object_type: ty.ObjectType, name: str) -> bool:
    """Whether a function-typed slot has a default (a child's method became its value)."""
    slot = object_type.field(name)
    return slot is not None and isinstance(slot.type, ty.FunctionType) and slot.default is not None


def _metatype_member(value: hir.AST, name: str, binop: p0.BinOp, *, ctx: Context) -> hir.AST:
    """A member of a `type<Family>` value: `typename`, or a static method dispatched by the brand."""
    if name == 'typename':
        return _typename(value, binop.loc, ctx=ctx)
    metatype = ty.unfold(ty.strip_refinement(value.type))
    assert isinstance(metatype, ty.MetaType)
    if _family_signature(metatype.family, name, ctx=ctx) is not None:
        dispatcher = _brand_dispatcher(metatype.family, name, binop.loc, ctx=ctx)
        assert isinstance(dispatcher.type, ty.FunctionType)
        function = hir.ExpressedIdentifier(binop.right.loc, dispatcher.type, dispatcher.name, binding_id=dispatcher.id)
        bound_type = replace(dispatcher.type, pos_or_kw=dispatcher.type.pos_or_kw[1:])
        return hir.BoundMethod(binop.loc, bound_type, function, value)   # the type value is the first argument
    type_error(
        ctx.srcfile,
        f'a type value has no member `{name}`',
        Pointer(span=binop.right.loc, message=f'`{type_to_dewy(metatype)}` names a type, not a value of it'),
        hint='`typename` gives its name; a static method or a function-typed slot declared on the family dispatches',
    )


def _forwarding_member_access(value: hir.AST, name: str, binop: p0.BinOp, *, ctx: Context) -> hir.AST | None:
    """Member access on a union receiver `V… | X…` (`X…` the exception
    alternatives, possibly none). Every ordinary alternative must have the
    member; the result is `R… | X…`: the member read from whichever ordinary
    alternative is live, an exception alternative forwarded unchanged (see the
    errors reference). With no exceptions this is plain common-member access."""
    assert isinstance(value.type, ty.TypeOr)
    members = list(value.type.items)
    exceptions = [m for m in members if ctx.type_system.is_subtype(m, ty.EXCEPTION_TYPE)]
    ordinary = [m for m in members if m not in exceptions]
    if not ordinary:
        return None
    if not all(isinstance(ty.unfold(m), ty.ObjectType) for m in ordinary):
        return None  # strings, arrays, …: the ordinary error paths explain
    results: list[ty.TypeExpr] = []
    for member in ordinary:
        unfolded = ty.unfold(member)
        field = unfolded.field(name) if isinstance(unfolded, ty.ObjectType) else None
        if field is None:
            type_error(
                ctx.srcfile,
                f'member access requires every ordinary alternative to have `{name}`',
                Pointer(span=binop.right.loc, message=f'`{type_to_dewy(member)}` has no field `{name}`'),
                Pointer(span=value.loc, message=f'this has type `{type_to_dewy(value.type)}`; only its exception alternatives forward'),
                hint='narrow the value with `is?` first, or give every ordinary alternative the field',
            )
        results.append(field.type)
    binding = ctx.binding_registry.allocate(binop, f'__dewy_forward_{ctx.binding_registry.next_id}', 'value', binop.loc)
    binding.type = value.type
    return hir.ForwardingAccess(
        binop.loc,
        ty.union(*results, *exceptions),
        value,
        name,
        binding.name,
        binding.id,
        ty.union(*exceptions) if exceptions else ty.BOTTOM_TYPE,
    )


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

    if isinstance(expected, ty.RefinedType):
        expected = expected.base   # `array<uint64 length >? 0>`: the literal is proven against the refinement afterwards
    expected_array = expected if isinstance(expected, ty.ArrayType) else None
    if expected_array is None and isinstance(expected, ty.TypeOr):
        # A literal checked against a union targets the union's unique
        # array member, if there is exactly one.
        candidates = [item for item in expected.items if isinstance(item, ty.ArrayType)]
        if len(candidates) == 1:
            expected_array = candidates[0]
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
            hint=_ELEMENT_TYPE_HINT,
        )

    checked_items: list[hir.AST] = []
    for item in items:
        require_valued(item.type, ctx.srcfile, item.loc, 'array element')
        checked_items.append(check_against(item, element_type, ctx=ctx))
    array_type = ty.ArrayType(element_type, len(checked_items))
    return hir.ArrayLiteral(block.loc, array_type, checked_items)


def _tcr_spread_array_literal(
    block: p0.Block,
    *,
    expected: ty.Type | None,
    ctx: Context,
) -> hir.ArrayLiteral:
    """`[xs... 0 ys...]`: elements of the spread arrays (a set spreads its
    members) in order with the written elements. The length is exact when
    every spread operand's length is."""
    expected_array = expected if isinstance(expected, ty.ArrayType) else None
    items: list[hir.AST] = []
    plain: list[hir.AST] = []
    for item in block.inner:
        operand = _spread_operand(item)
        if operand is None:
            value = typecheck_and_resolve_inner(item, ctx=ctx, expected=expected_array.element if expected_array is not None else None)
            require_valued(value.type, ctx.srcfile, value.loc, 'array element')
            items.append(value)
            plain.append(value)
            continue
        source = _spread_source(operand, ctx=ctx)
        element = ty.set_element(source.type) if isinstance(source.type, ty.ObjectType) else None
        if element is not None:
            source = hir.DictView(item.loc, ty.ArrayType(element, None), source, 'values')
        if not isinstance(source.type, ty.ArrayType):
            user_error(
                ctx.srcfile,
                'array spread requires an array or set',
                Pointer(span=source.loc, message=f'this has type `{type_to_dewy(source.type)}`'),
                hint='dictionaries spread into dictionary literals; objects into object literals',
            )
        items.append(hir.Spread(item.loc, source.type, source))
    if expected_array is not None:
        element_type: ty.TypeExpr = expected_array.element
    else:
        # a spread fixes the element type (written elements adapt to it);
        # with no spread the written elements infer as in a plain literal
        first = next(item for item in items if isinstance(item, hir.Spread))
        assert isinstance(first.type, ty.ArrayType)
        element_type = first.type.element
        if isinstance(element_type, ty.IntegerLiteralType | ty.StringLiteralType):
            element_type = _tcr_array_literal(block, plain, expected=None, ctx=ctx).type.element if plain else element_type
    checked: list[hir.AST] = []
    length: int | None = 0
    for item in items:
        if isinstance(item, hir.Spread):
            assert isinstance(item.type, ty.ArrayType)
            if not ctx.type_system.is_subtype(item.type.element, element_type):
                type_error(
                    ctx.srcfile,
                    'array elements are not homogeneous',
                    Pointer(span=item.loc, message=f'this spreads `{type_to_dewy(item.type.element)}` elements into an array of `{type_to_dewy(element_type)}`'),
                )
            checked.append(item)
            length = length + item.type.length if length is not None and item.type.length is not None else None
        else:
            checked.append(check_against(item, element_type, ctx=ctx))
            length = length + 1 if length is not None else None
    if expected_array is not None and expected_array.length is not None and expected_array.length != length:
        type_error(
            ctx.srcfile,
            'array length mismatch',
            Pointer(span=block.loc, message=f'expected length {expected_array.length}, got {length if length is not None else "a runtime length"}'),
        )
    return hir.ArrayLiteral(block.loc, ty.ArrayType(element_type, length), checked)


_ELEMENT_TYPE_HINT = (
    'container elements need a fixed runtime width: a sized integer (`int64`, `uint8`, …), `bool`, '
    '`string`, an object type, or a union of those with `none`'
)


def _word_element_type(type_: ty.Type) -> ty.Type:
    """The element type a container annotation names, with the abstract
    integers taking the 64-bit word representation — `array<int>`,
    `dict<string int | none>`, `set<uint>` — the way `int` in a
    signature does (the hidden-width selection pass is still ahead)."""
    if type_ == 'int':
        return 'int64'
    if type_ == 'uint':
        return 'uint64'
    if isinstance(type_, ty.TypeOr):
        items = [_word_element_type(item) for item in type_.items]
        return ty.TypeOr(items) if items != type_.items else type_
    return type_


def _supported_array_element_type(type_: ty.Type) -> bool:
    return (
        isinstance(
            type_,
            (
                ty.ArrayType,
                ty.FunctionType,
                ty.ObjectType,
                ty.StringLiteralType,
                ty.StringType,
                ty.TypeVariable,  # concrete at instantiation
                ty.NamedType,
                ty.MetaType,      # a type value: a word
            ),
        )
        or isinstance(type_, str)
        and (
            type_ in ty.FIXED_INTEGER_TYPES
            or type_ in {'bool', 'string', 'grapheme', 'char'}
        )
        or ty.string_valued(type_)   # a union of string literals: string handles
        or _optional_container_element(type_)
        or _union_container_element(type_)
    )


def _union_container_element(type_: ty.Type) -> bool:
    """A general union of words, strings, `none`, and plain objects
    (`Number | Name | Punct`): containers hold such elements as one-word
    pointers to tagged cells they own."""
    if isinstance(type_, str):
        return False
    members = ty.runtime_union_members(ty.strip_refinement(type_))
    if members is None:
        return False
    for member in members:
        unfolded = ty.unfold(member)
        if member == 'none' or member == 'bool' or ty.fixed_integer_layout(member) is not None or ty.string_valued(member):
            continue
        if isinstance(unfolded, ty.ObjectType) and (unfolded.brand is None or ty.user_branded(unfolded)):
            continue
        return False
    return True


def _optional_container_element(type_: ty.Type) -> bool:
    """`T | none` with a word or string payload: containers hold such
    elements as one-word cells."""
    if isinstance(type_, str):
        return False
    payload = ty.optional_payload(ty.strip_refinement(type_))
    if payload is None:
        return False
    return (
        payload == 'bool'
        or ty.fixed_integer_layout(payload) is not None
        or ty.string_valued(payload)
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
        outer = ctx
        ctx = replace(
            ctx,
            declarations=ctx.declarations.new_child(),
            binding_scopes=ctx.binding_scopes.new_child(),
            module_namespaces=ctx.module_namespaces.new_child(),
            label_scopes=(*ctx.label_scopes, _collect_label_scope(block, ctx=ctx)),
        )
        if outer.module is None:
            # the module's root block: methods and overloads are declared in
            # this scope, and the module checker sweeps it at the end
            outer.module = ctx
            ctx.module = ctx

    if block.kind == '[]' and len(block.inner) == 1 and _loop_flow(block.inner[0]) is not None:
        return _tcr_loop_capture(block, kind='array', expected=expected, ctx=ctx)

    if block.kind == '[]':
        arrows = [item for item in block.inner if _is_top_level_arrow(item)]
        if arrows and len(arrows) != len([item for item in block.inner if _spread_operand(item) is None]):
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
        spreads = [item for item in block.inner if _spread_operand(item) is not None]
        kind = _bracket_kind([item for item in block.inner if _spread_operand(item) is None])
        if spreads and kind == 'array' and len(spreads) == len(block.inner) and not isinstance(expected, (ty.ArrayType, ty.ObjectType)):
            # `[a...]`: only the operand says whether this builds an object, a dictionary, or an array
            first = _spread_source(_spread_operand(spreads[0]), ctx=ctx)
            if isinstance(first.type, ty.ObjectType) and (first.type.brand is None or ty.user_branded(first.type)):
                kind = 'object'
            elif ty.dict_key_value(first.type) is not None:
                kind = 'dict'
        if kind == 'bidict':
            not_implemented(ctx.srcfile, block.loc, 'bidirectional dictionary literals')
        if kind == 'dict' or (not block.inner and expected is not None and ty.dict_key_value(ty.strip_refinement(expected)) is not None):
            if spreads:
                not_implemented(ctx.srcfile, spreads[0].loc, 'spreading into a dictionary literal (entries need a runtime replace-or-append)')
            return _tcr_dict_literal(block, expected=expected, ctx=ctx)
        if kind == 'object' or isinstance(ty.unfold(ty.strip_refinement(expected)) if expected is not None else None, ty.ObjectType):
            # (a recursive alias's reference unfolds to its object type for the literal)
            return _tcr_object_literal(block, expected=expected, ctx=ctx)
        if spreads:
            return _tcr_spread_array_literal(block, expected=expected, ctx=ctx)

    _collect_block_bindings(block, ctx=ctx)
    aliases = _prebind_type_aliases(block, ctx=ctx)

    # The block's leading imports run first, then its aliases resolve in
    # declaration order: the signature pre-pass below would otherwise touch
    # them in use order, and a cycle through a function type (a context whose
    # tokens' `eat` takes the context) would surface at the function alias —
    # which cannot carry a recursion — instead of at the object that can.
    leading_results: dict[int, hir.AST] = {}
    if not type_block:
        for index, item in enumerate(block.inner):
            if not (isinstance(item, p0.KeywordExpr) and item.parts and isinstance(item.parts[0], t1.Keyword) and item.parts[0].name in ('import', 'from')):
                break
            leading_results[index] = typecheck_and_resolve_inner(item, ctx=ctx, type_block=type_block)
        for binding in aliases:
            _resolve_type_alias(binding, ctx=ctx)

    deferred_functions: set[int] = set()
    if not type_block:
        seen_implicit: set[str] = set()
        for item in block.inner:
            declaration = _block_declaration_parts(item, seen_implicit, ctx=ctx)
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
            if _generic_function_parts(expression) is None:
                # (a generic's declaration is only its placeholder — bodies are
                # checked per instance — so it is checked in order, and a
                # module-level call after it finds the instantiable source)
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
    items = block.inner
    results: list[hir.AST | None] = [None] * len(items)
    for index, item in enumerate(items):
        if index in leading_results:
            results[index] = leading_results[index]   # a leading import, already run
            continue
        if _test_annotation(item) is not None:
            user_error(
                ctx.srcfile,
                '`$test` inside a block',
                Pointer(span=item.loc, message='tests are module-level function declarations'),
                hint='move the test to the top level of the module',
            )
        if id(item) in deferred_functions:
            continue
        item_expected = (
            expected.element
            if block.kind == '[]' and isinstance(expected, ty.ArrayType)
            else expected
            if expected is not None and len(items) == 1
            else None
        )
        if block.kind == '{}':
            ctx.hoisted = []   # a loop capture in this statement declares and fills its array first
        results[index] = typecheck_and_resolve_inner(
            item,
            ctx=ctx,
            type_block=type_block,
            expected=item_expected,
        )
        if block.kind == '{}' and ctx.hoisted:
            results[index] = hir.Block(item.loc, results[index].type, [*ctx.hoisted, results[index]], False)
        if block.kind == '{}':
            ctx.hoisted = None
    for index, item in enumerate(items):
        if id(item) not in deferred_functions:
            continue
        results[index] = typecheck_and_resolve_inner(item, ctx=ctx, type_block=type_block)
    for binding in aliases:
        _resolve_type_alias(binding, ctx=ctx)   # an alias nothing referred to still has to be well-formed
    checked_results: list[hir.AST] = []
    for item, result in zip(items, results, strict=True):
        if result is None:
            raise ValueError('INTERNAL ERROR: block item was not checked')
        if (
            isinstance(item, p0.Flow)
            and isinstance(result, hir.Block)
            and not result.scoped
        ):
            # A target-gated `{}` arm was already checked in this scope;
            # its items belong to this block directly.
            checked_results.extend(result.items)
        else:
            checked_results.append(result)
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


RATIONAL_TYPE_NAME = 'Rational'          # the explicit fixed-width `rational<int64>`
BIG_RATIONAL_TYPE_NAME = 'BigRational'   # the runtime representation of the abstract `rational`
_RATIONAL_BINARY_FUNCTIONS = {
    '__add__': '_rational_add',
    '__sub__': '_rational_sub',
    '__mul__': '_rational_mul',
    '__truediv__': '_rational_div',
    '__eq__': '_rational_eq',
    '__ne__': '_rational_ne',
    '__lt__': '_rational_lt',
    '__le__': '_rational_le',
    '__gt__': '_rational_gt',
    '__ge__': '_rational_ge',
}
_BIG_RATIONAL_BINARY_FUNCTIONS = {name: helper.replace('_rational_', '_bigrational_') for name, helper in _RATIONAL_BINARY_FUNCTIONS.items()}


def _rational_type(ctx: Context, loc: Span) -> ty.Type:
    """The runtime type of the abstract `rational`: the prelude's `BigRational` (big-integer parts, total arithmetic)."""
    binding = ctx.binding_scopes.get(BIG_RATIONAL_TYPE_NAME)
    if binding is None or binding.type_value is None:
        user_error(
            ctx.srcfile,
            'rationals need the prelude',
            Pointer(span=loc, message='`BigRational` from `library/bigrational.dewy` is not in scope'),
        )
    return binding.type_value


def _word_rational_type(ctx: Context, loc: Span) -> ty.Type:
    """The explicit `rational<int64>`: the prelude's `Rational` with int64 parts (runtime arithmetic may `Overflow`)."""
    binding = ctx.binding_scopes.get(RATIONAL_TYPE_NAME)
    if binding is None or binding.type_value is None:
        user_error(
            ctx.srcfile,
            'rationals need the prelude',
            Pointer(span=loc, message='`Rational` from `library/rational.dewy` is not in scope'),
        )
    return binding.type_value


def _is_word_rational(type_: ty.Type, *, ctx: Context) -> bool:
    binding = ctx.binding_scopes.get(RATIONAL_TYPE_NAME)
    return binding is not None and binding.type_value is not None and type_ == binding.type_value


def _union_object_member(type_: ty.Type) -> ty.Type:
    """The object member of `0 | [...]`; any other type is itself."""
    if isinstance(type_, ty.TypeOr):
        objects = [item for item in type_.items if isinstance(item, ty.ObjectType)]
        if len(objects) == 1:
            return objects[0]
    return type_


def _is_prelude_number(type_: ty.Type, name: str, *, ctx: Context) -> bool:
    """Whether ``type_`` is the prelude type ``name`` — the `0 | [...]` union or its nonzero object."""
    binding = ctx.binding_scopes.get(name)
    if binding is None or binding.type_value is None:
        return False
    declared = binding.type_value
    return type_ == declared or type_ == _union_object_member(declared)


def _is_nonzero_form(type_: ty.Type, name: str, *, ctx: Context) -> bool:
    """Whether ``type_`` is the nonzero object of the prelude's `0 | [...]` type ``name``."""
    binding = ctx.binding_scopes.get(name)
    if binding is None or binding.type_value is None:
        return False
    member = _union_object_member(binding.type_value)
    return member is not binding.type_value and type_ == member


def _is_big_rational(type_: ty.Type, *, ctx: Context) -> bool:
    return _is_prelude_number(type_, BIG_RATIONAL_TYPE_NAME, ctx=ctx)


BIGINT_TYPE_NAME = 'BigInt'
_BIGINT_BINARY_FUNCTIONS = {
    '__add__': '_bigint_add',
    '__sub__': '_bigint_sub',
    '__mul__': '_bigint_mul',
    '__floordiv__': '_bigint_floordiv',
    '__mod__': '_bigint_mod',
    '__eq__': '_bigint_eq',
    '__ne__': '_bigint_ne',
    '__lt__': '_bigint_lt',
    '__le__': '_bigint_le',
    '__gt__': '_bigint_gt',
    '__ge__': '_bigint_ge',
}


def _bigint_type(ctx: Context, loc: Span) -> ty.Type:
    """The prelude's `BigInt` object type, which `bigint` names."""
    binding = ctx.binding_scopes.get(BIGINT_TYPE_NAME)
    if binding is None or binding.type_value is None:
        user_error(
            ctx.srcfile,
            'big integers need the prelude',
            Pointer(span=loc, message='`BigInt` from `library/bigint.dewy` is not in scope'),
        )
    return binding.type_value


def _is_bigint(type_: ty.Type, *, ctx: Context) -> bool:
    return _is_prelude_number(type_, BIGINT_TYPE_NAME, ctx=ctx)


def _require_nonzero_divisor(arg: hir.AST, name: str, *, ctx: Context) -> None:
    """A `0 | [...]` divisor must have been narrowed to its nonzero form."""
    number, _ = _number_and_dimension(arg.type)
    if _is_prelude_number(number, name, ctx=ctx) and not _is_nonzero_form(number, name, ctx=ctx):
        type_error(
            ctx.srcfile,
            'cannot prove the divisor is nonzero',
            Pointer(span=arg.loc, message='this may be zero'),
            hint='guard the division (`if d not=? 0 { … }`), or take the divisor as `d:bigint & ~0`',
        )


def _bigint_literal(value: int, *, loc: Span, ctx: Context) -> hir.AST:
    """A big integer constant: the literal `0`, or the nonzero object from its base-2^32 limbs."""
    if value == 0:
        return hir.Integer(loc, ty.IntegerLiteralType(0), '0d', 0)
    magnitude = abs(value)
    limbs: list[int] = []
    while magnitude:
        limbs.append(magnitude & 0xFFFFFFFF)
        magnitude >>= 32
    limb_nodes = [hir.Integer(loc, 'uint64', '0d', limb) for limb in limbs]
    nonzero = ty.unfold(_union_object_member(_bigint_type(ctx, loc)))
    assert isinstance(nonzero, ty.ObjectType)
    sign = -1 if value < 0 else 1
    return hir.ObjectLiteral(loc, nonzero, [
        hir.ObjectField(loc, 'sign', hir.Integer(loc, ty.IntegerLiteralType(sign), '0d', sign)),
        hir.ObjectField(loc, 'limbs', hir.ArrayLiteral(loc, ty.ArrayType('uint64', len(limbs)), limb_nodes)),
    ])


def _to_bigint(arg: hir.AST, *, ctx: Context, nonzero: bool = False) -> hir.AST:
    """An operand as a runtime `BigInt`; integers widen, constants fold.

    With ``nonzero`` the result must be the nonzero form `bigint & ~0`: a big
    operand must already be narrowed, and an integer operand's nonzeroness is
    proven like any `int64 & ~0` argument.
    """
    if _is_bigint(arg.type, ctx=ctx):
        if nonzero:
            _require_nonzero_divisor(arg, BIGINT_TYPE_NAME, ctx=ctx)
        return arg
    constant = _constant_integer(_unwrap_parens(arg), ctx=ctx)
    if constant is not None:
        return _bigint_literal(constant, loc=arg.loc, ctx=ctx)
    if not ctx.type_system.is_subtype(arg.type, 'int'):
        type_error(
            ctx.srcfile,
            'no big-integer conversion for this operand',
            Pointer(span=arg.loc, message=f'this has type `{type_to_dewy(arg.type)}`'),
        )
    if nonzero:
        return _prelude_call('_bigint_from_int_nonzero', [_as_int64(arg, ctx=ctx)], loc=arg.loc, ctx=ctx)
    return _prelude_call('_bigint_from_int', [_as_int64(arg, ctx=ctx)], loc=arg.loc, ctx=ctx)


def _dispatch_bigint(
    fname: str,
    args: list[hir.AST],
    *,
    loc: Span,
    source_name: str,
    ctx: Context,
    expected: ty.Type | None = None,
) -> hir.AST | None:
    """Operations with a big-integer operand: the other integer operand widens.

    Integer constants beyond the 64-bit range (such as a folded `2^100`) are
    big-integer operands too, and a big-integer expected type selects this
    path for integer constants.
    """
    if BIGINT_TYPE_NAME not in ctx.binding_scopes:
        return None  # no prelude: integers stay words (µDewy-style programs)
    fixed_widths = [
        arg.type for arg in args
        if isinstance(arg.type, str) and arg.type in ty.FIXED_INTEGER_TYPES
    ]

    def oversized(arg: hir.AST) -> bool:
        # a constant beyond every word type present; a literal that fits the
        # other operand's fixed width (`x =? 18446744073709551615` on uint64) is not
        value = _constant_integer(_unwrap_parens(arg), ctx=ctx)
        if value is None:
            return False
        # any 64-bit word (signed or unsigned) is still a word literal
        candidates = [*fixed_widths, 'int64', 'uint64']
        if isinstance(expected, str) and expected in ty.FIXED_INTEGER_TYPES:
            candidates.append(expected)
        return not any(ty.integer_literal_fits(value, width) for width in candidates)

    if not any(_is_bigint(arg.type, ctx=ctx) or oversized(arg) for arg in args) and not (
        expected is not None and _is_bigint(expected, ctx=ctx)
    ):
        return None
    if fname == '__unary_sub__' and len(args) == 1:
        constant = _constant_integer(_unwrap_parens(args[0]), ctx=ctx)
        if constant is not None:
            # `-9223372036854775808` negates an oversized literal into a word
            negated = -constant
            if ty.integer_literal_fits(negated, 'int64') and not (expected is not None and _is_bigint(expected, ctx=ctx)):
                return hir.Integer(loc, ty.IntegerLiteralType(negated), '0d', negated)
            return _bigint_literal(negated, loc=loc, ctx=ctx)
        return _prelude_call('_bigint_neg', [_to_bigint(args[0], ctx=ctx)], loc=loc, ctx=ctx)
    if fname == '__truediv__':
        return None   # `big / x` is a rational: the rational dispatch builds it
    helper = _BIGINT_BINARY_FUNCTIONS.get(fname)
    if helper is None or len(args) != 2:
        type_error(
            ctx.srcfile,
            f'operator `{source_name}` is not defined for big integers',
            Pointer(span=loc, message='big integers support `+ - * // % ^`, negation, and comparisons'),
        )
    if fname in {'__floordiv__', '__mod__'} and _constant_integer(_unwrap_parens(args[1]), ctx=ctx) == 0:
        type_error(
            ctx.srcfile,
            'division by zero',
            Pointer(span=args[1].loc, message='the divisor is the constant `0`'),
        )
    constants = [_constant_integer(_unwrap_parens(arg), ctx=ctx) for arg in args]
    if all(value is not None for value in constants):
        # both constants: fold exactly, then materialize
        a, b = cast(list[int], constants)
        folded = {
            '__add__': a + b, '__sub__': a - b, '__mul__': a * b,
            '__floordiv__': a // b if b else None, '__mod__': a % b if b else None,
            '__eq__': a == b, '__ne__': a != b, '__lt__': a < b, '__le__': a <= b, '__gt__': a > b, '__ge__': a >= b,
        }[fname]
        if isinstance(folded, bool):
            return hir.Bool(loc, 'bool', folded)
        if folded is not None:
            if ty.integer_literal_fits(folded, 'int64') and not (expected is not None and _is_bigint(expected, ctx=ctx)):
                return hir.Integer(loc, ty.IntegerLiteralType(folded), '0d', folded)
            return _bigint_literal(folded, loc=loc, ctx=ctx)
    divides = fname in {'__floordiv__', '__mod__'}
    operands = [_to_bigint(arg, ctx=ctx, nonzero=divides and index == 1) for index, arg in enumerate(args)]
    return _prelude_call(helper, operands, loc=loc, ctx=ctx)


FIXED_TYPE_NAME = 'Fixed'
FIXED_SCALE = 1 << 32
_FIXED_BINARY_FUNCTIONS = {
    '__add__': '_fixed_add',
    '__sub__': '_fixed_sub',
    '__mul__': '_fixed_mul',
    '__truediv__': '_fixed_div',
    '__eq__': '_fixed_eq',
    '__ne__': '_fixed_ne',
    '__lt__': '_fixed_lt',
    '__le__': '_fixed_le',
    '__gt__': '_fixed_gt',
    '__ge__': '_fixed_ge',
}


def _fixed_type(ctx: Context, loc: Span) -> ty.Type:
    """The prelude's `Fixed` object type, which `fixed` names."""
    binding = ctx.binding_scopes.get(FIXED_TYPE_NAME)
    if binding is None or binding.type_value is None:
        user_error(
            ctx.srcfile,
            'fixed-point numbers need the prelude',
            Pointer(span=loc, message='`Fixed` from `library/fixed.dewy` is not in scope'),
        )
    return binding.type_value


def _is_fixed(type_: ty.Type, *, ctx: Context) -> bool:
    binding = ctx.binding_scopes.get(FIXED_TYPE_NAME)
    return (
        binding is not None
        and binding.type_value is not None
        and type_ == binding.type_value
    )


def _is_rational(type_: ty.Type, *, ctx: Context) -> bool:
    """Either runtime rational representation."""
    return _is_big_rational(type_, ctx=ctx) or _is_word_rational(type_, ctx=ctx)


def _prelude_call(name: str, args: list[hir.AST], *, loc: Span, ctx: Context) -> hir.FunctionCall:
    """Call a prelude function by name with already-checked arguments."""
    if name not in ctx.declarations:
        user_error(
            ctx.srcfile,
            'rationals need the prelude',
            Pointer(span=loc, message=f'`{name}` from `library/rational.dewy` is not in scope'),
        )
    func = tcr_identifier(t1.Identifier(loc, name), ctx=ctx)
    if not isinstance(func.type, ty.FunctionType):
        raise ValueError(f'INTERNAL ERROR: prelude helper `{name}` is not a plain function')
    checked = [
        check_against(arg, param.type, ctx=ctx)
        for arg, param in zip(args, func.type.pos_or_kw, strict=True)
    ]
    return hir.FunctionCall(loc, func.type.ret, func, checked, {})


def _to_rational(arg: hir.AST, *, ctx: Context) -> hir.AST:
    """Promote an integer operand to a rational; rationals pass through."""
    if _is_rational(arg.type, ctx=ctx):
        return arg
    if not ctx.type_system.is_subtype(arg.type, 'int'):
        type_error(
            ctx.srcfile,
            'no rational conversion for this operand',
            Pointer(span=arg.loc, message=f'this has type `{type_to_dewy(arg.type)}`'),
        )
    return _prelude_call('_rational_from_int', [arg], loc=arg.loc, ctx=ctx)


def _number_and_dimension(type_: ty.Type) -> tuple[ty.Type, ty.DimensionType]:
    if isinstance(type_, ty.QuantityType):
        return type_.number, type_.dimension
    return type_, ty.dimension()


def _with_dimension(number: ty.Type, dimension: ty.DimensionType) -> ty.Type:
    return number if not dimension.powers else ty.QuantityType(number, dimension)


def _with_dimension_result(declared: ty.Type, number: ty.Type, dimension: ty.DimensionType) -> ty.Type:
    """A prelude operation's result with the dimension: `Rational | Overflow` keeps its error member."""
    if declared == number:
        return _with_dimension(number, dimension)   # the `0 | [...]` rational is one number type
    if isinstance(declared, ty.TypeOr):
        return ty.union(*[
            _with_dimension(number, dimension) if ty.unfold(member) == number else member
            for member in declared.items
        ])
    return _with_dimension(number, dimension)


def _zero_test_on_field(fname: str, args: list[hir.AST], field: str, *, loc: Span, source_name: str, ctx: Context) -> hir.AST | None:
    """`q =? 0` / `q not=? 0` on a rational (or fixed) is a test of its normalized numerator (raw part).

    Spelling it as the field comparison lets the guard record a route fact,
    which is what a division by `q` needs.
    """
    if fname not in ('__eq__', '__ne__') or len(args) != 2:
        return None
    for value, other in ((args[0], args[1]), (args[1], args[0])):
        if _constant_rational(other, ctx=ctx) != 0:
            continue
        value_type = ty.unfold(_number_and_dimension(value.type)[0])
        if not (isinstance(value_type, ty.ObjectType) and value_type.field(field) is not None):
            continue
        member = hir.MemberAccess(value.loc, 'int64', _strip_dimension(value), field, True)
        zero = hir.Integer(other.loc, ty.IntegerLiteralType(0), '0d', 0)
        return _dispatch_builtin(fname, [member, zero], loc=loc, op_loc=loc, source_name=source_name, ctx=ctx)
    return None


def _is_compile_time_rational(type_: ty.Type) -> bool:
    number, _ = _number_and_dimension(type_)
    return isinstance(number, ty.RationalLiteralType)


def _constant_rational(node: hir.AST, *, ctx: Context) -> Fraction | None:
    """The exact value of a compile-time number (integer or rational, possibly dimensioned)."""
    node = _unwrap_parens(node)
    number, _ = _number_and_dimension(node.type)
    if isinstance(number, ty.RationalLiteralType):
        return Fraction(number.numerator, number.denominator)
    if isinstance(number, ty.IntegerLiteralType):
        return Fraction(number.value)
    if isinstance(node, hir.RationalConstant):
        return Fraction(node.numerator, node.denominator)
    value = _constant_integer(node, ctx=ctx)
    return None if value is None else Fraction(value)


def _rational_constant(value: Fraction, dimension: ty.DimensionType, *, loc: Span) -> hir.AST:
    """A compile-time number: integer-scaled quantities keep the integer singleton form."""
    if value.denominator == 1 and dimension.powers:
        return hir.Integer(
            loc,
            ty.QuantityType(ty.IntegerLiteralType(value.numerator), dimension),
            '0d',
            value.numerator,
        )
    literal = ty.RationalLiteralType(value.numerator, value.denominator)
    return hir.RationalConstant(loc, _with_dimension(literal, dimension), value.numerator, value.denominator)


def _rational_literal(numerator: int, denominator: int, *, loc: Span, ctx: Context) -> hir.AST:
    """A normalized compile-time rational from integer parts."""
    return _rational_constant(Fraction(numerator, denominator), ty.dimension(), loc=loc)


def _materialize_rational(node: hir.AST, *, ctx: Context, word: bool = False) -> hir.AST:
    """A compile-time rational (possibly dimensioned) as a runtime rational value.

    The abstract `rational` is a `BigRational` (exact limbs, any size); with
    ``word`` it is the explicit `rational<int64>` (`Rational`), which the
    constant must fit.
    """
    value = _constant_rational(node, ctx=ctx)
    if value is None:
        raise ValueError('INTERNAL ERROR: compile-time rational without a value')
    _, dimension = _number_and_dimension(node.type)
    if word:
        for part in (value.numerator, value.denominator):
            if not ty.integer_literal_fits(part, 'int64'):
                type_error(
                    ctx.srcfile,
                    'rational constant does not fit `rational<int64>`',
                    Pointer(span=node.loc, message=f'`{value}` has a part outside int64'),
                    hint='use the abstract `rational` (big-integer parts) here',
                )
        parts = [
            hir.Integer(node.loc, ty.IntegerLiteralType(part), '0d', part)
            for part in (value.numerator, value.denominator)
        ]
        call = _prelude_call('_rational_make', parts, loc=node.loc, ctx=ctx)
        return replace(call, type=_with_dimension(call.type, dimension))
    if value == 0:
        # the abstract rational is `0 | [...]`: zero is the union's own literal
        # member, typed as the union so a `let` declares the union
        return hir.Integer(node.loc, _with_dimension(_rational_type(ctx, node.loc), dimension), '0d', 0)
    parts = [_bigint_literal(part, loc=node.loc, ctx=ctx) for part in (value.numerator, value.denominator)]
    call = _prelude_call('_bigrational_coprime', parts, loc=node.loc, ctx=ctx)   # a Fraction is normalized
    return replace(call, type=_with_dimension(call.type, dimension))


def _strip_dimension(node: hir.AST) -> hir.AST:
    """The same value typed by its numeric representation alone."""
    if isinstance(node.type, ty.QuantityType):
        return replace(node, type=node.type.number)
    return node


def _to_rational(arg: hir.AST, *, ctx: Context, word: bool = False) -> hir.AST:
    """An operand as a runtime rational (dimension stripped); integers promote.

    ``word`` selects the explicit `rational<int64>` representation; otherwise a
    `Rational` operand widens to the abstract `BigRational`.
    """
    if _is_compile_time_rational(arg.type):
        return _strip_dimension(_materialize_rational(arg, ctx=ctx, word=word))
    number, _ = _number_and_dimension(arg.type)
    if _is_big_rational(number, ctx=ctx):
        if word:
            type_error(
                ctx.srcfile,
                'a `rational` operand in fixed-width rational arithmetic',
                Pointer(span=arg.loc, message='this is an abstract rational (big-integer parts)'),
                hint='the other operand is a `rational<int64>`; keep both abstract, or convert explicitly',
            )
        return _strip_dimension(arg)
    if _is_word_rational(number, ctx=ctx):
        if word:
            return _strip_dimension(arg)
        return _prelude_call('_bigrational_from_rational', [_strip_dimension(arg)], loc=arg.loc, ctx=ctx)
    if _is_bigint(number, ctx=ctx) and not word:
        return _prelude_call('_bigrational_from_bigint', [_strip_dimension(arg)], loc=arg.loc, ctx=ctx)
    if not ctx.type_system.is_subtype(number, 'int'):
        type_error(
            ctx.srcfile,
            'no rational conversion for this operand',
            Pointer(span=arg.loc, message=f'this has type `{type_to_dewy(arg.type)}`'),
        )
    helper = '_rational_from_int' if word else '_bigrational_from_int'
    return _prelude_call(helper, [_as_int64(_strip_dimension(arg), ctx=ctx)], loc=arg.loc, ctx=ctx)


def _fixed_constant(value: Fraction, *, loc: Span, ctx: Context) -> hir.AST:
    """A compile-time number as a fixed value (raw Q32.32, rounded to nearest)."""
    magnitude = (2 * abs(value.numerator) * FIXED_SCALE + value.denominator) // (2 * value.denominator)
    raw = -magnitude if value < 0 else magnitude
    if not -(1 << 63) <= raw < (1 << 63):
        type_error(
            ctx.srcfile,
            'value is outside the fixed-point range',
            Pointer(span=loc, message=f'`{value}` does not fit Q32.32'),
        )
    # an object literal, not a `_fixed_from_raw` call: the constant `raw` is
    # then a compile-time fact (a nonzero divisor proves itself)
    fixed_type = ty.unfold(_fixed_type(ctx, loc))
    assert isinstance(fixed_type, ty.ObjectType)
    field = hir.ObjectField(loc, 'raw', hir.Integer(loc, ty.IntegerLiteralType(raw), '0d', raw))
    return hir.ObjectLiteral(loc, fixed_type, [field])


def _to_fixed(arg: hir.AST, *, ctx: Context) -> hir.AST:
    """An operand as a runtime `Fixed` (dimension stripped); constants and rationals convert."""
    number, _ = _number_and_dimension(arg.type)
    if _is_fixed(number, ctx=ctx):
        return _strip_dimension(arg)
    constant = _constant_rational(arg, ctx=ctx)
    if constant is not None:
        return _fixed_constant(constant, loc=arg.loc, ctx=ctx)
    if _is_word_rational(number, ctx=ctx):
        return _prelude_call('_fixed_from_rational', [_strip_dimension(arg)], loc=arg.loc, ctx=ctx)
    if _is_big_rational(number, ctx=ctx):
        type_error(
            ctx.srcfile,
            'a runtime `rational` in fixed-point arithmetic',
            Pointer(span=arg.loc, message='its big-integer parts may not fit the fixed representation'),
            hint='convert it first: `let f:fixed = q` yields `fixed | Overflow`, which you handle; or keep the arithmetic rational',
        )
    if not ctx.type_system.is_subtype(number, 'int'):
        type_error(
            ctx.srcfile,
            'no fixed-point conversion for this operand',
            Pointer(span=arg.loc, message=f'this has type `{type_to_dewy(arg.type)}`'),
        )
    return _prelude_call('_fixed_from_int', [_as_int64(_strip_dimension(arg), ctx=ctx)], loc=arg.loc, ctx=ctx)


_COMPARISON_DUNDERS = {'__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__'}
_SAME_DIMENSION_DUNDERS = {'__add__', '__sub__', *_COMPARISON_DUNDERS}


def _fold_constant_operation(fname: str, values: list[Fraction]) -> Fraction | bool | None:
    a = values[0]
    if fname == '__unary_sub__':
        return -a
    b = values[1]
    match fname:
        case '__add__': return a + b
        case '__sub__': return a - b
        case '__mul__': return a * b
        case '__truediv__': return a / b
        case '__eq__': return a == b
        case '__ne__': return a != b
        case '__lt__': return a < b
        case '__le__': return a <= b
        case '__gt__': return a > b
        case '__ge__': return a >= b
    return None


def _result_dimension(fname: str, dimensions: list[ty.DimensionType], *, loc: Span, ctx: Context) -> ty.DimensionType:
    if fname == '__unary_sub__':
        return dimensions[0]
    left, right = dimensions
    if fname == '__mul__':
        return ty.multiply_dimensions(left, right)
    if fname == '__truediv__':
        return ty.divide_dimensions(left, right)
    if fname in _SAME_DIMENSION_DUNDERS:
        if left != right:
            type_error(
                ctx.srcfile,
                'incompatible physical dimensions',
                Pointer(
                    span=loc,
                    message=f'`{type_to_dewy(left)}` and `{type_to_dewy(right)}` cannot be combined',
                ),
                hint='only quantities of the same dimension add, subtract, or compare',
            )
        return ty.dimension() if fname in _COMPARISON_DUNDERS else left
    return ty.dimension()


def _dispatch_rational(
    fname: str,
    args: list[hir.AST],
    *,
    loc: Span,
    source_name: str,
    ctx: Context,
) -> hir.AST | None:
    """Route `/`, rational operands, and dimensioned operands.

    Compile-time operands (integer and rational singletons, including unit
    scales) fold exactly; runtime rationals call the prelude; dimensions
    combine in the result type. Returns None when the ordinary builtin
    dispatch should handle the operation.
    """
    parts = [_number_and_dimension(arg.type) for arg in args]
    numbers = [number for number, _ in parts]
    dimensions = [dimension for _, dimension in parts]
    involves_rational = any(
        _is_rational(number, ctx=ctx) or isinstance(number, ty.RationalLiteralType)
        for number in numbers
    )
    involves_fixed = any(_is_fixed(number, ctx=ctx) for number in numbers)
    involves_quantity = any(isinstance(arg.type, ty.QuantityType) for arg in args)
    is_division = fname == '__truediv__' and len(args) == 2
    if not (involves_rational or involves_fixed or involves_quantity or is_division):
        return None
    if involves_fixed:
        return _dispatch_fixed(fname, args, loc=loc, source_name=source_name, ctx=ctx)
    if fname == '__unary_sub__':
        if len(args) != 1:
            return None
    elif len(args) != 2 or fname not in {*_SAME_DIMENSION_DUNDERS, '__mul__', '__truediv__'}:
        if involves_rational:
            type_error(
                ctx.srcfile,
                f'operator `{source_name}` is not defined for rationals',
                Pointer(span=loc, message='rationals support `+ - * / ^`, negation, and comparisons'),
            )
        return None
    if not all(ctx.type_system.is_subtype(number, 'number') or _is_rational(number, ctx=ctx) or _is_fixed(number, ctx=ctx) or _is_bigint(number, ctx=ctx) for number in numbers):
        type_error(
            ctx.srcfile,
            f'no matching overload for operator `{source_name}`',
            *[
                Pointer(span=arg.loc, message=f'this has type `{type_to_dewy(arg.type)}`')
                for arg in args
            ],
            hint='`/` divides numbers exactly; use `//` for floor division' if is_division else None,
        )
    result_dimension = _result_dimension(fname, dimensions, loc=loc, ctx=ctx)
    constants = [_constant_rational(arg, ctx=ctx) for arg in args]
    if is_division and constants[1] == 0:
        type_error(
            ctx.srcfile,
            'division by zero',
            Pointer(span=args[1].loc, message='the divisor is the constant `0`'),
        )
    if all(value is not None for value in constants):
        folded = _fold_constant_operation(fname, cast(list[Fraction], constants))
        if isinstance(folded, bool):
            return hir.Bool(loc, 'bool', folded)
        if isinstance(folded, Fraction):
            all_integers = all(isinstance(number, ty.IntegerLiteralType) for number in numbers)
            if all_integers and not is_division and folded.denominator == 1:
                return hir.Integer(
                    loc,
                    _with_dimension(ty.IntegerLiteralType(folded.numerator), result_dimension),
                    '0d',
                    folded.numerator,
                )
            return _rational_constant(folded, result_dimension, loc=loc)
    if not involves_rational and not is_division:
        # Dimensioned integers: operate on the numbers, keep the dimension.
        if fname == '__mul__':
            return None  # the quantity product path handles representations
        stripped = [_strip_dimension(arg) for arg in args]
        result = _dispatch_builtin(
            fname,
            stripped,
            loc=loc,
            op_loc=loc,
            source_name=source_name,
            ctx=ctx,
        )
        if fname in _COMPARISON_DUNDERS:
            return result
        return replace(result, type=_with_dimension(result.type, result_dimension))
    # the representation: the abstract `rational` (big-integer parts) unless the
    # runtime operands are all the explicit `rational<int64>`
    word = any(_is_word_rational(number, ctx=ctx) for number in numbers) and not any(_is_big_rational(number, ctx=ctx) for number in numbers)
    rational_type = _word_rational_type(ctx, loc) if word else _rational_type(ctx, loc)
    if is_division and not involves_rational:
        # integer / integer: build the fraction directly (`b` proven nonzero)
        if _is_bigint(numbers[0], ctx=ctx) or _is_bigint(numbers[1], ctx=ctx):
            call = _prelude_call(
                '_bigrational_make',
                [_to_bigint(args[0], ctx=ctx), _to_bigint(args[1], ctx=ctx, nonzero=True)],
                loc=loc,
                ctx=ctx,
            )
        else:
            operands = [_as_int64(_strip_dimension(arg), ctx=ctx) for arg in args]
            call = _prelude_call('_rational_make', operands, loc=loc, ctx=ctx)
            call = _prelude_call('_bigrational_from_rational', [call], loc=loc, ctx=ctx)
        return replace(call, type=_with_dimension(rational_type, result_dimension))
    if fname == '__unary_sub__':
        call = _prelude_call('_rational_neg' if word else '_bigrational_neg', [_to_rational(args[0], ctx=ctx, word=word)], loc=loc, ctx=ctx)
        return replace(call, type=_with_dimension(rational_type, result_dimension))
    helper = (_RATIONAL_BINARY_FUNCTIONS if word else _BIG_RATIONAL_BINARY_FUNCTIONS)[fname]
    if word:
        zero_test = _zero_test_on_field(fname, args, 'numerator', loc=loc, source_name=source_name, ctx=ctx)
        if zero_test is not None:
            return zero_test
    elif is_division and constants[1] is None:
        _require_nonzero_divisor(args[1], BIG_RATIONAL_TYPE_NAME, ctx=ctx)
    operands = [_to_rational(arg, ctx=ctx, word=word) for arg in args]
    call = _prelude_call(helper, operands, loc=loc, ctx=ctx)
    if fname in _COMPARISON_DUNDERS:
        return call
    return replace(call, type=_with_dimension_result(call.type, rational_type, result_dimension))


def _dispatch_fixed(
    fname: str,
    args: list[hir.AST],
    *,
    loc: Span,
    source_name: str,
    ctx: Context,
) -> hir.AST:
    """Operations with a fixed operand: fixed absorbs integers and rationals."""
    dimensions = [_number_and_dimension(arg.type)[1] for arg in args]
    if fname == '__unary_sub__':
        if len(args) != 1:
            raise ValueError('INTERNAL ERROR: unary minus takes one operand')
        call = _prelude_call('_fixed_neg', [_to_fixed(args[0], ctx=ctx)], loc=loc, ctx=ctx)
        return replace(call, type=_with_dimension(_fixed_type(ctx, loc), dimensions[0]))
    helper = _FIXED_BINARY_FUNCTIONS.get(fname)
    if helper is None or len(args) != 2:
        type_error(
            ctx.srcfile,
            f'operator `{source_name}` is not defined for fixed-point values',
            Pointer(span=loc, message='fixed supports `+ - * /`, negation, and comparisons'),
        )
    result_dimension = _result_dimension(fname, dimensions, loc=loc, ctx=ctx)
    if fname == '__truediv__' and _constant_rational(args[1], ctx=ctx) == 0:
        type_error(
            ctx.srcfile,
            'division by zero',
            Pointer(span=args[1].loc, message='the divisor is the constant `0`'),
        )
    zero_test = _zero_test_on_field(fname, args, 'raw', loc=loc, source_name=source_name, ctx=ctx)
    if zero_test is not None:
        return zero_test
    operands = [_to_fixed(arg, ctx=ctx) for arg in args]
    call = _prelude_call(helper, operands, loc=loc, ctx=ctx)
    if fname in _COMPARISON_DUNDERS:
        return call
    return replace(call, type=_with_dimension_result(call.type, _fixed_type(ctx, loc), result_dimension))


def _as_int64(arg: hir.AST, *, ctx: Context) -> hir.AST:
    """An integer operand as `int64`, widening narrower fixed widths."""
    if isinstance(arg.type, str) and arg.type in ty.FIXED_INTEGER_TYPES and arg.type != 'int64':
        return hir.ValueCast(arg.loc, 'int64', arg)
    if arg.type == 'int':
        # Abstract integers currently lower as int64 words.
        return hir.ValueCast(arg.loc, 'int64', arg)
    return check_against(arg, 'int64', ctx=ctx)


_SET_ALGEBRA = {'__or__': 'union', '__and__': 'intersection', '__sub__': 'difference', '__xor__': 'symmetric'}


def _dispatch_set_algebra(
    fname: str,
    args: list[hir.AST],
    *,
    loc: Span,
    source_name: str,
    ctx: Context,
) -> hir.AST | None:
    """`a | b`, `a & b`, `a - b`, `a xor b` on two sets of one element type; `d1 | d2` on dictionaries."""
    if len(args) != 2 or not any(ty.container_entry_types(arg.type) is not None for arg in args):
        return None
    if all(ty.dict_key_value(arg.type) is not None for arg in args):
        if fname != '__or__':
            type_error(
                ctx.srcfile,
                f'no matching overload for operator `{source_name}`',
                *[Pointer(span=arg.loc, message=f'this has type `{type_to_dewy(arg.type)}`') for arg in args],
                hint='dictionaries combine with `|`/`or` (the right value wins for shared keys); use `.keys` for set algebra',
            )
        if args[0].type != args[1].type:
            type_error(
                ctx.srcfile,
                'dictionary operands have different types',
                *[Pointer(span=arg.loc, message=f'`{type_to_dewy(arg.type)}`') for arg in args],
            )
        return hir.SetAlgebra(loc, args[0].type, 'union', args[0], args[1])
    elements = [ty.set_element(arg.type) for arg in args]
    if elements[0] is None or elements[1] is None or fname not in _SET_ALGEBRA:
        type_error(
            ctx.srcfile,
            f'no matching overload for operator `{source_name}`',
            *[Pointer(span=arg.loc, message=f'this has type `{type_to_dewy(arg.type)}`') for arg in args],
            hint='sets combine with `|`/`or` (union), `&`/`and` (intersection), `-` (difference), `xor` (symmetric difference)',
        )
    if elements[0] != elements[1]:
        type_error(
            ctx.srcfile,
            'set operands have different element types',
            *[Pointer(span=arg.loc, message=f'`{type_to_dewy(arg.type)}`') for arg in args],
        )
    return hir.SetAlgebra(loc, args[0].type, _SET_ALGEBRA[fname], args[0], args[1])


def _dispatch_pow(
    args: list[hir.AST],
    *,
    loc: Span,
    ctx: Context,
) -> hir.AST:
    """`base ^ exponent` over integers, rationals, and dimensioned quantities.

    Compile-time bases fold exactly (a negative exponent makes an integer base
    rational); runtime integer bases with a non-negative exponent call
    `_int_pow`; runtime rational bases take any integer exponent through
    `_rational_pow`. The dimension is raised to the same power.
    """
    if len(args) != 2:
        raise ValueError('INTERNAL ERROR: `^` takes two operands')
    base, exponent = args
    if not ctx.type_system.is_subtype(exponent.type, 'int'):
        type_error(
            ctx.srcfile,
            'exponent must be an integer',
            Pointer(span=exponent.loc, message=f'this has type `{type_to_dewy(exponent.type)}`'),
        )
    exponent_value = _constant_integer(_unwrap_parens(exponent), ctx=ctx)
    number, dimension = _number_and_dimension(base.type)
    if dimension.powers and exponent_value is None:
        type_error(
            ctx.srcfile,
            'a dimensioned quantity needs a constant exponent',
            Pointer(span=exponent.loc, message='the result dimension must be known at compile time'),
        )
    if _is_fixed(number, ctx=ctx):
        not_implemented(ctx.srcfile, loc, '`^` on fixed-point bases')
    if _is_bigint(number, ctx=ctx):
        if exponent_value is not None and exponent_value < 0:
            not_implemented(ctx.srcfile, loc, 'negative powers of big integers (rationals over big integers)')
        if exponent_value is None and not ctx.type_system.is_subtype(exponent.type, 'uint'):
            type_error(
                ctx.srcfile,
                'integer exponent must be known to be non-negative',
                Pointer(span=exponent.loc, message='a negative exponent would make the result a rational'),
            )
        return _prelude_call('_bigint_pow', [base, _as_int64(exponent, ctx=ctx)], loc=loc, ctx=ctx)
    base_rational = _is_rational(number, ctx=ctx) or isinstance(number, ty.RationalLiteralType)
    if not base_rational and not ctx.type_system.is_subtype(number, 'int'):
        type_error(
            ctx.srcfile,
            'no matching overload for operator `^`',
            Pointer(span=base.loc, message=f'this has type `{type_to_dewy(base.type)}`'),
            hint='`^` raises integers and rationals to integer powers',
        )
    base_value = _constant_rational(base, ctx=ctx)
    if base_value is not None and exponent_value is not None:
        if base_value == 0 and exponent_value < 0:
            type_error(
                ctx.srcfile,
                'division by zero',
                Pointer(span=loc, message='zero raised to a negative power'),
            )
        result_dimension = ty.power_dimension(dimension, exponent_value)
        folded = base_value ** exponent_value
        if not base_rational and exponent_value >= 0:
            return hir.Integer(
                loc,
                _with_dimension(ty.IntegerLiteralType(folded.numerator), result_dimension),
                '0d',
                folded.numerator,
            )
        return _rational_constant(folded, result_dimension, loc=loc)
    result_dimension = ty.power_dimension(dimension, exponent_value) if exponent_value is not None else dimension
    exponent64 = _as_int64(exponent, ctx=ctx)
    if base_rational or (exponent_value is not None and exponent_value < 0):
        word = _is_word_rational(_number_and_dimension(base.type)[0], ctx=ctx)
        prefix = '_rational' if word else '_bigrational'
        helper = f'{prefix}_pow_negative' if exponent_value is not None and exponent_value < 0 else f'{prefix}_pow'
        call = _prelude_call(helper, [_to_rational(base, ctx=ctx, word=word), exponent64], loc=loc, ctx=ctx)
        result_type = _word_rational_type(ctx, loc) if word else _rational_type(ctx, loc)
        return replace(call, type=_with_dimension_result(call.type, result_type, result_dimension))
    if exponent_value is None and not ctx.type_system.is_subtype(exponent.type, 'uint'):
        type_error(
            ctx.srcfile,
            'integer exponent must be known to be non-negative',
            Pointer(span=exponent.loc, message='a negative exponent would make the result a rational'),
            hint='use an unsigned exponent, or make the base a rational (`(1/1 * base) ^ n`)',
        )
    if number not in ('int', 'int64') and not isinstance(number, ty.IntegerLiteralType):
        not_implemented(ctx.srcfile, loc, f'`^` on `{type_to_dewy(base.type)}` bases')
    call = _prelude_call('_int_pow', [_as_int64(_strip_dimension(base), ctx=ctx), exponent64], loc=loc, ctx=ctx)
    return replace(call, type=_with_dimension('int64', result_dimension))


def _real_literal(real: t1.Real, *, loc: Span, ctx: Context) -> hir.AST:
    """A decimal literal such as `9.8` is the exact rational 49/5."""
    def digits(number: t0.Number) -> tuple[int, int]:
        if number.prefix != '0d':
            not_implemented(ctx.srcfile, loc, 'non-decimal real literals')
        text = number.src[2:] if number.src[:2].casefold() == '0d' else number.src
        text = text.replace('_', '')
        return int(text, 10), len(text)

    numerator, _ = digits(real.whole)
    denominator = 1
    if real.fraction is not None:
        fraction, count = digits(real.fraction)
        denominator = 10 ** count
        numerator = numerator * denominator + fraction
    if real.exponent is not None:
        if real.exponent.binary:
            not_implemented(ctx.srcfile, loc, 'binary exponents in real literals')
        power, _ = digits(real.exponent.value)
        if real.exponent.positive:
            numerator *= 10 ** power
        else:
            denominator *= 10 ** power
    return _rational_literal(numerator, denominator, loc=loc, ctx=ctx)


def _integer_singleton_test(value: hir.AST, test_type: ty.Type, *, negated: bool, loc: Span, op_loc: Span, ctx: Context) -> hir.AST | None:
    """`picked is? 3` on an integer word (`picked:1|2|3`) is `picked =? 3`;
    against `1|2` it is `picked =? 1 or picked =? 2`. None for other operands."""
    number, _ = _number_and_dimension(value.type)
    base = ty.strip_refinement(number)
    if not (isinstance(base, str) and ctx.type_system.is_subtype(base, 'int')):
        return None
    members = list(test_type.items) if isinstance(test_type, ty.TypeOr) else [test_type]
    if not members or not all(isinstance(m, ty.IntegerLiteralType) for m in members):
        return None
    tests = [
        _dispatch_builtin(
            '__ne__' if negated else '__eq__',
            [value, hir.Integer(loc, ty.IntegerLiteralType(m.value), '0d', m.value)],
            loc=loc, op_loc=op_loc, source_name='not=?' if negated else '=?', ctx=ctx,
        )
        for m in members
    ]
    combined = tests[0]
    for test in tests[1:]:
        combined = hir.ShortCircuit(loc, 'bool', 'and' if negated else 'or', combined, test)
    return combined


def _literal_member_test(args: list[hir.AST], *, negated: bool, loc: Span, ctx: Context) -> hir.AST | None:
    """`value =? 0` where `value : 0 | [...]` tests the union's tag.

    Equality against a literal that is one member of a mixed union (a literal
    beside object or nominal members, as in `bigint = 0 | [sign limbs]`) is
    `value is? 0`, so the condition narrows the binding like a type test.
    """
    for value, other in ((args[0], args[1]), (args[1], args[0])):
        union = ty.strip_refinement(_number_and_dimension(value.type)[0])
        if not isinstance(union, ty.TypeOr):
            continue
        other_node = _unwrap_parens(other)
        constant = _constant_integer(other_node, ctx=ctx)
        if constant is not None:
            literal = next(
                (m for m in union.items if isinstance(m, ty.IntegerLiteralType) and m.value == constant),
                None,
            )
            if literal is None or all(isinstance(m, ty.IntegerLiteralType) for m in union.items):
                continue
            return hir.TypeTest(loc, 'bool', value, literal, negated)
        if isinstance(other_node.type, ty.StringLiteralType):
            # `mode =? 'A'` on an enum `'A' | 'B' | 'C'`: the member's tag
            literal = next((m for m in union.items if m == other_node.type), None)
            if literal is not None:
                return hir.TypeTest(loc, 'bool', value, literal, negated)
    return None


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
    if fname == '__pow__':
        return _dispatch_pow(args, loc=loc, ctx=ctx)
    if fname in ('__eq__', '__ne__') and len(args) == 2:
        member_test = _literal_member_test(args, negated=fname == '__ne__', loc=loc, ctx=ctx)
        if member_test is not None:
            return member_test
        metatypes = [ty.unfold(ty.strip_refinement(arg.type)) for arg in args]
        if any(isinstance(item, ty.MetaType) for item in metatypes):
            # `kind =? Whitespace`: type values compare by brand id
            family = next(item for item in metatypes if isinstance(item, ty.MetaType))
            root = ty.MetaType(ty.USER_BRAND_TYPES[ty.brand_root(family.brand or '')])   # any type of the family compares
            words = [hir.Transmute(arg.loc, 'int64', check_against(arg, root, ctx=ctx)) for arg in args]
            comparison = hir.FunctionCall(loc, 'bool', hir.ExpressedIdentifier(loc, ty.FunctionType([ty.PosOrKwArg('left', 'int64'), ty.PosOrKwArg('right', 'int64')], [], None, 'bool', []), fname), words, {})
            return comparison
    big = _dispatch_bigint(fname, args, loc=loc, source_name=source_name, ctx=ctx, expected=expected)
    if big is not None:
        return big
    algebra = _dispatch_set_algebra(fname, args, loc=loc, source_name=source_name, ctx=ctx)
    if algebra is not None:
        return algebra
    rational = _dispatch_rational(fname, args, loc=loc, source_name=source_name, ctx=ctx)
    if rational is not None:
        return rational
    if (
        fname in {'__lt__', '__le__', '__gt__', '__ge__', '__eq__', '__ne__'}
        and len(args) == 2
        and ty.fixed_integer_layout(ty.strip_refinement(arg_types[0])) is not None
        and ty.fixed_integer_layout(ty.strip_refinement(arg_types[1])) is not None
        and ty.strip_refinement(arg_types[0]) != ty.strip_refinement(arg_types[1])
    ):
        # `i:uint64 <? length:int64`: the comparison happens in the left
        # operand's width — the right operand takes a value cast the bounds
        # analysis must prove in range (`length >= 0` here), so no value is
        # ever reinterpreted
        args = [args[0], check_against(args[1], ty.strip_refinement(arg_types[0]), ctx=ctx)]
        arg_types = [args[0].type, args[1].type]
    if (
        fname in {'__eq__', '__ne__'}
        and len(args) == 2
        and all(_is_string_type(arg.type) or ty.string_valued(ty.strip_refinement(arg.type)) for arg in args)
        and not all(isinstance(arg.type, ty.StringLiteralType) for arg in args)
    ):
        # runtime string equality, whatever the operands' spellings (`string`, a
        # view `StringType`, a literal): the generic `(T T)` overload would not unify them
        return hir.StringEqual(loc, 'bool', args[0], args[1], fname == '__ne__')
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
        expected_return = expected if expected not in (None, ty.VOID_TYPE, ty.INFERRED_TYPE, ty.TOP_TYPE) else None
        if isinstance(expected_return, ty.TypeOr):
            # `return id * 2` into `int64 | NotFound`: the union does not
            # choose the operator; the result converts to the union afterwards
            expected_return = None
        if expected_return is not None:
            expected_number, _ = _number_and_dimension(expected_return)
            if _is_rational(expected_number, ctx=ctx) or _is_fixed(expected_number, ctx=ctx):
                # Integer results convert to rational/fixed targets afterwards
                # (`let c:fixed = -7`), so they must not constrain dispatch.
                expected_return = None
            elif (
                isinstance(expected_number, str)
                and expected_number in ty.FIXED_INTEGER_TYPES
                and any(arg_type in ('int', 'uint') or ty.fixed_integer_layout(ty.strip_refinement(arg_type)) is not None for arg_type in arg_types)
            ):
                # Abstract-integer arithmetic stays abstract, and fixed-width
                # arithmetic stays at the operands' width (`let w:uint64 = end - start`);
                # the result meets the fixed width afterwards (validated by
                # the bounds analysis).
                expected_return = None
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

    if (
        fname in {'__eq__', '__ne__'}
        and len(args) == 2
        and all(isinstance(arg.type, ty.StringLiteralType) for arg in args)
    ):
        # Two exact strings compare at compile time (used by `$target`
        # gating); this precedes contextual casts, which erase exactness.
        equal = args[0].type.value == args[1].type.value
        value = equal if fname == '__eq__' else not equal
        if any(isinstance(arg, hir.TargetString) for arg in args):
            return hir.TargetBool(loc, 'bool', value)
        return hir.Bool(loc, 'bool', value)
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
    if prefix.op.symbol == 'type of':
        user_error(
            ctx.srcfile,
            '`type of` mints only in an alias declaration',
            Pointer(span=prefix.loc, message='a fresh type needs a name to be referred to by'),
            hint='write `let Name = type of ...` (or `Name:type = ...`) and use `Name` here',
        )
    if prefix.op.symbol == '@':
        handle_ast = prefix.item
        if isinstance(handle_ast, p0.Block) and handle_ast.kind == '()' and len(handle_ast.inner) == 1:
            handle_ast = handle_ast.inner[0]
        if isinstance(handle_ast, p0.Atom) and isinstance(handle_ast.item, t1.Identifier):
            handle = tcr_identifier(handle_ast.item, ctx=ctx)
            if isinstance(handle.type, ty.FunctionType) and handle.type.type_params:
                user_error(
                    ctx.srcfile,
                    'a generic function cannot be used as a value',
                    Pointer(span=prefix.loc, message='it has no single representation; call it, or name an instance'),
                )
            if isinstance(handle.type, (ty.FunctionType, ty.OverloadType)):
                # `@name` selects the function value instead of calling it
                return handle
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
            if (reason := _read_only_reason(binding)) is not None:
                user_error(
                    ctx.srcfile,
                    'cannot pass a const binding as a mutable place',
                    Pointer(
                        span=prefix.loc,
                        message=f'`{binding.name}` {reason}',
                    ),
                    *_declaration_pointers(binding),
                )
            # the callee may change the value: forget what was known about it
            # (an exact length after `= []`, a refinement) for the code after the call
            ctx.refinements.pop(binding.id, None)
            ctx.length_bounds.pop(binding.id, None)
            _invalidate_routes(binding.id, ctx=ctx)
            _drop_key_facts(ctx, dictionary_id=binding.id)
            _drop_key_facts(ctx, key_id=binding.id)
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
    if isinstance(target_bool := _unwrap_parens(item), hir.TargetBool) and prefix.op.symbol == 'not':
        return hir.TargetBool(prefix.loc, 'bool', not target_bool.value)
    if isinstance(target_bool, hir.DecidedBool) and prefix.op.symbol == 'not':
        return hir.DecidedBool(prefix.loc, 'bool', not target_bool.value)
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


def _substitute_end(index: hir.AST, end_id: int, sequence: hir.AST, *, ctx: Context) -> hir.AST:
    """Replace the hidden `end` binding in an index expression by `sequence.length - 1`."""

    def last_index(loc: Span) -> hir.AST:
        measured = copy.deepcopy(sequence)  # its own node: lowering keys analyses by node identity
        length: hir.AST = (
            hir.StringLength(loc, 'int64', measured)
            if _is_string_type(sequence.type)
            else hir.ArrayLength(loc, 'int64', measured)
        )
        one = hir.Integer(loc, ty.IntegerLiteralType(1), '0d', 1)
        return _dispatch_builtin('__sub__', [length, one], loc=loc, op_loc=loc, source_name='-', ctx=ctx)

    def walk(value: object) -> object:
        if isinstance(value, hir.ExpressedIdentifier):
            return last_index(value.loc) if value.binding_id == end_id else value
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, tuple):
            return tuple(walk(item) for item in value)
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        if isinstance(value, hir.AST):
            changes = {}
            for field_info in fields(value):
                if field_info.name in ('type', 'annotation'):
                    continue
                current = getattr(value, field_info.name)
                if isinstance(current, (hir.AST, list, tuple, dict)):
                    updated = walk(current)
                    if updated is not current:
                        changes[field_info.name] = updated
            return replace(value, **changes) if changes else value
        return value

    result = walk(index)
    assert isinstance(result, hir.AST)
    return result


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
    found_dict = _dict_value(array)
    if found_dict is not None and found_dict[2] is None:
        user_error(
            ctx.srcfile,
            'sets are not indexable',
            Pointer(span=binop.loc, message='a set has members, not values'),
            hint='test membership with `x in? s`',
        )
    if found_dict is not None:
        dictionary, key_type, value_type = found_dict
        assert value_type is not None
        if not isinstance(binop.right, p0.Block) or len(binop.right.inner) != 1:
            user_error(
                ctx.srcfile,
                'dictionary lookup takes one key',
                Pointer(span=binop.right.loc, message='expected exactly one key expression'),
            )
        key = check_against(
            typecheck_and_resolve_inner(binop.right.inner[0], ctx=ctx, expected=key_type),
            key_type,
            ctx=ctx,
        )
        keys, values = _dict_arrays(dictionary, binop.loc, ctx=ctx)
        fact = _proven_key(dictionary, key, ctx=ctx)
        if fact is None:
            user_error(
                ctx.srcfile,
                'dictionary key is not proven present',
                Pointer(
                    span=binop.right.loc,
                    message='no fact establishes that this key is in the dictionary (neither proven nor refuted)',
                ),
                hint='guard with `if key in? d { ... }`, iterate the dictionary, store the key first, '
                'or use `d.get(key)` (optionally `d.get(key default)`) for a lookup that may miss',
            )
        position, static_position = fact
        return hir.DictLookup(
            binop.loc, value_type, keys, values, key,
            proven=True, position=position, static_position=static_position,
        )
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
    end_binding: sb.Binding | None = None
    if length is not None:
        index_ctx = replace(
            ctx,
            declarations=ctx.declarations.new_child(
                {'end': ty.IntegerLiteralType(length - 1)}
            ),
            binding_scopes=ctx.binding_scopes.new_child(),
        )
    else:
        # `end` in an index of a runtime-length sequence is `seq.length - 1`,
        # usable in any expression (`s[end - 1]`, `s[2..end]`): it is bound
        # here and substituted after checking
        end_binding = ctx.binding_registry.allocate_param('end', 'int64', binop.right.loc)
        index_ctx = replace(
            ctx,
            declarations=ctx.declarations.new_child({'end': 'int64'}),
            binding_scopes=ctx.binding_scopes.new_child({'end': end_binding}),
        )
    index_ast: p0.AST = (
        binop.right.inner[0]
        if binop.right.kind == '[]'
        else binop.right
    )
    index = typecheck_and_resolve_inner(index_ast, ctx=index_ctx)
    if end_binding is not None:
        index = _substitute_end(index, end_binding.id, array, ctx=ctx)
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
        if (
            length is None
            and (index.left is not None or index.right is not None)
            and not (_is_string_type(array.type) and sb.array_route_id(array, ctx.binding_registry) is not None)
        ):
            # a named runtime-length string defers to the bounds analysis
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
    if length is None and not (
        (isinstance(array.type, ty.ArrayType) or _is_string_type(array.type))
        and sb.array_route_id(array, ctx.binding_registry) is not None
    ):
        user_error(
            ctx.srcfile,
            'sequence index is not proven in bounds',
            Pointer(
                span=array.loc,
                message='this sequence does not have an exact compile-time length',
            ),
        )
    # A named runtime-length array defers to the bounds analysis, which
    # proves indexes from length facts and `i <? xs.length` guards.
    if (
        length is not None
        and constant_index is not None
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


def _unwrap_parens(node: hir.AST) -> hir.AST:
    """Look through `( ... )` around a single expression."""
    while (
        isinstance(node, hir.Block)
        and not node.scoped
        and len(node.items) == 1
    ):
        node = node.items[0]
    return node


def _target_membership(left: hir.AST, right: hir.AST, loc: Span) -> hir.TargetBool | None:
    """`$target in? ["x86_64" "riscv" ...]` folds at compile time.

    Returns None when this is not a target-list membership test.
    """
    left = _unwrap_parens(left)
    right = _unwrap_parens(right)
    if not isinstance(left, hir.TargetString):
        return None
    if not isinstance(right, hir.ArrayLiteral):
        return None
    names: set[str] = set()
    for item in right.items:
        # Literal elements are cast to the array's element representation.
        while isinstance(item, hir.RepresentationCast):
            item = item.expr
        if not isinstance(item, hir.String):
            return None
        names.add(item.content)
    return hir.TargetBool(loc, 'bool', left.content in names)


_CHAIN_RISING = {'<?', '<=?'}
_CHAIN_FALLING = {'>?', '>=?'}
_CHAIN_COMPARISONS = _CHAIN_RISING | _CHAIN_FALLING | {'=?'}
_TEST_OPERATORS = {'is?', 'isnt?', 'in?'}


def _comparison_operator(op: object) -> str | None:
    """The spelling of a comparison or test operator, `not =?` included; None for anything else."""
    if isinstance(op, t2.InvertedComparisonOp):
        return f'not {op.op}'
    if isinstance(op, t1.Operator) and op.symbol in _CHAIN_COMPARISONS | _TEST_OPERATORS:
        return op.symbol
    return None


def _comparison_chain(binop: p0.BinOp, *, ctx: Context, expected: ty.Type | None) -> hir.AST | None:
    """`0 <? x <? 10` is `0 <? x and x <? 10`, each interior operand evaluated
    once. A chain is one monotonic statement: rising (`<?` `<=?`) or falling
    (`>?` `>=?`) comparisons, with `=?` allowed in either; `not =?` and the
    tests (`is?` `isnt?` `in?`) do not chain. Parenthesizing the left
    comparison (`(a <? b) <? c`) compares its boolean instead."""
    if _comparison_operator(binop.op) is None:
        return None
    ops: list[p0.BinOp] = []
    node: p0.AST = binop
    while isinstance(node, p0.BinOp) and _comparison_operator(node.op) is not None:
        ops.insert(0, node)
        node = node.left
    if len(ops) < 2:
        return None
    operands: list[p0.AST] = [ops[0].left, *(op.right for op in ops)]
    directions: set[str] = set()
    for op in ops:
        symbol = _comparison_operator(op.op)
        assert symbol is not None
        if symbol not in _CHAIN_COMPARISONS:
            user_error(
                ctx.srcfile,
                'comparison does not chain',
                Pointer(span=op.op.loc, message=f'`{symbol}` cannot be part of a comparison chain'),
                hint='combine the tests with `and`',
            )
        if symbol in _CHAIN_RISING:
            directions.add('rising')
        elif symbol in _CHAIN_FALLING:
            directions.add('falling')
    if len(directions) == 2:
        user_error(
            ctx.srcfile,
            'comparison chain changes direction',
            *[
                Pointer(span=op.op.loc, message=f'`{_comparison_operator(op.op)}` is {"rising" if _comparison_operator(op.op) in _CHAIN_RISING else "falling"}')
                for op in ops
                if _comparison_operator(op.op) in _CHAIN_RISING | _CHAIN_FALLING
            ],
            hint='a chain reads one way (`0 <? x <? 10`, `10 >? x >=? 0`); write the other comparison with `and`',
        )
    # interior operands are evaluated once: a name or literal is reused as
    # written, anything else is bound to a hidden local before the statement
    for index in range(1, len(operands) - 1):
        operand = operands[index]
        if isinstance(operand, p0.Atom) and isinstance(operand.item, (t1.Identifier, t1.String, t1.Integer)):
            continue
        if ctx.hoisted is None:
            user_error(
                ctx.srcfile,
                'chained comparison needs a bound interior operand here',
                Pointer(span=operand.loc, message='this operand is used by two comparisons, so it must be evaluated once'),
                hint='bind it first (`let mid = ...`) and chain on the name',
            )
        value = typecheck_and_resolve_inner(operand, ctx=ctx)
        require_valued(value.type, ctx.srcfile, value.loc, 'comparison operand')
        name = f'__dewy_chain_{ctx.binding_registry.next_id}'
        binding = ctx.binding_registry.allocate(_fresh_syntax(ctx), name, 'value', operand.loc)
        binding.type = value.type
        declaration = hir.Declare(operand.loc, ty.VOID_TYPE, 'let', name, value.type, value, binding_id=binding.id)
        binding.declaration = declaration
        ctx.declarations[name] = value.type
        ctx.binding_scopes[name] = binding
        ctx.hoisted.append(declaration)
        operands[index] = p0.Atom(operand.loc, t1.Identifier(operand.loc, name))
    conjunction: p0.AST | None = None
    for index, op in enumerate(ops):
        comparison = p0.BinOp(Span(operands[index].loc.start, operands[index + 1].loc.stop), op.op, operands[index], operands[index + 1])
        conjunction = comparison if conjunction is None else p0.BinOp(
            Span(conjunction.loc.start, comparison.loc.stop),
            t1.Operator(op.op.loc, 'and'),
            conjunction,
            comparison,
        )
    assert conjunction is not None
    return typecheck_and_resolve_inner(conjunction, ctx=ctx, expected=expected)


def tcr_binop(binop: p0.BinOp, *, ctx: Context, type_block:bool=False, expected: ty.Type|None=None, call_target: bool=False) -> hir.AST:
    """
    typecheck and resolve a binary operator node.
    
    NOTE:
    type_block is used to disambiguate the context these binops occur in. 
    mainly for distinguishing type expressions using literals from regular operations between said literals
    e.g. `true | false` -> `true` vs `<true | false>` -> `literal<true>|literal<false>`
    most other operators are unaffected by this flag.
    """

    if not type_block:
        chain = _comparison_chain(binop, ctx=ctx, expected=expected)
        if chain is not None:
            return chain

    # quantum juxtapose: which operator this is depends on the operand types,
    # so try each reading as a candidate like an Ambiguous node
    if (
        isinstance(binop.op, (t2.QJuxtapose, t2.IndexJuxtapose, t2.CallJuxtapose))
        and isinstance(binop.left, p0.Atom)
        and isinstance(binop.left.item, t1.Identifier)
        and binop.left.item.name == 'set'
        and 'set' not in ctx.declarations
        and isinstance(binop.right, p0.Block)
        and binop.right.kind == '[]'
    ):
        spread = next((item for item in binop.right.inner if _spread_operand(item) is not None), None)
        if spread is not None:
            not_implemented(ctx.srcfile, spread.loc, 'spreading into a set literal (members need a runtime add)')
        if len(binop.right.inner) == 1 and _loop_flow(binop.right.inner[0]) is not None:
            return _tcr_loop_capture(binop.right, kind='set', expected=expected, ctx=ctx)
        return _tcr_set_literal(binop.right, binop.loc, expected=expected, ctx=ctx)
    if (
        isinstance(binop.op, (t2.QJuxtapose, t2.IndexJuxtapose, t2.CallJuxtapose))
        and isinstance(binop.left, p0.Atom)
        and isinstance(binop.left.item, t1.Identifier)
        and binop.left.item.name == 'set'
        and 'set' not in ctx.declarations
    ):
        return _tcr_set_from(binop.right, binop.loc, ctx=ctx)
    if isinstance(binop.op, t2.QJuxtapose):
        constructor = _type_constructor_target(binop.left, ctx=ctx)
        if constructor is not None:
            # a type cannot be multiplied: `Span(1 9)` is only ever a construction
            return tcr_function_call(constructor, _construction_arguments(binop.right), ctx=ctx, expected=expected)
        if isinstance(binop.left, p0.BinOp) and _operator_symbol(binop.left.op) == '.':
            # `s.grow(2)`: a method is only ever called, never multiplied
            member = typecheck_and_resolve_inner(binop.left, ctx=ctx, type_block=type_block, call_target=True)
            if isinstance(member, hir.BoundMethod):
                return tcr_function_call(member, binop.right, ctx=ctx, expected=expected)
        candidates: list[p0.AST] = [replace(binop, op=option) for option in binop.op.options]
        return typecheck_and_resolve_inner(p0.Ambiguous(binop.loc, candidates), ctx=ctx, type_block=type_block, expected=expected)

    if isinstance(binop.op, t2.CallJuxtapose):
        if (
            isinstance(binop.left, p0.Atom) and isinstance(binop.left.item, t1.Identifier)
            and binop.left.item.name == 'typeof' and 'typeof' not in ctx.declarations
        ):
            return _tcr_typeof(binop, ctx=ctx)
        constructor = _type_constructor_target(binop.left, ctx=ctx)
        if constructor is not None:
            return tcr_function_call(constructor, binop.right, ctx=ctx, expected=expected)
        left = typecheck_and_resolve_inner(binop.left, ctx=ctx, type_block=type_block, call_target=True)
        if (
            isinstance(binop.left, p0.Prefix)
            and isinstance(binop.left.op, t1.Operator)
            and binop.left.op.symbol == '@'
            and isinstance(left.type, (ty.FunctionType, ty.OverloadType))
        ):
            not_implemented(ctx.srcfile, binop.loc, 'partial application with `@`')
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
        # the right operand is an ordinary expression: a bare function name
        # would be called, so a named function is written `@name`; function
        # literals and function-valued expressions pipe as they are
        callable_value = typecheck_and_resolve_inner(binop.right, ctx=ctx)
        return tcr_function_call(callable_value, binop.left, ctx=ctx, expected=expected)

    if symbol == '<|':
        # the mirror image: callable on the left, its argument on the right
        callable_value = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        return tcr_function_call(callable_value, binop.right, ctx=ctx, expected=expected)

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
        included_args = _include_bytes_call(binop.left)
        if included_args is not None and isinstance(binop.right, p0.Atom) and isinstance(binop.right.item, t1.Identifier):
            # `$include_bytes(p"…") as name`: a declaration of `name`
            value = _tcr_include_bytes(binop.loc, included_args, ctx=ctx)
            name = binop.right.item.name
            declaration = _complete_binding(
                binop,
                hir.Declare(binop.loc, ty.VOID_TYPE, 'let', name, value.type, value),
                ctx=ctx,
            )
            ctx.declarations[name] = value.type   # resolution consults the declaration map, as `let` does
            return declaration
        item = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        require_valued(item.type, ctx.srcfile, item.loc, 'conversion operand')
        target = ast_to_type(binop.right, ctx=ctx)
        return _explicit_value_conversion(item, target, binop.loc, ctx=ctx)

    if symbol in {'is?', 'isnt?'}:
        value = typecheck_and_resolve_inner(binop.left, ctx=ctx)
        require_valued(value.type, ctx.srcfile, value.loc, 'type-test operand')
        test_type = ast_to_type(binop.right, ctx=ctx)
        equality = _integer_singleton_test(value, test_type, negated=symbol == 'isnt?', loc=binop.loc, op_loc=binop.op.loc, ctx=ctx)
        if equality is not None:
            return equality
        metatype_test = _metatype_test(value, test_type, negated=symbol == 'isnt?', loc=binop.loc, ctx=ctx)
        if metatype_test is not None:
            return metatype_test
        decided = _decided_type_test(value.type, test_type, ctx=ctx)
        if decided is not None:
            return hir.DecidedBool(binop.loc, 'bool', decided != (symbol == 'isnt?'))
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
            equality = _integer_singleton_test(value, test_type, negated=binop.op.op == 'is?', loc=binop.loc, op_loc=binop.op.loc, ctx=ctx)
            if equality is not None:
                return equality
            decided = _decided_type_test(value.type, test_type, ctx=ctx)
            if decided is not None:
                return hir.DecidedBool(binop.loc, 'bool', decided != (binop.op.op == 'is?'))
            return hir.TypeTest(
                binop.loc,
                'bool',
                value,
                test_type,
                binop.op.op == 'is?',
            )
        left = typecheck_and_resolve_inner(binop.left, ctx=ctx, type_block=type_block)
        right = typecheck_and_resolve_inner(binop.right, ctx=ctx, type_block=type_block)
        if binop.op.op == 'in?':
            membership = _target_membership(left, right, binop.loc)
            if membership is not None:
                return replace(membership, value=not membership.value)
            found_dict = _dict_value(right)
            if found_dict is not None:
                # `x not in? container` is the negated membership test
                dictionary, key_type, _value_type = found_dict
                keys, _values = _dict_arrays(dictionary, binop.loc, ctx=ctx)
                contains = hir.DictContains(binop.loc, 'bool', keys, check_against(left, key_type, ctx=ctx))
                return _dispatch_builtin('__not__', [contains], loc=binop.loc, op_loc=binop.op.loc, source_name='not', ctx=ctx)
        fname = builtins.INVERTED_COMPARISON_DUNDER_MAP.get(binop.op.op)
        if fname is None:
            not_implemented(ctx.srcfile, binop.op.loc, f'inverted comparison `not{binop.op.op}`')
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

    left_target = _unwrap_parens(left)
    right_target = _unwrap_parens(right)
    if isinstance(left_target, hir.TargetBool) and isinstance(right_target, hir.TargetBool):
        # Compile-time target conditions combine at compile time so gated
        # `if` arms can be selected during checking.
        a, b = left_target.value, right_target.value
        folded = {
            'and': a and b,
            '&': a and b,
            'or': a or b,
            '|': a or b,
            'nand': not (a and b),
            'nor': not (a or b),
            'xor': a != b,
            'xnor': a == b,
        }.get(symbol)
        if folded is not None:
            return hir.TargetBool(binop.loc, 'bool', folded)

    if symbol == 'in?':
        membership = _target_membership(left, right, binop.loc)
        if membership is not None:
            return membership
        range_operand = (
            right
            if isinstance(right, hir.Range)
            else _resolve_range_value(right, ctx=ctx)
        )
        if range_operand is not None:
            return _tcr_range_membership(left, range_operand, ctx=ctx)
        found_dict = _dict_value(right)
        if found_dict is not None:
            dictionary, key_type, _value_type = found_dict
            keys, _values = _dict_arrays(dictionary, binop.loc, ctx=ctx)
            return hir.DictContains(
                binop.loc,
                'bool',
                keys,
                check_against(left, key_type, ctx=ctx),
                position=_new_key_position_name(),
            )
    
    match binop.op:
        case t2.QJuxtapose():
            not_implemented(ctx.srcfile, binop.loc, 'quantum juxtapose')
        case t2.IndexJuxtapose():
            not_implemented(ctx.srcfile, binop.loc, 'index juxtapose')
        case t2.MultiplyJuxtapose():
            if (
                isinstance(left, hir.FunctionCall)
                and isinstance(left.func, (hir.ArrayMethod, hir.MemberAccess, hir.ExpressedIdentifier))
                and not left.pos_args
                and not left.kw_args
                and isinstance(binop.right, p0.Block)
                and binop.right.kind == '()'
            ):
                # `xs.pop(2)` and `choose(22)` are calls with arguments, never
                # `(xs.pop) * (2)`: an auto-called function followed by
                # parentheses is not a product
                type_error(
                    ctx.srcfile,
                    'function followed by parentheses is a call',
                    Pointer(span=binop.loc, message='this reads as a call, not a product'),
                )
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
        binding = ctx.binding_registry.by_id.get(resolved.binding_id) if resolved.binding_id is not None else None
        if binding is not None and binding.read_only_reason is not None:
            user_error(
                ctx.srcfile,
                'cannot assign to a read-only binding',
                Pointer(span=target.loc, message=f'`{binding.name}` {binding.read_only_reason}'),
            )
        return resolved

    if isinstance(target, p0.BinOp):
        if isinstance(target.op, t1.Operator) and target.op.symbol == '.':
            access = _tcr_member_access(target, ctx=ctx)
            if isinstance(access, hir.ForwardingAccess):
                user_error(
                    ctx.srcfile,
                    'assignment through a union route',
                    Pointer(span=access.value.loc, message=f'this has type `{type_to_dewy(access.value.type)}`, so `{access.field}` is not one definite place'),
                    hint='narrow the receiver with `is?` (or propagate with `or_throw`) before assigning',
                )
            if not isinstance(access, hir.MemberAccess):
                not_implemented(ctx.srcfile, target.loc, 'assignment to `.length`')
            if not access.mutable:
                user_error(
                    ctx.srcfile,
                    f'cannot mutate const object field `{access.name}`',
                    Pointer(span=target.loc, message='this field is const'),
                )
            binding = _member_root_binding(access, ctx=ctx)
            if (reason := _read_only_reason(binding)) is not None:
                assert binding is not None
                user_error(
                    ctx.srcfile,
                    'cannot mutate a field of a const object',
                    Pointer(span=access.value.loc, message=f'`{binding.name}` {reason}'),
                    *_declaration_pointers(binding),
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
                if (reason := _read_only_reason(binding)) is not None:
                    user_error(
                        ctx.srcfile,
                        'cannot mutate an element of a const array',
                        Pointer(
                            span=root.loc,
                            message=f'`{root.name}` {reason}',
                        ),
                        *_declaration_pointers(binding),
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
    generic = _generic_signature(fn_ast, ctx=ctx)
    if generic is not None:
        return generic[0]
    signature = fn_ast.left
    if not (isinstance(signature, p0.BinOp) and isinstance(signature.op, t1.Operator) and signature.op.symbol == ':>'):
        return None
    rettype = _value_type(ast_to_type(signature.right, ctx=ctx), loc=signature.right.loc, ctx=ctx)
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
    if _generic_function_parts(binop) is not None:
        user_error(
            ctx.srcfile,
            'a generic function must be declared with `let`',
            Pointer(span=binop.loc, message='its instances are created where it is called by name'),
        )
    signature = binop.left
    rettype: ty.Type = ty.INFERRED_TYPE
    rettype_loc: Span | None = None
    
    # if the return type was annotated, capture it
    if isinstance(signature, p0.BinOp) and signature.op.symbol == ':>':
        rettype = _value_type(ast_to_type(signature.right, ctx=ctx), loc=signature.right.loc, ctx=ctx)
        rettype_loc = signature.right.loc
        signature = signature.left
    
    # collect function signature parameters
    pos_or_kw_args, kw_only_args, rest_args = collect_function_signature_args(signature, ctx=ctx)

    # insert the arguments from the signature into the body, and install a fresh catcher
    # for this function's returns
    inner_scope = ctx.declarations.new_child()
    inner_bindings = ctx.binding_scopes.new_child()

    def bind_param(param: hir.Param | hir.BoundParam) -> hir.Param | hir.BoundParam:
        # inside the body the binding has the base type; the refinement is a fact (bounds analysis)
        binding = ctx.binding_registry.allocate_param(param.name, ty.strip_refinement(param.type), binop.loc)
        if isinstance(param.type, ty.RefinedType):
            _record_refinement_facts(binding.id, param.type, ctx=ctx)
        inner_bindings[param.name] = binding
        return replace(param, binding_id=binding.id)

    pos_or_kw_args = [bind_param(param) for param in pos_or_kw_args]
    kw_only_args = [bind_param(param) for param in kw_only_args]
    rest_args = bind_param(rest_args) if rest_args is not None else None
    for param in pos_or_kw_args:
        inner_scope[param.name] = ty.strip_refinement(param.type)
    for param in kw_only_args:
        inner_scope[param.name] = ty.strip_refinement(param.type)
    if rest_args is not None:
        inner_scope[rest_args.name] = ty.strip_refinement(rest_args.type)
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
        length_bounds={},
        key_facts=_const_key_facts(ctx),
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
            args.append(ty.PosOrKwArg(item.left.item.name, ast_to_type(item.right, ctx=replace(ctx, refinement_subject=item.left.item.name))))
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
    """Parse one `name:type` row of an object type, including `fn:(T):>U` desugaring.

    `name:type = default` declares a default: the type's constructor may omit
    the field, and the default may refer to earlier fields by name.
    """

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
        and item.op.symbol == '='
        and isinstance(item.left, p0.BinOp)
        and isinstance(item.left.op, t1.Operator)
        and item.left.op.symbol == ':'
    ):
        declared = _object_type_member(item.left, ctx=ctx)
        return replace(declared, mutable=mutable, default=item.right)
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
        declared_type = ast_to_type(item.right, ctx=replace(ctx, refinement_subject=item.left.item.name))
        if isinstance(declared_type, ty.TypeOr):
            # `sign:-1|1`: a field of integer singletons is a word whose value
            # set is its invariant (elsewhere a singleton union stays a tagged cell)
            literal_set = _integer_literal_set(declared_type, loc=item.right.loc, ctx=ctx)
            if literal_set is not None:
                declared_type = literal_set
        if isinstance(declared_type, ty.RefinedType):
            # an invariant of the field: kept beside the base type (value
            # comparisons, or a length bound of an array or string field)
            if any(p.subject not in ('self', 'length') and p.field is None for p in declared_type.propositions):
                not_implemented(ctx.srcfile, item.right.loc, 'field invariants other than value and length comparisons')
            return ty.ObjectField(item.left.item.name, declared_type.base, mutable, refinement=declared_type.propositions)
        return ty.ObjectField(
            item.left.item.name,
            declared_type,
            mutable,
        )
    if (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol == '='
        and isinstance(item.right, p0.AST)
    ):
        # a defaulted field: `stop:int64 = start` declares the type, `severity = 'error'`
        # takes the default's (widened) type
        target = item.left
        if (
            isinstance(target, p0.BinOp)
            and isinstance(target.op, t1.Operator)
            and target.op.symbol == ':'
            and isinstance(target.left, p0.Atom)
            and isinstance(target.left.item, t1.Identifier)
        ):
            declared_type = _value_type(ast_to_type(target.right, ctx=ctx), loc=target.right.loc, ctx=ctx)
            return ty.ObjectField(target.left.item.name, ty.strip_refinement(declared_type), mutable, default=item.right)
        if isinstance(target, p0.Atom) and isinstance(target.item, t1.Identifier):
            value = typecheck_and_resolve_inner(item.right, ctx=ctx)
            inferred = _widen_type_argument(value.type, loc=item.right.loc, ctx=ctx)
            return ty.ObjectField(target.item.name, inferred, mutable, default=item.right)
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


_REFINEMENT_COMPARISONS = {'>?', '>=?', '<?', '<=?', '=?'}
_INVERTED_REFINEMENT_COMPARISONS = {'=?': 'not=?', '>?': '<=?', '>=?': '<?', '<?': '>=?', '<=?': '>?'}


def _literal_integer_ast(ast: p0.AST) -> int | None:
    """An integer literal, possibly parenthesized or negated, in type position."""
    if isinstance(ast, p0.Block) and ast.kind == '()' and len(ast.inner) == 1:
        return _literal_integer_ast(ast.inner[0])
    if isinstance(ast, p0.Atom) and isinstance(ast.item, t1.Integer):
        return t0.parse_integer(ast.item.value.src, ast.item.value.prefix)
    if (
        isinstance(ast, p0.Prefix)
        and isinstance(ast.op, t1.Operator)
        and ast.op.symbol == '-'
    ):
        inner = _literal_integer_ast(ast.item)
        return None if inner is None else -inner
    return None


def _comparison_proposition(ast: p0.AST, subject_name: str, subject: str, *, ctx: Context, fields: bool = False) -> ty.Proposition | None:
    """`<subject> <op> <int>` (or mirrored) as a proposition; None if not that shape.

    The subject may be spelled as the name itself (`i`, `d`, `length`), as
    `<name>.length`, or as `<name>.field` (a field of the value); with
    ``fields``, a bare other identifier is a field of the value too
    (`Ratio<bottom >? 0>`). Field subjects are validated against the base
    type afterwards (`_check_refinement_subjects`).
    """
    if not isinstance(ast, p0.BinOp):
        return None
    if isinstance(ast.op, t2.InvertedComparisonOp):
        op = _INVERTED_REFINEMENT_COMPARISONS.get(ast.op.op)
        if op is None:
            return None
    elif isinstance(ast.op, t1.Operator) and ast.op.symbol in _REFINEMENT_COMPARISONS:
        op = ast.op.symbol
    else:
        return None

    def identifier(node: p0.AST) -> str | None:
        return node.item.name if isinstance(node, p0.Atom) and isinstance(node.item, t1.Identifier) else None

    def subject_of(node: p0.AST) -> str | None:
        """The proposition subject this side spells, or None."""
        name = identifier(node)
        if name is not None:
            if name == subject_name:
                return subject
            if fields and name != 'length':
                return f'.{name}'
            return None
        if isinstance(node, p0.BinOp) and _operator_symbol(node.op) == '.' and identifier(node.left) == subject_name:
            member = identifier(node.right)
            if member is None:
                return None
            return 'length' if member == 'length' else f'.{member}'
        return None

    left_subject = subject_of(ast.left)
    if left_subject is not None:
        value = _refinement_bound_ast(ast.right)
        if value is None:
            not_implemented(ctx.srcfile, ast.right.loc, 'refinement conditions beyond integer literals and fixed-width `min`/`max`')
        return ty.Proposition(left_subject, op, value)
    right_subject = subject_of(ast.right)
    if right_subject is not None:
        value = _refinement_bound_ast(ast.left)
        if value is None:
            not_implemented(ctx.srcfile, ast.left.loc, 'refinement conditions beyond integer literals and fixed-width `min`/`max`')
        mirrored = {'>?': '<?', '<?': '>?', '>=?': '<=?', '<=?': '>=?'}.get(op, op)
        return ty.Proposition(right_subject, mirrored, value)
    return None


def _refinement_bound_ast(node: p0.AST) -> int | None:
    """A refinement bound: an integer literal, or a fixed-width type's `min`/`max` (`uint64.max`)."""
    literal = _literal_integer_ast(node)
    if literal is not None:
        return literal
    if (
        isinstance(node, p0.BinOp)
        and _operator_symbol(node.op) == '.'
        and isinstance(node.left, p0.Atom)
        and isinstance(node.left.item, t1.Identifier)
        and isinstance(node.right, p0.Atom)
        and isinstance(node.right.item, t1.Identifier)
        and node.right.item.name in {'min', 'max'}
        and (bounds := ty.fixed_integer_bounds(node.left.item.name)) is not None
    ):
        return bounds[0] if node.right.item.name == 'min' else bounds[1]
    return None


def _refinement_comparison_chain(ast: p0.AST) -> list[p0.BinOp] | None:
    """`0 <? length <=? uint64.max` inside a refinement: the pairwise comparisons
    of a one-direction chain (see `_comparison_chain`), or None when `ast` is
    not a chain of two or more."""
    ops: list[p0.BinOp] = []
    node = ast
    while isinstance(node, p0.BinOp) and _comparison_operator(node.op) is not None:
        ops.insert(0, node)
        node = node.left
    if len(ops) < 2:
        return None
    operands = [ops[0].left, *(op.right for op in ops)]
    return [
        p0.BinOp(Span(operands[index].loc.start, operands[index + 1].loc.stop), op.op, operands[index], operands[index + 1])
        for index, op in enumerate(ops)
    ]


def _refinement_conditions(item: p0.AST, *, ctx: Context) -> list[ty.Proposition] | None:
    """All the propositions of one parameterize-block entry (`n >? 0 and n <? 10` is two,
    as is the chain `0 <? n <? 10`), or None."""
    chain = _refinement_comparison_chain(item)
    if chain is not None:
        _validate_refinement_chain(chain, ctx=ctx)
        parts: list[ty.Proposition] = []
        for pair in chain:
            found = _refinement_conditions(pair, ctx=ctx)
            if found is None:
                return None
            parts.extend(found)
        return parts
    if (
        isinstance(item, p0.BinOp)
        and _operator_symbol(item.op) == '=>'
        and isinstance(item.left, p0.Atom)
        and isinstance(item.left.item, t1.Identifier)
        and (body_chain := _refinement_comparison_chain(item.right)) is not None
    ):
        # `i => 0 <? i <? 10`: the lambda body chains the same way
        _validate_refinement_chain(body_chain, ctx=ctx)
        parts = []
        for pair in body_chain:
            found = _refinement_conditions(replace(item, right=pair), ctx=ctx)
            if found is None:
                return None
            parts.extend(found)
        return parts
    if isinstance(item, p0.BinOp) and _operator_symbol(item.op) == 'and':
        left = _refinement_conditions(item.left, ctx=ctx)
        right = _refinement_conditions(item.right, ctx=ctx)
        if left is None or right is None:
            return None
        return [*left, *right]
    if (
        isinstance(item, p0.BinOp)
        and _operator_symbol(item.op) == '=>'
        and isinstance(item.left, p0.Atom)
        and isinstance(item.left.item, t1.Identifier)
        and isinstance(item.right, p0.BinOp)
        and _operator_symbol(item.right.op) == 'and'
    ):
        # `i => i >? 0 and i <? 10`: the lambda body splits the same way
        name = item.left.item.name
        parts = _refinement_conditions(replace(item, right=item.right.left), ctx=ctx)
        rest = _refinement_conditions(replace(item, right=item.right.right), ctx=ctx)
        if parts is None or rest is None:
            return None
        return [*parts, *rest]
    single = _refinement_condition(item, ctx=ctx)
    return None if single is None else [single]


def _validate_refinement_chain(chain: list[p0.BinOp], *, ctx: Context) -> None:
    """A refinement chain reads one way, like a value chain (`_comparison_chain`)."""
    directions: set[str] = set()
    for pair in chain:
        symbol = _comparison_operator(pair.op)
        if symbol not in _CHAIN_COMPARISONS:
            user_error(
                ctx.srcfile,
                'comparison does not chain',
                Pointer(span=pair.op.loc, message=f'`{symbol}` cannot be part of a comparison chain'),
                hint='combine the conditions with `and`',
            )
        if symbol in _CHAIN_RISING:
            directions.add('rising')
        elif symbol in _CHAIN_FALLING:
            directions.add('falling')
    if len(directions) == 2:
        user_error(
            ctx.srcfile,
            'comparison chain changes direction',
            *[Pointer(span=pair.op.loc, message=f'`{_comparison_operator(pair.op)}` is {"rising" if _comparison_operator(pair.op) in _CHAIN_RISING else "falling"}') for pair in chain if _comparison_operator(pair.op) in _CHAIN_RISING | _CHAIN_FALLING],
            hint='a chain reads one way (`0 <? x <? 10`, `10 >? x >=? 0`); write the other comparison with `and`',
        )


def _refinement_condition(item: p0.AST, *, ctx: Context) -> ty.Proposition | None:
    """Classify one parameterize-block entry as a refinement condition.

    Conditions are a one-argument lambda (`i => i >? 0`, about the value), a
    `?`-comparison on `length`, or a `?`-comparison on the declared name;
    anything else is a type parameter.
    """
    if (
        isinstance(item, p0.BinOp)
        and isinstance(item.op, t1.Operator)
        and item.op.symbol == '=>'
        and isinstance(item.left, p0.Atom)
        and isinstance(item.left.item, t1.Identifier)
    ):
        proposition = _comparison_proposition(item.right, item.left.item.name, 'self', ctx=ctx)
        if proposition is None:
            not_implemented(ctx.srcfile, item.right.loc, 'this refinement proposition')
        return proposition
    if isinstance(item, p0.BinOp) and (
        isinstance(item.op, t2.InvertedComparisonOp)
        or (isinstance(item.op, t1.Operator) and item.op.symbol in _REFINEMENT_COMPARISONS)
    ):
        proposition = _comparison_proposition(item, 'length', 'length', ctx=ctx)
        if proposition is None and ctx.refinement_subject is not None:
            # `d:int64<d not=? 0>`, `xs:array<int64 xs.length >? 0>`,
            # `r:Ratio<r.bottom >? 0>`: the declared name is the value
            proposition = _comparison_proposition(item, ctx.refinement_subject, 'self', ctx=ctx)
        if proposition is None:
            # `Ratio<bottom >? 0>`: a bare name is a field of the value
            proposition = _comparison_proposition(item, '', 'self', ctx=ctx, fields=True)
        if proposition is None:
            not_implemented(ctx.srcfile, item.loc, 'this refinement condition')
        return proposition
    return None


def _check_refinement_subjects(base: ty.Type, propositions: list[ty.Proposition], *, loc: Span, ctx: Context) -> None:
    for proposition in propositions:
        if (field_name := proposition.field) is not None:
            current: ty.Type = base
            field: ty.ObjectField | None = None
            for part in field_name.split('.'):
                unfolded = ty.unfold(_union_object_member(ty.strip_refinement(current)))
                field = unfolded.field(part) if isinstance(unfolded, ty.ObjectType) else None
                if field is None:
                    type_error(
                        ctx.srcfile,
                        'refinement subject does not apply',
                        Pointer(span=loc, message=f'`{type_to_dewy(base)}` has no field `{field_name}`'),
                    )
                current = field.type
            assert field is not None
            if proposition.of == 'length':
                if not (field.type == 'array' or field.type == 'string' or isinstance(field.type, (ty.ArrayType, ty.StringType))):
                    type_error(
                        ctx.srcfile,
                        'refinement subject does not apply',
                        Pointer(span=loc, message=f'field `{field_name}` has no `length`'),
                    )
                continue
            if not (isinstance(field.type, str) and ctx.type_system.is_subtype(field.type, 'int')):
                not_implemented(ctx.srcfile, loc, f'refinements on a field of type `{type_to_dewy(field.type)}`')
            continue
        if proposition.subject == 'length' and not (
            base == 'array' or base == 'string' or isinstance(base, (ty.ArrayType, ty.StringType))
        ):
            type_error(
                ctx.srcfile,
                'refinement subject does not apply',
                Pointer(span=loc, message=f'`{type_to_dewy(base)}` has no `length`'),
            )
        if proposition.subject == 'self' and not ctx.type_system.is_subtype(base, 'int'):
            not_implemented(ctx.srcfile, loc, f'value refinements on `{type_to_dewy(base)}`')


def _excluded_literals(type_: ty.Type) -> list[int] | None:
    """The integers `~0` or `~(0 | 1)` exclude; None when the type is not such a negation."""
    if not isinstance(type_, ty.TypeNot):
        return None
    inner = type_.type
    members = list(inner.items) if isinstance(inner, ty.TypeOr) else [inner]
    values: list[int] = []
    for member in members:
        if not isinstance(member, ty.IntegerLiteralType):
            return None
        values.append(member.value)
    return values


def _value_type(type_: ty.Type, *, loc: Span, ctx: Context) -> ty.Type:
    """A type at a value boundary (a binding, parameter, or result annotation).

    A union of integer singletons (`x:1|2|3`, `sign:-1|1`) is a word whose
    value set is its invariant, as for object fields; every other type is
    itself (a mixed union such as `1|2|"fast"` stays a tagged union).
    """
    if isinstance(type_, ty.TypeOr):
        literal_set = _integer_literal_set(type_, loc=loc, ctx=ctx)
        if literal_set is not None:
            return literal_set
    return type_


def _integer_literal_set(union: ty.TypeOr, *, loc: Span, ctx: Context) -> ty.Type | None:
    """`-1|1` or `0|1|2`: a union of integer singletons is a refined word.

    The value set becomes the closed interval plus the excluded gaps, so the
    bounds analysis proves memberships (`sign = -a.sign`) and reads the facts
    (`sign not=? 0`) exactly as for any other refined integer. None when the
    union is not made of integer singletons alone.
    """
    values: list[int] = []
    for member in union.items:
        if not isinstance(member, ty.IntegerLiteralType):
            return None
        values.append(member.value)
    values = sorted(set(values))
    low, high = values[0], values[-1]
    if not (ty.integer_literal_fits(low, 'int64') and ty.integer_literal_fits(high, 'int64')):
        not_implemented(ctx.srcfile, loc, 'integer singleton unions outside the int64 range')
    if high - low > 1024:
        not_implemented(ctx.srcfile, loc, 'integer singleton unions spanning more than 1024 values')
    present = set(values)
    propositions = [ty.Proposition('self', '>=?', low), ty.Proposition('self', '<=?', high)]
    propositions += [ty.Proposition('self', 'not=?', gap) for gap in range(low, high + 1) if gap not in present]
    return _refined('int64', propositions)


def _is_integer_base(type_: ty.Type, *, ctx: Context) -> bool:
    base = ty.strip_refinement(type_)
    return isinstance(base, str) and ctx.type_system.is_subtype(base, 'int')


def _refined(base: ty.Type, propositions: list[ty.Proposition]) -> ty.Type:
    if not propositions:
        return base
    if isinstance(base, ty.RefinedType):
        return ty.RefinedType(base.base, (*base.propositions, *propositions))
    return ty.RefinedType(base, tuple(propositions))


def _describe_proposition(proposition: ty.Proposition) -> str:
    op = proposition.op.replace('not=?', 'not =?')
    subject = proposition.field or ('value' if proposition.subject == 'self' else 'length')
    if proposition.field is not None and proposition.of == 'length':
        subject = f'{proposition.field}.length'
    return f'{subject} {op} {proposition.value}'


def _prove_refinements(node: hir.AST, refined: ty.RefinedType, *, ctx: Context) -> hir.AST:
    """Prove each proposition from compile-time facts, or report a refuted one.

    A proposition the checker cannot decide (a runtime value) becomes an
    `hir.Obligation` for the bounds analysis, which proves it from intervals,
    guards, and length facts — or reports it, like `$assert`.
    """
    if isinstance(node, hir.Obligation) and node.refined == refined:
        return node  # already deferred once (arguments are checked at parsing and again at dispatch)
    pending: list[ty.Proposition] = []
    for proposition in refined.propositions:
        fact: int | None
        if (field_name := proposition.field) is not None:
            literal = node
            field_value: hir.AST | None = None
            for part in field_name.split('.'):
                while isinstance(literal, (hir.ValueCast, hir.RepresentationCast)):
                    literal = literal.expr
                field_value = next((f.value for f in literal.fields if f.name == part), None) if isinstance(literal, hir.ObjectLiteral) else None
                if field_value is None:
                    break
                literal = field_value
            if field_value is None:
                fact = None
            elif proposition.of == 'length':
                fact = (
                    field_value.type.length if isinstance(field_value.type, ty.ArrayType)
                    else _known_string_length(field_value.type) if _is_string_type(field_value.type)
                    else None
                )
            else:
                fact = _constant_integer(field_value, ctx=ctx)
        elif proposition.subject == 'self':
            fact = _constant_integer(node, ctx=ctx)
        else:
            fact = (
                node.type.length if isinstance(node.type, ty.ArrayType)
                else _known_string_length(node.type) if _is_string_type(node.type)
                else None
            )
        requirement = _describe_proposition(proposition)
        if fact is None:
            pending.append(proposition)
            continue
        if not proposition.holds(fact):
            type_error(
                ctx.srcfile,
                'refinement refuted',
                Pointer(
                    span=node.loc,
                    message=f'the {proposition.field or ("value" if proposition.subject == "self" else "length")} is {fact}, but `{requirement}` is required',
                ),
            )
    if not pending:
        return node
    deferred = ty.RefinedType(refined.base, tuple(pending))
    description = ' and '.join(_describe_proposition(p) for p in pending)
    return hir.Obligation(node.loc, node.type, node, deferred, description)


def _canonical_union(type_: ty.TypeOr, *, ctx: Context) -> ty.TypeOr:
    """Spell a recursive alias by reference wherever it is a union member.

    `Node | none` written inside `Node`'s own body already resolves to the
    reference; written elsewhere it resolves to the alias's object type. Both
    must be the same union — the same member order, the same tags — so every
    union member that is a recursive alias's object type becomes its reference.
    """
    if not ctx.named_types:
        return type_
    references = [named for named in ctx.named_types.values() if named._target]

    def canonical(item: ty.TypeExpr) -> ty.TypeExpr:
        if isinstance(item, ty.ObjectType):
            for named in references:
                if named.target == item:
                    return named
        return item

    return ty.TypeOr([canonical(item) for item in type_.items])


def _metatype(ast: p0.AST, *, ctx: Context) -> ty.MetaType | None:
    """`type<Token>`: the type of the types under the minted `Token`, as runtime values."""
    if not (
        isinstance(ast, p0.BinOp)
        and isinstance(ast.op, t2.TypeParamJuxtapose)
        and isinstance(ast.left, p0.Atom)
        and isinstance(ast.left.item, t1.Identifier)
        and ast.left.item.name == 'type'
        and 'type' not in ctx.declarations
        and isinstance(ast.right, p0.Block)
        and ast.right.kind == '<>'
    ):
        return None
    if len(ast.right.inner) != 1:
        user_error(ctx.srcfile, '`type<…>` takes one type', Pointer(span=ast.right.loc, message='the family whose types are the values'))
    family = ty.unfold(ast_to_type(ast.right.inner[0], ctx=ctx))
    if not (isinstance(family, ty.ObjectType) and ty.user_branded(family)):
        user_error(
            ctx.srcfile,
            '`type<…>` needs a minted type',
            Pointer(span=ast.right.inner[0].loc, message=f'`{type_to_dewy(family)}` is not minted with `type of`, so its types are not runtime values'),
        )
    return ty.MetaType(family)


def ast_to_type(ast: p0.AST, *, ctx: Context) -> ty.Type:
    """convert an AST from a position that is expected to be a type into a type"""
    metatype = _metatype(ast, ctx=ctx)
    if metatype is not None:
        return metatype
    if (
        isinstance(ast, p0.BinOp)
        and isinstance(ast.op, t2.TypeParamJuxtapose)
        and isinstance(ast.right, p0.Block)
        and ast.right.kind == '<>'
        and (alias_value := _named_type_alias_value(ast.left, ctx=ctx))
        is not None
    ):
        if isinstance(alias_value, ty.RefinedType) and alias_value.base == 'array':
            # `NonEmptyArray = array<length >? 0>` keeps the element open.
            conditions = [
                proposition
                for item in ast.right.inner
                for proposition in (_refinement_conditions(item, ctx=ctx) or [])
            ]
            parameters = [item for item in ast.right.inner if _refinement_conditions(item, ctx=ctx) is None]
            if len(parameters) != 1:
                type_error(
                    ctx.srcfile,
                    'array type requires an element type',
                    Pointer(span=ast.right.loc, message=f'use `{type_to_dewy(alias_value)}<T>`'),
                )
            element = ast_to_type(parameters[0], ctx=ctx)
            if element in ('int', 'uint'):
                element = 'int64' if element == 'int' else 'uint64'
            return _refined(ty.ArrayType(element, None), [*alias_value.propositions, *conditions])
        if not isinstance(alias_value, ty.GenericTypeAlias):
            entries = [_refinement_conditions(item, ctx=ctx) for item in ast.right.inner]
            if entries and all(entry is not None for entry in entries):
                # `Ratio<bottom >? 0>`, `Positive<i => i <? 10>`: a refinement of the alias's type
                propositions = [proposition for entry in entries for proposition in (entry or [])]
                base = ty.strip_refinement(alias_value)
                if isinstance(base, ty.TypeOr) and propositions and all(p.field is not None for p in propositions):
                    # `bigint<sign =? 1>`: a field of the union's object member
                    # refines that member — the literal member has no fields
                    member = _union_object_member(base)
                    if member is not base:
                        _check_refinement_subjects(member, propositions, loc=ast.loc, ctx=ctx)
                        return _refined(member, propositions)
                _check_refinement_subjects(base, propositions, loc=ast.loc, ctx=ctx)
                return _refined(alias_value, propositions)
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
            if name == 'rational' and RATIONAL_TYPE_NAME in ctx.binding_scopes:
                return _rational_type(ctx, ast.loc)
            if name == 'fixed' and FIXED_TYPE_NAME in ctx.binding_scopes:
                return _fixed_type(ctx, ast.loc)
            if name == 'bigint' and BIGINT_TYPE_NAME in ctx.binding_scopes:
                return _bigint_type(ctx, ast.loc)
            if name in ctx.type_system._named_types or name in (ty.VOID_TYPE, ty.INFERRED_TYPE):
                return name
            # an unknown name is an error here, not a fresh nominal type: the
            # annotation `dict<BasePrefix …>` with a misspelled alias would
            # otherwise fail far away, on the representation the name cannot have
            import difflib
            known = {
                *ctx.type_system._named_types,
                *builtins.builtin_type_aliases,
                *(candidate for candidate, binding in ctx.binding_scopes.items() if getattr(binding, 'type_value', None) is not None or binding.id in ctx.type_alias_asts),
            }
            suggestions = difflib.get_close_matches(name, known, n=1, cutoff=0.6)
            user_error(
                ctx.srcfile,
                f'undefined type `{name}`',
                Pointer(span=ast.loc, message='no type of this name is in scope'),
                hint=f'did you mean `{suggestions[0]}`?' if suggestions else None,
            )

        case p0.Atom(item=t1.Integer(value=value)):
            return ty.IntegerLiteralType(
                t0.parse_integer(value.src, value.prefix)
            )

        case p0.Prefix(op=t1.Operator(symbol='-'), item=p0.Atom(item=t1.Integer(value=value))):
            # `-1` in `sign:-1|1`: a negative singleton
            return ty.IntegerLiteralType(-t0.parse_integer(value.src, value.prefix))

        case p0.Atom(item=t1.String(content=content)):
            # a string literal in type position is its singleton type
            from .unicode.graphemes import unicode_scalars

            try:
                unicode_scalars(content)
            except ValueError:
                user_error(
                    ctx.srcfile,
                    'string literal contains a Unicode surrogate',
                    Pointer(span=ast.item.loc, message='Dewy strings contain Unicode scalar values only'),
                )
            return ty.StringLiteralType(content)
        case p0.Atom(item=t1.BasedString() as literal):
            packed, _digits = _pack_based_string(literal, ctx=ctx)
            return ty.BinaryLiteralType(packed)
        case p0.Atom(item=t1.Bool()):
            not_implemented(ctx.srcfile, ast.loc, 'a boolean literal type (use `bool`)')
        case p0.Block(kind='[]', inner=items):
            seen: dict[str, Span] = {}
            fields: list[ty.ObjectField] = []
            methods: list[ty.MethodSpec] = []
            for item in items:
                overload_row = _method_row(item, symbol='&=')
                if overload_row is not None:
                    # `__as__ &= ():>int64 => …`: another method of the same name
                    # (a conversion to another target); no duplicate check
                    member_name, literal = overload_row
                    methods.append(ty.MethodSpec(member_name, literal))
                    continue
                method_row = _method_row(item)
                if method_row is not None:
                    member_name, literal = method_row
                    methods.append(ty.MethodSpec(member_name, literal))
                else:
                    field = _object_type_member(item, ctx=ctx)
                    member_name = field.name
                    fields.append(field)
                previous = seen.get(member_name)
                if previous is not None:
                    user_error(
                        ctx.srcfile,
                        f'duplicate object member `{member_name}`',
                        Pointer(span=item.loc, message='this member repeats a name'),
                        Pointer(span=previous, message='the earlier member is here'),
                    )
                seen[member_name] = item.loc
            return ty.ObjectType(tuple(fields), methods=tuple(methods))

        case p0.BinOp(
            op=t2.TypeParamJuxtapose(),
            left=p0.Atom(item=t1.Identifier(name='array')),
            right=p0.Block(kind='<>', inner=items),
        ):
            element_ast: p0.AST | None = None
            length: int | None = None
            conditions: list[ty.Proposition] = []
            for item in items:
                entry_conditions = _refinement_conditions(item, ctx=ctx)
                if entry_conditions is not None:
                    for condition in entry_conditions:
                        if condition.subject != 'length':
                            not_implemented(ctx.srcfile, item.loc, 'value refinements on arrays')
                        conditions.append(condition)
                    continue
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
                if conditions and length is None:
                    return _refined('array', conditions)  # element supplied on application
                user_error(
                    ctx.srcfile,
                    'array type requires an element type',
                    Pointer(span=ast.loc, message='use `array<T>`'),
                )
            element = _word_element_type(ast_to_type(element_ast, ctx=ctx))
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
                    hint=_ELEMENT_TYPE_HINT,
                )
            return _refined(ty.ArrayType(element, length), conditions)

        case p0.BinOp(
            op=t2.TypeParamJuxtapose(),
            left=p0.AST() as base_ast,
            right=p0.Block(kind='<>', inner=items),
        ) if items and all(_refinement_conditions(item, ctx=ctx) is not None for item in items):
            # `int< i => i >? 0 >`: a parameterize block holding only conditions
            base = ast_to_type(base_ast, ctx=ctx)
            propositions = [
                proposition
                for item in items
                for proposition in (_refinement_conditions(item, ctx=ctx) or [])
            ]
            _check_refinement_subjects(ty.strip_refinement(base), propositions, loc=ast.loc, ctx=ctx)
            return _refined(base, propositions)

        case p0.BinOp(
            op=t2.TypeParamJuxtapose(),
            left=p0.Atom(item=t1.Identifier(name='range')),
            right=p0.Block(kind='<>', inner=[element_ast]),
        ):
            return ty.TypeParameterize(
                'range',
                [ast_to_type(element_ast, ctx=ctx)],
            )

        case p0.BinOp(
            op=t2.TypeParamJuxtapose(),
            left=p0.Atom(item=t1.Identifier(name='set')),
            right=p0.Block(kind='<>', inner=[element_ast]),
        ):
            return ty.set_type(_word_element_type(ast_to_type(element_ast, ctx=ctx)))

        case p0.BinOp(
            op=t2.TypeParamJuxtapose(),
            left=p0.Atom(item=t1.Identifier(name='dict')),
            right=p0.Block(kind='<>', inner=[key_ast, value_ast]),
        ):
            return ty.dict_type(
                _word_element_type(ast_to_type(key_ast, ctx=ctx)),
                _word_element_type(ast_to_type(value_ast, ctx=ctx)),
            )

        case p0.BinOp(
            op=t2.TypeParamJuxtapose(),
            left=p0.Atom(item=t1.Identifier(name='rational')),
            right=p0.Block(kind='<>', inner=[part_ast]),
        ) if 'rational' not in ctx.declarations:
            # `rational<int64>`: word parts, arithmetic may `Overflow`; `rational<bigint>`: the abstract representation
            part = ast_to_type(part_ast, ctx=ctx)
            if part == 'int64':
                return _word_rational_type(ctx, ast.loc)
            if _is_bigint(part, ctx=ctx) or part == 'int':
                return _rational_type(ctx, ast.loc)
            user_error(
                ctx.srcfile,
                'rational parts must be `int64` or `bigint`',
                Pointer(span=part_ast.loc, message=f'`{type_to_dewy(part)}` is not a supported part type'),
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
            def numeric(type_: ty.Type) -> bool:
                return (
                    ctx.type_system.is_subtype(type_, 'number')
                    or _is_rational(type_, ctx=ctx)
                    or _is_fixed(type_, ctx=ctx)
                )
            if isinstance(left, ty.DimensionType):
                if isinstance(right, ty.QuantityType):
                    return ty.QuantityType(
                        right.number,
                        ty.multiply_dimensions(left, right.dimension),
                    )
                if numeric(right):
                    return ty.QuantityType(right, left)
            if isinstance(right, ty.DimensionType):
                if isinstance(left, ty.QuantityType):
                    return ty.QuantityType(
                        left.number,
                        ty.multiply_dimensions(left.dimension, right),
                    )
                if numeric(left):
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
                union = ty.TypeOr(left.items + right.items)
            elif isinstance(left, ty.TypeOr):
                union = ty.TypeOr(left.items + [right])
            elif isinstance(right, ty.TypeOr):
                union = ty.TypeOr([left] + right.items)
            else:
                union = ty.TypeOr([left, right])
            return _canonical_union(union, ctx=ctx)
        
        case p0.BinOp(op=t1.Operator(symbol='and'|'&')):
            left = ast_to_type(ast.left, ctx=ctx)
            right = ast_to_type(ast.right, ctx=ctx)
            excluded = _excluded_literals(right)
            if excluded is not None and isinstance(left, ty.TypeOr):
                # `bigint & ~0`: the union without its literal member
                remaining = [
                    member for member in left.items
                    if not (isinstance(member, ty.IntegerLiteralType) and member.value in excluded)
                ]
                if len(remaining) == len(left.items):
                    type_error(
                        ctx.srcfile,
                        'excluded value is not a member of the union',
                        Pointer(span=ast.right.loc, message=f'`{type_to_dewy(left)}` has no such member'),
                    )
                return remaining[0] if len(remaining) == 1 else ty.TypeOr(remaining)
            if excluded is not None and _is_integer_base(left, ctx=ctx):
                # `int64 & ~0`: the structural spelling of `int64<i => i not=? 0>`
                return _refined(left, [ty.Proposition('self', 'not=?', value) for value in excluded])
            excluded = _excluded_literals(left)
            if excluded is not None and _is_integer_base(right, ctx=ctx):
                return _refined(right, [ty.Proposition('self', 'not=?', value) for value in excluded])
            merged = _intersect_object_types([left, right], loc=ast.loc, ctx=ctx)
            if merged is not None:
                return merged
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

        case p0.Prefix(op=t1.Operator(symbol='type of')):
            user_error(
                ctx.srcfile,
                '`type of` mints only in an alias declaration',
                Pointer(span=ast.loc, message='a fresh type needs a name to be referred to by'),
                hint='write `let Name = type of ...` (or `Name:type = ...`) and use `Name` here',
            )
        
        case p0.Postfix(op=t1.Operator(symbol='?')):
            # `T?` is the optional `T | none`
            return ty.optional(ast_to_type(ast.item, ctx=ctx))

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
    if not isinstance(signature, p0.Block): return collect_function_signature_args(p0.Block(signature.loc, [signature], '()', None), ctx=ctx)

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
                    type=_value_type(ast_to_type(item.right, ctx=replace(ctx, refinement_subject=name)), loc=item.right.loc, ctx=ctx),
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
                param_type = _value_type(ast_to_type(typeexpr, ctx=ctx), loc=typeexpr.loc, ctx=ctx)
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
            case p0.BinOp(op=t1.Operator(symbol=':'), left=p0.Block(kind='()')):
                user_error(
                    ctx.srcfile,
                    'a function result type is written `:>`',
                    Pointer(span=item.op.loc, message='`:` here reads as an annotation on the parameter list'),
                    hint='write `(params):>T => body`',
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
                # `top` (an intrinsic's untyped address parameter) says nothing about the argument
                literal_expected = ty.strip_refinement(expected_arg) if expected_arg is not None and expected_arg != ty.TOP_TYPE else None
                arg = typecheck_and_resolve_inner(
                    value,
                    ctx=argument_ctx,
                    expected=literal_expected,
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
                literal_expected = ty.strip_refinement(expected_arg) if expected_arg is not None else None
                arg = typecheck_and_resolve_inner(
                    item,
                    ctx=argument_ctx,
                    expected=literal_expected,
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
    declared = ty.unfold(left.type.ret)
    methods = declared.methods if isinstance(declared, ty.ObjectType) else ()
    return ty.PathLiteralType(argument.type.value, methods=methods)   # `p"…"` has `Path`'s methods


def _prepared_single_argument(argument: hir.AST, *, ctx: Context) -> hir.AST:
    """An interpolation field as it is printed: rationals materialized, abstract
    integers as words, dimensions erased."""
    if _is_compile_time_rational(argument.type):
        argument = _materialize_rational(argument, ctx=ctx)
    if argument.type in ('int', 'uint'):
        # arbitrary-precision integers print as 64-bit words; the bounds
        # analysis proves the value fits
        argument = hir.ValueCast(argument.loc, 'int64' if argument.type == 'int' else 'uint64', argument)
    if isinstance(argument.type, ty.QuantityType):
        # Dimensions are erased at runtime; the number prints in its canonical scale.
        argument = _strip_dimension(argument)
    return argument


def _callable_methods(func: hir.AST, *, ctx: Context) -> list[ty.FunctionType]:
    if isinstance(func.type, ty.FunctionType):
        return [func.type]
    if isinstance(func.type, ty.OverloadType):
        return list(func.type.methods)
    type_error(
        ctx.srcfile,
        'call target is not a function',
        Pointer(
            span=func.loc,
            message=f'this has type `{type_to_dewy(func.type)}`, which is not callable',
        ),
    )


# ---------------------------------------------------------------- printing values
# `print` and `printl` are ordinary generic functions in `library/io.dewy`: a
# value prints by its type, and anything else as its `as string` text. The
# compiler's part is the conversion — a container or a plain object converts
# to its literal syntax (`_structure_string`: the library's `_array_as_string`
# family, and a hidden field-by-field conversion synthesized per object type)
# — and one representation choice: an interpolated argument of `print` is
# written part by part, each part passed to `print`, instead of building the
# string first.

_STRUCTURE_STRINGS = {'array': '_array_as_string', 'set': '_set_as_string', 'dict': '_dict_as_string'}
_MATERIALIZED_INTEGERS = frozenset({'int', 'uint', 'int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64'})
_NUMBER_OBJECT_NAMES = (RATIONAL_TYPE_NAME, BIG_RATIONAL_TYPE_NAME, FIXED_TYPE_NAME, BIGINT_TYPE_NAME)


def _structure_members(type_: ty.TypeExpr) -> tuple[str, list[ty.TypeExpr]] | None:
    """The container kind and member types of a container type, else None."""
    unfolded = ty.unfold(ty.strip_refinement(type_))
    if isinstance(unfolded, ty.ArrayType):
        return 'array', [unfolded.element]
    key_value = ty.dict_key_value(unfolded)
    if key_value is not None:
        return 'dict', [key_value[0], key_value[1]]
    element = ty.set_element(unfolded)
    if element is not None:
        return 'set', [element]
    return None


def _plain_object_type(type_: ty.TypeExpr) -> ty.ObjectType | None:
    """The object type of a value that converts field by field (no compiler-provided family)."""
    unfolded = ty.unfold(ty.strip_refinement(type_))
    if isinstance(unfolded, ty.ObjectType) and (unfolded.brand is None or ty.user_branded(unfolded)):
        return unfolded
    return None


def _quoted_member(type_: ty.TypeExpr) -> bool:
    """String members print quoted inside a structure (`["a" "b"]`, `[name="x"]`);
    for a union member the flag applies to its string alternatives."""
    plain = ty.strip_refinement(type_)
    if ty.string_valued(plain):
        return True
    members = ty.runtime_union_members(plain) or (('none', ty.optional_payload(plain)) if ty.optional_payload(plain) is not None else ())
    return any(member != 'none' and ty.string_valued(member) for member in members)


def _number_object(type_: ty.TypeExpr, *, ctx: Context) -> str | None:
    """The name of the prelude number object (`Rational`, `BigInt`, …) values
    of this type are, else None: they print through their own `print` arm but
    have no string form yet."""
    for name in _NUMBER_OBJECT_NAMES:
        binding = ctx.binding_scopes.get(name)
        if binding is not None and binding.type_value is not None and not isinstance(binding.type_value, ty.GenericTypeAlias):
            if ctx.type_system.is_subtype(type_, binding.type_value):
                return name
    return None


def _unconvertible_part(type_: ty.TypeExpr, *, ctx: Context, seen: frozenset[str] = frozenset()) -> ty.TypeExpr | None:
    """The type — a member, a field, or `type_` itself — that keeps a value of
    `type_` from converting to string as a structure, else None."""
    plain = ty.strip_refinement(type_)
    if _is_string_type(plain) or ty.string_valued(plain) or plain == 'bool' or isinstance(plain, ty.IntegerLiteralType) or (isinstance(plain, str) and plain in _MATERIALIZED_INTEGERS):
        return None
    if isinstance(plain, (ty.FunctionType, ty.OverloadType)):
        return None   # a function field prints as its type's spelling
    if isinstance(ty.optional_payload(plain), (ty.FunctionType, ty.OverloadType)):
        return None   # `none` or the spelling
    if isinstance(plain, ty.MetaType):
        return None   # a type value prints as its name
    if _optional_container_element(plain):
        return None   # an optional member: `none` or its payload's text
    if _union_container_element(plain):
        found = ty.runtime_union_members(plain)
        assert found is not None
        for member in found:
            if member == 'none':
                continue
            bad = _unconvertible_part(member, ctx=ctx, seen=seen)
            if bad is not None:
                return bad
        return None
    if _number_object(plain, ctx=ctx) is not None:
        return plain
    members = _structure_members(plain)
    if members is not None:
        for member in members[1]:
            if _structure_members(member) is not None:
                return member   # iteration over container members is not implemented
            bad = _unconvertible_part(member, ctx=ctx, seen=seen)
            if bad is not None:
                return bad
        return None
    object_type = _plain_object_type(plain)
    if object_type is not None:
        if _conversion_method_binding(object_type, ty.StringType(), Span(0, 0), ctx=ctx) is not None:
            return None
        key = repr(plain)
        if key in seen:
            return None
        for field_ in object_type.fields:
            bad = _unconvertible_part(field_.type, ctx=ctx, seen=seen | {key})
            if bad is not None:
                return bad
        return None
    return plain


def _library_call(
    name: str,
    arguments: list[hir.AST],
    loc: Span,
    *,
    ctx: Context,
    expected_return: ty.TypeExpr | None = None,
) -> hir.FunctionCall:
    """A call to a prelude function by name with checked arguments; a generic
    is instantiated for them (and for `expected_return` when the arguments do
    not determine every type parameter)."""
    func = tcr_identifier(t1.Identifier(loc, name), ctx=ctx)
    methods = _callable_methods(func, ctx=ctx)
    pos_types = [require_valued(argument.type, ctx.srcfile, argument.loc, 'function call argument') for argument in arguments]
    result = ctx.type_system.match_best_function(methods, pos_types, {}, expected_return=expected_return)
    if isinstance(func.type, ty.FunctionType) and func.type.type_params:
        func, result = _instantiate_generic_call(func, result, pos_types, {}, expected_return, ctx=ctx)
    contextual = [
        argument if isinstance(argument, hir.Place) else check_against(argument, param.type, ctx=ctx)
        for argument, param in zip(arguments, result.method.pos_or_kw, strict=True)
    ]
    return hir.FunctionCall(
        loc,
        ty.strip_refinement(result.method.ret),
        func,
        apply_promotions(contextual, result.promote_pos),
        {},
        result.method_index if isinstance(func.type, ty.OverloadType) else None,
    )


def _structure_string(value: hir.AST, loc: Span, *, ctx: Context) -> hir.AST | None:
    """`value as string` for a container or a plain object: the call building
    its literal syntax, else None. A member that cannot convert is an error
    here, on the value, rather than inside the generated code."""
    members = _structure_members(value.type)
    object_type = _plain_object_type(value.type) if members is None else None
    if members is None and object_type is None:
        return None
    if _number_object(value.type, ctx=ctx) is not None:
        return None   # prints through its own `print` arm; no string form yet
    bad = _unconvertible_part(value.type, ctx=ctx)
    if bad is not None:
        number = _number_object(bad, ctx=ctx)
        subject = 'this' if bad == ty.strip_refinement(value.type) else f'its member of type `{number or type_to_dewy(bad)}`'
        detail = (
            f'{subject} prints but does not convert to string yet'
            if number is not None
            else f'its members of type `{type_to_dewy(bad)}` are containers, which a loop cannot visit yet'
            if _structure_members(bad) is not None
            else f'this has type `{type_to_dewy(bad)}`, which does not convert to string'
            if subject == 'this'
            else f'{subject} does not convert to string'
        )
        type_error(
            ctx.srcfile,
            'no string conversion for this value',
            Pointer(span=value.loc, message=detail),
            hint='give the type a conversion method: `__as__ = ():>string => …`',
        )
    if members is not None:
        kind, member_types = members
        flags = [hir.Bool(loc, 'bool', _quoted_member(member)) for member in member_types]
        return _library_call(_STRUCTURE_STRINGS[kind], [value, *flags], loc, ctx=ctx)
    assert object_type is not None
    conversion = _object_string(value.type, object_type, loc, ctx=ctx)
    conversion_type = conversion.type
    assert isinstance(conversion_type, ty.FunctionType)
    callee = hir.ExpressedIdentifier(loc, conversion_type, conversion.name, binding_id=conversion.id)
    argument = check_against(value, conversion_type.pos_or_kw[0].type, ctx=ctx)
    return hir.FunctionCall(loc, ty.strip_refinement(conversion_type.ret), callee, [argument], {})


def _object_string(type_: ty.TypeExpr, object_type: ty.ObjectType, loc: Span, *, ctx: Context) -> sb.Binding:
    """The hidden function building an object's literal syntax field by field
    — `[x=1 y="a"]`, one per type — synthesized as Dewy over a hidden alias of
    the type and hoisted like a generic instance."""
    plain = ty.strip_refinement(type_)
    key = repr(plain)
    existing = ctx.object_strings.get(key)
    if existing is not None:
        return existing
    module_ctx = ctx.module if ctx.module is not None else ctx
    number = len(ctx.object_strings) + 1
    shape = f'__dewy_shape_{number}'
    alias = ctx.binding_registry.allocate_param(shape, ty.TYPE_TYPE, loc)
    alias.type_value = plain
    module_ctx.declarations.maps[0][shape] = ty.TYPE_TYPE
    module_ctx.binding_scopes.maps[0][shape] = alias
    # a minted type's value carries its name (`Name[text="x"]`; an empty one is just `Whitespace`)
    brand = object_type.brand if ty.user_branded(object_type) else ''
    lines = [f'(__dewy_value:{shape}):>string => {{', '    let __dewy_pieces:array<string> = []']
    for index, field_ in enumerate(object_type.fields):
        prefix = (f'{brand}[' if index == 0 else ' ') + field_.name + '='
        lines.append(f'    __dewy_pieces.push"{prefix}"')
        function_payload = ty.optional_payload(field_.type)
        if isinstance(field_.type, (ty.FunctionType, ty.OverloadType)) or isinstance(function_payload, (ty.FunctionType, ty.OverloadType)):
            # a function value prints as its type's spelling, as one converts
            # to string (an optional one: `none` or the spelling)
            spelled_type = function_payload if isinstance(function_payload, (ty.FunctionType, ty.OverloadType)) else field_.type
            spelled = type_to_dewy(spelled_type).replace('\\', '\\\\').replace('"', '\\"').replace('{', '\\{').replace('}', '\\}')
            if function_payload is not None:
                lines.append(f'    __dewy_pieces.push(if __dewy_value.{field_.name} is? none "none" else "{spelled}")')
            else:
                lines.append(f'    __dewy_pieces.push"{spelled}"')
            continue
        text = f"'{{__dewy_value.{field_.name}}}'"
        lines.append(f'    __dewy_pieces.push({f"_quoted({text})" if _quoted_member(field_.type) else text})')
    lines.append(f'    __dewy_pieces.push"{"]" if object_type.fields else brand or "[]"}"')
    lines += ['    return __dewy_pieces.join', '}']
    # parsed at the use site's offset, so a report on it points there
    parsed = p0.parse(SrcFile(None, ' ' * loc.start + '\n'.join(lines) + '\n'))
    literal = parsed.inner[0]
    assert isinstance(literal, p0.BinOp)
    ctx.synthesized.append(literal)
    name = f'__dewy_object_string_{number}'
    binding = ctx.binding_registry.allocate(_fresh_syntax(ctx), name, 'function', loc)
    binding.type = signature_of(literal, ctx=module_ctx)   # known before the body: a field may hold the type again
    ctx.object_strings[key] = binding
    checked = tcr_function_literal(literal, ctx=module_ctx)
    binding.type = checked.type
    declaration = hir.Declare(loc, ty.VOID_TYPE, 'let', name, None, checked, binding_id=binding.id)
    binding.declaration = declaration
    binding.function = checked
    ctx.generic_instances.append(declaration)
    return binding


def _tcr_output_call(left: hir.AST, right: p0.AST, *, ctx: Context) -> hir.AST | None:
    """`print"…{x}…"` / `printl"…{x}…"`: the interpolation is written part by
    part — each literal chunk and field passed to `print` — rather than built
    into one string first. A representation choice only; nothing else about
    these calls is special."""
    if not (
        isinstance(left, hir.ExpressedIdentifier)
        and left.name in {'print', 'printl'}
        and isinstance(left.type, ty.FunctionType)
        and left.type.type_params
    ):
        return None
    items = list(right.inner) if isinstance(right, p0.Block) and right.kind == '()' else [right]
    if len(items) != 1 or not isinstance(items[0], p0.IString):
        return None
    interpolation = tcr_istring(items[0], ctx=ctx)
    loc = Span(left.loc.start, right.loc.stop)
    parts = list(interpolation.parts)
    if left.name == 'printl':
        parts.append(hir.String(loc, ty.StringLiteralType('\n'), '\n'))
    statements = [
        _library_call('print', [_prepared_single_argument(part, ctx=ctx)], part.loc, ctx=ctx)
        for part in parts
    ]
    return hir.Block(loc, ty.VOID_TYPE, statements, False)


def _construction_arguments(arguments: p0.AST) -> p0.AST:
    """`Protocol[let eat = …]`: a field spelled as a declaration, as an untyped
    object literal accepts it, is the keyword argument `eat = …`."""
    if not isinstance(arguments, p0.Block):
        return arguments
    items = [
        item.parts[1] if _is_top_level_declare(item) and isinstance(item, p0.KeywordExpr) and len(item.parts) == 2 else item
        for item in arguments.inner
    ]
    return replace(arguments, inner=items) if items != list(arguments.inner) else arguments


def _type_constructor_target(ast: p0.AST, *, ctx: Context) -> hir.TypeValue | None:
    """`Span` in call position, when `Span` names an object type: the value being called is the type."""
    if not (isinstance(ast, p0.Atom) and isinstance(ast.item, t1.Identifier)):
        return None
    binding = ctx.binding_scopes.get(ast.item.name)
    if binding is None or binding.type_value is None or isinstance(binding.type_value, ty.GenericTypeAlias):
        return None
    candidate = hir.TypeValue(ast.loc, ty.TYPE_TYPE, binding.type_value, ast.item.name)
    return candidate if _constructed_object_type(candidate) is not None else None


def _reject_abstract_construction(left: hir.AST, object_type: ty.ObjectType, *, ctx: Context) -> None:
    if object_type.brand in ty.USER_ABSTRACT_BRANDS:
        children = [child for child in ty.brand_children(object_type.brand) if ty.brand_concrete(child)]
        user_error(
            ctx.srcfile,
            f'`{object_type.brand}` is abstract',
            Pointer(span=left.loc, message='it was minted `$abstract`, so it has no values of its own'),
            hint=('construct one of its children: ' + ', '.join(f'`{child}`' for child in children)) if children else 'mint a child with `type of ' + object_type.brand + '`',
        )


def _constructed_object_type(left: hir.AST) -> ty.ObjectType | None:
    """The object type a call target names, when calling it constructs a value."""
    if not isinstance(left, hir.TypeValue) or isinstance(left.value, ty.GenericTypeAlias):
        return None
    unfolded = ty.unfold(left.value)
    if isinstance(unfolded, ty.ObjectType) and (unfolded.brand is None or ty.user_branded(unfolded)):
        return unfolded
    return None


def _tcr_type_constructor_call(
    left: hir.TypeValue,
    object_type: ty.ObjectType,
    right: p0.AST,
    *,
    ctx: Context,
) -> hir.AST:
    """`Span(1 9)` / `Span(stop=9 start=1)`: the field list read as the constructor's signature.

    Positional arguments fill fields in declaration order, keywords name
    them, and a field left out takes its declared default (checked in field
    order, so a default may use earlier fields). The call becomes the object
    literal `[start=1 stop=9]` checked against the type.
    """
    overload = _select_constructor_overload(left, object_type, right, ctx=ctx)
    if overload is not None:
        return tcr_function_call(overload, right, ctx=ctx)
    items = right.inner if isinstance(right, p0.Block) else [right]
    given: dict[str, p0.AST] = {}
    positional: list[p0.AST] = []
    for item in items:
        if (
            isinstance(item, p0.BinOp)
            and _operator_symbol(item.op) == '='
            and isinstance(item.left, p0.Atom)
            and isinstance(item.left.item, t1.Identifier)
        ):
            name = item.left.item.name
            if name in given:
                user_error(ctx.srcfile, f'field `{name}` is given twice', Pointer(span=item.loc, message='this repeats an earlier argument'))
            if not any(f.name == name for f in object_type.fields):
                user_error(ctx.srcfile, f'`{(left.name or type_to_dewy(left.value))}` has no field `{name}`', Pointer(span=item.left.loc, message='unknown field'))
            given[name] = item.right
        else:
            positional.append(item)
    if len(positional) > len(object_type.fields):
        user_error(
            ctx.srcfile,
            'too many constructor arguments',
            Pointer(span=positional[len(object_type.fields)].loc, message=f'`{(left.name or type_to_dewy(left.value))}` has {len(object_type.fields)} fields'),
        )
    for field_, value in zip(object_type.fields, positional):
        if field_.name in given:
            user_error(ctx.srcfile, f'field `{field_.name}` is given twice', Pointer(span=value.loc, message='this positional argument names a field also given by keyword'))
        given[field_.name] = value
    literal_items: list[p0.AST] = []
    for field_ in object_type.fields:
        value = given.get(field_.name)
        if value is None:
            if field_.default is None:
                user_error(
                    ctx.srcfile,
                    f'missing constructor argument `{field_.name}`',
                    Pointer(span=right.loc, message=f'`{(left.name or type_to_dewy(left.value))}` needs `{field_.name}:{type_to_dewy(field_.type)}`'),
                    hint='give it positionally, by keyword, or declare a default in the type (`name:type = default`)',
                )
            value = field_.default
            assert isinstance(value, p0.AST)
        loc = Span(right.loc.start, right.loc.stop)
        literal_items.append(p0.BinOp(loc, t1.Operator(loc, '='), p0.Atom(loc, t1.Identifier(loc, field_.name)), value))
    literal = p0.Block(right.loc, literal_items, '[]', None)
    ctx.synthesized.append(literal)
    return typecheck_and_resolve_inner(literal, ctx=ctx, expected=left.value)


def _include_bytes_call(ast: p0.AST) -> p0.AST | None:
    """The argument block of `$include_bytes(…)` when ``ast`` is that expression."""
    if (
        isinstance(ast, p0.BinOp)
        and isinstance(ast.op, (t2.QJuxtapose, t2.CallJuxtapose))
        and isinstance(ast.left, p0.Atom)
        and isinstance(ast.left.item, t1.Metatag)
        and ast.left.item.name == 'include_bytes'
    ):
        return ast.right
    return None


def _tcr_include_bytes(loc: Span, right: p0.AST, *, ctx: Context) -> hir.AST:
    """`$include_bytes(p"…")`: a file's bytes as a compile-time binary literal.

    The path must be known at compile time — today a path literal (`p"…"`
    or `p(text)` with a literal argument); a relative path is resolved
    against the source file. The bytes are read now (their length is part of
    the type, `BinaryLiteralType`), and the target embeds the file itself
    rather than a spelled-out literal.
    """
    pos_args, kw_args, _ = parse_call_arguments(right, ctx=ctx)
    if kw_args or len(pos_args) != 1:
        user_error(ctx.srcfile, '`$include_bytes` takes one path', Pointer(span=right.loc, message='write `$include_bytes(p"…")`'))
    argument = _unwrap_literal_value(pos_args[0])
    path_text: str | None = None
    if isinstance(argument.type, ty.PathLiteralType):
        path_text = argument.type.value
    elif isinstance(argument.type, ty.ObjectType):
        path_field = argument.type.field('path')
        if path_field is not None and isinstance(path_field.type, ty.StringLiteralType):
            path_text = path_field.type.value
    if path_text is None:
        user_error(
            ctx.srcfile,
            '`$include_bytes` needs a compile-time path',
            Pointer(span=pos_args[0].loc, message=f'this has type `{type_to_dewy(pos_args[0].type)}`'),
            hint='a path literal such as `p"data/table.bin"` (relative to this source file)',
        )
    included = Path(path_text)
    if not included.is_absolute():
        base = Path(str(ctx.srcfile.path)).resolve().parent if ctx.srcfile.path is not None else Path.cwd()
        included = (base / included).resolve()
    if not included.is_file():
        user_error(ctx.srcfile, 'included file not found', Pointer(span=pos_args[0].loc, message=f'no such file: {included}'))
    content = included.read_bytes()
    return hir.BasedString(loc, ty.BinaryLiteralType(content), t0.base16, content.hex(), content, include_path=str(included))


def tcr_function_call(left: hir.AST, right: p0.AST, *, ctx: Context, expected: ty.Type|None=None) -> hir.AST:
    if isinstance(left, hir.Block) and not left.scoped and len(left.items) == 1:
        left = left.items[0]

    receiver: hir.AST | None = None
    if isinstance(left, hir.BoundMethod):
        receiver = left.receiver
        left = left.function

    constructed = _constructed_object_type(left)
    if constructed is not None:
        assert isinstance(left, hir.TypeValue)
        _reject_abstract_construction(left, constructed, ctx=ctx)
        return _tcr_type_constructor_call(left, constructed, right, ctx=ctx)
    if receiver is None and isinstance(ty.unfold(ty.strip_refinement(left.type)), ty.MetaType):
        # `kind(src=… idx=…)`: construct whichever type under the family `kind` names
        metatype = ty.unfold(ty.strip_refinement(left.type))
        assert isinstance(metatype, ty.MetaType)
        constructor = _brand_constructor(metatype.family, left.loc, ctx=ctx)
        assert isinstance(constructor.type, ty.FunctionType)
        function = hir.ExpressedIdentifier(left.loc, constructor.type, constructor.name, binding_id=constructor.id)
        bound = hir.BoundMethod(left.loc, replace(constructor.type, pos_or_kw=constructor.type.pos_or_kw[1:]), function, left)
        return tcr_function_call(bound, right, ctx=ctx, expected=expected)

    if receiver is None:
        output = _tcr_output_call(left, right, ctx=ctx)
        if output is not None:
            return output

    methods: list[ty.FunctionType]
    if isinstance(left.type, ty.FunctionType):
        methods = [left.type]
    elif isinstance(left.type, ty.OverloadType):
        methods = left.type.methods
    else:
        type_error(ctx.srcfile, 'call target is not a function',
            Pointer(span=left.loc, message=f'this has type `{type_to_dewy(left.type)}`, which is not callable'))

    contextual_method = methods[0] if len(methods) == 1 and not methods[0].type_params else None
    if receiver is not None and contextual_method is not None:
        # the arguments written at the call site do not include `self`
        contextual_method = replace(contextual_method, pos_or_kw=contextual_method.pos_or_kw[1:])
    pos_args, kw_args, argument_order = parse_call_arguments(
        right,
        ctx=ctx,
        method=contextual_method,
    )
    if receiver is not None:
        # a method call: the receiver is the hidden first parameter `self`
        self_param = methods[0].pos_or_kw[0]
        if self_param.place:
            if not isinstance(receiver, (hir.ExpressedIdentifier, hir.MemberAccess)):
                user_error(
                    ctx.srcfile,
                    'this method changes the object, so it needs a place',
                    Pointer(span=receiver.loc, message='this value is not a binding or a field'),
                    hint='bind the value first (`let s = …`), then call the method on `s`',
                )
            receiver = hir.Place(receiver.loc, receiver.type, receiver)
        pos_args = [receiver, *pos_args]
        argument_order = [None, *argument_order]
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
    if isinstance(left.type, ty.FunctionType) and left.type.type_params:
        # a generic's value parameter receives a compile-time-only argument
        # (a type, a function) as its spelling
        pos_args = [_spelling_string(arg, ctx=ctx) or arg for arg in pos_args]
        kw_args = {name: _spelling_string(arg, ctx=ctx) or arg for name, arg in kw_args.items()}
    pos_types = [require_valued(a.type, ctx.srcfile, a.loc, 'function call argument') for a in pos_args]
    kw_types = {k: require_valued(v.type, ctx.srcfile, v.loc, f'keyword argument `{k}`') for k, v in kw_args.items()}
    try:
        expected_return = expected if expected not in (None, ty.VOID_TYPE, ty.INFERRED_TYPE, ty.TOP_TYPE) else None
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

    if isinstance(left.type, ty.FunctionType) and left.type.type_params:
        # a user generic: the call targets a concrete instance from here on
        left, result = _instantiate_generic_call(left, result, pos_types, kw_types, expected_return, ctx=ctx)

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
    return_type = ty.strip_refinement(result.method.ret)
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
    if isinstance(left, hir.ArrayMethod):
        _apply_array_method_transition(
            left, call.loc, ctx=ctx, index=_array_method_index_argument(left.name, call),
        )
    if isinstance(left, hir.DictMethod):
        return _dict_method_call(left, call, ctx=ctx)
    return call


def _dict_method_call(method: hir.DictMethod, call: hir.FunctionCall, *, ctx: Context) -> hir.AST:
    if method.name == 'get':
        return _dict_get_call(method, call, ctx=ctx)
    found = _dict_value(method.dictionary)
    assert found is not None
    dictionary, _key_type, value_type = found
    keys, values = _dict_arrays(dictionary, call.loc, ctx=ctx)
    if method.name == 'clear':
        _forget_dictionary(dictionary, keys, values, cleared=True, ctx=ctx)
        return hir.DictRemove(call.loc, ty.VOID_TYPE, keys, values, None)
    key = call.pos_args[0] if call.pos_args else call.kw_args['key']
    if method.name == 'add':
        # a set store: appends the member unless present
        _invalidate_dict_lengths(dictionary, ctx=ctx)
        _forget_positions(dictionary, ctx=ctx)
        position = _new_key_position_name()
        _record_key_fact(dictionary, key, ctx=ctx, position=position)
        return hir.DictStore(call.loc, ty.VOID_TYPE, keys, None, key, None, position=position)
    # pop: the key must be proven present unless a default is supplied
    default = call.kw_args.get('default')
    fact = _proven_key(dictionary, key, ctx=ctx)
    if fact is None and default is None:
        container = 'dictionary' if value_type is not None else 'set'
        user_error(
            ctx.srcfile,
            f'{container} key is not proven present',
            Pointer(span=key.loc, message=f'`pop` removes a key that is known to be in the {container}'),
            hint=(
                'guard with `if key in? d { d.pop(key) }`, or pass `default=...` to get a value when the key is absent'
                if value_type is not None
                else 'guard with `if x in? s { s.pop(x) }`, or pass `default=none` (or a member) for a removal that may miss'
            ),
        )
    position, static_position = fact if fact is not None else (None, None)
    _forget_dictionary(dictionary, keys, values, cleared=False, removed=key, ctx=ctx)
    if value_type is None:
        # a set: the member, or the default when absent (`none` makes it optional)
        if default is None:
            result_type: ty.Type = _key_type
        elif isinstance(_unwrap_parens(default), hir.NoneValue):
            default = hir.NoneValue(default.loc, 'none')
            result_type = ty.optional(_key_type)
        else:
            default = check_against(default, _key_type, ctx=ctx)
            result_type = _key_type
        return hir.DictRemove(
            call.loc, result_type, keys, None, key,
            position=position, static_position=static_position, default=default, lenient=default is not None,
        )
    return hir.DictRemove(
        call.loc, value_type, keys, values, key,
        position=position, static_position=static_position, default=default,
    )


def _forget_dictionary(
    dictionary: hir.AST,
    keys: hir.AST,
    values: hir.AST,
    *,
    cleared: bool,
    ctx: Context,
    removed: hir.AST | None = None,
) -> None:
    """Update length and key facts after `pop`/`clear`.

    Removal leaves a tombstone, so the other keys stay proven *with* their
    positions; only the removed key's fact goes. `clear` forgets every key.
    """
    dictionary_id = _dictionary_fact_id(dictionary, ctx=ctx)
    removed_identity = _key_identity(removed, ctx=ctx) if removed is not None else None
    for fact_key in list(ctx.key_facts):
        route_id, identity = fact_key
        if route_id != dictionary_id:
            continue
        if cleared or identity == removed_identity:
            del ctx.key_facts[fact_key]
    for member in (keys, values):
        if member is None:
            continue
        route_id = sb.array_route_id(member, ctx.binding_registry)
        if route_id is None:
            continue
        current = ctx.refinements.get(route_id)
        exact = current.length if isinstance(current, ty.ArrayType) else None
        minimum = ctx.length_bounds.get(route_id, 0) if exact is None else exact
        assert isinstance(member.type, ty.ArrayType)
        if cleared:
            ctx.refinements[route_id] = ty.ArrayType(member.type.element, 0)
            ctx.length_bounds[route_id] = 0
        else:
            # the entry arrays keep their length (tombstone); a later
            # compaction shrinks them, so exact lengths are no longer known
            del exact, minimum
            ctx.refinements.pop(route_id, None)
            ctx.length_bounds.pop(route_id, None)


def _forget_positions(dictionary: hir.AST, *, ctx: Context) -> None:
    """Entries may move (compaction on resize or iteration): keys stay proven, positions do not."""
    dictionary_id = _dictionary_fact_id(dictionary, ctx=ctx)
    for fact_key, fact in list(ctx.key_facts.items()):
        if fact_key[0] == dictionary_id and fact != (None, None):
            ctx.key_facts[fact_key] = (None, None)


def _dict_get_call(method: hir.DictMethod, call: hir.FunctionCall, *, ctx: Context) -> hir.DictLookup:
    """`d.get(key)` is `V | none`; `d.get(key default)` is `V`."""
    found = _dict_value(method.dictionary)
    assert found is not None
    dictionary, _key_type, value_type = found
    key = call.pos_args[0] if call.pos_args else call.kw_args['key']
    default = call.pos_args[1] if len(call.pos_args) > 1 else call.kw_args.get('default')
    keys, values = _dict_arrays(dictionary, call.loc, ctx=ctx)
    result_type = value_type if default is not None else ty.optional(value_type)
    return hir.DictLookup(call.loc, result_type, keys, values, key, default=default)


def _array_method_index_argument(name: str, call: hir.FunctionCall) -> hir.AST | None:
    """The index/count argument of `pop(idx)`, `insert(value idx)`, `truncate(count)`."""
    if name == 'pop':
        return call.pos_args[0] if call.pos_args else call.kw_args.get('idx')
    if name == 'insert':
        return call.pos_args[1] if len(call.pos_args) > 1 else call.kw_args.get('idx')
    if name == 'truncate':
        return call.pos_args[0] if call.pos_args else call.kw_args.get('count')
    return None


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


def _spelling_string(node: hir.AST, *, ctx: Context) -> hir.String | None:
    """A compile-time-only value — a type, a function, an overload set — as
    the string it is spelled as: `int64 | string`, `<(a:int64):>int64>`.
    These have no runtime representation, so where a value is needed (an
    interpolation field, `as string`, a generic's value parameter) this
    spelling is the value."""
    if isinstance(node, hir.Place):
        node = node.target
    if isinstance(node, hir.TypeValue):
        value = node.value
        text = node.name if isinstance(value, ty.GenericTypeAlias) and node.name is not None else type_to_dewy(value)
    elif isinstance(node.type, (ty.FunctionType, ty.OverloadType)):
        text = type_to_dewy(node.type)
    else:
        return None
    return hir.String(node.loc, ty.StringLiteralType(text), text)


def _explicit_value_conversion(
    node: hir.AST,
    target: ty.Type,
    loc: Span,
    *,
    ctx: Context,
) -> hir.AST:
    if _is_string_type(target):
        spelled = _spelling_string(node, ctx=ctx)
        if spelled is not None:
            return spelled
    source = node.type
    target = _refine_binary_materialization_target(source, target)
    target = _refine_string_materialization_target(source, target)
    if source == target:
        return node
    if (
        isinstance(source, ty.BinaryLiteralType)
        and isinstance(target, ty.TypeOr)
        and ty.optional_payload(target) in ('string', ty.StringType())
    ):
        # `0x"..." as string | none`: decode the packed bytes at runtime
        bytes_node = hir.RepresentationCast(loc, ty.ArrayType('uint8', len(source.value)), node)
        return hir.RepresentationCast(loc, ty.optional(ty.StringType()), bytes_node)
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
        if (
            source.element == 'uint8'
            and isinstance(target, ty.TypeOr)
            and ty.optional_payload(target) in ('string', ty.StringType())
        ):
            # the checked decode: `none` when the bytes are not valid UTF-8
            return hir.RepresentationCast(loc, ty.optional(ty.StringType()), node)
        if target in {'string', 'grapheme', 'char'}:
            if isinstance(source.element, str) and source.element in {'uint8', 'uint32'}:
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
                    hint=(
                        'write `bytes as string | none` for a decode that yields `none` on invalid UTF-8'
                        if source.element == 'uint8'
                        else 'validation-backed refinement types are not implemented yet'
                    ),
                )
            if (
                isinstance(source.element, str) and source.element in {'grapheme', 'char'}
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
    if ty.fixed_integer_layout(ty.strip_refinement(source)) is not None and ty.fixed_integer_layout(target) is not None:
        # `src.length as uint64`: one fixed width to another, a value cast the
        # bounds analysis must prove in range (as at an annotated binding)
        return hir.ValueCast(loc, target, node)
    if _is_string_type(target) and isinstance(ty.unfold(ty.strip_refinement(node.type)), ty.MetaType):
        return _typename(node, loc, ctx=ctx)   # a type value converts to its name
    if _is_string_type(target):
        # a value that may carry a child's brand at runtime converts as that
        # child (its own `__as__`, or its literal syntax under its name)
        dispatched = _brand_dispatch(
            node, loc,
            lambda narrowed, _child: _static_string_conversion(narrowed, loc, ctx=ctx),
            lambda readable: _static_string_conversion(readable, loc, ctx=ctx),
            ctx=ctx,
        )
        if dispatched is not None:
            return dispatched
    converted = _conversion_method_call(node, target, loc, ctx=ctx)
    if converted is None and _is_string_type(target):
        union_flow = _optional_field_flow(node, ctx=ctx)
        if union_flow is not None:
            return union_flow
        number = _number_object(source, ctx=ctx)
        if number is not None:
            type_error(
                ctx.srcfile,
                'no string conversion for this value',
                Pointer(span=loc, message=f'`{number}` prints, but has no string form yet'),
            )
        converted = _structure_string(node, loc, ctx=ctx)
    if converted is not None:
        return converted
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


def _static_string_conversion(node: hir.AST, loc: Span, *, ctx: Context) -> hir.AST:
    """An object's string form by its static type alone: its `__as__`, else its literal syntax."""
    converted = _conversion_method_call(node, 'string', loc, ctx=ctx)
    if converted is not None:
        return converted
    structural = _structure_string(node, loc, ctx=ctx)
    if structural is not None:
        return structural
    type_error(
        ctx.srcfile,
        'unsupported value conversion',
        Pointer(span=loc, message=f'cannot convert `{type_to_dewy(node.type)}` to `string`'),
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
    if isinstance(target, ty.TypeOr) and any(
        item == 'string' or isinstance(item, ty.StringType) for item in target.items
    ):
        # a string literal in an optional/union slot materializes as a string
        # handle (the cell or argument packaging supplies the tag); a value
        # typed as the union would be mistaken for an already-built cell
        return ty.StringType()
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


def _runtime_shape(type_: ty.Type) -> object:
    """How a value of the type is passed and returned at runtime: two function
    types with the same shape everywhere can stand in for one another."""
    plain = ty.unfold(ty.strip_refinement(type_))
    if ty.optional_payload(plain) is not None or ty.runtime_union_members(plain) is not None:
        return 'cell'   # a tagged cell: tags are program-wide, so any union reads any narrower one
    if isinstance(plain, ty.ObjectType):
        return 'object'
    if plain in (ty.VOID_TYPE, ty.BOTTOM_TYPE):
        return 'void'
    return 'word'   # words, handles: one register either way


def _callable_shape_mismatch(actual: ty.FunctionType, expected: ty.FunctionType) -> str | None:
    """Why a function of type ``actual`` cannot be stored as ``expected`` even
    though its type fits: a result (or parameter) with another runtime shape.
    The caller reads the result through the slot's type, so an `int64?` written
    where `int64? | Bad` is read would be misread."""
    if _runtime_shape(actual.ret) != _runtime_shape(expected.ret):
        return f'it returns `{type_to_dewy(actual.ret)}`, whose runtime form differs from `{type_to_dewy(expected.ret)}`'
    for mine, theirs in zip(actual.pos_or_kw, expected.pos_or_kw):
        if _runtime_shape(mine.type) != _runtime_shape(theirs.type):
            return f'its parameter `{mine.name}:{type_to_dewy(mine.type)}` has another runtime form than `{type_to_dewy(theirs.type)}`'
    return None


def check_against(node: hir.AST, expected: ty.Type, *, ctx: Context) -> hir.AST:
    """Check a synthesized node against an expected type (bidirectional checking's checking mode).

    Subsumption passes the node through unchanged; a legal numeric promotion wraps it in a
    ValueCast; anything else is a type error. An object type's field invariants the value
    does not already carry become obligations (proven from a literal, else by the analysis).
    """
    if isinstance(node.type, ty.FunctionType) and isinstance(ty.strip_refinement(expected), ty.FunctionType) and node.type != expected:
        # a function value stored under another function type: its type may
        # fit (covariant result), but the call site reads the result through
        # the slot's type, so the runtime forms must agree
        assert isinstance(expected, ty.FunctionType)
        if ctx.type_system.is_subtype(node.type, expected):
            mismatch = _callable_shape_mismatch(node.type, expected)
            if mismatch is not None:
                type_error(
                    ctx.srcfile,
                    'function result form does not match the slot',
                    Pointer(span=node.loc, message=mismatch),
                    hint=f'declare the function with the slot\'s types: `:>{type_to_dewy(expected.ret)}`',
                )
    checked = _check_against_shape(node, expected, ctx=ctx)
    target = ty.unfold(ty.strip_refinement(expected))
    if isinstance(target, ty.ObjectType):
        missing = _missing_invariants(checked.type, target)
        if missing:
            checked = _prove_refinements(checked, ty.RefinedType(target, tuple(missing)), ctx=ctx)
    return checked


def _field_expectation(field: ty.ObjectField) -> ty.Type:
    """A field's type with its invariant, for checking a value stored into it."""
    return _refined(field.type, list(field.refinement)) if field.refinement else field.type


def _missing_invariants(source: ty.Type, target: ty.ObjectType) -> list[ty.Proposition]:
    """The target's field invariants the source type does not already guarantee."""
    unfolded = ty.unfold(ty.strip_refinement(source))
    if unfolded is target:
        return []
    missing: list[ty.Proposition] = []
    for field in target.fields:
        if not field.refinement:
            continue
        carried = unfolded.field(field.name) if isinstance(unfolded, ty.ObjectType) else None
        if carried is not None and carried.refinement == field.refinement:
            continue
        missing.extend(
            ty.Proposition(
                f'.{field.name}{p.subject}' if p.field is not None else f'.{field.name}',
                p.op,
                p.value,
                of='length' if p.subject == 'length' or (p.field is not None and p.of == 'length') else 'value',
            )
            for p in field.refinement
        )
    return missing


def _unit_inhabitant(node: hir.AST, expected: ty.Type | None, *, ctx: Context) -> hir.ObjectLiteral | None:
    """An empty minted type named where a value is wanted (`[Whitespace Name(…)]`,
    `return Whitespace`, `let w = Whitespace`) is its single inhabitant, as an
    error type's name is — the type and the value share the spelling. With an
    expectation, only where the inhabitant fits it (`Whitespace` for a `Token`)."""
    if not isinstance(node, hir.TypeValue) or not ty.user_branded(node.value):
        return None
    minted = node.value
    assert isinstance(minted, ty.ObjectType)
    if minted.brand in ty.USER_ABSTRACT_BRANDS:
        return None   # an abstract type has no value of its own
    if expected is not None and not ctx.type_system.is_subtype(minted, ty.strip_refinement(expected)):
        return None
    if not minted.fields:
        return hir.ObjectLiteral(node.loc, minted, [])
    if all(field_.default is not None for field_ in minted.fields):
        # every field defaulted: the name is the construction `Name()`, as a
        # zero-argument callable is called by its bare name
        constructed = _tcr_type_constructor_call(node, minted, p0.Block(node.loc, [], '()', None), ctx=ctx)
        return constructed if isinstance(constructed, hir.ObjectLiteral) else None
    return None


def _brand_value(node: hir.AST, expected: ty.Type | None, *, ctx: Context) -> hir.BrandValue | None:
    """A minted type named where a `type<Family>` value is wanted: its brand id, when it is under the family."""
    if not isinstance(node, hir.TypeValue) or not isinstance(expected, ty.MetaType):
        return None
    minted = node.value
    if not (isinstance(minted, ty.ObjectType) and ty.user_branded(minted) and minted.brand is not None):
        return None
    if not (minted == expected.family or ty.user_brand_descends(minted, expected.family)):
        type_error(
            ctx.srcfile,
            'type value outside its family',
            Pointer(span=node.loc, message=f'`{minted.brand}` is not minted under `{type_to_dewy(expected.family)}`'),
        )
    return hir.BrandValue(node.loc, ty.MetaType(minted), minted.brand)


def _check_against_shape(node: hir.AST, expected: ty.Type, *, ctx: Context) -> hir.AST:
    if isinstance(expected, ty.RefinedType):
        checked = check_against(node, expected.base, ctx=ctx)
        return _prove_refinements(checked, expected, ctx=ctx)
    inhabitant = _unit_inhabitant(node, expected, ctx=ctx)
    if inhabitant is not None:
        node = inhabitant
    brand_value = _brand_value(node, expected, ctx=ctx)
    if brand_value is not None:
        node = brand_value
    if node.type == expected:
        return node
    if node.type == ty.BOTTOM_TYPE:
        return node  # unreachable; vacuously satisfies any expectation
    if node.type == ty.VOID_TYPE or node.type == ty.INFERRED_TYPE or expected == ty.VOID_TYPE:
        expected_str = type_to_dewy(expected) if expected != ty.VOID_TYPE else 'void'
        type_error(ctx.srcfile, 'type mismatch',
            Pointer(span=node.loc, message=f'expected `{expected_str}`, got `{node.type}`'))
    if _is_bigint(expected, ctx=ctx) and not _is_bigint(node.type, ctx=ctx):
        nonzero = _is_nonzero_form(expected, BIGINT_TYPE_NAME, ctx=ctx)
        constant = _constant_integer(_unwrap_parens(node), ctx=ctx)
        if constant is not None and not (nonzero and constant == 0):
            return _bigint_literal(constant, loc=node.loc, ctx=ctx)
        if constant is None and ctx.type_system.is_subtype(node.type, 'int'):
            return _to_bigint(node, ctx=ctx, nonzero=nonzero)
    node_number, node_dimension = _number_and_dimension(node.type)
    if isinstance(node_number, (ty.RationalLiteralType, ty.IntegerLiteralType)):
        # Compile-time numbers materialize into runtime rational or fixed
        # targets of the same dimension.
        expected_number, expected_dimension = _number_and_dimension(expected)
        if (
            isinstance(expected_number, ty.TypeOr)
            and node_dimension == expected_dimension
            and _constant_rational(node, ctx=ctx) == 0
            and any(isinstance(m, ty.IntegerLiteralType) and m.value == 0 for m in expected_number.items)
        ):
            # `0` meeting `0 | [...]`: the union's own literal member
            return hir.Integer(node.loc, node.type if isinstance(node_number, ty.IntegerLiteralType) else _with_dimension(ty.IntegerLiteralType(0), node_dimension), '0d', 0)
        if node_dimension == expected_dimension:
            if _is_rational(expected_number, ctx=ctx):
                return _materialize_rational(node, ctx=ctx, word=_is_word_rational(expected_number, ctx=ctx))
            if _is_fixed(expected_number, ctx=ctx):
                value = _constant_rational(node, ctx=ctx)
                if value is not None:
                    return replace(_fixed_constant(value, loc=node.loc, ctx=ctx), type=expected)
    if isinstance(node.type, ty.BinaryLiteralType):
        target = _refine_binary_materialization_target(node.type, expected)
        if ctx.type_system.is_subtype(node.type, target):
            return hir.RepresentationCast(node.loc, target, node)
    expected_enum = ty.enum_members(expected)
    node_enum = ty.enum_members(node.type)
    if expected_enum is not None and ctx.type_system.is_subtype(node.type, expected) and (
        isinstance(node.type, (ty.StringLiteralType, ty.IntegerLiteralType)) or (node_enum is not None and node_enum != expected_enum)
    ):
        # a singleton (or a narrower enum) meeting an enum: the value is the
        # member's tag word — the lowering converts
        return hir.RepresentationCast(node.loc, expected, node)
    if node_enum is not None and _is_string_type(expected) and ctx.type_system.is_subtype(node.type, expected):
        # an enum meeting a string: the member's text
        return hir.RepresentationCast(node.loc, expected, node)
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
    if ty.fixed_integer_layout(ty.strip_refinement(node.type)) is not None and ty.fixed_integer_layout(expected) is not None:
        # one fixed width meeting another (`int64` length into `uint64`): a
        # value cast the bounds analysis must prove in range
        return hir.ValueCast(node.loc, expected, node)
    if isinstance(expected, ty.TypeOr) and _integer_valued(node.type):
        # an integer meeting `uint64 | none`: it is the union's one fixed-width
        # integer member, with that member's proof obligation (the bounds
        # analysis validates the range, as for a plain `uint64` target)
        words = [member for member in expected.items if ty.fixed_integer_layout(member) is not None]
        if len(words) == 1:
            return check_against(node, words[0], ctx=ctx)
    type_error(ctx.srcfile, 'type mismatch',
        Pointer(span=node.loc, message=f'expected `{type_to_dewy(expected)}`, got `{type_to_dewy(node.type)}`'))


def _integer_valued(type_: ty.Type) -> bool:
    """An abstract or literal integer, or a fixed-width one (a value the bounds analysis ranges)."""
    plain = ty.strip_refinement(type_)
    return plain in ('int', 'uint') or isinstance(plain, ty.IntegerLiteralType) or ty.fixed_integer_layout(plain) is not None


def apply_promotions(args: list[hir.AST], promote_pos: list[ty.TypeExpr | None]) -> list[hir.AST]:
    """Wrap args that need promotion in Cast nodes. `promote_pos` is parallel to `args`."""
    out: list[hir.AST] = []
    for arg, target in zip(args, promote_pos):
        if target is None:
            out.append(arg)
        else:
            out.append(hir.ValueCast(arg.loc, target, arg))
    return out


# `$prototype` deferrals of the entry program's proofs, printed as warnings after the compile
last_prototype_reports: list = []

_PROTOTYPE_DUNDERS = {'=?': '__eq__', 'not=?': '__ne__', '<?': '__lt__', '<=?': '__le__', '>?': '__gt__', '>=?': '__ge__'}


_PROTOTYPE_PURE_CALLS = frozenset({'__add__', '__sub__', '__mul__', '__floordiv__', '__mod__', '__lshift__', '__rshift__', '__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__'})


def _prototype_simple(node: hir.AST) -> bool:
    """An operand a check may re-read: effect-free (names, literals, lengths,
    member reads, arithmetic over those), so evaluating it twice is only a cost."""
    if isinstance(node, (hir.ExpressedIdentifier, hir.Integer, hir.Bool)):
        return True
    if isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Obligation)):
        return _prototype_simple(node.expr if not isinstance(node, hir.Obligation) else node.value)
    if isinstance(node, (hir.ArrayLength, hir.StringLength)):
        return _prototype_simple(node.array if isinstance(node, hir.ArrayLength) else node.string)
    if isinstance(node, hir.MemberAccess):
        return _prototype_simple(node.value)
    if isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
        return _prototype_simple(node.items[0])
    if (
        isinstance(node, hir.FunctionCall)
        and isinstance(node.func, hir.ExpressedIdentifier)
        and node.func.name in _PROTOTYPE_PURE_CALLS
        and not node.kw_args
    ):
        return all(_prototype_simple(argument) for argument in node.pos_args)
    return False


def _prototype_comparison(name: str, left: hir.AST, right: hir.AST, loc: Span) -> hir.FunctionCall:
    func = hir.ExpressedIdentifier(loc, builtins.builtin_types.get(name, ty.TOP_TYPE), name)
    return hir.FunctionCall(loc, 'bool', func, [left, right], {})


def _prototype_length(value: hir.AST, loc: Span) -> hir.AST | None:
    plain = ty.unfold(ty.strip_refinement(value.type))
    if isinstance(plain, ty.ArrayType):
        return hir.ArrayLength(loc, 'int64', value)
    if _is_string_type(plain):
        return hir.StringLength(loc, 'int64', value)
    return None


def _prototype_detail_value(value: hir.AST, loc: Span) -> hir.AST | None:
    """The value as an `int64` the panic may print, or None when its
    representation is not a plain word."""
    plain = ty.strip_refinement(value.type)
    if isinstance(plain, ty.IntegerLiteralType):
        return hir.Integer(loc, 'int64', '0d', plain.value) if ty.integer_literal_fits(plain.value, 'int64') else None
    layout = ty.fixed_integer_layout(plain)
    if layout is not None:
        width, signed = layout
        if width < 64 or signed:
            return value if plain == 'int64' else hir.ValueCast(loc, 'int64', value)
        return value if isinstance(value, hir.ExpressedIdentifier) else None   # printed as a signed word; fine below 2^63
    return None


def _prototype_runtime_report(node: hir.AST, kind: str, loc: Span, srcfile: SrcFile):
    """The report a failed `$prototype` check prints: the *violated requirement*,
    concretely — at this point the program observed the failure, so the wording
    is about what happened, not about what could not be proven. Returns the
    report, the panic's detail kind, and the observed int64 values to print."""
    from .analyze.bounds import _describe_proposition_text

    if kind == 'index':
        assert isinstance(node, (hir.Index, hir.StringIndex))
        sequence = node.array if isinstance(node, hir.Index) else node.string
        what = 'array' if isinstance(node, hir.Index) else 'string'
        report = Error(
            srcfile=srcfile,
            title='Runtime Panic',
            message=f'{what} index out of bounds',
            pointer_messages=[Pointer(span=node.index.loc, message=f'this index was past the {what}\'s end (or negative)')],
            hint=f'prove it before this point (`i <? xs.length`, or a length guard) and the compiler will catch this case; `$prototype` deferred that proof to this check',
        )
        detail = _prototype_detail_value(node.index, loc)
        length_value = _prototype_length(sequence, loc)
        if detail is not None and length_value is not None:
            return report, 1, [detail, length_value]
        return report, 0, []
    if kind == 'cast':
        assert isinstance(node, hir.ValueCast)
        layout = ty.fixed_integer_layout(node.type)
        assert layout is not None
        width, signed = layout
        minimum = -(1 << (width - 1)) if signed else 0
        maximum = (1 << (width - (1 if signed else 0))) - 1
        report = Error(
            srcfile=srcfile,
            title='Runtime Panic',
            message=f'value does not fit `{node.type}`',
            pointer_messages=[Pointer(span=node.loc, message=f'this value was outside `{node.type}`\'s range [{minimum}, {maximum}]')],
            hint='narrow the value with a comparison and the compiler will catch this case; `$prototype` deferred that proof to this check',
        )
        detail = _prototype_detail_value(node.expr, loc)
        if detail is not None:
            return report, 2, [detail]
        return report, 0, []
    assert kind == 'obligation' and isinstance(node, hir.Obligation)
    requirements = ', '.join(_describe_proposition_text(p) for p in node.refined.propositions)
    report = Error(
        srcfile=srcfile,
        title='Runtime Panic!',
        pointer_messages=[Pointer(span=node.value.loc, message=f'this value was required to satisfy `{requirements}`, and did not')],
        hint='prove it before this point with a guard and the compiler will catch this case; `$prototype` deferred that proof to this check',
    )
    if all(p.subject == 'self' and p.field is None for p in node.refined.propositions):
        detail = _prototype_detail_value(node.value, loc)
        if detail is not None:
            return report, 3, [detail]
    length_value = _prototype_length(node.value, loc) if all(p.subject == 'length' for p in node.refined.propositions) else None
    if length_value is not None:
        return report, 3, [length_value]
    return report, 0, []


def insert_prototype_checks(
    root: hir.Block,
    sites: 'dict[int, tuple[str, object]]',
    *,
    ctx: Context,
) -> list[object]:
    """`$prototype`: wrap each unproven site in the runtime check that panics
    with the deferred compile error. Returns the reports of sites no check
    could be built for (they stay compile errors)."""
    from .analyze.bounds import prototype_check_condition

    unhandled: list[object] = []
    panic_binding = ctx.binding_scopes.get('_prototype_panic')
    if panic_binding is None:
        return [report for _kind, report in sites.values()]

    def wrap(node: hir.AST, kind: str, report: object) -> hir.AST | None:
        loc = node.loc
        condition = prototype_check_condition(
            node,
            kind,
            simple=_prototype_simple,
            comparison=lambda name, a, b: _prototype_comparison(name, a, b, loc),
            length_of=lambda value: _prototype_length(value, loc),
            integer=lambda value: hir.Integer(loc, 'int64', '0d', value),
        )
        if condition is None:
            return None
        runtime_report, detail_kind, detail_values = _prototype_runtime_report(node, kind, loc, ctx.srcfile)
        runtime_report.use_color = True
        colored_text = str(runtime_report) + '\n'
        runtime_report.use_color = False
        plain_text = str(runtime_report) + '\n'
        panic = hir.ExpressedIdentifier(loc, panic_binding.type or ty.TOP_TYPE, '_prototype_panic', binding_id=panic_binding.id)
        colored = hir.String(loc, ty.StringLiteralType(colored_text), colored_text)
        plain = hir.String(loc, ty.StringLiteralType(plain_text), plain_text)
        arguments: list[hir.AST] = [colored, plain, hir.Integer(loc, 'int64', '0d', detail_kind), *detail_values]
        while len(arguments) < 5:
            arguments.append(hir.Integer(loc, 'int64', '0d', 0))
        failure = hir.Block(loc, ty.BOTTOM_TYPE, [hir.FunctionCall(loc, ty.BOTTOM_TYPE, panic, arguments, {})], True)
        check_flow = hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(loc, ty.VOID_TYPE, condition, hir.Void(loc, ty.VOID_TYPE))], failure)
        return hir.Block(loc, node.type, [check_flow, node], False)

    def visit(value: object) -> object:
        if isinstance(value, hir.AST):
            for name in value.__dataclass_fields__:
                child = getattr(value, name)
                replaced = visit(child)
                if replaced is not child:
                    object.__setattr__(value, name, replaced)
            site = sites.get(id(value))
            if site is not None:
                kind, report = site
                wrapped = wrap(value, kind, report)
                if wrapped is None:
                    unhandled.append(report)
                    return value
                return wrapped
            return value
        if isinstance(value, list):
            return [visit(item) for item in value]
        if isinstance(value, dict):
            return {key: visit(item) for key, item in value.items()}
        if isinstance(value, hir.ObjectField):
            replaced = visit(value.value)
            if replaced is not value.value:
                object.__setattr__(value, 'value', replaced)
            return value
        return value

    visit(root)
    return unhandled


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
        if binding is not None and ty.is_user_nominal(binding.type_value):
            # the canonical inhabitant of a unit-like error type is spelled with its name
            assert isinstance(binding.type_value, str)
            return hir.ErrorValue(id.loc, binding.type_value, binding.type_value)
        if declared_type == ty.TYPE_TYPE or (
            binding is not None and binding.type_value is not None
        ):
            # a type as a value: it has no runtime representation, but it
            # converts to its spelling (`'{T}'`, `T as string`, `print(T)`)
            value = binding.type_value if binding is not None else None
            if value is None and binding is not None and binding.id in ctx.type_alias_asts:
                value = _resolve_type_alias(binding, ctx=ctx)
            if value is None:
                not_implemented(ctx.srcfile, id.loc, 'runtime type values')
            type_value = hir.TypeValue(id.loc, ty.TYPE_TYPE, value, id.name)
            if expected is not None and expected != ty.TYPE_TYPE:
                inhabitant = _unit_inhabitant(type_value, expected, ctx=ctx)
                if inhabitant is not None:
                    return inhabitant
            return type_value
        resolved_type = ty.unfold(ty.strip_refinement(
            ctx.refinements.get(binding.id, declared_type)
            if refined and binding is not None
            else declared_type
        ))
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
