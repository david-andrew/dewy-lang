from . import t0, t1, p0
from .backend import Backend, BackendName, get_backend
from .backend.common import RunOptions
from .cache import cache_layout
from .compilation import compiler_allocation_scope
from .stream import Recorder, Stream
import os
from pathlib import Path
from dataclasses import dataclass
from collections.abc import Callable

@dataclass
class EntryPointOptions:
    compile_only: bool = False
    target: BackendName = "x86_64"
    split_wasm: bool = False
    serve_wasm: bool = False
    debug_info: bool = True

@compiler_allocation_scope()
def entry_point(input_file: Path, script_args: list[str], options: EntryPointOptions|None=None,
                *, generate: Callable[[Backend], str] | None = None) -> int:
    """
    Entry point for the udewy compiler.

    Args:
        input_file: Path to the input file
        script_args: Command-line arguments to pass to the program
        options: Options for the compiler
        generate: Optional internal backend producer for an already lowered
            module. Loading still supplies its link artifacts and source inputs.

    Returns:
        Exit code of the program or 0 if in compile-only mode

    Raises:
        SyntaxError: If the input file is not a valid udewy program
        RuntimeError: If the program fails to compile or link
    """
    if options is None: options = EntryPointOptions()

    # possible raise SyntaxError
    backend = get_backend(options.target)
    backend.debug_info = options.debug_info
    if Path(input_file).suffix == '.ubc':
        # µDewy bytecode (udewy/BYTECODE.md): replay the recorded backend
        # calls; no tokenizing or parsing.
        stream = Stream(Path(input_file).read_bytes())
        asm = stream.play(backend)
        link_artifacts = stream.link_artifacts
        imported_sources = [str(path) for path in stream.imported_sources]
    else:
        loaded = t0.load_program(input_file, target_backend=options.target)
        link_artifacts = loaded.link_artifacts
        imported_sources = loaded.imported_sources
        # UDEWY_RECORD=path also writes the module's bytecode to `path`.
        record_path = os.environ.get('UDEWY_RECORD')
        target = Recorder(backend, link_artifacts) if record_path else backend
        target.set_imported_sources([Path(path) for path in loaded.imported_sources])
        if generate is None:
            toks = t1.tokenize(loaded.source)
            asm = p0.parse(toks, loaded.source, target, source_path=str(Path(input_file).resolve()))
        else:
            asm = generate(target)
        if record_path:
            Path(record_path).write_bytes(target.stream())

    
    cache_dir, input_name = cache_layout(input_file)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Use the backend to compile and link
    output_path = backend.compile_and_link(
        asm,
        input_name,
        cache_dir,
        split_wasm=options.split_wasm,
        link_artifacts=link_artifacts,
        imported_sources=imported_sources,
    )

    
    if options.compile_only:
        print(backend.get_compile_message(output_path, split_wasm=options.split_wasm))
        return 0
    
    run_options = RunOptions(
        split_wasm=options.split_wasm,
        serve_wasm=options.serve_wasm,
        input_file=input_file,
        link_artifacts=[Path(path) for path in link_artifacts],
    )
    exit_code = backend.run(output_path, script_args, run_options)
    if exit_code is not None:
        return exit_code
    
    print(backend.get_compile_message(output_path, split_wasm=options.split_wasm))
    return 0
