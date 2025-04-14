from ...tokenizer import tokenize
from ...postok import post_process
from ...typecheck import (
    Scope as TypecheckScope,
    typecheck_and_resolve,
    typecheck_call, typecheck_index, typecheck_multiply,
    register_typeof, short_circuit, typeof, TypeExpr,
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
# (Keep existing imports: BaseOptions, Backend, platform, dataclasses, Path, Protocol, Literal, cache, count, Namespace, ArgumentParser, subprocess, os)
from ...utils import BaseOptions, Backend

import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Literal, cast
from functools import cache
from itertools import count
from argparse import Namespace, ArgumentParser
import subprocess
import os


import pdb


from functools import cache
from pathlib import Path



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

    # parent.add_argument('--test-qbe', action='store_true', help='Test option for the QBE backend')
    # parent.add_argument('--opt-level', type=int, default=2, help='Optimization level for QBE codegen')
    # TODO: figure out how to allow these to optionally accept a path as --emit-asm=<path>
    #       tried: nargs='?', const=True, default=False, but this will cause the args to greedily eat any positional arguments after
    #       if there is no `=`. Somehow need to ignore such cases which instead just go with True 
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
    ast, scope = typecheck_and_resolve(ast, scope)

    # debug printing
    if options.verbose:
        print(repr(ast))

    # Initialize QBE Module with __main__ function stub
    qbe = QbeModule([
        QbeFunction('$__main__', True, [QbeArg('%argc', 'l'), QbeArg('%argv', 'l'), QbeArg('%envp', 'l')], 'w', [])
    ])

    # Compile the AST into the QBE module
    qbe, meta_info = compile(ast, scope, qbe)

    # Add a fallback exit block to the __main__ function (if it exists and doesn't already have one or a ret)
    main_fn = next((f for f in qbe.functions if f.name == '$__main__'), None)
    if main_fn:
        # Check if the last block already ends with ret or jmp
        needs_fallback = True
        if main_fn.blocks:
            last_block_lines = main_fn.blocks[-1].lines
            if last_block_lines and (last_block_lines[-1].strip().startswith('ret') or last_block_lines[-1].strip().startswith('jmp')):
                 needs_fallback = False

        if needs_fallback:
            main_fn.blocks.append(QbeBlock('@__fallback_exit__', ['ret 0']))
    else:
       print("Warning: No $__main__ function generated.")


    # generate the QBE IR string
    ssa = str(qbe)

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
    subprocess.run(['rm', program.with_suffix('.o'), syscalls.with_suffix('.o')], check=True)
    if options.emit_qbe:
        print(f'QBE output written to {qbe_file}')
    else:
        subprocess.run(['rm', qbe_file], check=True)
    if options.emit_asm:
        print(f'Assembly output written to {program.with_suffix(".s")}')
        print(f'Syscall assembly output at {syscalls}')
    else:
        subprocess.run(['rm', program.with_suffix('.s')], check=True)


    # Run the program
    if options.run_program:
        if options.verbose: print(f'./{program} {" ".join(args)}')
        os.execv(program, [program] + args)



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
    def linux_default() -> 'Scope':
        """A default scope for when compiling to linux. Contains merely __syscall1__ to __syscall6__"""
        return Scope(vars={f'__syscall{i}__': Scope._make_linux_syscall_builtin(i) for i in range(1, 7)})


    # # Add apple_default(), windows_default() etc. later

# QBE Type definition (can be expanded later for structs etc.)
QbeType = Literal['w', 'l', 's', 'd', 'b', 'h'] | str # Allow custom type names (structs)

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
        blocks_str = '\n'.join(map(str, filter(lambda b: b.lines, self.blocks)))
        # Ensure there's a newline between header and first block if blocks exist
        sep = '\n' if blocks_str else ''
        return f'{export_str}function {ret_str}{self.name}({args_str}) {{\n{blocks_str}{sep}}}'


@dataclass
class QbeModule:
    functions: list[QbeFunction] = field(default_factory=list)
    global_data: list[str] = field(default_factory=list)
    _counter: count = field(default_factory=lambda: count(0))
    _symbols: dict[str, TypeExpr] = field(default_factory=dict) # Map temp names to Dewy types

    def get_temp(self, prefix: str = "tmp") -> str:
        """Gets the next available temporary variable name."""
        return f"%{prefix}{next(self._counter)}"

    def __str__(self) -> str:
        # Ensure proper spacing between sections
        data_str = '\n'.join(self.global_data)
        funcs_str = '\n\n'.join(map(str, self.functions))
        sep1 = '\n\n' if data_str and funcs_str else '\n' if data_str or funcs_str else ''
        return f'{data_str}{sep1}{funcs_str}'.strip()


# --- Compilation Logic ---

from typing import TypeVar, Optional
T = TypeVar('T', bound=AST)
class CompileFunc(Protocol):
    def __call__(self, ast: T, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> Optional[str]:
        """
        Compiles the AST node, appending instructions to current_block.
        Returns the QBE temporary variable name (%tmpN) or literal ('l 42')
        representing the result of the expression, or None if the node
        represents an action with no return value (like Assign).
        """
        ...

@dataclass
class MetaInfo:
    """Placeholder for potential future metadata from compilation."""
    pass

# --- Specific Compile Functions ---

def compile_assign(ast: Assign, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> Optional[str]:
    """Handles top-level assignment, especially for __main__."""
    # Check for the specific case: __main__ = FunctionLiteral(...)
    if isinstance(ast.left, Identifier) and ast.left.name == '__main__':
        if isinstance(ast.right, FunctionLiteral):
            # Find the QBE function for __main__
            main_func = next((f for f in qbe.functions if f.name == '$__main__'), None)
            if not main_func:
                # This shouldn't happen with the current setup, but good practice
                raise ValueError("Could not find $__main__ QBE function stub.")

            # Create the entry block if it doesn't exist
            start_block = next((b for b in main_func.blocks if b.label == '@start'), None)
            if start_block is None:
                start_block = QbeBlock('@start')
                main_func.blocks.insert(0, start_block) # Ensure it's the first block

            # Compile the body of the function literal into the start block
            compile_node(ast.right.body, scope, qbe, start_block)

            # Ensure the main function returns 0 (success exit code)
            # Only add `ret 0` if the block doesn't already end with `ret` or `jmp`
            if not start_block.lines or not (start_block.lines[-1].strip().startswith('ret') or start_block.lines[-1].strip().startswith('jmp')):
                start_block.lines.append('ret 0')

            return None # Assignment itself doesn't produce a value
        else:
            raise NotImplementedError(f"Cannot assign non-function literal to __main__ yet. Got: {type(ast.right)}")
    else:
        # Handle general assignment (later)
        raise NotImplementedError(f"General assignment compilation not implemented yet. Assigning to: {ast.left}")

def compile_call(ast: Call, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> Optional[str]:
    """Compiles a function call."""
    # 1. Resolve the function name
    if not isinstance(ast.f, Identifier):
        # Later handle complex function expressions (e.g., (get_func())())
        raise NotImplementedError(f"Cannot compile call to non-identifier function: {ast.f}")

    func_name = ast.f.name
    qbe_func_name = f"${func_name}" # Basic convention: prepend $

    # 2. Compile arguments
    qbe_args = []
    if ast.args:
        if isinstance(ast.args, Group):
            for arg_ast in ast.args.items:
                arg_val = compile_node(arg_ast, scope, qbe, current_block)
                if arg_val is None:
                    raise ValueError(f"Argument expression did not produce a value: {arg_ast}")
                # Determine argument type (simple for now)
                # TODO: Use type information from scope/qbe._symbols
                arg_type = 'l' # Assume long for now for syscalls
                qbe_args.append(f"{arg_type} {arg_val}")
        else:
            # Handle single argument not in a group
            arg_val = compile_node(ast.args, scope, qbe, current_block)
            if arg_val is None:
                 raise ValueError(f"Argument expression did not produce a value: {ast.args}")
            arg_type = 'l'
            qbe_args.append(f"{arg_type} {arg_val}")


    # 3. Generate the call instruction
    args_str = ", ".join(qbe_args)
    call_instr = f"call {qbe_func_name}({args_str})"

    # 4. Handle return value (if necessary)
    # TODO: Check the return type of the function from scope/type info
    # For syscalls, the convention often puts return in a specific register (%rax/%eax)
    # QBE's `call` can assign the result to a temporary. For now, assume void return.
    # If it did return:
    #   ret_temp = qbe.get_temp()
    #   ret_type = 'l' # Get from type info
    #   call_instr = f"{ret_temp} = {ret_type} call {qbe_func_name}({args_str})"
    #   current_block.lines.append(call_instr)
    #   return ret_temp
    current_block.lines.append(call_instr)
    return None # Syscalls here effectively return void in the Dewy sense

def compile_int(ast: Int, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> Optional[str]:
    """Returns the QBE representation of an integer literal."""
    # Assume 'l' (long) for now. Could be 'w' (word) based on context/type info later.
    return f"{ast.val}" # QBE uses direct integers for constants

def compile_group(ast: Group, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> Optional[str]:
    """Compiles a group. Typically returns the result of the last expression."""
    last_val = None
    for item in ast.items:
        last_val = compile_node(item, scope, qbe, current_block)
    # If the group was used as args, compile_call handles iteration.
    # If used stand-alone, return the value of the last item.
    return last_val

def compile_node(ast: AST, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> Optional[str]:
    """Dispatches compilation to the appropriate function based on AST node type."""
    eval_fn_map = get_compile_fn_map()
    ast_type = type(ast)

    if ast_type in eval_fn_map:
        # Cast to ensure the protocol is satisfied (mypy helper)
        compile_func = cast(CompileFunc, eval_fn_map[ast_type])
        return compile_func(ast, scope, qbe, current_block) # Pass current_block

    # Fallback for nodes that might represent themselves directly (like Int handled above)
    # Or raise error for unhandled types.
    # if isinstance(ast, Int): return compile_int(ast, scope, qbe, current_block) # Example if Int wasn't mapped

    raise NotImplementedError(f'QBE compilation not implemented for AST type: {ast_type}')


@cache
def get_compile_fn_map() -> dict[type[AST], CompileFunc]:
    """Returns the dispatch map for compilation functions."""
    return {
        Assign: compile_assign,
        Call: compile_call,
        Int: compile_int,
        Group: compile_group, # Groups are handled contextually (e.g., by compile_call) or compile last expr
        # Add other AST types here as they are implemented
        # e.g., FunctionLiteral might create a new QbeFunction
        #       Identifier might return a QBE variable name ('%var' or parameter name)
        #       Add, Sub, etc. would generate corresponding QBE instructions
    }


# Main compile entry point (modified slightly)
def compile(ast: AST, scope: Scope, qbe: QbeModule) -> tuple[QbeModule, MetaInfo]:
    """Top-level compilation function."""
    if isinstance(ast, Void):
        return qbe, MetaInfo()

    # For top-level, we don't have a 'current_block' initially.
    # Top-level nodes like Assign (to __main__) will find/create their own blocks.
    # We pass None initially, and specific handlers manage blocks.
    # --- Revision: The top-level Assign(__main__) handler needs *a* block.
    # Let's assume compile is called *after* the $__main__ stub exists.
    # The handler for Assign(__main__) will specifically target $__main__.
    compile_node(ast, scope, qbe, None) # Pass None, handlers must manage block context

    return qbe, MetaInfo()


# --- Builtin Class Definitions (Keep as is for now) ---
class Builtin(CallableBase):
    signature: Signature
    return_type: AST
    def __str__(self): return f'{self.signature}:> {self.return_type} => ...'

class Closure(CallableBase):
    fn: FunctionLiteral
    scope: Scope
    def __str__(self): return f'{self.fn} with <Scope@{hex(id(self.scope))}>'