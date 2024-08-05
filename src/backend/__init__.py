from .python import python_interpreter
from .qbe import qbe_compiler
from .llvm import llvm_compiler
from .c import c_compiler
from .x86_64 import x86_64_compiler
from .arm import arm_compiler
from .riscv import riscv_compiler
from .shell import shell_compiler
from typing import Protocol

class Backend(Protocol):
    def __call__(self, path: str, args: list[str]) -> None:
        ...


backend_map: dict[str, Backend] = {
    'python': python_interpreter,
    'qbe': qbe_compiler,
    'llvm': llvm_compiler,
    'c': c_compiler,
    'x86_64': x86_64_compiler,
    'arm': arm_compiler,
    'riscv': riscv_compiler,
    'sh': shell_compiler,
    'zsh': shell_compiler,
    'bash': shell_compiler,
    'fish': shell_compiler,
    'posix': shell_compiler,
    'powershell': shell_compiler,
}
backends = [*backend_map.keys()]


def get_backend(name: str) -> Backend:
    try:
        return backend_map[name.lower()]
    except:
        raise ValueError(f'Unknown backend "{name}"') from None


def get_version() -> str:
    """Return the semantic version of the language"""
    from pathlib import Path
    return (Path(__file__).parent.parent.parent / 'VERSION').read_text().strip()
