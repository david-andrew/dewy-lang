from ...tokenizer import tokenize
from ...postok import post_process
from ...typecheck import (
    Scope as TypecheckScope,
    typecheck_and_resolve,
    typecheck_call, typecheck_index, typecheck_multiply,
    register_typeof, short_circuit,
    CallableBase, IndexableBase, IndexerBase, MultipliableBase, ObjectBase,
)
from ...parser import top_level_parse, QJux
from ...syntax import (
    AST,
    DeclarationType,
    Type, TypeParam,
    PointsTo, BidirPointsTo,
    ListOfASTs, PrototypeTuple, Block, Array, Group, Range, ObjectLiteral, Dict, BidirDict, UnpackTarget,
    TypedIdentifier,
    Void, void, Undefined, undefined, untyped,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    Identifier, Express, Declare,
    PrototypeBuiltin, Call, Access, Index,
    Assign,
    Int, Bool,
    Range, IterIn,
    BinOp,
    Less, LessEqual, Greater, GreaterEqual, Equal, MemberIn,
    LeftShift, RightShift, LeftRotate, RightRotate, LeftRotateCarry, RightRotateCarry,
    Add, Sub, Mul, Div, IDiv, Mod, Pow,
    And, Or, Xor, Nand, Nor, Xnor,
    UnaryPrefixOp, UnaryPostfixOp,
    Not, UnaryPos, UnaryNeg, UnaryMul, UnaryDiv, AtHandle,
    CycleLeft, CycleRight, Suppress,
    BroadcastOp,
    CollectInto, SpreadOutFrom,
)

from ...postparse import post_parse, FunctionLiteral, Signature, normalize_function_args
from ...utils import BaseOptions, Backend

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Literal
from functools import cache
from itertools import count
from argparse import ArgumentParser, Namespace


import pdb


from functools import cache
from pathlib import Path


# TODO: not quite sure what to do about scope. for now, just steal from
# from ..python import Scope, Closure

# command to compile a .qbe file to an executable
# qbe <file>.ssa | gcc -x assembler -static -o hello

OS = Literal['linux', 'apple', 'windows']
Arch = Literal['x86_64', 'arm64', 'riscv64']

@dataclass
class Options(BaseOptions):
    os: OS
    arch: Arch
    build_only: bool
    test_qbe: bool
    opt_level: int
    emit_asm: bool
    emit_qbe: bool

def make_argparser(parent: ArgumentParser) -> None:
    parent.add_argument('-os', type=str, help='Operating system name for cross compilation. If not provided, defaults to current host OS', choices=OS.__args__)
    parent.add_argument('-arch', type=str, help='Architecture name for cross compilation. If not provided, defaults to current host arch', choices=Arch.__args__)
    parent.add_argument('-b', '--build-only', action='store_true', help='Only compile/build the program, do not run it')

    parent.add_argument('--test-qbe', action='store_true', help='Test option for the QBE backend')
    parent.add_argument('--opt-level', type=int, default=2, help='Optimization level for QBE codegen')
    parent.add_argument('--emit-asm', action='store_true', help='Emit final assembly output')
    parent.add_argument('--emit-qbe', action='store_true', help='Emit QBE IR output')

def make_options(args: Namespace) -> Options:
    return Options(
        os=args.os,
        arch=args.arch,
        build_only=args.build_only,
        tokens=args.tokens,
        verbose=args.verbose,
        test_qbe=args.test_qbe,
        opt_level=args.opt_level,
        emit_asm=args.emit_asm,
        emit_qbe=args.emit_qbe,
    )


