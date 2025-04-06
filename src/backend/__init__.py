"""
Collection of all the Dewy Language backends
"""

from .python import PythonBackend, python_repl
from .qbe import QbeBackend
# from .llvm import llvm_compiler
# from .c import c_compiler
# from .x86_64 import x86_64_compiler
# from .arm import arm_compiler
# from .riscv import riscv_compiler
# from .shell import shell_compiler
# from typing import Protocol
from pathlib import Path
# from argparse import ArgumentParser
# from dataclasses import dataclass
from ..utils import Backend



# TODO: perhaps we could automatically discover these backends based on files in the backend/ folder
backends: list[Backend] = [
    PythonBackend,
    QbeBackend,
    # llvm_compiler,
    # c_compiler,
    # x86_64_compiler,
    # arm_compiler,
    # riscv_compiler,
    # shell_compiler,
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
