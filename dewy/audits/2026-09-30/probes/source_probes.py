import json
import time

from audit_support import output_directory

from dewy.reporting import SrcFile
from dewy.semantic import check, ty

HERE = output_directory()

out = []
for n in (4, 8):
    expression = " & ".join(f"([a{i}:int64] | [b{i}:int64])" for i in range(n))
    source = f"$no_prelude=true\nT:type={expression}\nprobe=(item:T):>int64=>if item is? int64 0 else 1\nmain=():>int64=>42\n"
    counts = {"calls": 0, "output_clauses": 0, "max_clauses": 0}
    original = ty._distribute

    def observe(left, right, *, audit_original=original, audit_counts=counts):
        if len(left) * len(right) > 8192:
            raise RuntimeError("audit guard: stop before large distribution")
        result = audit_original(left, right)
        audit_counts["calls"] += 1
        audit_counts["output_clauses"] += len(result)
        audit_counts["max_clauses"] = max(audit_counts["max_clauses"], len(result))
        return result

    ty._distribute = observe
    start = time.process_time()
    try:
        check.typecheck_and_resolve(SrcFile(None, source), include_prelude=False)
        status, message = "accepted", ""
    except Exception as e:  # noqa: BLE001 - compiler failures are audit observations.
        status, message = type(e).__name__, str(e)[:200]
    finally:
        ty._distribute = original
    out.append(
        {
            "name": "source_type_intersection",
            "choices": n,
            "status": status,
            "message": message,
            "distribution": counts,
            "cpu_seconds": time.process_time() - start,
        }
    )

versions = {
    "inline_guard": "if 0 <=? i <? xs.length xs[i] else 0",
    "helper_guard": "if fits(i xs) xs[i] else 0",
    "wrapped_helper_guard": "if wrapped(i xs) xs[i] else 0",
}
for name, body in versions.items():
    source = f"""$no_prelude=true
let fits = (i:int64 xs:array<int64>):>bool => 0 <=? i <? xs.length
let wrapped = (i:int64 xs:array<int64>):>bool => fits(i xs)
let read = (xs:array<int64> i:int64):>int64 => {body}
let main = ():>int64 => read([42] 0)
"""
    start = time.process_time()
    try:
        check.typecheck_and_resolve(SrcFile(None, source), include_prelude=False)
        status, message = "accepted", ""
    except Exception as e:  # noqa: BLE001 - compiler failures are audit observations.
        status, message = type(e).__name__, str(e)[:1000]
    out.append(
        {
            "name": name,
            "status": status,
            "message": message,
            "cpu_seconds": time.process_time() - start,
        }
    )

(HERE / "source_probes.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
