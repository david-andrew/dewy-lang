# llvm backend or interpreter
# all backends either compile+run the code or just run it directly

from argparse import ArgumentParser, REMAINDER
from backend import backends, get_backend, python_interpreter, llvm_compiler

import pdb

def main():
    arg_parser = ArgumentParser(description='Dewy Compiler')

    # positional argument for the file to compile
    arg_parser.add_argument('file', help='.dewy file to run')

    # mutually exclusive flags for specifying the backend to use
    group = arg_parser.add_mutually_exclusive_group()
    group.add_argument('-i', action='store_true', help='(DEFAULT) Run in interpreter mode with the python backend')
    group.add_argument('-c', action='store_true', help='Run in compiler mode with the llvm backend (not implemented yet)')
    group.add_argument('--backend', type=str, help=f'Specify a backend compiler/interpreter by name to use. Backends will include: {backends} (however currently only python is available).')

    arg_parser.add_argument('args', nargs=REMAINDER, help='Arguments after the file are passed directly to program')

    args = arg_parser.parse_args()

    # default interpreter is python. default compiler is llvm. default with no args is python.
    if args.backend: backend = get_backend(args.backend)
    elif args.c:     backend = llvm_compiler
    elif args.i:     backend = python_interpreter
    else:            backend = python_interpreter
    
    # run with the selected backend
    backend(args.file, args.args)





if __name__ == '__main__':
    main()