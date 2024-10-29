from pathlib import Path
from ..utils import Options

def llvm_compiler(path: Path, args: list[str], options: Options) -> None:
    raise NotImplementedError('LLVM backend is not yet supported')
