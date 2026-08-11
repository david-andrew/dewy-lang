"""Command-line entry point for ``python -m src.cleanparse.backend.udewy``."""

from pathlib import Path

from ....myargparse import ArgumentParser
from ...reporting import SrcFile
from . import codegen


def main() -> None:
    """Compile one Dewy source file to udewy source on standard output."""
    parser = ArgumentParser()
    parser.add_argument('path', type=Path, required=True, help='path to file to compile')
    args = parser.parse_args()
    path: Path = args.path
    print(codegen(SrcFile.from_path(path)), end='')


if __name__ == '__main__':
    main()