def qbe_compiler(path: Path, args: list[str], options: Options) -> None:
    # get the source code and tokenize
    src = path.read_text()
    tokens = tokenize(src)
    post_process(tokens)

    # parse tokens into AST
    ast = top_level_parse(tokens)
    ast = post_parse(ast)

    # typecheck and collapse any Quantum ASTs to a concrete selection
    scope = Scope.linux_default()
    ast, scope = typecheck_and_resolve(ast, scope)

    # debug printing
    if options.verbose:
        print(repr(ast))

    # generate the program qbe
    qbe = QbeModule([
        QbeFunction('$__main__', True, [QbeArg('%argc', 'l'), QbeArg('%argv', 'l'), QbeArg('%envp', 'l')], 'w', [])
    ])
    qbe, meta_info = compile(ast, scope, qbe)
    
    # add a fallback exit block to the __main__ function
    assert qbe.functions[0].name == '$__main__', 'Internal Error: expected __main__ as first function'
    qbe.functions[0].blocks.append(QbeBlock('@__fallback_exit__', ['ret 0']))

    ssa = str(qbe)
    #DEBUG
    print(ssa)

    # TODO:
    # write the ssa to a file
    # compile the ssa with qbe
    # construct the full executable
    # run the executable



qbe_backend = Backend[Options](
    name='qbe',
    exec=qbe_compiler,
    make_argparser = make_argparser,
    make_options = make_options
)

# def top_level_compile(ast: AST, scope: Scope) -> 'QbeModule':
#     # TODO: pull in relevant files for os envm abd select relevant scope
#     # os_env = determine_os_env()
#     qbe = QbeModule()
#     compile(ast, scope, qbe)
#     return qbe

# TODO: move this to something more central like utils
# from ..python import MetaNamespaceDict

@dataclass
class Scope(TypecheckScope):

    # TODO: note that these are only relevant for linux
    # so probably have default versions for other OS environments...
    @staticmethod
    def linux_default() -> 'Scope':
        return Scope(vars={
            '__syscall1__': Scope._var(
                DeclarationType.CONST, Type(Builtin),
                Builtin(normalize_function_args(Group([
                    TypedIdentifier(Identifier('n'), Type(Int)),
                    TypedIdentifier(Identifier('a0'), Type(Int))
                ])), Type(Int))
            ),
            '__syscall2__': Scope._var(
                DeclarationType.CONST, Type(Builtin),
                Builtin(normalize_function_args(Group([
                    TypedIdentifier(Identifier('n'), Type(Int)),
                    TypedIdentifier(Identifier('a0'), Type(Int)),
                    TypedIdentifier(Identifier('a1'), Type(Int))
                ])), Type(Int))
            ),
            '__syscall3__': Scope._var(
                DeclarationType.CONST, Type(Builtin),
                Builtin(normalize_function_args(Group([
                    TypedIdentifier(Identifier('n'), Type(Int)),
                    TypedIdentifier(Identifier('a0'), Type(Int)),
                    TypedIdentifier(Identifier('a1'), Type(Int)),
                    TypedIdentifier(Identifier('a2'), Type(Int))
                ])), Type(Int))
            ),
            '__syscall4__': Scope._var(
                DeclarationType.CONST, Type(Builtin),
                Builtin(normalize_function_args(Group([
                    TypedIdentifier(Identifier('n'), Type(Int)),
                    TypedIdentifier(Identifier('a0'), Type(Int)),
                    TypedIdentifier(Identifier('a1'), Type(Int)),
                    TypedIdentifier(Identifier('a2'), Type(Int)),
                    TypedIdentifier(Identifier('a3'), Type(Int))
                ])), Type(Int))
            ),
            '__syscall5__': Scope._var(
                DeclarationType.CONST, Type(Builtin),
                Builtin(normalize_function_args(Group([
                    TypedIdentifier(Identifier('n'), Type(Int)),
                    TypedIdentifier(Identifier('a0'), Type(Int)),
                    TypedIdentifier(Identifier('a1'), Type(Int)),
                    TypedIdentifier(Identifier('a2'), Type(Int)),
                    TypedIdentifier(Identifier('a3'), Type(Int)),
                    TypedIdentifier(Identifier('a4'), Type(Int))
                ])), Type(Int))
            ),
            '__syscall6__': Scope._var(
                DeclarationType.CONST, Type(Builtin),
                Builtin(normalize_function_args(Group([
                    TypedIdentifier(Identifier('n'), Type(Int)),
                    TypedIdentifier(Identifier('a0'), Type(Int)),
                    TypedIdentifier(Identifier('a1'), Type(Int)),
                    TypedIdentifier(Identifier('a2'), Type(Int)),
                    TypedIdentifier(Identifier('a3'), Type(Int)),
                    TypedIdentifier(Identifier('a4'), Type(Int)),
                    TypedIdentifier(Identifier('a5'), Type(Int))
                ])), Type(Int))
            ),
        })



