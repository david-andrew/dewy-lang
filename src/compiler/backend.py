from typing import Callable


def python_interpreter(path:str, args:list[str]):
    from tokenizer import tokenize
    from postok import post_process
    from parser import top_level_parse # type: ignore[reportShadowedImports]
    from dewy import Scope, void

    with open(path) as f:
        src = f.read()
    
    tokens = tokenize(src)
    post_process(tokens)

    root = Scope.default()
    ast = top_level_parse(tokens, root)
    res = ast.eval(root)
    if res and res is not void: print(res)

def qbe_compiler(path:str, args:list[str]):
    raise NotImplementedError('QBE backend is not yet supported')

def llvm_compiler(path:str, args:list[str]):
    raise NotImplementedError('LLVM backend is not yet supported')

def c_compiler(path:str, args:list[str]):
    raise NotImplementedError('C backend is not yet supported')

def x86_64_compiler(path:str, args:list[str]):
    raise NotImplementedError('x86_64 backend is not yet supported')

def arm(path:str, args:list[str]):
    raise NotImplementedError('ARM backend is not yet supported')

def riscv(path:str, args:list[str]):
    raise NotImplementedError('RISC-V backend is not yet supported')

def shell(path:str, args:list[str]):
    """this would target sh/powershell/etc. all simultaneously"""
    raise NotImplementedError('Shell backend is not yet supported')

backend_map = {
    'python': python_interpreter,
    'QBE': qbe_compiler,
    'llvm': llvm_compiler,
    'c': c_compiler,
    'x86_64': x86_64_compiler,
    'arm': arm,
    'riscv': riscv,
    'sh': shell,
    'zsh': shell,
    'bash': shell,
    'fish': shell,
    'posix': shell,
    'powershell': shell,
}
backends = [*backend_map.keys()]

def get_backend(name:str) -> Callable[[str, list[str]], None]:
    try:
        return backend_map[name.lower()]
    except:
        raise ValueError(f'Unknown backend "{name}"') from None


def get_version() -> str:
    """Return the semantic version of the language"""
    from pathlib import Path
    return (Path(__file__).parent.parent.parent / 'VERSION').read_text().strip()