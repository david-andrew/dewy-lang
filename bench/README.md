# Application benchmarks

Small programs, each with a Dewy source and a C counterpart of the same
algorithm. `python3 -m tools.compiler.benchmark_apps` builds them, checks that
every build agrees on the checksum at each input size, and compares runtimes
with C (`-O2`). Other runners in `tools/compiler/` reuse `harness.h`,
`graph.c` and `records.c`. The correctness gate also runs the workloads on
native and web targets.

| name | what it exercises |
|---|---|
| `helpers` | small functions called from a hot scalar loop: gcd, a bounded Collatz walk, a clamp |
| `arrays` | flat `array<int64>` loops: prefix sums, in-place reverse, a sieve |
| `records` | passes over an `array<Particle>` of four-integer records, updating fields in place |
| `text` | byte scanning: words hashed, decimal numbers parsed, lines counted |
| `graph` | breadth-first search over `dict<int64 array<int64>>` with a `dict<int64 int64>` of distances |
| `string_equal`, `match_dispatch`, `branch_dispatch` | string comparison, constant-result and computed match arms |
| `managed_params`, `method_params` | read-only helpers taking arrays and records by value, called directly or as methods |
| `shifted_arrays` | shifted array indexes with a runtime offset: bounds-check elimination and vectorization |
| `array_swap`, `case_conversion`, `integer_parse`, `records_nested`, `recursive_list`, `recursive_tree` | further focused kernels |

Every program takes its size from the command line and generates its input
from a fixed linear congruential sequence, so nothing folds away at compile
time. Setup and output are outside the timed kernel; a program prints
`<checksum> <kernel nanoseconds>`.

Semantics matched between the languages: 64-bit signed integer arithmetic with
non-negative division operands, and text as bytes. Dewy checks or proves every
index; the C counterparts do not check. C has no dictionary, so `graph.c`
carries a hand-written open-addressing table and keeps every node's targets in
one flat array, while Dewy uses its insertion-ordered `dict` and one array per
node; that comparison includes representation and library costs.

`records.jo` performs the same particle updates in the implementation language,
for `tools/compiler/benchmark_sloppy.py`.
