#llvm backend or interpreter

from argparse import ArgumentParser




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

    args = arg_parser.parse_args()

    if args.i:
        python_interpreter(args.file)
    elif args.c:
        llvm_compiler(args.file)
    elif args.backend:
        try:
            backend = backend_map[args.backend.lower()]
        except:
            raise ValueError(f'Unknown backend "{args.backend}"')
        backend(args.file)
    else:
        #current default is python interpreter
        python_interpreter(args.file)


# TODO: import these from somewhere?
def python_interpreter(path:str):
    pdb.set_trace()
    ...

def llvm_compiler(path:str):
    raise NotImplementedError('LLVM backend is not yet supported')

def c_compiler(path:str):
    raise NotImplementedError('C backend is not yet supported')

def x86_64_compiler(path:str):
    raise NotImplementedError('x86_64 backend is not yet supported')

backend_map = {
    'python': python_interpreter,
    'llvm': llvm_compiler,
    'c': c_compiler,
    'x86_64': x86_64_compiler
}



if __name__ == '__main__':
    main()