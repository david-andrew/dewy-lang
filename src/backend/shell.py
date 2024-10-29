from pathlib import Path
from ..utils import Options

def shell_compiler(path: Path, args: list[str], options: Options) -> None:
    """this would target sh/powershell/etc. all simultaneously"""
    # TODO: find the explanation of how this works
    # https://en.wikipedia.org/wiki/Polyglot_(computing)
    raise NotImplementedError('Shell backend is not yet supported')
