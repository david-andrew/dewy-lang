import hashlib
import json
import re
import time

from audit_support import output_directory

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check

HERE = output_directory()
original = check._instantiate_generic_function
results = []
for n in (3, 5, 7):
    requests = []

    def observe(generic, arguments, *, audit_requests=requests, **kwargs):
        if generic.name == "probe":
            audit_requests.append(tuple(repr(v) for v in arguments.values()))
        return original(generic, arguments, **kwargs)

    check._instantiate_generic_function = observe
    lines = [
        "$no_prelude=true",
        "let probe=<A B>(a:A b:B):>int64=>0",
        "main=():>int64=>{",
    ]
    for a in range(1, n + 1):
        for b in range(1, n + 1):
            left = "[" + " ".join("1" for _ in range(a)) + "]"
            right = "[" + " ".join("2" for _ in range(b)) + "]"
            lines.append(f"probe({left} {right});")
    lines.append("return 42}")
    source = "\n".join(lines) + "\n"
    (HERE / f"specialization-{n}.dewy").write_text(source)
    start = time.process_time()
    row = {"lengths_per_argument": n, "calls": n * n}
    try:
        emitted = codegen(SrcFile(None, source), debug_locations=False)
        (HERE / f"specialization-{n}.udewy").write_text(emitted)
        functions = list(
            re.finditer(
                r"^let (probe__\S+) = ([^\n]+)\n(.*?)^}",
                emitted,
                re.MULTILINE | re.DOTALL,
            )
        )
        variants = {
            hashlib.sha256((m.group(2) + "\n" + m.group(3)).encode()).hexdigest()
            for m in functions
        }
        row.update(
            status="lowered",
            body_checks=len(requests),
            emitted_functions=len(functions),
            distinct_headers_and_bodies=len(variants),
            emitted_bytes=len(emitted.encode()),
            example=functions[0].group(0) if functions else emitted[:1000],
        )
    except Exception as e:  # noqa: BLE001 - compiler failures are audit observations.
        row.update(
            status=type(e).__name__, body_checks=len(requests), message=str(e)[:1000]
        )
    finally:
        check._instantiate_generic_function = original
    row["cpu_seconds"] = time.process_time() - start
    results.append(row)
    print(
        json.dumps({k: v for k, v in row.items() if k not in ("example", "message")}),
        flush=True,
    )
    (HERE / "specialization.json").write_text(json.dumps(results, indent=2))
