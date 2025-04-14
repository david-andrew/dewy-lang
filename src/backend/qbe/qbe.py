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
from ...utils import BaseOptions, Backend

import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Literal, TypeVar, Optional
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

    # Initialize an *empty* QBE Module
    qbe = QbeModule()

    # Compile the AST into the QBE module. This will create functions as needed.
    qbe, meta_info = top_level_compile(ast, scope, qbe)

    # Check if __main__ was defined by the user's code. If not, add a fallback.
    main_fn_exists = any(f.name == '$__main__' for f in qbe.functions)
    if not main_fn_exists:
        if options.verbose:
            print("Warning: No __main__ function defined in source, adding fallback exit.")
        # Add the fallback __main__ that just exits with 0
        qbe.functions.append(
            QbeFunction(
                name='$__main__',
                export=True,
                args=[QbeArg('%argc', 'l'), QbeArg('%argv', 'l'), QbeArg('%envp', 'l')],
                ret='w', # Exit code is typically 'w' (word)
                blocks=[QbeBlock('@start', ['ret 0'])]
            )
        )

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
def top_level_compile(ast: AST, scope: 'Scope', qbe: 'QbeModule') -> 'tuple[QbeModule, MetaInfo]':
    """Top-level compilation function."""
    if isinstance(ast, Void):
        return qbe, MetaInfo()

    # Top-level compilation starts without a specific block context.
    # Handlers for top-level definitions (like Assign for functions) must manage this.
    compile(ast, scope, qbe, None) # Start with current_block=None

    return qbe, MetaInfo()



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

T = TypeVar('T', bound=AST)
class CompileFunc(Protocol):
    def __call__(self, ast: T, scope: Scope, qbe: QbeModule, current_block: Optional[QbeBlock]) -> Optional[str]:
        """
        Compiles the AST node, potentially adding instructions to current_block
        (if provided and applicable, e.g., inside a function).
        Returns the QBE temporary variable name (%tmpN) or literal ('l 42')
        representing the result of the expression, or None if the node
        represents an action with no return value (like top-level Assign).
        For top-level nodes like function definitions, current_block might be None.
        """
        ...

@dataclass
class MetaInfo:
    """Placeholder for potential future metadata from compilation."""
    pass

# --- Specific Compile Functions ---
@cache
def get_compile_fn_map() -> dict[type[AST], CompileFunc]:
    """Returns the dispatch map for compilation functions."""
    return {
        Assign: compile_assign,
        Call: compile_call,
        Int: compile_int,
        Group: compile_group,
        # Add other AST types here as they are implemented
    }


def compile(ast: AST, scope: Scope, qbe: QbeModule, current_block: Optional[QbeBlock]) -> Optional[str]:
    """Dispatches compilation to the appropriate function based on AST node type."""
    compile_fn_map = get_compile_fn_map()

    ast_type = type(ast)
    if ast_type in compile_fn_map:
        return compile_fn_map[ast_type](ast, scope, qbe, current_block)

    raise NotImplementedError(f'QBE compilation not implemented for AST type: {ast_type}')


def compile_assign(ast: Assign, scope: Scope, qbe: QbeModule, current_block: Optional[QbeBlock]) -> Optional[str]:
    """Handles assignments, creating functions when assigning FunctionLiterals."""
    match ast:
        case Assign(left=Identifier(name=func_name), right=FunctionLiteral(args=signature, body=body)):
            # This assignment defines a function
            if current_block is not None:
                 # TODO: Handle nested function definitions later if needed
                 raise NotImplementedError("Nested function definitions not yet supported.")

            # Determine QBE function properties
            qbe_func_name = f"${func_name}"
            is_export = func_name == '__main__'
            # TODO: Translate Dewy signature to QBE args
            qbe_args = []
            if func_name == '__main__':
                 qbe_args = [QbeArg('%argc', 'l'), QbeArg('%argv', 'l'), QbeArg('%envp', 'l')]
            # else: Handle user function signatures later

            # TODO: Determine return type from Dewy type info
            qbe_ret_type = 'w' if func_name == '__main__' else None # Assume exit code for main, void otherwise

            # Create the new QBE function
            new_func = QbeFunction(
                name=qbe_func_name,
                export=is_export,
                args=qbe_args,
                ret=qbe_ret_type,
                blocks=[] # Start with no blocks
            )

            # Create the entry block
            start_block = QbeBlock('@start')
            new_func.blocks.append(start_block)

            # Add the function to the module *before* compiling body
            # (needed if the body recursively calls itself)
            qbe.functions.append(new_func)

            # Compile the function body into the start block
            # A new scope might be needed for the function body later
            compile(body, scope, qbe, start_block)

            # Add final return if necessary (especially for __main__)
            if func_name == '__main__':
                 if not start_block.lines or not (start_block.lines[-1].strip().startswith('ret') or start_block.lines[-1].strip().startswith('jmp')):
                     start_block.lines.append('ret 0')
            # else: Handle returns for user functions later

            return None # Function definition itself doesn't yield a value here

        case Assign(left=Identifier(name=var_name), right=value_ast):
             # Handle variable assignment (later)
             if current_block is None:
                 raise NotImplementedError(f"Top-level variable assignment ('{var_name}') not yet supported.")
             # Compile value, generate store instruction, etc.
             raise NotImplementedError(f"Variable assignment compilation not implemented yet.")

        case _:
            # Handle other assignment targets (unpacking, etc.) later
            raise NotImplementedError(f"Assignment compilation not implemented for target: {ast.left}")


