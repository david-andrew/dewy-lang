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

    # Check if __main__ was defined by the user's code. If not, add a fallback.
    # pdb.set_trace()
    # main_fn_exists = any(f.name == '$__main__' for f in qbe.functions)
    # if not main_fn_exists:
    #     if options.verbose:
    #         print("Warning: No __main__ function defined in source, adding fallback exit.")
    #     # Add the fallback __main__ that just exits with 0
    #     qbe.functions.append(
    #         QbeFunction(
    #             name='$__main__',
    #             export=True,
    #             args=[QbeArg('%argc', 'l'), QbeArg('%argv', 'l'), QbeArg('%envp', 'l')],
    #             ret='w', # Exit code is typically 'w' (word)
    #             blocks=[QbeBlock('@start', ['ret 0'])]
    #         )
    #     )

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
        blocks=[start_block:=QbeBlock('@start')]
    )
    qbe.functions.append(__main__)

    compile_group(ast, scope, qbe, start_block)

    # Add a fallback block that will return from the main function
    __main__.blocks.append(QbeBlock('@__fallback_exit__', ['ret 0']))
    # If the start block is empty, add a default return
    # if len(start_block.lines) == 0:
    #     start_block.lines.append('ret 0')

    return qbe
    
    # if isinstance(ast, Void):
    #     return qbe, MetaInfo()

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
        return Scope(vars={f'__syscall{i}__': Scope._make_linux_syscall_builtin(i) for i in range(0, 7)})


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
    #TODO: something about the scope it's in... Or more specifically which QBE function it is in and can be accessed from

    def __str__(self) -> str:
        return f'IR(qbe=`{self.qbe_type} {self.qbe_value}`, type=`{self.dewy_type}`)'


T = TypeVar('T', bound=AST)
class CompileFunc(Protocol):
    def __call__(self, ast: T, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> Optional[IR]:
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
        Declare: compile_declare,
        Assign: compile_assign,
        Express: compile_express,
        Call: compile_call,
        Group: compile_group,
        Int: compile_int,
        String: compile_string,
        And: compile_base_logical_binop,
        Or: compile_base_logical_binop,
        Xor: compile_base_logical_binop,
        Nand: compile_notted_logical_binop,
        Nor: compile_notted_logical_binop,
        Xnor: compile_notted_logical_binop,
        Not: compile_not,
        # Less: compile_less,
        # LessEqual: compile_less_equal,
        # Greater: compile_greater,
        # GreaterEqual: compile_greater_equal,
        # Equal: compile_equal,
        # NotEqual: compile_not_equal,


        # Add other AST types here as they are implemented
    }


