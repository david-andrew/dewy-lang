from ..utils import Backend, BaseOptions

from pathlib import Path
from dataclasses import dataclass
from argparse import ArgumentParser, Namespace

@dataclass
class Options(BaseOptions): ...

def make_argparser(parent: ArgumentParser) -> None:
    #TODO: any options for the arm backend
    ...

def make_options(args: Namespace) -> Options:
    return Options(
        tokens=args.tokens,
        verbose=args.verbose,
    )

def arm_compiler(path: Path, args: list[str], options: Options) -> None:
    raise NotImplementedError('ARM backend is not yet supported')


arm_backend = Backend[Options](
    name='arm',
    exec=arm_compiler,
    make_argparser=make_argparser,
    make_options=make_options
)