# @dataclass
# class CAST:
#     ast: AST
#     id: str | None = None


# TODO: include user defined struct types...
QbeType = Literal['w', 'l', 's', 'd', 'b', 'h'] | str

@dataclass
class QbeBlock:
    label: str
    lines: list[str]

    def __str__(self) -> str:
        return '\n    '.join([self.label, *self.lines])

@dataclass
class QbeArg:
    name: str
    type: QbeType

    def __str__(self) -> str:
        return f'{self.type} {self.name}'

@dataclass
class QbeFunction:
    name: str
    export: bool
    args: list[QbeArg]
    ret: QbeType | None
    blocks: list[QbeBlock]

    def __str__(self) -> str:
        export = 'export ' if self.export else ''
        args = ', '.join(map(str, self.args))
        ret = f'{self.ret} ' if self.ret else ''
        blocks = '\n'.join(map(str, self.blocks))
        return f'{export}function {ret}{self.name}({args}) {{\n{blocks}\n}}'

@dataclass
class QbeModule:
    functions: list[QbeFunction] = field(default_factory=list)
    global_data: list[str] = field(default_factory=list)
    _counter = count(0)
    _symbols: dict[str, Type] = field(default_factory=dict)

    # TODO: function for getting identifiers, or next counter


    def __str__(self) -> str:
        functions = '\n\n'.join(map(str, self.functions))
        global_data = '\n'.join(self.global_data)
        return f'{global_data}\n\n{functions}'


from typing import Protocol, TypeVar
T = TypeVar('T', bound=AST)
U = TypeVar('U', bound=AST)
class CompileFunc(Protocol):
    def __call__(self, ast: T, scope: Scope, qbe: QbeModule) -> str | None:
        """
        Converts the AST to corresponding QBE code.
        If anything is expressed, the %temporary name of the expression is returned
        the type of the %temporary is store in module._symbols[%temporary]
        """



@cache
def get_compile_fn_map() -> dict[type[AST], CompileFunc]:
    return {
        # Declare: compile_declare,
        QJux: compile_qjux,
        Call: compile_call,
        # Block: compile_block,
        # Group: compile_group,
        # Array: compile_array,
        # Dict: compile_dict,
        # PointsTo: compile_points_to,
        # BidirDict: compile_bidir_dict,
        # BidirPointsTo: compile_bidir_points_to,
        # ObjectLiteral: compile_object_literal,
        # Object: no_op,
        # Access: compile_access,
        # Index: compile_index,
        # Assign: compile_assign,
        # IterIn: compile_iter_in,
        # FunctionLiteral: compile_function_literal,
        # Closure: compile_closure,
        # Builtin: compile_builtin,
        String: compile_string,
        # IString: compile_istring,
        # Identifier: cannot_evaluate,
        # Express: compile_express,
        # Int: no_op,
        # Float: no_op,
        # Bool: no_op,
        # Range: no_op,
        # Flow: compile_flow,
        # Default: compile_default,
        # If: compile_if,
        # Loop: compile_loop,
        # UnaryPos: compile_unary_dispatch,
        # UnaryNeg: compile_unary_dispatch,
        # UnaryMul: compile_unary_dispatch,
        # UnaryDiv: compile_unary_dispatch,
        # Not: compile_unary_dispatch,
        # Greater: compile_binary_dispatch,
        # GreaterEqual: compile_binary_dispatch,
        # Less: compile_binary_dispatch,
        # LessEqual: compile_binary_dispatch,
        # Equal: compile_binary_dispatch,
        # And: compile_binary_dispatch,
        # Or: compile_binary_dispatch,
        # Xor: compile_binary_dispatch,
        # Nand: compile_binary_dispatch,
        # Nor: compile_binary_dispatch,
        # Xnor: compile_binary_dispatch,
        # Add: compile_binary_dispatch,
        # Sub: compile_binary_dispatch,
        # Mul: compile_binary_dispatch,
        # Div: compile_binary_dispatch,
        # Mod: compile_binary_dispatch,
        # Pow: compile_binary_dispatch,
        # AtHandle: compile_at_handle,
        # Undefined: no_op,
        # Void: no_op,
        # #TODO: other AST types here
    }


