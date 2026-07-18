from . import t0, t1, p0
from .backend import BackendName, get_backend
from .backend.common import RunOptions
from pathlib import Path
from dataclasses import dataclass

@dataclass
class EntryPointOptions:
    compile_only: bool = False
    target: BackendName = "x86_64"
    split_wasm: bool = False
    serve_wasm: bool = False

def entry_point(input_file: Path, script_args: list[str], options: EntryPointOptions|None=None) -> int:
    """
    Entry point for the udewy compiler.

    Args:
        input_file: Path to the input file
        script_args: Command-line arguments to pass to the program
        options: Options for the compiler

    Returns:
        Exit code of the program or 0 if in compile-only mode

    Raises:
        SyntaxError: If the input file is not a valid udewy program
        RuntimeError: If the program fails to compile or link
    """
    if options is None: options = EntryPointOptions()

    # possible raise SyntaxError
    backend = get_backend(options.target)
    loaded = t0.load_program(input_file, target_backend=options.target)
    backend.set_imported_sources([Path(path) for path in loaded.imported_sources])
    toks = t1.tokenize(loaded.source)
    asm = p0.parse(toks, loaded.source, backend)

    
    cache_dir = Path("__dewycache__")
    cache_dir.mkdir(exist_ok=True)
    
    # Use the backend to compile and link
    output_path = backend.compile_and_link(
        asm, 
        input_file.stem, 
        cache_dir,
        split_wasm=options.split_wasm,
        link_artifacts=loaded.link_artifacts,
        imported_sources=loaded.imported_sources,
    )

    
    if options.compile_only:
        print(backend.get_compile_message(output_path, split_wasm=options.split_wasm))
        return 0
    
    run_options = RunOptions(
        split_wasm=options.split_wasm,
        serve_wasm=options.serve_wasm,
        input_file=input_file,
        link_artifacts=[Path(path) for path in loaded.link_artifacts],
    )
    exit_code = backend.run(output_path, script_args, run_options)
    if exit_code is not None:
        return exit_code
    
    print(backend.get_compile_message(output_path, split_wasm=options.split_wasm))
    return 0