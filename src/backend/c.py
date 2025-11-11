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
    String, IString, Call,
)


from pathlib import Path
from dataclasses import dataclass, field
from argparse import ArgumentParser, Namespace
import subprocess
import os



import pdb


@dataclass
class Options(BaseOptions):
    run_program: bool
    emit_c: bool|Path
    emit_asm: bool|Path
    cc: str
    std: str

def make_argparser(parent: ArgumentParser) -> None:
    parent.add_argument('-b', '--build-only', action='store_true', help='Only compile/build the program, do not run it')
    parent.add_argument('--emit-c', action='flag_or_explicit', const=True, default=False, metavar='PATH', help='Emit generated C source. If no path, write to __dewycache__/<program>.c')
    parent.add_argument('--emit-asm', action='flag_or_explicit', const=True, default=False, metavar='PATH', help='Emit assembly via cc -S. If no path, write to __dewycache__/<program>.s')
    parent.add_argument('--cc', type=str, default='cc', help='C compiler to use (default: cc)')
    parent.add_argument('--std', type=str, default='c11', help='C language standard to compile with (default: c11)')

def make_options(args: Namespace) -> Options:
    emit_c = args.emit_c if isinstance(args.emit_c, bool) else Path(args.emit_c)
    emit_asm = args.emit_asm if isinstance(args.emit_asm, bool) else Path(args.emit_asm)
    return Options(
        tokens=args.tokens,
        verbose=args.verbose,
        run_program=not args.build_only,
        emit_c=emit_c,
        emit_asm=emit_asm,
        cc=args.cc,
        std=args.std,
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

    # Compile to a C module
    scope = Scope.c_default()
    c_mod = top_level_compile(ast, scope)

    c_src = str(c_mod)
    c_file = cache_dir / f'{path.name}.c'
    program = cache_dir / path.stem

    # write C source
    c_file.write_text(c_src)

    # Emit assembly if requested
    asm_file = program.with_suffix('.s')
    if options.emit_asm:
        subprocess.run([options.cc, f'-std={options.std}', '-S', '-o', str(asm_file), str(c_file)], check=True)
        if options.emit_asm is True:
            print(f'Assembly output written to {asm_file}')
        else:
            target = options.emit_asm
            asm_file.replace(target)
            print(f'Assembly output written to {target}')
    else:
        asm_file.unlink(missing_ok=True)

    # Build executable
    subprocess.run([options.cc, f'-std={options.std}', '-o', str(program), str(c_file)], check=True)

    # Handle emit_c
    if options.emit_c is True:
        print(f'C output written to {c_file}')
    elif isinstance(options.emit_c, Path):
        target = options.emit_c
        c_file.replace(target)
        print(f'C output written to {target}')
    else:
        c_file.unlink(missing_ok=True)

    # Run the program
    if options.run_program:
        if options.verbose:
            print(f'dewy {path} {" ".join(args)}')
        os.execv(str(program), ['dewy', str(path)] + args)


def top_level_compile(ast: AST, scope: 'Scope') -> 'CModule':
    if not isinstance(ast, Group):
        ast = Group([ast])
    mod = CModule()
    main_fn = CFunction(
        name='main',
        ret='int',
        args=['int argc', 'char **argv'],
        body_lines=[],
    )
    compile_group(ast, scope, mod, main_fn)
    main_fn.body_lines.append('return 0;')
    mod.functions.append(main_fn)
    return mod


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
                    TypedIdentifier(Identifier('format'), Type(String))
                ])), Type(Int))
            )
        }

        scope = Scope(vars=vars)
        return scope

@dataclass
class CExpr:
    code: str
    dewy_type: Type|None = None

@dataclass
class CFunction:
    name: str
    ret: str
    args: list[str] = field(default_factory=list)
    body_lines: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        args_str = ', '.join(self.args)
        body = '\n'.join(f'    {line}' for line in self.body_lines if line is not None)
        return f'{self.ret} {self.name}({args_str}) {{\n{body}\n}}'

@dataclass
class CModule:
    includes: set[str] = field(default_factory=set)
    global_lines: list[str] = field(default_factory=list)
    functions: list[CFunction] = field(default_factory=list)

    def __str__(self) -> str:
        incs = '\n'.join(f'#include {h}' for h in sorted(self.includes))
        globals_str = '\n'.join(self.global_lines)
        funcs = '\n\n'.join(str(f) for f in self.functions)
        parts = [s for s in [incs, globals_str, funcs] if s]
        return '\n\n'.join(parts)

def c_escape_string_literal(s: str) -> str:
    out_chars: list[str] = []
    for ch in s:
        match ch:
            case '"':
                out_chars.append(r'\"')
            case '\\':
                out_chars.append(r'\\')
            case '\n':
                out_chars.append(r'\n')
            case '\r':
                out_chars.append(r'\r')
            case '\t':
                out_chars.append(r'\t')
            case '\b':
                out_chars.append(r'\b')
            case '\f':
                out_chars.append(r'\f')
            case '\v':
                out_chars.append(r'\v')
            case _:
                code = ord(ch)
                if code < 0x20 or code == 0x7F:
                    out_chars.append(f'\\x{code:02x}')
                else:
                    out_chars.append(ch)
    return '"' + ''.join(out_chars) + '"'

# --- Minimal compile dispatch ---
def compile(ast: AST, scope: Scope, mod: CModule, current_fn: CFunction) -> CExpr|None:
    match ast:
        case Group():
            return compile_group(ast, scope, mod, current_fn)
        case String(val=val):
            return CExpr(c_escape_string_literal(val), Type(String))
        case IString(parts=parts):
            if all(isinstance(p, String) for p in parts):
                text = ''.join(p.val for p in parts)
                return CExpr(c_escape_string_literal(text), Type(String))
            raise NotImplementedError('IString with non-String parts not supported yet')
        case Call(f=Identifier(name=name), args=args):
            return compile_call(name, args, scope, mod, current_fn)
        case _:
            raise NotImplementedError(f'C codegen not implemented for AST type: {type(ast)}')

def compile_group(ast: Group, scope: Scope, mod: CModule, current_fn: CFunction) -> None:
    for item in ast.items:
        compile(item, scope, mod, current_fn)
    return None

def compile_call(name: str, args_ast: AST|None, scope: Scope, mod: CModule, current_fn: CFunction) -> CExpr|None:
    if name == 'printf':
        # ensure stdio include
        mod.includes.add('<stdio.h>')
        # compile single-arg (IString/String) call
        if args_ast is None:
            raise ValueError('printf requires an argument')
        arg = compile(args_ast, scope, mod, current_fn)
        assert isinstance(arg, CExpr)
        current_fn.body_lines.append(f'printf({arg.code});')
        return None
    raise NotImplementedError(f'Call to unknown function {name!r}')















class Builtin(CallableBase):
    signature: Signature
    return_type: AST
    def __str__(self): return f'{self.signature}:> {self.return_type} => ...'
