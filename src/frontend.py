from pathlib import Path
from argparse import ArgumentParser, REMAINDER
from .backend import backend_names, get_backend, python_interpreter, python_repl, qbe_compiler, get_version
from .utils import Options

import pdb



def main():
    arg_parser = ArgumentParser(description='Dewy Compiler')

    # positional argument for the file to compile
    arg_parser.add_argument('file', nargs='?', help='.dewy file to run. If not provided, will enter REPL mode using the python backend')

    # mutually exclusive flags for specifying the backend to use
    group = arg_parser.add_mutually_exclusive_group()
    group.add_argument('-i', action='store_true', help='(DEFAULT) Run in interpreter mode with the python backend')
    group.add_argument('-c', action='store_true', help='Run in compiler mode with the QBE backend (not implemented yet)')
    group.add_argument('--backend', type=str, help=f'Specify a backend compiler/interpreter by name to use. Backends will include: {backend_names} (however currently only python is available).')

    arg_parser.add_argument('-v', '--version', action='version', version=f'Dewy {get_version()}', help='Print version information and exit')
    arg_parser.add_argument('-p', '--disable-rich-print', action='store_true', help='Disable using rich for printing stack traces')
    arg_parser.add_argument('args', nargs=REMAINDER, help='Arguments after the file are passed directly to program')
    arg_parser.add_argument('--verbose', action='store_true', help='Print verbose output')
    arg_parser.add_argument('--tokens', action='store_true', help='Print tokens for the input expression')


    args = arg_parser.parse_args()

    # if file is not provided, ensure that -c and --backend are not provided
    if not args.file and (args.c or args.backend):
        arg_parser.error('Cannot enter REPL mode when -c or --backend is provided')

    # use rich for pretty traceback printing
    #TODO: maybe add a util or something for trying to import rich and replacing print in all files
    if not args.disable_rich_print:
        try:
            from rich import traceback
            traceback.install(show_locals=True)
        except:
            print('rich unavailable for import. using built-in printing')

    options = Options(args.tokens, args.verbose)

    # if no file is provided, enter REPL mode
    if args.file is None:
        python_repl(args.args, options)
        return
    
    # default interpreter is python. default compiler is qbe. default with no args is python.
    if args.backend:
        backend = get_backend(args.backend)
    elif args.c:
        backend = qbe_compiler
    elif args.i:
        backend = python_interpreter
    else:
        backend = python_interpreter

    # run with the selected backend
    backend(Path(args.file), args.args, options)




if __name__ == '__main__':
    main()
