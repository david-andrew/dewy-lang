"""The `dewy` command.

    dewy [options] file.dewy [program args]   compile and run a program
    dewy analyze [options] file.dewy          compile and report the analysis decisions

Actions are subcommands (`dewy analyze`, later `dewy test`, `dewy lint`, …);
flags are only ever options of the command or subcommand they follow.
"""
import sys
from argparse import REMAINDER, ArgumentParser
from pathlib import Path
from typing import cast

from udewy.backend import BackendName
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

from .backend.udewy import codegen
from .reporting import Info, Pointer, SrcFile, color_enabled
from .targets import TARGETS, identify_host_target


def get_version() -> str:
    """Return the semantic version of the language"""
    return (Path(__file__).parents[1] / 'VERSION').read_text().strip()


def _add_target_option(parser: ArgumentParser) -> None:
    parser.add_argument('-t', '--target', choices=TARGETS, help='backend target the program should compile to.')


def _resolve_target(name: str | None) -> BackendName:
    return cast(BackendName, name or identify_host_target())


# ---------------------------------------------------------------- dewy <file>
def run(argv: list[str]) -> int:
    parser = ArgumentParser(prog='dewy', description='Dewy Compiler', epilog='subcommands: analyze')
    parser.add_argument('file', nargs='?', help='.dewy file to run. If not provided, enter REPL mode')
    _add_target_option(parser)
    parser.add_argument('-v', '--version', action='version', version=f'dewy {get_version()}', help='Print version information and exit')
    parser.add_argument('-c', '--compile', action='store_true', help="compile only, don't run")
    parser.add_argument('remainder', nargs=REMAINDER, default=[], help='arguments to pass to the program')
    args = parser.parse_args(argv)

    if args.file is None:
        if args.remainder or not sys.stdin.isatty():
            parser.error(f'unrecognized arguments: {" ".join(args.remainder)}' if args.remainder else 'a .dewy file is required')
        # need to enter REPL mode...
        import pdb

        pdb.set_trace()
        return 0

    # compile the program and output udewy source code
    path = Path(args.file)
    srcfile = SrcFile.from_path(path)
    target = _resolve_target(args.target)
    udewy_src = codegen(srcfile, target=target)

    # set up udewy options, and save the udewy source code to a cache file
    options = EntryPointOptions(
        compile_only=args.compile,
        target=target,
        # TODO: for now wasm extra args are ignored
    )
    udewy_path = cache_artifact(path, '.udewy')
    udewy_path.parent.mkdir(parents=True, exist_ok=True)
    udewy_path.write_text(udewy_src)

    # run the udewy compiler/executor
    try:
        return entry_point(udewy_path, args.remainder, options)
    except Exception as e:
        print(f'Error: {e}')
        return 1


# ---------------------------------------------------------- dewy analyze <file>
def analyze(argv: list[str]) -> int:
    """Compile a program and report the compiler's analysis decisions."""
    parser = ArgumentParser(prog='dewy analyze', description='report the analysis decisions made while compiling a program (currently: which integers became big integers, and why)')
    parser.add_argument('file', help='.dewy file to analyze')
    _add_target_option(parser)
    args = parser.parse_args(argv)

    from .semantic import check
    from .semantic.analyze import representation

    srcfile = SrcFile.from_path(Path(args.file))
    check.typecheck_and_resolve(srcfile, include_prelude=True, target=_resolve_target(args.target))

    use_color = color_enabled(sys.stdout)
    notes = representation.last_notes
    for note in notes:
        print(Info(
            srcfile=note.srcfile,
            title='big integer representation',
            pointer_messages=[Pointer(span=note.loc, message=note.message)],
            use_color=use_color,
        ))
        print()
    summary = (
        f'{len(notes)} representation decision{"s" if len(notes) != 1 else ""}: the values above are big integers; every other integer is a 64-bit word'
        if notes
        else 'every integer is a 64-bit word'
    )
    print(Info(srcfile=srcfile, title='representation report', message=summary, use_color=use_color))
    return 0


SUBCOMMANDS = {'analyze': analyze}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in SUBCOMMANDS:
        return SUBCOMMANDS[argv[0]](argv[1:])
    return run(argv)


if __name__ == '__main__':
    sys.exit(main())
