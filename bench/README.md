# Application benchmarks

Small programs, each with a Dewy source and a C counterpart of the same
algorithm. `python3 -m tools.core bench [-k WORDS]` builds them (Dewy default
and release, C with `cc -O2`), runs each a few times and prints the median
kernel times, the Dewy/C ratios and whether the checksums agree. The
correctness suite also runs the workloads on native and web targets.

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
| `broadcast` | tensor broadcasting: a matrix plus a row and a column through `new` axes, clipped at zero, then a same-shape product and sum |
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

The compiler does not yet accept `harness.dewy` (a `$target` metatag and raw
intrinsics); builds substitute `harness.jo`, which uses the core library.
`records_nested` has no C file of its own: it shares `records.c`.
