from pathlib import Path
from ..utils import Options

def c_compiler(path: Path, args: list[str], options: Options) -> None:
    raise NotImplementedError('C backend is not yet supported')
