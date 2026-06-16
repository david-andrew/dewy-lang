from pathlib import Path
from argparse import ArgumentParser

from .reporting import SrcFile
from .targets import TARGETS
from .backend.udewy import codegen
# from ...udewy import __main__ #TODO

import pdb


def get_version() -> str:
    """Return the semantic version of the language"""
    return (Path(__file__).parents[2] / 'VERSION').read_text().strip()


parser = ArgumentParser(description='Dewy Compiler')
parser.add_argument('file', nargs='?', help='.dewy file to run. If not provided, enter REPL mode')
parser.add_argument('-t', '--target', choices=TARGETS, help='backend target the program should compile to.')
parser.add_argument('-v', '--version', action='version', version=f'dewy {get_version()}', help='Print version information and exit')
parser.add_argument('-c', '--compile', action='store_true', help="compile only, don't run")

args = parser.parse_args()


path: Path|None = args.file
if path is None:
    # need to enter REPL mode...
    pdb.set_trace()


srcfile = SrcFile.from_path(args.file)
udewy = codegen(srcfile)

print(udewy)
pdb.set_trace()
#TODO: call udewy compiler with this and args..