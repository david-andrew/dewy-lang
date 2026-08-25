from pathlib import Path
from argparse import ArgumentParser, REMAINDER

from .reporting import SrcFile
from .targets import TARGETS, identify_host_target
from .backend.udewy import codegen
from udewy.cache import cache_artifact
from udewy.frontend import entry_point, EntryPointOptions
from udewy.backend import BackendName
from typing import cast
import sys
import pdb


def get_version() -> str:
    """Return the semantic version of the language"""
    return (Path(__file__).parents[1] / 'VERSION').read_text().strip()


parser = ArgumentParser(description='Dewy Compiler')
parser.add_argument('file', nargs='?', help='.dewy file to run. If not provided, enter REPL mode')
parser.add_argument('-t', '--target', choices=TARGETS, help='backend target the program should compile to.')
parser.add_argument('-v', '--version', action='version', version=f'dewy {get_version()}', help='Print version information and exit')
parser.add_argument('-c', '--compile', action='store_true', help="compile only, don't run")
parser.add_argument('remainder', nargs=REMAINDER, default=[], help='arguments to pass to the program')
args = parser.parse_args()


# path: Path|None = args.file
if args.file is None:
    # need to enter REPL mode...
    pdb.set_trace()
    sys.exit(0)

# compile the program and output udewy source code
path = Path(args.file)
srcfile = SrcFile.from_path(path)
target = cast(BackendName, args.target or identify_host_target())
udewy_src = codegen(srcfile, target=target)

# set up udewy options, and save the udewy source code to a cache file
options = EntryPointOptions(
    compile_only=args.compile,
    target=target,
    #TODO: for now wasm extra args are ignored
)
udewy_path = cache_artifact(path, ".udewy")
udewy_path.parent.mkdir(parents=True, exist_ok=True)
udewy_path.write_text(udewy_src)

# run the udewy compiler/executor
try:
    exit_code = entry_point(udewy_path, args.remainder, options)
except Exception as e:
    print(f"Error: {e}")
    exit_code = 1
# finally:
#     # delete the cache file
#     udewy_path.unlink()
sys.exit(exit_code)