@dataclass
class MetaInfo: ...

def compile(ast:AST, scope:Scope, qbe: QbeModule) -> tuple[QbeModule, MetaInfo]:
    if isinstance(ast, Void):
        return qbe, MetaInfo()
    
    compile_fn_map = get_compile_fn_map()

    ast_type = type(ast)
    if ast_type in compile_fn_map:
        return compile_fn_map[ast_type](ast, scope, qbe)
    pdb.set_trace()
    raise NotImplementedError(f'AST type {ast_type} not implemented yet')

def compile_qjux(ast: QJux, scope: Scope, qbe: QbeModule) -> str:
    if ast.call is not None and typecheck_call(ast.call, scope):
        return compile_call(ast.call, scope, qbe)
    if ast.index is not None and typecheck_index(ast.index, scope):
        return compile_index(ast.index, scope, qbe)
    if typecheck_multiply(ast.mul, scope):
        return compile_binary_dispatch(ast.mul, scope, qbe)

    raise ValueError(f'Typechecking failed to match a valid evaluation for QJux. {ast=}')



def compile_string(ast: String, scope: Scope, qbe: QbeModule) -> str:
    pdb.set_trace()
    ...

def compile_call(call: Call, scope: Scope, qbe: QbeModule) -> str:
    f = call.f

    # get the expression of the group
    if isinstance(f, Group):
        pdb.set_trace()
        f = evaluate(f, scope)

    # get the value pointed to by the identifier
    if isinstance(f, Identifier):
        f = scope.get(f.name).value

    # if this is a handle, do a partial evaluation rather than a call
    if isinstance(f, AtHandle):
        pdb.set_trace()
        return apply_partial_eval(f.operand, call.args, scope)

    # AST being called must be TypingCallable
    assert isinstance(f, (PrototypeBuiltin, Closure)), f'expected Function or Builtin, got {f}'

    # save the args of the call as metadata for the function AST
    call_args, call_kwargs = collect_calling_args(call.args, scope)
    scope.meta[f].call_args = call_args, call_kwargs

    # run the function and return the result
    if isinstance(f, PrototypeBuiltin):
        return compile_call_pyaction(f, scope, qbe)
    if isinstance(f, Closure):
        return compile_call_closure(f, scope, qbe)

    pdb.set_trace()
    raise NotImplementedError(f'Function evaluation not implemented yet')





