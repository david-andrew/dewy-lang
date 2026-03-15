from .common import Backend
from .x86_64 import X86_64Backend
from .wasm import Wasm32Backend
from .riscv import RiscvBackend
from .arm import ArmBackend
from typing import Literal

BackendName = Literal["x86_64", "wasm32", "riscv", "arm"]

BACKEND_MAP: dict[BackendName, type[Backend]] = {
    "x86_64": X86_64Backend,
    "wasm32": Wasm32Backend,
    "riscv": RiscvBackend,
    "arm": ArmBackend,
}

def get_backend(name: BackendName) -> Backend:
    try:
        return BACKEND_MAP[name]()
    except KeyError:
        raise ValueError(f"Unknown backend: {name}. Supported backends: {list(BACKEND_MAP.keys())}")