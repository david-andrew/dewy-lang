"""The `dewy` command.

    dewy [options] file.dewy [program args]   compile and run a program
    dewy test [options] [file.dewy | dir]     run a module's `$test` functions, or every `$test` under a directory
    dewy analyze [options] file.dewy          compile and report the analysis decisions

Actions are subcommands (`dewy analyze`, `dewy test`, later `dewy lint`, …);
flags are rare and only ever options of the command or subcommand they follow.
"""
import io
import os
import subprocess
import sys
from argparse import REMAINDER, SUPPRESS, ArgumentParser
from contextlib import redirect_stdout
from pathlib import Path
from typing import cast

from udewy.backend import BackendName
from udewy.cache import cache_artifact, cache_layout
from udewy.frontend import EntryPointOptions, entry_point

from .backend.udewy import codegen
from .reporting import Info, Pointer, ReportException, SrcFile, color_enabled
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
    parser = ArgumentParser(prog='dewy analyze', description='report the analysis decisions made while compiling a program: the escape copies of strings, and which integers became big integers, and why')
    parser.add_argument('file', help='.dewy file to analyze')
    _add_target_option(parser)
    args = parser.parse_args(argv)

    from .backend.udewy import lower
    from .semantic.analyze import representation

    srcfile = SrcFile.from_path(Path(args.file))
    codegen(srcfile, target=_resolve_target(args.target))   # checks and lowers: both reports come from that

    use_color = color_enabled(sys.stdout)
    for note in lower.last_copy_notes:
        print(Info(
            srcfile=note.srcfile,
            title='escape copy',
            pointer_messages=[Pointer(span=note.loc, message=note.message)],
            use_color=use_color,
        ))
        print()
    copies = len(lower.last_copy_notes)
    print(Info(
        srcfile=srcfile,
        title='copy report',
        message=(
            f'{copies} escape cop{"ies" if copies != 1 else "y"}: the strings above are copied into the arena where they are stored; every other stored string is static or already arena-backed'
            if copies
            else 'no escape copies: every stored string is static or already arena-backed'
        ),
        use_color=use_color,
    ))
    print()
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


# ------------------------------------------------------------ dewy test [dir]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DRIVER = PROJECT_ROOT / 'tools' / 'dewy_test.dewy'


def _newest_mtime(*roots: Path, suffixes: tuple[str, ...]) -> float:
    newest = 0.0
    for root in roots:
        for candidate in root.rglob('*'):
            if candidate.suffix in suffixes and candidate.is_file():
                newest = max(newest, candidate.stat().st_mtime)
    return newest


def _compiler_mtime() -> float:
    """When the compiler or the library last changed: anything built before it is stale."""
    return _newest_mtime(PROJECT_ROOT / 'dewy', PROJECT_ROOT / 'udewy', PROJECT_ROOT / 'library', suffixes=('.py', '.dewy'))


def _build_test_driver(target: BackendName) -> Path:
    """Compile `tools/dewy_test.dewy` (the runner, written in Dewy) when it is missing or older than the compiler."""
    udewy_path = cache_artifact(TEST_DRIVER, '.udewy')
    cache_dir, name = cache_layout(udewy_path)
    binary = cache_dir / name
    sources_mtime = max(TEST_DRIVER.stat().st_mtime, _compiler_mtime())
    if binary.is_file() and binary.stat().st_mtime >= sources_mtime:
        return binary
    udewy_path.parent.mkdir(parents=True, exist_ok=True)
    udewy_path.write_text(codegen(SrcFile.from_path(TEST_DRIVER), target=target))
    with redirect_stdout(io.StringIO()):
        status = entry_point(udewy_path, [], EntryPointOptions(compile_only=True, target=target))
    if status != 0 or not binary.is_file():
        raise RuntimeError(f'could not build the test driver ({TEST_DRIVER})')
    return binary


# exit statuses of `dewy test file.dewy` (the driver reads them): 0–100 the
# number of failed tests, then the ways a module can fail to report at all
TEST_ABORTED = 101         # a `$runtime_assert` exited the test binary
TEST_NOT_BUILT = 102       # the module did not compile


def test(argv: list[str]) -> int:
    """Run one module's `$test` functions, or every module with tests under a directory."""
    parser = ArgumentParser(prog='dewy test', description="run a module's `$test` functions (a `.dewy` file), or find every `.dewy` file with `$test` functions under a directory and run them all")
    parser.add_argument('path', nargs='?', default='.', help='a .dewy file, or a directory to search (default: the current directory)')
    parser.add_argument('--json', action='store_true', help='one JSON object per test (and per file) instead of the text report')
    parser.add_argument('--brief', action='store_true', help=SUPPRESS)   # from the directory driver: the module leaves out its summary line
    _add_target_option(parser)
    args = parser.parse_args(argv)
    target = _resolve_target(args.target)
    path = Path(args.path)
    if path.is_dir():
        driver = _build_test_driver(target)
        # the driver runs `dewy test <file>` through this interpreter for each
        # test file; make the package importable from wherever it runs
        env = dict(os.environ)
        env['PYTHONPATH'] = os.pathsep.join(filter(None, [str(PROJECT_ROOT), env.get('PYTHONPATH')]))
        env['DEWY_PYTHON'] = sys.executable
        command = [str(driver), *(['--json'] if args.json else []), args.path]
        return subprocess.call(command, env=env)

    # one module: its `$test` functions get the generated runner as the entry
    # (a separate `<stem>.test` binary; the module's own `main` is untouched)
    udewy_path = cache_artifact(path, '.test.udewy')
    cache_dir, name = cache_layout(udewy_path)
    binary = cache_dir / name
    program_args = [*(['--json'] if args.json else []), *(['--brief'] if args.brief else [])]
    # the compile dominates a run (seconds, against milliseconds of tests):
    # reuse the binary unless the module, a `.dewy` file near it (its
    # imports), or the compiler changed since it was built
    sources_mtime = max(_newest_mtime(path.resolve().parent, suffixes=('.dewy',)), _compiler_mtime())
    if binary.is_file() and binary.stat().st_mtime >= sources_mtime:
        return subprocess.call([str(binary), *program_args])
    try:
        udewy_src = codegen(SrcFile.from_path(path), target=target, test=True)
    except ReportException as failure:
        failure.report.use_color = color_enabled(sys.stderr)
        print(failure.report, file=sys.stderr)
        return TEST_NOT_BUILT
    udewy_path.parent.mkdir(parents=True, exist_ok=True)
    udewy_path.write_text(udewy_src)
    try:
        return entry_point(udewy_path, program_args, EntryPointOptions(target=target))
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        return TEST_NOT_BUILT


SUBCOMMANDS = {'analyze': analyze, 'test': test}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in SUBCOMMANDS:
        return SUBCOMMANDS[argv[0]](argv[1:])
    return run(argv)


if __name__ == '__main__':
    sys.exit(main())