#TODO: longer term this might also return a list/dict of spread args passed into the function
def collect_calling_args(args: AST | None, scope: Scope) -> tuple[list[AST], dict[str, AST]]:
    """
    Collect the arguments that a function is being called with
    e.g. `let fn = (a b c) => a + b + c; fn(1 c=2 3)`
    then the calling args are [1, 3] and {c: 2}

    Args:
        args: the arguments being passed to the function. If None, then treat as a no-arg call
        scope: the scope in which the function is being called

    Returns:
        a tuple of the positional arguments and keyword arguments
    """
    match args:
        case None | Void(): return [], {}
        case Identifier(name): return [scope.get(name).value], {}
        case Assign(left=Identifier(name)|TypedIdentifier(id=Identifier(name)), right=right): return [], {name: right}
        # case Assign(left=UnpackTarget() as target, right=right): raise NotImplementedError('UnpackTarget not implemented yet')
        case Assign(): raise NotImplementedError('Assign not implemented yet') #called recursively if a calling arg was an keyword arg rather than positional
        case CollectInto(right=right):
            pdb.set_trace()
            ... #right should be iterable, so extend with the values it expresses
                #whether to add to args or kwargs depends on each type from right
            val = evaluate(right, scope)
            match val:
                case Array(items): ... #return [collect_calling_args(i, scope) for i in items]
        case Group(items):
            call_args, call_kwargs = [], {}
            for i in items:
                a, kw = collect_calling_args(i, scope)
                call_args.extend(a)
                call_kwargs.update(kw)
            return call_args, call_kwargs

        #TODO: eventually it should just be anything that is left over is positional args rather than specifying them all out
        case Int() | String() | IString() | Range() | Call() | Access() | Index() | Express() | QJux() | UnaryPrefixOp() | UnaryPostfixOp() | BinOp() | BroadcastOp():
            return [args], {}
        # case Call(): return [args], {}
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'collect_args not implemented yet for {args}')


    raise NotImplementedError(f'collect_args not implemented yet for {args}')










def compile_call_pyaction(f: PrototypeBuiltin, scope: Scope, qbe: QbeModule) -> str:
    pdb.set_trace()
    ...


def compile_call_closure(f: 'Closure', scope: Scope, qbe: QbeModule) -> str:
    pdb.set_trace()
    ...





# #TODO: consider adding a flag repr vs str, where initially str is used, but children get repr.
# # as is, stringifying should put quotes around strings that are children of other objects
# # but top level printed strings should not show their quotes
# def py_stringify(ast: AST, scope: Scope, top_level:bool=False) -> str:
#     # don't evaluate. already evaluated by resolve_calling_args
#     ast = evaluate(ast, scope) if not isinstance(ast, (Builtin, Closure)) else ast
#     match ast:
#         # types that require special handling (i.e. because they have children that need to be stringified)
#         case String(val): return val# if top_level else f'"{val}"'
#         case Array(items): return f"[{' '.join(py_stringify(i, scope) for i in items)}]"
#         case Dict(items): return f"[{' '.join(py_stringify(kv, scope) for kv in items)}]"
#         case PointsTo(left, right): return f'{py_stringify(left, scope)}->{py_stringify(right, scope)}'
#         case BidirDict(items): return f"[{' '.join(py_stringify(kv, scope) for kv in items)}]"
#         case BidirPointsTo(left, right): return f'{py_stringify(left, scope)}<->{py_stringify(right, scope)}'
#         case Range(left, right, brackets): return f'{brackets[0]}{py_stringify_range_operands(left, scope)}..{py_stringify_range_operands(right, scope)}{brackets[1]}'
#         case Closure(fn): return f'{fn}'
#         case FunctionLiteral() as fn: return f'{fn}'
#         case Builtin() as fn: return f'{fn}'
#         case Object() as obj: return f'{obj}'
#         # case AtHandle() as at: return py_stringify(evaluate(at, scope), scope)

#         # can use the built-in __str__ method for these types
#         case Int() | Float() | Bool() | Undefined(): return str(ast)

#         # TBD what other types need to be handled
#         case _:
#             pdb.set_trace()
#             raise NotImplementedError(f'stringify not implemented for {type(ast)}')
#     pdb.set_trace()


#     raise NotImplementedError('stringify not implemented yet')

# def py_stringify_range_operands(ast: AST, scope: Scope) -> str:
#     """helper function to stringify range operands which may be a single value or a tuple (represented as an array)"""
#     if isinstance(ast, Array):
#         return f"{','.join(py_stringify(i, scope) for i in ast.items)}"
#     return py_stringify(ast, scope)

# def preprocess_py_print_args(args: list[AST], kwargs: dict[str, AST], scope: Scope) -> tuple[list[Any], dict[str, Any]]:
#     py_args = [py_stringify(i, scope, top_level=True) for i in args]
#     py_kwargs = {k: py_stringify(v, scope) for k, v in kwargs.items()}
#     return py_args, py_kwargs


