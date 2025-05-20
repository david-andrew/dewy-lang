from ...tokenizer import tokenize
from ...postok import post_process
from ...typecheck import (
    Scope as TypecheckScope,
    top_level_typecheck_and_resolve,# typecheck_and_resolve,
    typecheck_call, typecheck_index, typecheck_multiply,
    register_typeof, register_typeof_call, short_circuit, typeof, TypeExpr,
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
    Less, LessEqual, Greater, GreaterEqual, Equal, NotEqual, MemberIn,
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

import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Literal, TypeVar, Optional
from types import SimpleNamespace
from functools import cache
from itertools import count, groupby
from argparse import Namespace, ArgumentParser
import subprocess
import os


import pdb


from functools import cache
from pathlib import Path



class TBD: ...

# command to compile a .qbe file to an executable
# $ qbe <file>.ssa | gcc -x assembler -static -o hello

# bare metal version of qbe (requires some assembly as the entrypoint/syscall interface, e.g. syscalls.s)
# $ qbe -t <target> all.qbe files.qbe toinclude.qbe > program.s
# $ as -o program.o program.s
# $ as -o syscalls.o
# $ ld -o program program.o syscalls.o


# location of this directory (for referencing build files)
here = Path(__file__).parent


OS = Literal['linux', 'apple', 'windows']
Arch = Literal['x86_64', 'arm64', 'riscv64']
QbeSystem = Literal['amd64_sysv', 'amd64_apple', 'arm64', 'arm64_apple', 'rv64']

arch_map: dict[Arch, str] = {
    'x86_64': 'amd64',
    'arm64': 'arm64',
    'riscv64': 'rv64',
}
os_map: dict[OS, str] = {
    'linux': 'sysv',
    'apple': 'apple',
    'windows': 'windows',
}

@dataclass
class Options(BaseOptions):
    target_os: OS
    target_arch: Arch
    target_system: QbeSystem
    run_program: bool
    emit_asm: bool|Path
    emit_qbe: bool|Path

def make_argparser(parent: ArgumentParser) -> None:
    parent.add_argument('-os', type=str, help='Operating system name for cross compilation. If not provided, defaults to current host OS', choices=OS.__args__)
    parent.add_argument('-arch', type=str, help='Architecture name for cross compilation. If not provided, defaults to current host arch', choices=Arch.__args__)
    parent.add_argument('-b', '--build-only', action='store_true', help='Only compile/build the program, do not run it')
    parent.add_argument('--emit-asm', action='flag_or_explicit', const=True, default=False, metavar='PATH', help='Emit final assembly output. If no path is specified, output will be placed in __dewycache__/<program>.s')
    parent.add_argument('--emit-qbe', action='flag_or_explicit', const=True, default=False, metavar='PATH', help='Emit QBE IR output. If no path is specified, output will be placed in __dewycache__/<program>.qbe')

def make_options(args: Namespace) -> Options:
    # get the host system info
    host_os = platform.system().lower()
    host_arch = platform.machine().lower()
    host_system = get_qbe_target(host_arch, host_os)

    target_os: str = args.os if args.os else host_os
    target_arch: str = args.arch if args.arch else host_arch
    target_system = get_qbe_target(target_arch, target_os)

    cross_compiling = target_system != host_system
    run_program = not args.build_only and not cross_compiling

    # collect the bool or path args
    emit_asm = args.emit_asm if isinstance(args.emit_asm, bool) else Path(args.emit_asm)
    emit_qbe = args.emit_qbe if isinstance(args.emit_qbe, bool) else Path(args.emit_qbe)

    return Options(
        tokens=args.tokens,
        verbose=args.verbose,
        # -------------------- #
        target_os=target_os,
        target_arch=target_arch,
        target_system=target_system,
        run_program=run_program,
        emit_asm=emit_asm,
        emit_qbe=emit_qbe,
    )


def qbe_compiler(path: Path, args: list[str], options: Options) -> None:
    # create a __dewycache__ directory if it doesn't exist
    cache_dir = path.parent / '__dewycache__'
    cache_dir.mkdir(exist_ok=True)

    # get the source code and tokenize
    src = path.read_text()
    tokens = tokenize(src)
    post_process(tokens)

    # parse tokens into AST
    ast = top_level_parse(tokens)
    ast = post_parse(ast)

    # typecheck and collapse any Quantum ASTs to a concrete selection
    scope = Scope.linux_default()
    ast, scope_map = top_level_typecheck_and_resolve(ast, scope)

    # debug printing
    if options.verbose:
        print(repr(ast))

    # Initialize an *empty* QBE Module
    # qbe = QbeModule()

    # Compile the AST into the QBE module. This will create functions as needed.
    scope = Scope.linux_default()
    qbe = top_level_compile(ast, scope)

    # generate the QBE IR string
    ssa = str(qbe)
    if options.verbose:
        print("--- Generated QBE ---")
        print(ssa)
        print("---------------------")

    # write the qbe to a file
    qbe_file = cache_dir / f'{path.name}.qbe'
    qbe_file.write_text(ssa)

    # get paths to the relevant core files
    syscalls = here / f'{options.target_os}-syscalls-{options.target_arch}.s'
    syscalls = syscalls.relative_to(os.getcwd(), walk_up=True)
    program = cache_dir / path.stem

    # compile the qbe file to assembly
    # assemble the assembly files into object files
    # link the object files into an executable
    with program.with_suffix('.s').open('w') as f:
        subprocess.run(['qbe', '-t', options.target_system, qbe_file], stdout=f, check=True)
    subprocess.run(['as', '-o', program.with_suffix('.o'), program.with_suffix('.s')], check=True)
    subprocess.run(['as', '-o', syscalls.with_suffix('.o'), syscalls], check=True)
    subprocess.run(['ld', '-o', program, program.with_suffix('.o'), syscalls.with_suffix('.o')], check=True)

    # clean up qbe, assembly, and object files
    program.with_suffix('.o').unlink(missing_ok=True)
    syscalls.with_suffix('.o').unlink(missing_ok=True) # Keep syscalls.o optional

    # Handle emit options
    if options.emit_qbe is True:
        print(f'QBE output written to {qbe_file}')
    elif isinstance(options.emit_qbe, Path):
        qbe_file.rename(options.emit_qbe)
        print(f'QBE output written to {options.emit_qbe}')
    else: # False
        qbe_file.unlink(missing_ok=True)

    if options.emit_asm is True:
        print(f'Assembly output written to {program.with_suffix(".s")}')
        print(f'Syscall assembly used: {syscalls}')
    elif isinstance(options.emit_asm, Path):
        program.with_suffix('.s').rename(options.emit_asm)
        print(f'Assembly output written to {options.emit_asm}')
        print(f'Syscall assembly used: {syscalls}')
    else: # False
        program.with_suffix('.s').unlink(missing_ok=True)


    # Run the program
    if options.run_program:
        if options.verbose: print(f'./{program} {" ".join(args)}')
        os.execv(program, [program] + args)


# Main compile entry point (modified slightly)
def top_level_compile(ast: AST, scope: 'Scope') -> 'QbeModule':
    """Top-level compilation function."""
    if not isinstance(ast, Group):
        ast = Group([ast])  # Wrap in a Group if not already
    qbe = QbeModule()
    __main__ = QbeFunction(
        name='$__main__',
        export=True,
        args=[QbeArg('%argc', 'l'), QbeArg('%argv', 'l'), QbeArg('%envp', 'l')],
        ret='w', # Exit code is typically 'w' (word)
        blocks=[QbeBlock('@start')]
    )
    qbe.functions.append(__main__)

    compile_group(ast, scope, qbe, __main__)
    compile_deferred_functions(scope, qbe)

    # Add a fallback block that will return from the main function
    __main__.blocks.append(QbeBlock('@__fallback_exit__', ['ret 0']))

    return qbe




qbe_backend = Backend[Options](
    name='qbe',
    exec=qbe_compiler,
    make_argparser = make_argparser,
    make_options = make_options
)



def get_qbe_target(arch_name: Arch, os_name: OS) -> QbeSystem:
    if arch_name not in arch_map:
        raise ValueError(f"Unsupported architecture: {arch_name}, supported: {list(arch_map.keys())}")
    if os_name not in os_map:
        raise ValueError(f"Unsupported OS: {os_name}, supported: {list(os_map.keys())}")

    arch_name = arch_map[arch_name]
    os_name = os_map[os_name]

    qbe_target = arch_name
    if arch_name in ['amd64', 'arm64'] and os_name == 'apple':
        qbe_target += '_apple'
    elif arch_name == 'amd64' and os_name == 'sysv':
        qbe_target += '_sysv'

    return qbe_target

# --- Scope and QBE Data Structures ---
@dataclass
class Scope(TypecheckScope):
    # TODO: note that these are only relevant for linux
    # so probably have default versions for other OS environments...
    @staticmethod
    def _make_linux_syscall_builtin(n:int) -> 'Scope._var':
        """Creates a syscall builtin for the given syscall number"""
        return Scope._var(
            DeclarationType.CONST, Type(Builtin),
            Builtin(normalize_function_args(Group([
                TypedIdentifier(Identifier('n'), Type(Int)),
                *[TypedIdentifier(Identifier(f'a{i}'), Type(Int)) for i in range(n)]
            ])), Type(Int))
        )
    @staticmethod
    def _make_qbe_builtin(args: 'list[QbeType]', ret: 'QbeType|None'=None) -> 'Scope._var':
        return Scope._var(
            DeclarationType.CONST, Type(Builtin),
            Builtin(normalize_function_args(Group([
                TypedIdentifier(Identifier(f'a{i}'), Type(Int)) for i in range(len(args))
            ])), Type(Int) if ret else void),
        )

    @staticmethod
    def linux_default() -> 'Scope':
        """A default scope for when compiling to linux. Contains merely __syscall1__ to __syscall6__"""
        syscalls = {f'__syscall{i}__': Scope._make_linux_syscall_builtin(i) for i in range(0, 7)}
        """
        TODO: stack memory functions in qbe
        stored -- (d,m)
        stores -- (s,m)
        storel -- (l,m)
        storew -- (w,m)
        storeh -- (w,m)
        storeb -- (w,m)
        loadd -- d(m)
        loads -- s(m)
        loadl -- l(m)
        loadsw, loaduw -- I(mm)
        loadsh, loaduh -- I(mm)
        loadsb, loadub -- I(mm)
        blit -- (m,m,w)
        alloc4 -- m(l)
        alloc8 -- m(l)
        alloc16 -- m(l)
        """
        stackmem = {
            '#storel': Scope._make_qbe_builtin(['l', 'l']),
            '#loadl': Scope._make_qbe_builtin(['l'], 'l'),
            '#loadub': Scope._make_qbe_builtin(['l'], 'l'),
            '#alloc8': Scope._make_qbe_builtin(['l'], 'l'),
        }
        scope = Scope(vars={**syscalls, **stackmem})
        # scope.meta[void].stackmem = stackmem # hack for now to let us know which functions are these specific qbe opcodes
        return scope


    # # Add apple_default(), windows_default() etc. later

# QBE Type definition (can be expanded later for structs etc.)
QbeType = Literal['w', 'l', 's', 'd', 'b', 'h'] | str # Allow custom type names (structs)


# how are specific dewy types represented as QBE values (what is physically passed around)
# most things will probably be `l` and just be a void* pointer under the hood...
dewy_qbe_type_map: dict[Type, QbeType] = {
    Type(Int): 'l',
    # TODO: add more...
}

@dataclass
class QbeBlock:
    label: str
    lines: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        indent = '    '
        # Ensure label starts with @, handle empty lines
        label_str = self.label if self.label.startswith('@') else f'@{self.label}'
        lines_str = '\n'.join(f'{indent}{line}' for line in self.lines if line.strip())
        # Only add newline if there are lines
        return f'{label_str}\n{lines_str}' if lines_str else label_str

@dataclass
class QbeArg:
    name: str
    type: QbeType

    def __str__(self) -> str:
        # Handle potential custom types (structs) prepended with ':'
        type_str = self.type if not self.type.startswith(':') else self.type[1:]
        return f'{type_str} {self.name}'

@dataclass
class QbeFunction:
    name: str
    export: bool
    args: list[QbeArg]
    ret: QbeType | None
    blocks: list[QbeBlock]

    def __str__(self) -> str:
        export_str = 'export ' if self.export else ''
        args_str = ', '.join(map(str, self.args))
        ret_str = f'{self.ret} ' if self.ret else '' # QBE requires space after type if present
        # Filter out empty blocks before joining
        # Ensure there's at least one block string, even if empty, to put inside {}
        block_strs = [str(b) for b in self.blocks if b.label or b.lines]
        blocks_str = '\n'.join(block_strs) if block_strs else ''
        # Ensure there's a newline between header and first block if blocks exist
        sep = '\n' if blocks_str else ''
        return f'{export_str}function {ret_str}{self.name}({args_str}) {{\n{blocks_str}{sep}}}'


@dataclass
class QbeModule:
    functions: list[QbeFunction] = field(default_factory=list)
    global_data: list[str] = field(default_factory=list)
    _counter: count = field(default_factory=lambda: count(0))
    # _symbols: dict[str, TypeExpr] = field(default_factory=dict) # Map temp names to Dewy types
    _symbols: dict[str, str] = field(default_factory=dict) # Map dewy scope names to QBE IR names

    def get_temp(self, prefix: str = "%.") -> str:
        """Gets the next available temporary variable name."""
        return f"{prefix}{next(self._counter)}"

    def __str__(self) -> str:
        # Ensure proper spacing between sections
        data_str = '\n'.join(self.global_data)
        funcs_str = '\n\n'.join(map(str, self.functions))
        sep1 = '\n\n' if data_str and funcs_str else '\n' if data_str or funcs_str else ''
        return f'{data_str}{sep1}{funcs_str}'.strip()


# --- Compilation Logic ---

# return type from compiling. AST so it can go in the scope
class IR(AST):
    qbe_type: QbeType
    qbe_value: str # could be a literal value or a name
    dewy_type: Type
    meta: SimpleNamespace = field(default_factory=SimpleNamespace)
    #TODO: something about the scope it's in... Or more specifically which QBE function it is in and can be accessed from

    def __str__(self) -> str:
        return f'IR(qbe=`{self.qbe_type} {self.qbe_value}`, type=`{self.dewy_type}`)'

    def __repr__(self) -> str:
        return self.__str__()

class DeferredFunctionIR(AST):
    # type: Literal['function'] # TODO: potentially have multiple deferred types
    name: str
    fn: FunctionLiteral
    scope: Scope
    qbe: QbeModule
    current_func: QbeFunction
    meta: SimpleNamespace = field(default_factory=SimpleNamespace)

    def __str__(self) -> str:
        return f'DeferredFunctionIR(name={self.name}, fn={self.fn}, ...)'


T = TypeVar('T', bound=AST)
class CompileFunc(Protocol):
    def __call__(self, ast: T, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> Optional[IR]:
        """
        Compiles the AST node, potentially adding instructions to current_block
        (if provided and applicable, e.g., inside a function).
        Returns the QBE temporary variable name (%tmpN) or literal ('l 42')
        representing the result of the expression, or None if the node
        represents an action with no return value (like top-level Assign).
        For top-level nodes like function definitions, current_block might be None.
        """
        ...


# --- Specific Compile Functions ---
@cache
def get_compile_fn_map() -> dict[type[AST], CompileFunc]:
    """Returns the dispatch map for compilation functions."""
    return {
        Void: lambda ast, scope, qbe, current_func: None,
        Declare: compile_declare,
        Assign: compile_assign,
        Express: compile_express,
        FunctionLiteral: compile_fn_literal,
        Closure: compile_fn_literal,
        Call: compile_call,
        Group: compile_group,
        Int: compile_int,
        String: compile_string,
        IString: compile_istring,
        And: compile_base_logical_binop,
        Or: compile_base_logical_binop,
        Xor: compile_base_logical_binop,
        Nand: compile_notted_logical_binop,
        Nor: compile_notted_logical_binop,
        Xnor: compile_notted_logical_binop,
        Not: compile_not,
        Less: compile_compare,
        LessEqual: compile_compare,
        Greater: compile_compare,
        GreaterEqual: compile_compare,
        Equal: compile_compare,
        NotEqual: compile_compare,
        Add: compile_arithmetic_binop,
        Sub: compile_arithmetic_binop,
        Mul: compile_arithmetic_binop,
        # Div: compile_arithmetic_binop,
        IDiv: compile_arithmetic_binop,
        Mod: compile_arithmetic_binop,
        Flow: compile_flow,
        Access: compile_access,
        IterIn: compile_iter_in,
        Range: compile_range,


        # Add other AST types here as they are implemented
    }


def compile(ast: AST, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> Optional[IR]:
    """Dispatches compilation to the appropriate function based on AST node type."""
    compile_fn_map = get_compile_fn_map()

    ast_type = type(ast)
    if ast_type in compile_fn_map:
        return compile_fn_map[ast_type](ast, scope, qbe, current_func)

    raise NotImplementedError(f'QBE compilation not implemented for AST type: {ast_type}')




def compile_declare(ast: Declare, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> None:
    """Handles variable declarations."""
    match ast.target:
        case Identifier(name=name):
            pdb.set_trace()
            ...
        case Assign(left=Identifier(name=name)):
            scope.declare(name, void, untyped, ast.decltype)
            compile_assign(ast.target, scope, qbe, current_func)
        case _:
            raise NotImplementedError(f"Declaration target not implemented: {ast.target}")

    return None



def compile_assign(ast: Assign, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> None:
    """Handles assignments, creating functions when assigning FunctionLiterals."""
    current_block = current_func.blocks[-1]
    match ast:
        case Assign(left=Identifier(name=name), right=FunctionLiteral() as fn):
            # functions are compiled after all expressions in the current block have been done
            defer_compile_assign_fn(name, fn, scope, qbe, current_func)
        case Assign(left=Identifier(name=name), right=right):
            rhs = compile(right, scope, qbe, current_func)
            if rhs is None:
                raise ValueError(f'INTERNAL ERROR: attempting to assign some type that doesn\'t produce a value: {name}={right!r}')
            scope.assign(name, rhs)
            qid = qbe._symbols.get(name) or qbe.get_temp() # see if a variable exists already. otherwise make a new one
            qbe._symbols[name] = qid
            current_block.lines.append(f'{qid} ={rhs.qbe_type} copy {rhs.qbe_value}')
        case _:
            raise NotImplementedError(f"Assignment target not implemented: left={ast.left}, right={ast.right}")

    return None


def defer_compile_assign_fn(name: str, fn: FunctionLiteral, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> None:
    # attach this function for later compilation
    root = list(scope)[-1]  # get the top most scope
    if not hasattr(root.meta, 'deferred_functions'):
        root.meta.deferred_functions = {}
    root.meta.deferred_functions[name] = (fn, scope, qbe, current_func)

    # insert the function into the scope so other stuff can refer to it
    # ir = IR('l', 'function l ${name}(l %argc, l %argv, l %envp) {{...}}', Type(FunctionLiteral))
    ir = DeferredFunctionIR(name, fn, scope, qbe, current_func)
    # ir.meta.fn = fn
    # ir.meta.name = name
    # ir.meta.scope = scope
    # # ir.meta.qbe = qbe  # TBD if we need this. for now compiling single files, there will only be a single module.
    # ir.meta.current_func = current_func
    scope.assign(name, ir)


def compile_deferred_functions(scope: Scope, qbe: QbeModule) -> None:
    root = list(scope)[-1]
    if not hasattr(root.meta, 'deferred_functions'):
        return
    for name, (fn, scope, qbe, current_func) in root.meta.deferred_functions.items():
        # compile the function
        ir = compile_fn_literal(fn, scope, qbe, current_func)
        # add the function IR into the QBE module
        qbe.functions.append(QbeFunction(name, False, ir.meta.args, ir.meta.ret, ir.meta.blocks))


def compile_fn_literal(ast: 'FunctionLiteral|Closure', scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:
    """
    ir = compile_fn_literal(fn, scope, qbe, current_func)
    qbe.functions.append(QbeFunction(name, False, ir.meta.args, ir.meta.ret, ir.meta.blocks))
    """
    pdb.set_trace()
    ...

def compile_express(ast: Express, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:
    # get the previous IR for the original value that should be set
    ir_var = scope.get(ast.id.name)
    ir = ir_var.value
    assert isinstance(ir, (IR, DeferredFunctionIR)), f'INTERNAL ERROR: expected IR AST in scope for id "{ast.id}", but got {ir!r}'

    if isinstance(ir, DeferredFunctionIR):
        # the function must be compiled at this point since it's being used
        ir = compile_fn_literal(ir.fn, ir.scope, ir.qbe, ir.current_func)

    if ir.dewy_type.t in (FunctionLiteral, Closure):
        #TBD, not sure if this is even allowed
        pdb.set_trace()
        return compile_call_function

    #TODO: need a check to verify the IR is contained in the same QBE function as it's being used...

    # value should be in symbol table? there are cases where it wouldn't but that's advanced out of order compilation stuff...
    assert ast.id.name in qbe._symbols, f'TBD if this is an internal error or not. Attempted to express a value which is not in the symbol table from compiling. {ast=!r}'
    express_ir = IR(ir.qbe_type, qbe._symbols[ast.id.name], ir.dewy_type, ir.meta)

    return express_ir


def make_anonymous_function_name(qbe: QbeModule) -> str:
    """Generates a unique name for an anonymous function."""
    return f'.anonymous_fn.{next(qbe._counter)}'


def compile_call(ast: Call, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> Optional[IR]:
    """Compiles a function call."""
    if not isinstance(ast.f, Identifier):
        # create an anonymous function
        ir = compile(ast.f, scope, qbe, current_func)
        pdb.set_trace()
        # assert isinstance(ast.f, (FunctionLiteral, Closure)), f"INTERNAL ERROR: expected identifier or function literal for function call, but got {ast.f!r}"
        # ir = compile_fn_literal(ast.f, scope, qbe, current_func)
        name = make_anonymous_function_name(qbe)
        scope.assign(name, ir)
        qbe.functions.append(QbeFunction(name, False, ir.meta.args, ir.meta.ret, ir.meta.blocks))
        ast.f = Identifier(name)  # Update the function call to use the new name


    if ast.f.name.startswith('#'):
        return compile_call_hashtag(ast, scope, qbe, current_func)

    # get the QBE name of the function
    f_id = f'${ast.f.name}'

    # get the return type of the function
    f_var = scope.get(ast.f.name)
    match f_var.value:
        case FunctionLiteral(return_type=dewy_return_type) | Builtin(return_type=dewy_return_type) | Closure(FunctionLiteral(return_type=dewy_return_type)):
            # dewy_return_type = return_type
            if not isinstance(dewy_return_type, Type):
                pdb.set_trace()
                dewy_return_type = typeof(dewy_return_type, scope)
            ret_type = dewy_qbe_type_map[dewy_return_type]
        case _:
            raise ValueError(f'Unrecognized AST type to call: {f_var.value!r}')


    # convert calling args into a group if not already
    ast_args = ast.args
    match ast_args:
        case Group(): ... # already good
        case Void() | None:  ast_args = Group([])
        case _:       ast_args = Group([ast_args])


    qbe_args = [compile(arg, scope, qbe, current_func) for arg in ast_args.items]
    assert not any(arg is None for arg in qbe_args), f"INTERNAL ERROR: function call arguments must produce values: {ast_args}"

    args_str = ', '.join([f'{arg.qbe_type} {arg.qbe_value}' for arg in qbe_args])

    # insert the call with the result being saved to a new temporary id
    ret_id = qbe.get_temp()
    current_block = current_func.blocks[-1]
    current_block.lines.append(f'{ret_id} ={ret_type} call {f_id}({args_str})')

    return IR(ret_type, ret_id, dewy_return_type)

"""
TODO: stack memory functions in qbe
stored -- (d,m)
stores -- (s,m)
storel -- (l,m)
storew -- (w,m)
storeh -- (w,m)
storeb -- (w,m)
loadd -- d(m)
loads -- s(m)
loadl -- l(m)
loadsw, loaduw -- I(mm)
loadsh, loaduh -- I(mm)
loadsb, loadub -- I(mm)
blit -- (m,m,w)
alloc4 -- m(l)
alloc8 -- m(l)
alloc16 -- m(l)
"""
# stackmem = {
#     '#storel': Scope._make_qbe_builtin(['l', 'l']),
#     '#loadl': Scope._make_qbe_builtin(['l'], 'l'),
#     '#loadub': Scope._make_qbe_builtin(['l'], 'l'),
#     '#alloc8': Scope._make_qbe_builtin(['l'], 'l'),
# }
stackmem_types: dict[str, tuple[QbeType|None, tuple[QbeType, ...]]] = {
    "#stored": (None, ('d','l')),
    "#stores": (None, ('s','l')),
    "#storel": (None, ('l','l')),
    "#storew": (None, ('w','l')),
    "#storeh": (None, ('w','l')),
    "#storeb": (None, ('w','l')),
    "#loadd": ('d', ('l',)),
    "#loads": ('s', ('l',)),
    "#loadl": ('l', ('l',)),
    # TODO: tbd how these signed loads work, what types they return, etc.
    # "#loadsw": loaduw -- I(mm)),
    # "#loadsh": loaduh -- I(mm)),
    # "#loadsb": loadub -- I(mm)),
    '#loadub': ('l', ('l',)),
    '#loadsb': ('l', ('l',)),
    '#loaduh': ('l', ('l',)),
    '#loadsh': ('l', ('l',)),
    '#loaduw': ('l', ('l',)),
    '#loadsw': ('l', ('l',)),
    "#blit": (None, ('l','l','w')),
    "#alloc4": ('l', ('l',)),
    "#alloc8": ('l', ('l',)),
    "#alloc16": ('l', ('l',)),
}


def compile_call_hashtag(ast: Call, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR|None:
    """Compiles a call to a hashtag function which might get special handling"""
    assert isinstance(ast.f, Identifier), f'INTERNAL ERROR: compile_call_hashtag expected a hashtag (Identifier) as the function. Got {ast.f!r}'



    # collect the function from the scope
    name = ast.f.name
    assert name in stackmem_types or name in scope.vars, f'ERROR: attempted to call nonexistent hashtag function'

    # build the args that will be used to call the fn
    args = compile_call_args(ast.args, scope, qbe, current_func)

    # check if name is a qbe intrinsic operation
    if name in stackmem_types:
        res_type, call_types = stackmem_types[name]
        opcode = name[1:]
        qbe_lhs = ''
        ir = None
        if res_type is not None:
            res_id = qbe.get_temp()
            qbe_lhs = f'{res_id} ={res_type} '
            ir = IR(res_type, res_id, Type(Int))
        current_func.blocks[-1].lines.append(f'{qbe_lhs}{opcode} {", ".join(a.qbe_value for a in args)}')
        return ir


    # more regular function compilation
    var = scope.get(name, False)
    if var is None:
        raise Exception(f'ERROR: attempted to call non-existent hashtag function `{name}` with args {ast.args}.')

    pdb.set_trace()
    raise NotImplementedError(f"Hashtag function calls are not implemented yet: {ast.f.name}({ast.args})")

def compile_call_args(ast: AST|None, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> list[IR]:
    if ast is None:
        return []

    if not isinstance(ast, Group):
        ast = Group([ast])

    args: list[IR] = []

    for arg_ast in ast.items:
        ir = compile(arg_ast, scope, qbe, current_func)
        if ir is not None:
            args.append(ir)

    return args


def compile_group(ast: Group, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> Optional[IR]:
    """Compiles a group"""

    results = []
    for item in ast.items:
        result = compile(item, scope, qbe, current_func)
        if result is not None:
            results.append(result)

    # depending on how many values are present in the result, handle the group differently
    if len(results) == 0:
        return None
    elif len(results) == 1:
        return results[0]


    # if top level scope, doesn't matter if there were multiple values
    # TODO: this isn't actually correct, because there could be an unscoped group at the top level...
    if scope.parent is None:
        return

    print('WARNING/TODO: group has multiple values. probably handle at the higher level')
    pdb.set_trace()
    ...
    raise NotImplementedError(f'groups that express more than 1 value are not implemented yet. {ast} => {list(map(str, results))}')

    # if current_block is None and len(ast.items) > 0:
    #     # This might happen if a Group is the top-level AST node after `compile` starts.
    #     # This case needs refinement. Can a bare group be a valid top-level program?
    #     # For now, assume it needs a block context.
    #     raise ValueError("Cannot compile a Group node outside of a function block context.")
    #     # OR, if valid: Compile last item, but where do instructions go? Needs thought.

    # last_val = None
    # for item in ast.items:
    #     # Ensure we pass the current_block down
    #     last_val = compile(item, scope, qbe, current_block)

    # # The group itself evaluates to its last contained expression's value.
    # return last_val


def compile_int(ast: Int, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:
    """Returns the QBE representation of an integer literal."""
    # QBE uses direct integers for constants. Prepend type for clarity in instruction.
    # The 'l' type is added by the instruction using this value (e.g., call)
    # TODO: check if the integer overflows, and return a big int
    # TODO: use concrete integer type (i.e. probably int64, and then is BigInt if overflows)
    return IR( 'l', f"{ast.val}", Type(Int))


def string_to_qbe_repr(s: str, include_null_terminator: bool = True) -> tuple[str, int]:
    """Convert a string to a QBE literal representation. For now uses utf-8 encoding."""
    groups = groupby(s.encode('utf-8'), lambda c: 0x20 <= c <= 0x7E)
    groups = [''.join(map(chr, values)) if key else list(values) for key, values in groups]

    # combine printable characters into strings, leave non-printable as byte arrays
    items = []
    for element in groups:
        if isinstance(element, str):
            items.append(f'b "{element}"')
        else:
            # Non-printable characters are escaped
            items.append('b ' + ' '.join(f'{c}' for c in element))

    # Append null terminator if requested
    if include_null_terminator:
        items.append('b 0') # Append null terminator
    qbe_str = f'{{ {", ".join(items)}}}'

    # Calculate the length of the string representation
    length = sum(map(len, groups)) + int(include_null_terminator)

    return qbe_str, length


def compile_string(ast: String, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:
    """Returns the QBE representation of a string literal."""
    data_id = qbe.get_temp('$str')
    qbe_str_data, length = string_to_qbe_repr(ast.val)
    qbe.global_data.append(f'data {data_id} = {qbe_str_data}')
    ir = IR('l', data_id, Type(String))
    ir.meta.length = length
    return ir

def compile_istring(ast: IString, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:
    """Compile an interpolated string. If no interpolated values, fallback to regular string."""
    if all(isinstance(i, String) for i in ast.parts):
        return compile_string(String(''.join(i.val for i in ast.parts)), scope, qbe, current_func)

    pdb.set_trace()
    ...
    # TODO: consider this concrete representation:
    #       compiles to a function that takes a callback, and for each component of the istring
    #       calls the callback with the stringified current chunk from the istring
    # something like this:
    """
    function l $use_istring_<N>(l %callback) {
        # generate qbe for all chunks in the istring
        # if chunk is already string
        %chunk = $pointer to the string chunk
        call %callback(l %chunk)

        # otherwise, need to convert the chunk to a string which can then be passed to the callback
        # or if chunk is another istring, can recurse into it with the current callback
        # mainly it's when the chunk is a (non-const) variable that there needs to be a runtime conversion
    }
    """
    raise NotImplementedError(f"Interpolated strings not implemented yet: {ast!r}")



logical_binop_opcode_map = {
    (And, Int, Int): 'and',
    (And, Bool, Bool): 'and',
    (Or, Int, Int): 'or',
    (Or, Bool, Bool): 'or',
    (Xor, Int, Int): 'xor',
    (Xor, Bool, Bool): 'xor',

}
def compile_base_logical_binop(ast: And|Or|Xor, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:
    """Compiles a base/builtin logical operation."""
    left_ir = compile(ast.left, scope, qbe, current_func)
    assert left_ir is not None, f"INTERNAL ERROR: left side of `{ast.__class__.__name__}` must produce a value: {ast.left!r}"
    right_ir = compile(ast.right, scope, qbe, current_func)
    assert right_ir is not None, f"INTERNAL ERROR: right side of `{ast.__class__.__name__}` must produce a value: {ast.right!r}"
    assert left_ir.qbe_type == right_ir.qbe_type, f"INTERNAL ERROR: `{ast.__class__.__name__}` operands must be the same type: {left_ir.qbe_type} and {right_ir.qbe_type}"
    dewy_res_type = typeof(ast, scope)

    res_id = qbe.get_temp()
    res_type = left_ir.qbe_type

    # get the opcode name associated with this AST
    key = (type(ast), left_ir.dewy_type.t, right_ir.dewy_type.t)
    if key not in logical_binop_opcode_map:
        raise NotImplementedError(f'logical binop not implemented for types {key=}. from {ast!r}')
    opcode = logical_binop_opcode_map[key]

    # perform the logical operation
    current_block = current_func.blocks[-1]
    current_block.lines.append(f'{res_id} ={res_type} {opcode} {left_ir.qbe_value}, {right_ir.qbe_value}')

    # if type was bool, need to mask the upper bits
    # Note this is technically not SSA compliant as we reuse res_id, but QBE conveniently handles it properly
    if left_ir.dewy_type.t == Bool:
        current_block.lines.append(f'{res_id} ={res_type} and {res_id}, 1')

    return IR(res_type, res_id, dewy_res_type) #TBD if there is any propagating of the left+right meta info here...


def compile_not(ast: Not, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:
    """use xor x, -1 to handle NOT"""
    operand_ir = compile(ast.operand, scope, qbe, current_func)
    assert operand_ir is not None, f'INTERNAL ERROR: operand of `Not` must produce a value: {ast.operand!r}'
    dewy_res_type = typeof(ast, scope)

    res_id = qbe.get_temp()
    res_type = operand_ir.qbe_type

    # perform the not operation
    current_block = current_func.blocks[-1]
    current_block.lines.append(f'{res_id} ={res_type} xor {operand_ir.qbe_value}, -1')

    # if type was bool, need to mask the upper bits
    # Note this is technically not SSA compliant as we reuse res_id, but QBE conveniently handles it properly
    if operand_ir.dewy_type.t == Bool:
        current_block.lines.append(f'{res_id} ={res_type} and {res_id}, 1')

    return IR(res_type, res_id, dewy_res_type) #TBD if there is any propagating of the operand meta info here...


def compile_notted_logical_binop(ast: Nand|Nor|Xnor, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:

    match ast:
        case Nand(): base_cls = And
        case Nor():  base_cls = Or
        case Xnor(): base_cls = Xor
        case _:
            raise NotImplementedError(f"INTERNAL ERROR: expected Nand, Nor, or Xnor, but got {ast!r}")

    composite_ast = Not(base_cls(ast.left, ast.right))
    final_ir = compile_not(composite_ast, scope, qbe, current_func)

    return final_ir



comparison_binop_opcode_map = {
    (Less, Int): 'lt',
    (LessEqual, Int): 'lt',
    (Greater, Int): 'gt',
    (GreaterEqual, Int): 'ge',
    (Equal, Int): 'eq',
    (NotEqual, Int): 'ne',
}
def compile_compare(ast: Less|LessEqual|Greater|GreaterEqual|Equal|NotEqual, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:
    left_ir = compile(ast.left, scope, qbe, current_func)
    assert left_ir is not None, f"INTERNAL ERROR: left side of `{ast.__class__.__name__}` must produce a value: {ast.left!r}"
    right_ir = compile(ast.right, scope, qbe, current_func)
    assert right_ir is not None, f"INTERNAL ERROR: right side of `{ast.__class__.__name__}` must produce a value: {ast.right!r}"
    assert left_ir.dewy_type.t == right_ir.dewy_type.t, f"INTERNAL ERROR: `{ast.__class__.__name__}` operands must be the same type: {left_ir.dewy_type.t} and {right_ir.dewy_type.t}"
    dewy_res_type = typeof(ast, scope)

    res_id = qbe.get_temp()
    res_type: QbeType = 'l' # booleans are represented as integers in QBE. 0 is false, 1 is true


    # use signed comparisons for now
    # TODO: in the future, signed/unsigned will be based on the type

     # get the opcode name associated with this AST
    key = (type(ast), left_ir.dewy_type.t)
    if key not in comparison_binop_opcode_map:
        raise NotImplementedError(f'comparison binop not implemented for types {key=}. from {ast!r}')
    comparison_opcode = comparison_binop_opcode_map[key]
    #TODO: could be unsigned depending on the operand types. also floating point comparisons don't get the signed/unsigned marker--they are always assumed signed
    signed_marker = '' if type(ast) in (Equal, NotEqual) else 's'
    opcode = f'c{signed_marker}{comparison_opcode}{left_ir.qbe_type}'

    # perform the comparison operation
    current_block = current_func.blocks[-1]
    current_block.lines.append(f'{res_id} ={res_type} {opcode} {left_ir.qbe_value}, {right_ir.qbe_value}')
    return IR(res_type, res_id, dewy_res_type)



arithmetic_binop_opcode_map = {
    (Add, Int, Int): 'add',
    (Sub, Int, Int): 'sub',
    (Mul, Int, Int): 'mul',
    (IDiv, Int, Int): 'div',
    (Mod, Int, Int): 'rem',
}
# TODO: note div/rem have unsigned versions, otherwise assume inputs are signed.
def compile_arithmetic_binop(ast: Add|Sub|Mul|IDiv|Mod, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:
    left_ir = compile(ast.left, scope, qbe, current_func)
    assert left_ir is not None, f"INTERNAL ERROR: left side of `{ast.__class__.__name__}` must produce a value: {ast.left!r}"
    right_ir = compile(ast.right, scope, qbe, current_func)
    assert right_ir is not None, f"INTERNAL ERROR: right side of `{ast.__class__.__name__}` must produce a value: {ast.right!r}"
    assert left_ir.dewy_type.t == right_ir.dewy_type.t, f"INTERNAL ERROR: `{ast.__class__.__name__}` operands must be the same type: {left_ir.dewy_type.t} and {right_ir.dewy_type.t}"
    dewy_res_type = typeof(ast, scope)

    res_id = qbe.get_temp()
    res_type = left_ir.qbe_type

    # get the opcode name associated with this AST
    key = (type(ast), left_ir.dewy_type.t, right_ir.dewy_type.t)
    if key not in arithmetic_binop_opcode_map:
        raise NotImplementedError(f'arithmetic binop not implemented for types {key=}. from {ast!r}')
    opcode = arithmetic_binop_opcode_map[key]

    # perform the arithmetic operation
    current_block = current_func.blocks[-1]
    current_block.lines.append(f'{res_id} ={res_type} {opcode} {left_ir.qbe_value}, {right_ir.qbe_value}')

    return IR(res_type, res_id, dewy_res_type)


def compile_flow(ast: Flow, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> None | IR:

    # create blocks for each branch
    unique_num = qbe.get_temp('')
    assert len(ast.branches) > 0, f"INTERNAL ERROR: Flow must have at least one branch: {ast}"

    end_label = f'@.{unique_num}.flow.end'
    for i, branch in enumerate(ast.branches):
        base_label = f'@.{unique_num}.{i}.flow.{branch.__class__.__name__.lower()}'

        # determine the label of the next branch (i.e. if this one's condition is false)
        if i < len(ast.branches) - 1: next_label = f'@.{unique_num}.{i+1}.flow.{ast.branches[i+1].__class__.__name__.lower()}.start'
        else:                         next_label = end_label

        match branch:
            # TODO: eventually these may return IR
            case If():      compile_if(branch, scope, qbe, current_func, base_label, next_label, end_label)
            case Loop():    compile_loop(branch, scope, qbe, current_func, base_label, next_label, end_label)
            case Default(): compile_default(branch, scope, qbe, current_func, base_label, next_label, end_label)

    current_func.blocks.append(QbeBlock(end_label))

def compile_if(ast: If, scope: Scope, qbe: QbeModule, current_func: QbeFunction, base_label: str, next_label: str, end_label: str) -> IR|None:
    # create the first block containing the condition for the if statement
    start_block = QbeBlock(f'{base_label}.start')
    current_func.blocks.append(start_block)
    cond_ir = compile(ast.condition, scope, qbe, current_func)
    current_func.blocks[-1].lines.append(f'jnz {cond_ir.qbe_value}, {base_label}.body, {next_label}')

    # create the body block
    body_block = QbeBlock(f'{base_label}.body')
    current_func.blocks.append(body_block)
    body_ir = compile(ast.body, scope, qbe, current_func)
    # pdb.set_trace()
    current_func.blocks[-1].lines.append(f'jmp {end_label}')

    # TODO: this could potentially return IR


def compile_loop(ast: Loop, scope: Scope, qbe: QbeModule, current_func: QbeFunction, base_label: str, next_label: str, end_label: str) -> IR|None:
    # create the first block containing the initial condition for the loop
    start_block = QbeBlock(f'{base_label}.start')
    current_func.blocks.append(start_block)
    cond_ir = compile(ast.condition, scope, qbe, current_func)
    current_func.blocks[-1].lines.append(f'jnz {cond_ir.qbe_value}, {base_label}.body, {next_label}')

    # create the continue block (reuse the compile of the start block)
    continue_block = QbeBlock(f'{base_label}.continue')#, start_block.lines[:-1])
    current_func.blocks.append(continue_block)
    continue_ir = compile(ast.condition, scope, qbe, current_func)
    current_func.blocks[-1].lines.append(f'jnz {continue_ir.qbe_value}, {base_label}.body, {end_label}')

    # create the body block
    body_block = QbeBlock(f'{base_label}.body')
    current_func.blocks.append(body_block)
    body_ir = compile(ast.body, scope, qbe, current_func)
    current_func.blocks[-1].lines.append(f'jmp {base_label}.continue')


    # TODO: this could potentially return IR


def compile_default(ast: Default, scope: Scope, qbe: QbeModule, current_func: QbeFunction, base_label: str, next_label: str, end_label: str) -> IR|None:
    current_func.blocks.append(QbeBlock(f'{base_label}.start', [f'jmp {base_label}.body']))
    body_block = QbeBlock(f'{base_label}.body')
    current_func.blocks.append(body_block)
    body_ir = compile(ast.body, scope, qbe, current_func)
    body_block.lines.append(f'jmp {end_label}')


    # TODO: this could potentially return IR





def compile_access(ast: Access, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:
    left = compile(ast.left, scope, qbe, current_func)
    assert left is not None, f"INTERNAL ERROR: left side of `{ast.__class__.__name__}` must produce a value: {ast.left!r}"
    if left.dewy_type.t == String:
        if not isinstance(ast.right, Identifier):
            raise ValueError(f"ERROR: can only access string members with identifiers, not {ast.right!r}. `{ast}`")
        member = ast.right.name
        if member == '_bytes_ptr':
            return left # the string itself already is the bytes pointer
        if member == '_bytes_length':
            return IR('l', f'{left.meta.length}', Type(Int))

        raise NotImplementedError(f"ERROR: currently only support accessing `_bytes_ptr` and `_bytes_length` members of strings, not {member!r}. `{ast}`")



    pdb.set_trace()
    raise NotImplementedError(f"INTERNAL ERROR: Accessing type {left.dewy_type.t} is not implemented yet. {ast.left} -> {ast.right}")

    pdb.set_trace()
    ...



def compile_iter_in(ast: IterIn, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:
    if not isinstance(ast.left, Identifier):
        raise NotImplementedError(f"iter in is not implement for unpack/etc. left side. {ast.left!r} in {ast.right!r}")
    name = ast.left.name

    current_block = current_func.blocks[-1]

    # determine if the iterator is being used as part of a loop start condition
    context: Literal['loop.start', 'loop.continue', None] = None
    if current_block.label.endswith('loop.start'):
        context = 'loop.start'
    elif current_block.label.endswith('loop.continue'):
        context = 'loop.continue'
    else:
        raise NotImplementedError(f"iter in is not implement for non-loop contexts ({current_block.label}). {ast})")


    if context == 'loop.start':
        rhs = compile(ast.right, scope, qbe, current_func)
        if rhs is None:
            raise ValueError(f'INTERNAL ERROR: attempting to iterate over some type that doesn\'t produce a value: {name} in {ast.right!r}')

        iter_i_id = qbe._symbols.get(name) or qbe.get_temp() # see if a variable exists already. otherwise make a new one
        qbe._symbols[name] = iter_i_id

        if rhs.dewy_type.t == Range and rhs.meta.kind == (Int, Int):
            scope.assign(name, IR('l', f'{rhs.meta.left}', Type(Int)))
            current_block.lines.append(f'{iter_i_id} =l copy {rhs.meta.left}')
            cmp_id = qbe.get_temp()
            cmp_type = 'csltl' if rhs.meta.brackets[1] == ')' else 'cslel'
            current_block.lines.append(f'{cmp_id} =l {cmp_type} {iter_i_id}, {rhs.meta.right}')
            return IR('l', cmp_id, Type(Bool))
        # elif ...: ...
        else:
            pdb.set_trace()
            raise NotImplementedError(f"ERROR: iter in not implemented for type {rhs.dewy_type.t}. {ast.left} in {ast.right}")


        pdb.set_trace()
        ...
    if context == 'loop.continue':
        rhs = compile(ast.right, scope, qbe, current_func)
        if rhs is None:
            raise ValueError(f'INTERNAL ERROR: attempting to iterate over some type that doesn\'t produce a value: {name} in {ast.right!r}')

        assert name in qbe._symbols, f"INTERNAL ERROR: iter in failed to find {name} in the symbol table. {ast.left} in {ast.right}"
        iter_i_id = qbe._symbols.get(name) or qbe.get_temp() # see if a variable exists already. otherwise make a new one
        qbe._symbols[name] = iter_i_id

        if rhs.dewy_type.t == Range and rhs.meta.kind == (Int, Int):
            current_block.lines.append(f'{iter_i_id} =l add {iter_i_id}, {rhs.meta.step}')
            cmp_id = qbe.get_temp()
            cmp_type = 'csltl' if rhs.meta.brackets[1] == ')' else 'cslel'
            current_block.lines.append(f'{cmp_id} =l {cmp_type} {iter_i_id}, {rhs.meta.right}')
            return IR('l', cmp_id, Type(Bool))
        # elif ...: ...
        else:
            pdb.set_trace()
            raise NotImplementedError(f"ERROR: iter in not implemented for type {rhs.dewy_type.t}. {ast.left} in {ast.right}")


    pdb.set_trace()
    ...


def compile_range(ast: Range, scope: Scope, qbe: QbeModule, current_func: QbeFunction) -> IR:

    left_ir = compile(ast.left, scope, qbe, current_func)
    right_ir = compile(ast.right, scope, qbe, current_func)

    # obnoxious limitation of pattern matching where we can't match types because they're not instances,
    # and thus unqualified type names are interpreted as a capture pattern
    # see: https://peps.python.org/pep-0636/#matching-against-constants-and-enums
    from ... import syntax

    match left_ir, right_ir:
        case None, None:
            raise NotImplementedError(f"-inf..inf range not implemented yet. {ast.left!r}..{ast.right!r}")
        case IR(dewy_type=Type(t=syntax.Int)), IR(dewy_type=Type(t=syntax.Int)):
            ir = IR(':IIRange', f'{{{left_ir.qbe_type} {left_ir.qbe_value}, {right_ir.qbe_type} {right_ir.qbe_value}}}', Type(Range))
            ir.meta.kind = (Int, Int)
            ir.meta.left = int(left_ir.qbe_value)
            ir.meta.step = 1
            ir.meta.right = int(right_ir.qbe_value)
            ir.meta.brackets = ast.brackets
            return ir

        case _:
            pdb.set_trace()
            raise NotImplementedError(f"Unimplemented range type: {left_ir.dewy_type.t}..{right_ir.dewy_type.t}. {ast.left}..{ast.right}")
    #left or right could be void


    pdb.set_trace()
    ...


# --- Builtin Class Definitions (Keep as is for now) ---
class Builtin(CallableBase):
    signature: Signature
    return_type: AST
    def __str__(self): return f'{self.signature}:> {self.return_type} => ...'

class Closure(CallableBase):
    fn: FunctionLiteral
    scope: Scope
    def __str__(self): return f'{self.fn} with <Scope@{hex(id(self.scope))}>'


def typeof_builtin(builtin: Builtin, scope: Scope, params:bool=False) -> TypeExpr:
    """Returns the Dewy type of a builtin function."""
    pdb.set_trace()
    ...
register_typeof_call(Builtin, typeof_builtin)

def typeof_closure(closure: Closure, scope: Scope, params:bool=False) -> TypeExpr:
    """Returns the Dewy type of a closure."""
    pdb.set_trace()
    ...
register_typeof_call(Closure, typeof_closure)

def typeof_ir(ir: IR, scope: Scope, params:bool=False) -> TypeExpr:
    """Returns the Dewy type of an IR object."""
    return ir.dewy_type

register_typeof(IR, typeof_ir)
