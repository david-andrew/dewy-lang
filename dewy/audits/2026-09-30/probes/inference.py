import json
import time

from audit_support import output_directory

from dewy.reporting import SrcFile
from dewy.semantic import check, hir

HERE = output_directory()
choose = "let choose=<T>(a:T b:T):>T=>a\n"
identity = "let identity=<T>(x:T):>T=>x\n"
cases = {
    "unannotated": choose
    + "main=():>int64=>{let x=choose([1] [2 3]) return x.length}\n",
    "typed_local": choose
    + "main=():>int64=>{let x:array<int64>=choose([1] [2 3]) return x.length}\n",
    "typed_return": choose
    + "work=():>array<int64>=>choose([1] [2 3])\nmain=():>int64=>work().length\n",
    "monomorphic_argument": choose
    + "length=(x:array<int64>):>int64=>x.length\nmain=():>int64=>length(choose([1] [2 3]))\n",
    "monomorphic_unrelated_tag": choose
    + "length=(x:array<int64> tag:int64):>int64=>x.length\nmain=():>int64=>length(choose([1] [2 3]) 0)\n",
    "generic_unrelated_tag": choose
    + "let length=<Tag>(x:array<int64> tag:Tag):>int64=>x.length\nmain=():>int64=>length(choose([1] [2 3]) 0)\n",
    "generic_argument": choose
    + identity
    + "main=():>int64=>{let x:array<int64>=identity(choose([1] [2 3])) return x.length}\n",
    "typed_intermediate_then_generic": choose
    + identity
    + "main=():>int64=>{let intermediate:array<int64>=choose([1] [2 3]) let x=identity(intermediate) return x.length}\n",
    "record_result_context": "let wrap=<T>(a:T b:T):>[value:T]=>[value=a]\nmain=():>int64=>{let x:[value:array<int64>]=wrap([1] [2 3]) return x.value.length}\n",
    "optional_result_context": "let choose=<T>(a:T b:T):>T|none=>a\nmain=():>int64=>{let x:array<int64>|none=choose([1] [2 3]) return if x isnt? none x.length else 0}\n",
    "nested_array_result_context": "let wrap=<T>(a:T b:T):>array<T>=>[a]\nmain=():>int64=>{let x:array<array<int64>>=wrap([1] [2 3]) return x.length}\n",
    "nested_generic_with_annotated_inputs": choose
    + identity
    + "main=():>int64=>{let a:array<int64>=[1] let b:array<int64>=[2 3] let x=identity(choose(a b)) return x.length}\n",
    "erased_input_lengths": choose
    + identity
    + "erase=(xs:array<int64>):>array<int64>=>xs\nmain=():>int64=>{let x=identity(choose(erase([1]) erase([2 3]))) return x.length}\n",
    "generic_forwarder": choose
    + "let forward=<T>(a:T b:T):>T=>choose(a b)\nmain=():>int64=>{let x:array<int64>=forward([1] [2 3]) return x.length}\n",
    "record_argument_context": choose
    + "Holder:type=[values:array<int64>]\nmain=():>int64=>{let x=Holder[choose([1] [2 3])] return x.values.length}\n",
    "imported_typed_local": 'from [path="lib.dewy"] import choose\nmain=():>int64=>{let x:array<int64>=choose([1] [2 3]) return x.length}\n',
    "imported_typed_return": 'from [path="lib.dewy"] import choose\nwork=():>array<int64>=>choose([1] [2 3])\nmain=():>int64=>work().length\n',
    "imported_generic_forwarder": 'from [path="lib.dewy"] import forward\nmain=():>int64=>{let x:array<int64>=forward([1] [2 3]) return x.length}\n',
}
(HERE / "lib.dewy").write_text(
    "$no_prelude=true\n" + choose + "let forward=<T>(a:T b:T):>T=>choose(a b)\n"
)
results = []
for name, body in cases.items():
    path = HERE / f"{name}.dewy"
    path.write_text("$no_prelude=true\n" + body)
    started = time.process_time()
    try:
        root = check.typecheck_and_resolve(
            SrcFile.from_path(path), include_prelude=False
        )
        status, message = "accepted", ""
        instances = [
            n.name for n in root.items if isinstance(n, hir.Declare) and "__" in n.name
        ]
    except Exception as e:  # noqa: BLE001 - compiler failures are audit observations.
        status, message = type(e).__name__, str(e)[:1000]
        instances = []
    result = {
        "name": name,
        "status": status,
        "message": message,
        "instances": instances,
        "cpu_seconds": time.process_time() - started,
    }
    results.append(result)
    print(name, status, message[:120].replace("\n", " "), flush=True)
(HERE / "inference.json").write_text(json.dumps(results, indent=2))