def compile_call(ast: Call, scope: Scope, qbe: QbeModule, current_block: Optional[QbeBlock]) -> Optional[str]:
    """Compiles a function call."""
    if current_block is None:
        raise ValueError("Cannot compile a function call outside of a function block.")

    # 1. Resolve the function name
    if not isinstance(ast.f, Identifier):
        # Later handle complex function expressions (e.g., (get_func())())
        raise NotImplementedError(f"Cannot compile call to non-identifier function: {ast.f}")

    func_name = ast.f.name
    qbe_func_name = f"${func_name}" # Basic convention: prepend $

    # 2. Compile arguments
    qbe_args = []
    arg_nodes = []
    if ast.args:
        if isinstance(ast.args, Group):
            arg_nodes = ast.args.items
        else:
            arg_nodes = [ast.args] # Handle single argument

    for arg_ast in arg_nodes:
        # Pass the *current* block for argument compilation
        arg_val = compile(arg_ast, scope, qbe, current_block)
        if arg_val is None:
            raise ValueError(f"Argument expression did not produce a value: {arg_ast}")
        # Determine argument type (simple for now)
        # TODO: Use type information from scope/qbe._symbols
        arg_type = 'l' # Assume long for now for syscalls
        qbe_args.append(f"{arg_type} {arg_val}")


    # 3. Generate the call instruction
    args_str = ", ".join(qbe_args)
    call_instr = f"call {qbe_func_name}({args_str})"

    # 4. Handle return value (if necessary) - Assume void for syscalls for now
    # TODO: Check function return type and assign to temp if needed.
    current_block.lines.append(call_instr)
    return None # Syscalls here effectively return void in the Dewy sense

def compile_int(ast: Int, scope: Scope, qbe: QbeModule, current_block: Optional[QbeBlock]) -> Optional[str]:
    """Returns the QBE representation of an integer literal."""
    # QBE uses direct integers for constants. Prepend type for clarity in instruction.
    # The 'l' type is added by the instruction using this value (e.g., call)
    return f"{ast.val}"

def compile_group(ast: Group, scope: Scope, qbe: QbeModule, current_block: Optional[QbeBlock]) -> Optional[str]:
    """Compiles a group. Returns the result of the last expression."""
    if current_block is None and len(ast.items) > 0:
        # This might happen if a Group is the top-level AST node after `compile` starts.
        # This case needs refinement. Can a bare group be a valid top-level program?
        # For now, assume it needs a block context.
        raise ValueError("Cannot compile a Group node outside of a function block context.")
        # OR, if valid: Compile last item, but where do instructions go? Needs thought.

    last_val = None
    for item in ast.items:
        # Ensure we pass the current_block down
        last_val = compile(item, scope, qbe, current_block)

    # The group itself evaluates to its last contained expression's value.
    return last_val




# --- Builtin Class Definitions (Keep as is for now) ---
class Builtin(CallableBase):
    signature: Signature
    return_type: AST
    def __str__(self): return f'{self.signature}:> {self.return_type} => ...'

class Closure(CallableBase):
    fn: FunctionLiteral
    scope: Scope
    def __str__(self): return f'{self.fn} with <Scope@{hex(id(self.scope))}>'