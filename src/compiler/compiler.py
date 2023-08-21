# llvm backend or interpreter
# all backends either compile+run the code or just run it directly

from argparse import ArgumentParser, REMAINDER

import pdb

def main():
    arg_parser = ArgumentParser(description='Dewy Compiler')

    # positional argument for the file to compile
    arg_parser.add_argument('file', help='.dewy file to run')

    # mutually exclusive flags for specifying the backend to use
    group = arg_parser.add_mutually_exclusive_group()
    group.add_argument('-i', action='store_true', help='Run in interpreter mode')
    group.add_argument('-c', action='store_true', help='Run in compiler mode')
    group.add_argument('--backend', type=str, help=f'Specify a specific backend to compiler/interpret the program with. Backends include: {[*backend_map.keys()]}.')

    arg_parser.add_argument('args', nargs=REMAINDER, help='Arguments after the file are passed directly to program')

    args = arg_parser.parse_args()

    if args.i: backend = python_interpreter
    elif args.c: backend = llvm_compiler
    elif args.backend:
        try:
            backend = backend_map[args.backend.lower()]
        except:
            raise ValueError(f'Unknown backend "{args.backend}"')
    else: backend = python_interpreter #current default is python interpreter
    
    # run with the selected backend
    backend(args.file, args.args)


# TODO: import these from somewhere more legit
def python_interpreter(path:str, args:list[str]):
    from tokenizer import tokenize
    from postok import post_process
    from parser import top_level_parse
    from dewy import Scope

    with open(path) as f:
        src = f.read()
    
    tokens = tokenize(src)
    post_process(tokens)

    root = Scope.default()
    ast = top_level_parse(tokens, root)
    res = ast.eval(root)
    if res: print(res)


def llvm_compiler(path:str, args:list[str]):
    raise NotImplementedError('LLVM backend is not yet supported')

def c_compiler(path:str, forwarded_args:list[str]):
    raise NotImplementedError('C backend is not yet supported')

def x86_64_compiler(path:str, args:list[str]):
    raise NotImplementedError('x86_64 backend is not yet supported')

backend_map = {
    'python': python_interpreter,
    'llvm': llvm_compiler,
    'c': c_compiler,
    'x86_64': x86_64_compiler
}



if __name__ == '__main__':
    main()