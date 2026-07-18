from pathlib import Path
from .backend import BackendName
from .frontend import entry_point, EntryPointOptions
from typing import cast
import sys

# ============================================================================
# CLI entry point
# ============================================================================


if len(sys.argv) < 2:
    print("Usage: python -m udewy [-c] [--target TARGET] [--split-wasm] [--serve-wasm] <file.udewy> [args...]")
    print("  -c              Compile only, don't run")
    print("  --target TARGET Target backend (x86_64, wasm32, riscv, arm, c)")
    print("  --split-wasm    For wasm32: output separate .wasm file instead of embedded HTML")
    print("  --serve-wasm    For wasm32: serve the generated HTML over HTTP")
    sys.exit(1)

options = EntryPointOptions()
arg_idx = 1

while arg_idx < len(sys.argv) and sys.argv[arg_idx].startswith("-"):
    if sys.argv[arg_idx] == "-c":
        options.compile_only = True
        arg_idx += 1
    elif sys.argv[arg_idx] == "--target":
        arg_idx += 1
        options.target = cast(BackendName, sys.argv[arg_idx])
        arg_idx += 1
    elif sys.argv[arg_idx] == "--split-wasm":
        options.split_wasm = True
        arg_idx += 1
    elif sys.argv[arg_idx] == "--serve-wasm":
        options.serve_wasm = True
        arg_idx += 1
    else:
        break

if arg_idx >= len(sys.argv):
    print("Error: No input file specified")
    sys.exit(1)

input_file = Path(sys.argv[arg_idx])
script_args = sys.argv[arg_idx + 1:]

try:
    exit_code = entry_point(input_file, script_args, options)
except Exception as e:
    print(f"Error: {e}")
    exit_code = 1

sys.exit(exit_code)