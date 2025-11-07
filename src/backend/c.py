from ..utils import Backend, BaseOptions
from ..tokenizer import tokenize
from ..postok import post_process
from ..parser import top_level_parse
from ..postparse import normalize_function_args, post_parse, Signature
from ..typecheck import (
    Scope as TypecheckScope,
    top_level_typecheck_and_resolve,
    CallableBase
)
from ..syntax import (
    AST,
    DeclarationType,
    Group,
    Identifier,
    Int,
    Type, PrototypeBuiltin,
    TypedIdentifier,
)


from pathlib import Path
from dataclasses import dataclass
from argparse import ArgumentParser, Namespace



import pdb


@dataclass
class Options(BaseOptions): ...

def make_argparser(parent: ArgumentParser) -> None:
    #TODO: any options for the C backend
    ...

def make_options(args: Namespace) -> Options:
    return Options(
        tokens=args.tokens,
        verbose=args.verbose,
    )

def c_compiler(path: Path, args: list[str], options: Options) -> None:
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
    scope = Scope.c_default()
    ast, scope_map = top_level_typecheck_and_resolve(ast, scope)

    # debug printing
    if options.verbose:
        print(repr(ast))

    # Initialize an *empty* QBE Module
    # qbe = QbeModule()

    # Compile the AST into the QBE module. This will create functions as needed.
    scope = Scope.c_default()
    c = top_level_compile(ast, scope)

    pdb.set_trace()

    # # generate the QBE IR string
    # ssa = str(qbe)
    # if options.verbose:
    #     print("--- Generated QBE ---")
    #     print(ssa)
    #     print("---------------------")

    # # write the qbe to a file
    # qbe_file = cache_dir / f'{path.name}.qbe'
    # qbe_file.write_text(ssa)

    # # get paths to the relevant core files
    # syscalls = here / f'{options.target_os}-syscalls-{options.target_arch}.s'
    # syscalls = syscalls.relative_to(os.getcwd(), walk_up=True)
    # program = cache_dir / path.stem

    # # compile the qbe file to assembly
    # # assemble the assembly files into object files
    # # link the object files into an executable
    # with program.with_suffix('.s').open('w') as f:
    #     subprocess.run(['qbe', '-t', options.target_system, qbe_file], stdout=f, check=True)
    # subprocess.run(['as', '-o', program.with_suffix('.o'), program.with_suffix('.s')], check=True)
    # subprocess.run(['as', '-o', syscalls.with_suffix('.o'), syscalls], check=True)
    # subprocess.run(['ld', '-o', program, program.with_suffix('.o'), syscalls.with_suffix('.o')], check=True)

    # # clean up qbe, assembly, and object files
    # program.with_suffix('.o').unlink(missing_ok=True)
    # syscalls.with_suffix('.o').unlink(missing_ok=True) # Keep syscalls.o optional

    # # Handle emit options
    # if options.emit_qbe is True:
    #     print(f'QBE output written to {qbe_file}')
    # elif isinstance(options.emit_qbe, Path):
    #     qbe_file.rename(options.emit_qbe)
    #     print(f'QBE output written to {options.emit_qbe}')
    # else: # False
    #     qbe_file.unlink(missing_ok=True)

    # if options.emit_asm is True:
    #     print(f'Assembly output written to {program.with_suffix(".s")}')
    #     print(f'Syscall assembly used: {syscalls}')
    # elif isinstance(options.emit_asm, Path):
    #     program.with_suffix('.s').rename(options.emit_asm)
    #     print(f'Assembly output written to {options.emit_asm}')
    #     print(f'Syscall assembly used: {syscalls}')
    # else: # False
    #     program.with_suffix('.s').unlink(missing_ok=True)


    # # Run the program
    # if options.run_program:
    #     if options.verbose:
    #         # print(f'./{program} {" ".join(args)}')
    #         print(f'dewy {path} {" ".join(args)}')
    #     os.execv(program, ['dewy', path] + args)


def top_level_compile(ast: AST, scope: 'Scope') -> 'CModule':
    pdb.set_trace()


c_backend = Backend[Options](
    name='C',
    exec=c_compiler,
    make_argparser=make_argparser,
    make_options=make_options
)



@dataclass
class Scope(TypecheckScope):
    def __hash__(self) -> int:
        return hash(id(self))
    def __eq__(self, value):
        return self is value

    @staticmethod
    def c_default() -> 'Scope':
        vars: dict[str, Scope._var] = {
            "printf": Scope._var(
                DeclarationType.CONST, Type(Builtin),
                Builtin(normalize_function_args(Group([
                    TypedIdentifier(Identifier('pattern'), Type(Int))
                ])), Type(Int))
            )
        }

        scope = Scope(vars=vars)
        return scope

@dataclass
class CModule: ...















class Builtin(CallableBase):
    signature: Signature
    return_type: AST
    def __str__(self): return f'{self.signature}:> {self.return_type} => ...'
