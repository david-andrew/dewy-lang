from pathlib import Path
from argparse import ArgumentParser, REMAINDER
from .backend import backend_names, get_backend, python_repl, get_version
from .utils import try_install_rich
import sys

import pdb


default_backend_name = 'qbe'


def main():

    # base argparser without backend-specific options
    arg_parser = ArgumentParser(description='Dewy Compiler', add_help=False)

    # positional argument for the file to compile
    arg_parser.add_argument('file', nargs='?', help='.dewy file to run. If not provided, enter REPL mode')

    # mutually exclusive flags for specifying the backend to use
    group = arg_parser.add_mutually_exclusive_group()
    group.add_argument('-i', '--interpret', action='store_true', help=f'Run in interpreter mode with the python backend')
    group.add_argument('-c', '--compile', action='store_true', help=f'Run in compiler mode with the QBE backend')
    group.add_argument('--backend', choices=backend_names, type=str.lower, help=f'Specify a backend compiler/interpreter to use (default: {default_backend_name})')

    # other args for the base 
    arg_parser.add_argument('-v', '--version', action='version', version=f'Dewy {get_version()}', help='Print version information and exit')
    arg_parser.add_argument('-p', '--disable-rich-print', action='store_true', help='Disable using rich for printing stack traces')
    arg_parser.add_argument('--verbose', action='store_true', help='Print verbose output')
    arg_parser.add_argument('--tokens', action='store_true', help='Print tokens for the input expression')
    
    # all remaining args will be passed to the program
    arg_parser.add_argument('remaining', nargs=REMAINDER, help='Arguments after the file are passed directly to program')
    
    # initial pass over the args to figure out which backend to use
    args, _ = arg_parser.parse_known_args()

    # verify any file specified exists
    if args.file and not Path(args.file).exists():
        print(f"Error: file '{args.file}' does not exist")
        arg_parser.print_help()
        sys.exit(1)
    
    # if no file was provided, we enter REPL mode (backend is ignored)
    if args.file is None:
        if args.interpret or args.compile or args.backend:
            print("Warning: backend selection flags [--interpret --compile --backend] are ignored in REPL mode")
        args.backend = 'python'
        args.interpret = False
        args.compile = False

    # identify the backend based on any flags provided
    if args.compile:
        args.backend = 'qbe'
    elif args.interpret:
        args.backend = 'python'
    if args.backend is None:
        args.backend = default_backend_name

    # augment the argparser with backend-specific options
    backend = get_backend(args.backend)
    arg_parser = ArgumentParser(parents=[arg_parser], description=f'Dewy Compiler - Backend: {args.backend}')
    backend.make_argparser(arg_parser)

    # reparse now that all the args have been specified
    args = arg_parser.parse_args()

    # if no file is provided, we enter REPL mode (and no remaining args allowed)
    # TODO: this probably isn't possible to happen since positional args must be specified for there to be remaining args, and the first is taken as the file
    if not args.file and args.remaining:
        print("Error: unrecognized arguments:", " ".join(args.remaining))
        arg_parser.print_help()
        sys.exit(1)
    
    # use rich for pretty traceback printing
    if not args.disable_rich_print:
        try_install_rich()


    # get the options object for the backend
    options = backend.make_options(args)


    # if no file is provided, enter REPL mode
    if args.file is None:
        python_repl(args.remaining, options)
        return
    
    # run with the selected backend
    backend.exec(Path(args.file), args.remaining, options)




if __name__ == '__main__':
    main()