def compile(ast: AST, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> Optional[IR]:
    """Dispatches compilation to the appropriate function based on AST node type."""
    compile_fn_map = get_compile_fn_map()

    ast_type = type(ast)
    if ast_type in compile_fn_map:
        return compile_fn_map[ast_type](ast, scope, qbe, current_block)

    raise NotImplementedError(f'QBE compilation not implemented for AST type: {ast_type}')




def compile_declare(ast: Declare, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> None:
    """Handles variable declarations."""
    match ast.target:
        case Identifier(name=name):
            pdb.set_trace()
            ...
        case Assign(left=Identifier(name=name)):
            scope.declare(name, void, untyped, ast.decltype)
            compile_assign(ast.target, scope, qbe, current_block)
        case _:
            raise NotImplementedError(f"Declaration target not implemented: {ast.target}")

    return None

def compile_assign(ast: Assign, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> None:
    """Handles assignments, creating functions when assigning FunctionLiterals."""
    match ast:
        case Assign(left=Identifier(name=name), right=FunctionLiteral(args=signature, body=body)):
            pdb.set_trace()
            ...
            #TODO: save compiling the function literal for later...
            # defer_compile_fn(name, signature, body)
        case Assign(left=Identifier(name=name), right=right):
            rhs = compile(right, scope, qbe, current_block)
            if rhs is None:
                raise ValueError(f'INTERNAL ERROR: attempting to assign some type that doesn\'t produce a value: {name}={right!r}')
            scope.assign(name, rhs)
            qid = qbe.get_temp()
            qbe._symbols[name] = qid
            current_block.lines.append(f'{qid} ={rhs.qbe_type} copy {rhs.qbe_value}')
        case _:
            raise NotImplementedError(f"Assignment target not implemented: left={ast.left}, right={ast.right}")    

    return None

            

def compile_express(ast: Express, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> IR:
    # get the previous IR for the original value that should be set
    ir_var = scope.get(ast.id.name)
    ir = ir_var.value
    assert isinstance(ir, IR), f'INTERNAL ERROR: expected IR AST in scope for id "{ast.id}", but got {ir!r}'

    #TODO: need a check to verify the IR is contained in the same QBE function as it's being used...

    # value should be in symbol table? there are cases where it wouldn't but that's advanced out of order compilation stuff...
    assert ast.id.name in qbe._symbols, f'TBD if this is an internal error or not. Attempted to express a value which is not in the symbol table from compiling. {ast=!r}'
    express_ir = IR(ir.qbe_type, qbe._symbols[ast.id.name], ir.dewy_type)

    return express_ir


    


def compile_call(ast: Call, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> Optional[IR]:
    """Compiles a function call."""
    if not isinstance(ast.f, Identifier):
        raise NotImplementedError(f"calling non-identifier functions is not implemented yet. {ast.f} called with args {ast.args}")
    
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
    

    qbe_args = [compile(arg, scope, qbe, current_block) for arg in ast_args.items]
    assert not any(arg is None for arg in qbe_args), f"INTERNAL ERROR: function call arguments must produce values: {ast_args}"

    args_str = ', '.join([f'{arg.qbe_type} {arg.qbe_value}' for arg in qbe_args])

    # insert the call with the result being saved to a new temporary id
    ret_id = qbe.get_temp()
    current_block.lines.append(f'{ret_id} ={ret_type} call {f_id}({args_str})')

    return IR(ret_type, ret_id, dewy_return_type)



def compile_group(ast: Group, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> Optional[IR]:
    """Compiles a group"""

    results = []
    for item in ast.items:
        result = compile(item, scope, qbe, current_block)
        if result is not None:
            results.append(result)
    
    # depending on how many values are present in the result, handle the group differently
    if len(results) == 0:
        return None
    elif len(results) == 1:
        return results[0]

    print('WARNING/TODO: group has multiple values. probably handle at the higher level')


    pdb.set_trace()
    ...
    # raise NotImplementedError(f'groups that express more than 1 value are not implemented yet. {ast} => {list(map(str, results))}')

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


def compile_int(ast: Int, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> IR:
    """Returns the QBE representation of an integer literal."""
    # QBE uses direct integers for constants. Prepend type for clarity in instruction.
    # The 'l' type is added by the instruction using this value (e.g., call)
    # TODO: check if the integer overflows, and return a big int
    return IR( 'l', f"{ast.val}", Type(Int))


def compile_string(ast: String, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> IR:
    """Returns the QBE representation of a string literal."""
    # data $greet = { b "Hello World!\n\0" }
    data_id = qbe.get_temp('$str')
    str_data = f'"{repr(ast.val)[1:-1]}"'
    # qbe.global_data.append(f'data {data_id}.len = {{ l {len(ast.val)} }}')
    # qbe.global_data.append(f'data {data_id}.data = {{ b {str_data}, b 0 }}')
    qbe.global_data.append(f'data {data_id} = {{ b {str_data}, b 0 }}')
    return IR('l', data_id, Type(String))

logical_binop_opcode_map = {
    (And, Int, Int): 'and',
    (Or, Int, Int): 'or',
    (Xor, Int, Int): 'xor',

}
def compile_base_logical_binop(ast: And|Or|Xor, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> IR:
    """Compiles a base/builtin logical operation."""
    left_ir = compile(ast.left, scope, qbe, current_block)
    assert left_ir is not None, f"INTERNAL ERROR: left side of `{ast.__class__.__name__}` must produce a value: {ast.left!r}"
    right_ir = compile(ast.right, scope, qbe, current_block)
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


    current_block.lines.append(f'{res_id} ={res_type} {opcode} {left_ir.qbe_value}, {right_ir.qbe_value}')
    return IR(res_type, res_id, dewy_res_type)


def compile_not(ast: Not, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> IR:
    """use xor x, -1 to handle NOT"""
    operand_ir = compile(ast.operand, scope, qbe, current_block)
    assert operand_ir is not None, f'INTERNAL ERROR: operand of `Not` must produce a value: {ast.operand!r}'
    dewy_res_type = typeof(ast, scope)

    res_id = qbe.get_temp()
    res_type = operand_ir.qbe_type

    current_block.lines.append(f'{res_id} ={res_type} xor {operand_ir.qbe_value}, -1')
    return IR(res_type, res_id, dewy_res_type)


def compile_notted_logical_binop(ast: Nand|Nor|Xnor, scope: Scope, qbe: QbeModule, current_block: QbeBlock) -> IR:

    match ast:
        case Nand(): base_cls = And
        case Nor():  base_cls = Or
        case Xnor(): base_cls = Xor
        case _:
            raise NotImplementedError(f"INTERNAL ERROR: expected Nand, Nor, or Xnor, but got {ast!r}")
    
    composite_ast = Not(base_cls(ast.left, ast.right))
    final_ir = compile_not(composite_ast, scope, qbe, current_block)
    
    return final_ir

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