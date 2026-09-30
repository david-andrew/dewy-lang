import json
import sys
import time

from audit_support import output_directory

from dewy.reporting import SrcFile
from dewy.semantic import check, ty

HERE = output_directory()


out = {"normalization": [], "generic_programs": []}
for n in (6, 10, 14):
    # Distinct structural atoms allow compatible intersections, unlike a
    # conjunction of unrelated primitive numeric types.
    choices = [
        ty.TypeOr(
            [
                ty.ObjectType((ty.ObjectField(f"a{i}", "int64"),)),
                ty.ObjectType((ty.ObjectField(f"b{i}", "int64"),)),
            ]
        )
        for i in range(n)
    ]
    t = ty.TypeAnd(choices)
    start = time.process_time()
    clauses = ty.normalize(t)
    out["normalization"].append(
        {
            "choices": n,
            "clauses": len(clauses),
            "literal_entries": sum(map(len, clauses)),
            "cpu_seconds": time.process_time() - start,
        }
    )
    del clauses

original = check._instantiate_generic_function
instances = []


def observe(generic, arguments, **kwargs):
    instances.append(
        {"function": generic.name, "types": {k: repr(v) for k, v in arguments.items()}}
    )
    return original(generic, arguments, **kwargs)


check._instantiate_generic_function = observe

programs = {
    "length_specialization": """
let identity = <T>(x:T):>T => x
let main = ():>int64 => {
    let a = identity([1])
    let b = identity([1 2])
    let c = identity([1 2 3])
    let d = identity([4])
    return a.length + b.length + c.length + d.length
}
""",
    "array_join_inference": """
let choose = <T>(a:T b:T):>T => a
let main = ():>int64 => {
    let a = choose([1] [2 3])
    return a.length
}
""",
    "array_join_context": """
let choose = <T>(a:T b:T):>T => a
let main = ():>int64 => {
    let a:array<int64> = choose([1] [2 3])
    return a.length
}
""",
    "record_join_inference": """
let choose = <T>(a:T b:T):>T => a
let main = ():>int64 => {
    let a = choose([x=1] [x=2])
    return a.x
}
""",
    "growing_generic_recursion": """
let grow = <T>(x:T):>int64 => grow([x])
let main = ():>int64 => grow(1)
""",
}
for name, source in programs.items():
    instances.clear()
    start = time.process_time()
    previous_limit = sys.getrecursionlimit()
    if name == "growing_generic_recursion":
        sys.setrecursionlimit(220)
    try:
        root = check.typecheck_and_resolve(
            SrcFile(None, "$no_prelude=true\n" + source), include_prelude=False
        )
        status = "accepted"
        message = ""
    except Exception as e:  # noqa: BLE001 - compiler failures are audit observations.
        status = type(e).__name__
        message = str(e)[:1000]
    finally:
        sys.setrecursionlimit(previous_limit)
    out["generic_programs"].append(
        {
            "name": name,
            "status": status,
            "message": message,
            "instances": list(instances)[:8],
            "instance_count": len(instances),
            "cpu_seconds": time.process_time() - start,
        }
    )

(HERE / "results.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