# TODO
# class BuiltinArgsPreprocessor(Protocol):
#     def __call__(self, args: list[AST], kwargs: dict[str, AST], scope: Scope) -> tuple[list[Any], dict[str, Any]]:
#         ...

class Builtin(CallableBase):
    signature: Signature
    # preprocessor: BuiltinArgsPreprocessor
    # action: QbeFunction
    return_type: AST

    def __str__(self):
        return f'{self.signature}:> {self.return_type} => ...'

    # def from_prototype(proto: PrototypeBuiltin, preprocessor: BuiltinArgsPreprocessor, action: QbeFunction) -> 'Builtin':
    #     return Builtin(
    #         signature=normalize_function_args(proto.args),
    #         preprocessor=preprocessor,
    #         action=action,
    #         return_type=proto.return_type,
    #     )

class Closure(CallableBase):
    fn: FunctionLiteral
    scope: Scope

    def __str__(self):
        return f'{self.fn} with <Scope@{hex(id(self.scope))}>'


"""
# type :String = {l, w...} #long term want to just have unicode code points rather than utf-8 bytes
type :String = {l, b...}

"""

# # TODO:
# def preprocess_py_print_args(args: list[AST], kwargs: dict[str, AST], scope: Scope) -> tuple[list[Any], dict[str, Any]]: ...

# builtin_map: dict[str, tuple[BuiltinArgsPreprocessor, QbeFunction]] = {
#     'printl': (preprocess_py_print_args,
#         QbeFunction(
#             name='$printl',
#             export=False,
#             args=[QbeArg(r'%s', ':String')],
#             ret=None,
#             blocks=[
#                 QbeBlock(
#                     label='@start',
#                     lines=[
#                         'call $print(l %s)',
#                         'call $__putl()'
#                     ]
#                 )
#             ]
#         )
#     ),
#     'print': (preprocess_py_print_args,
#         QbeFunction(
#             name='$print',
#             export=False,
#             args=[QbeArg(r'%s', ':String')],
#             ret=None,
#             blocks=[
#                 QbeBlock(
#                     label='@start',
#                     lines=[
#                         '%len =l loadl %s',
#                         '%data =l add %s 8',
#                         'call $__write(l %val, l %len)',
#                     ]
#                 )
#             ]
#         )
#     ),
#     'readl': (lambda *a: ([],{}),
#         QbeFunction(
#             name='$readl',
#             export=False,
#             args=[QbeArg('%s_ptr', 'l')],
#             ret='l',
#             blocks=[
#                 QbeBlock(
#                     label='@start',
#                     lines=[
#                         # '%data_ptr =l add %s_ptr 8',
#                         # '%len =w call $getl(l %data_ptr)',
#                     ]
#                 )
#             ]
#         )
#     ),
# }

# def insert_builtins(scope: Scope):
#     """replace prototype builtin stubs with actual implementations"""
#     for name, (preprocessor, action) in builtin_map.items():
#         if name in scope.vars:
#             assert isinstance((proto:=scope.vars[name].value), PrototypeBuiltin)
#             scope.vars[name].value = Builtin.from_prototype(proto, preprocessor, action)
#     # if 'printl' in scope.vars:
#     #     assert isinstance((proto:=scope.vars['printl'].value), PrototypeBuiltin)
#     #     scope.vars['printl'].value = Builtin.from_prototype(proto, preprocess_py_print_args, py_printl)
#     # if 'print' in scope.vars:
#     #     assert isinstance((proto:=scope.vars['print'].value), PrototypeBuiltin)
#     #     scope.vars['print'].value = Builtin.from_prototype(proto, preprocess_py_print_args, py_print)
#     # if 'readl' in scope.vars:
#     #     assert isinstance((proto:=scope.vars['readl'].value), PrototypeBuiltin)
#     #     scope.vars['readl'].value = Builtin.from_prototype(proto, lambda *a: ([],{}), py_readl)
