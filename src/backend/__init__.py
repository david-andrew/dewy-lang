"""
Collection of all the Dewy Language backends
"""

from .python import python_backend, python_repl
from .qbe import qbe_backend
from .llvm import llvm_backend
from .c import c_backend
from .x86_64 import x86_64_backend
from .arm import arm_backend
from .riscv import riscv_backend
from .shell import shell_backend
from pathlib import Path
from ..utils import Backend



# TODO: perhaps we could automatically discover these backends based on files in the backend/ folder
backends: list[Backend] = [
    python_backend,
    qbe_backend,
    llvm_backend,
    c_backend,
    x86_64_backend,
    arm_backend,
    riscv_backend,
    shell_backend,
]

backend_map = {
    backend.name: backend for backend in backends
}

# TODO: for now we're gonna skip this and all shell backends are accessed under the name 'shell'
# backend_map = {
#     **backend_map,
#     'sh': shell_compiler,
#     'zsh': shell_compiler,
#     'bash': shell_compiler,
#     'fish': shell_compiler,
#     'posix': shell_compiler,
#     'powershell': shell_compiler,
# }


backend_names = [*backend_map.keys()]


def get_backend(name: str) -> Backend:
    try:
        return backend_map[name.lower()]
    except:
        raise ValueError(f'Unknown backend "{name}"') from None


def get_version() -> str:
    """Return the semantic version of the language"""
    return (Path(__file__).parent.parent.parent / 'VERSION').read_text().strip()
