from pathlib import Path
from . import t0, t1, p0
from .backend import BACKEND_NAMES, BackendName, get_backend
from .backend.common import RunOptions
from typing import cast

# ============================================================================
# CLI entry point
# ============================================================================


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m udewy [-c] [--target TARGET] [--split-wasm] [--serve-wasm] <file.udewy> [args...]")
        print("  -c              Compile only, don't run")
        print("  --target TARGET Target backend (x86_64, wasm32, riscv, arm, c)")
        print("  --split-wasm    For wasm32: output separate .wasm file instead of embedded HTML")
        print("  --serve-wasm    For wasm32: serve the generated HTML over HTTP")
        sys.exit(1)
    
    compile_only = False
    requested_target: BackendName | None = None
    split_wasm = False
    serve_wasm = False
    arg_idx = 1
    
    while arg_idx < len(sys.argv) and sys.argv[arg_idx].startswith("-"):
        if sys.argv[arg_idx] == "-c":
            compile_only = True
            arg_idx += 1
        elif sys.argv[arg_idx] == "--target":
            arg_idx += 1
            requested_target = cast(BackendName, sys.argv[arg_idx])
            arg_idx += 1
        elif sys.argv[arg_idx] == "--split-wasm":
            split_wasm = True
            arg_idx += 1
        elif sys.argv[arg_idx] == "--serve-wasm":
            serve_wasm = True
            arg_idx += 1
        else:
            break
    
    if arg_idx >= len(sys.argv):
        print("Error: No input file specified")
        sys.exit(1)
    
    input_file = Path(sys.argv[arg_idx])
    script_args = sys.argv[arg_idx + 1:]
    
    try:
        loaded = t0.load_program(
            input_file,
            requested_backend=requested_target,
            known_backends=BACKEND_NAMES,
        )
        backend = get_backend(cast(BackendName, loaded.selected_backend))
        backend.set_imported_sources([Path(path) for path in loaded.imported_sources])
        src = loaded.source
        toks = t1.tokenize(src)
        asm = p0.parse(toks, src, backend)
    except (SyntaxError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    cache_dir = Path("__dewycache__")
    cache_dir.mkdir(exist_ok=True)
    
    # Use the backend to compile and link
    try:
        output_path = backend.compile_and_link(
            asm, 
            input_file.stem, 
            cache_dir,
            split_wasm=split_wasm,
            link_artifacts=loaded.link_artifacts,
            imported_sources=loaded.imported_sources,
        )
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    if compile_only:
        print(backend.get_compile_message(output_path, split_wasm=split_wasm))
    else:
        run_options = RunOptions(
            split_wasm=split_wasm,
            serve_wasm=serve_wasm,
            input_file=input_file,
            link_artifacts=[Path(path) for path in loaded.link_artifacts],
        )
        exit_code = backend.run(output_path, script_args, run_options)
        if exit_code is not None:
            sys.exit(exit_code)
        else:
            print(backend.get_compile_message(output_path, split_wasm=split_wasm))
