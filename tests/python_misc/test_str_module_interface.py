import pdb




from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
import sys
from types import ModuleType


source_map: dict[str, str] = {}

def register_file(name: str, code: str):
    source_map[name] = code

class StringFinder(MetaPathFinder):
    def find_spec(self, fullname: str, path, target=None):
        spec = self._find_py_file_spec(fullname)
        if spec is not None:
            return spec

        spec = self._find_package_init_spec(fullname)
        if spec is not None:
            return spec

        return None

    def _find_py_file_spec(self, fullname: str):
        route = f"{fullname.replace('.', '/')}.py"
        source = source_map.get(route)
        if source is None:
            return None
        loader = StringLoader(fullname, source, route)
        return ModuleSpec(fullname, loader, origin=route)

    def _find_package_init_spec(self, fullname: str):
        route = f"{fullname.replace('.', '/')}/__init__.py"
        source = source_map.get(route)
        if source is None:
            return None
        loader = StringLoader(fullname, source, route)
        spec = ModuleSpec(fullname, loader, origin=route, is_package=True)
        return spec


class StringLoader(Loader):
    def __init__(self, fullname, source_code, route):
        self.fullname = fullname
        self.source_code = source_code
        self.route = route

    def create_module(self, spec):
        module = sys.modules.get(spec.name)
        if module is None:
            module = ModuleType(spec.name)
            sys.modules[spec.name] = module
        return module

    def exec_module(self, module):
        module.__file__ = self.route
        exec(self.source_code, module.__dict__)
        return module

    def get_source(self, name):
        return self.source_code


sys.meta_path.insert(0, StringFinder())









if __name__ == '__main__':
    from pathlib import Path
    root = Path(__file__).parent
    files = [
        'test_src/__init__.py',
        'test_src/frontend.py',
        'test_src/parser.py',
        'test_src/postok.py',
        'test_src/postparse.py',
        'test_src/syntax.py',
        'test_src/tokenizer.py',
        'test_src/utils.py',

        'test_src/backend/__init__.py',
        'test_src/backend/arm.py',
        'test_src/backend/c.py',
        'test_src/backend/llvm.py',
        'test_src/backend/python.py',
        'test_src/backend/qbe.py',
        'test_src/backend/riscv.py',
        'test_src/backend/shell.py',
        'test_src/backend/x86_64.py',
    ]

    # register_file('${module.name}', '''${code}''')
    for filename in files:
        filepath = root / filename[5:] # remove 'test_' prefix
        register_file(filename, filepath.read_text())





    # silent imports
    from test_src.backend.python import top_level_evaluate, BuiltinFuncs
    from test_src.tokenizer import tokenize
    from test_src.postok import post_process
    from test_src.postparse import post_parse
    from test_src.parser import top_level_parse
    from functools import partial


    source = '''printl"Hello, World! From Dewy!"'''
    # escaped_source = source.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'").replace('\n', '\\n')
    escaped_source = source # in this context, don't need to escape anything

    # define main entry point
    def dewy(src:str):
        # tokenize and parse
        tokens = tokenize(src)
        post_process(tokens)
        ast = top_level_parse(tokens)
        ast = post_parse(ast)

        # run the program
        res = top_level_evaluate(ast)
        # if res is not void: print(res) #causes weird behavior in most cases

    # replace pdb.set_trace with a message and exit(1)
    import pdb
    def pdb_set_trace():
        print('ERROR: encountered syntax which is not yet implemented. exiting.', flush=True)
        exit(1)
    pdb.set_trace = pdb_set_trace

    # run dewy source code
    try:
        dewy(f'''{escaped_source}'''); sys.stdout.flush()
    except IOError:
        print('ERROR: failed to read input. exiting.', flush=True)
    except Exception as e:
        print(f'ERROR: {e}')
        print('ERROR: encountered problem while running. exiting.', flush=True)



    # pdb.set_trace()
    # ...

