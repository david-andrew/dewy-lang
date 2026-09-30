import json
import os
import tempfile
from pathlib import Path

from audit_support import output_directory

from dewy import __main__ as cli

HERE = output_directory()

with tempfile.TemporaryDirectory(dir=HERE) as directory:
    work = Path(directory)
    source = work / "main.dewy"
    source.write_text("$no_prelude=true\nmain=():>int64=>42\n")
    binary = work / "cached-x86"
    binary.write_text("not executed: an existing x86 artifact sentinel")
    os.utime(binary, (source.stat().st_mtime + 10, source.stat().st_mtime + 10))
    cli.cache_artifact = lambda *args, **kwargs: work / "main.udewy"
    cli.cache_layout = lambda *args, **kwargs: (work, "cached-x86")
    cli._compiler_mtime = lambda: 0
    calls = []
    cli.subprocess.call = lambda arguments: calls.append(arguments) or 42

    def reject_build(*args, **kwargs):
        raise AssertionError("a fresh compile was requested")

    cli.emit.prepare_program = reject_build
    cli.codegen = reject_build
    results = []
    for target in ("x86_64", "c", "wasm32"):
        result = cli._build_and_run(
            source,
            target,
            [],
            [],
            compile_only=False,
            debug_values=False,
            print_prototype_warnings=lambda: None,
        )
        results.append(
            {
                "requested_target": target,
                "status": result,
                "executed_artifact": calls[-1][0],
            }
        )
    output = {
        "kind": "cache decision unit probe, no executable run or fresh backend build",
        "results": results,
    }
    (HERE / "cache_decision.json").write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))
