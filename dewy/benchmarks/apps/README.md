# Small cross-language application benchmarks

The suite the roadmap accepted on 2026-10-03
([`../../ROADMAP.md`](../../ROADMAP.md#small-cross-language-application-benchmarks-accepted-2026-10-03)):
application evidence beside the compiler self-build, comparing ordinary Dewy
source on the µDewy route and the native (optimizing) route with a C
counterpart of the same algorithm.

    ./run.py COMPILER_DIR [--rounds N] [--only NAME ...]

`COMPILER_DIR` holds the native `dewy` and its `udewy`. The runner builds each
workload three ways, checks that the three checksums agree at every input
size, and prints one table row per build and input.

## Workloads

| name | what it exercises | inputs (small, larger) |
|---|---|---|
| `helpers` | small functions called from a hot scalar loop: gcd, a bounded Collatz walk, a clamp | 200 000 and 2 000 000 iterations |
| `arrays` | flat `array<int64>` loops: prefix sums, in-place reverse, a sieve | 1 000 000 and 10 000 000 elements |
| `records` | 50 passes over an `array<Particle>` of four-integer records, updating fields in place | 100 000 and 1 000 000 records |
| `text` | byte scanning: words hashed, decimal numbers parsed, lines counted | 1 000 000 and 10 000 000 tokens |
| `graph` | breadth-first search over `dict<int64 array<int64>>` with a `dict<int64 int64>` of distances | 200 000 and 1 000 000 nodes |

Every program takes its size from the command line and generates its input
from a fixed linear congruential sequence, so nothing folds away at compile
time. Setup and output are outside the timed kernel; a program prints
`<checksum> <kernel nanoseconds>`. The runner also reports the whole run.

## Semantics matched and differences recorded

- Arithmetic is 64-bit signed integers in both languages; every division and
  remainder has non-negative operands, so truncation and flooring agree.
- Text is bytes in both (`array<uint8>` and `uint8_t *`).
- Dewy checks or proves every index; the C counterparts do not check.
  No workload needed `$runtime_assert`: the loop conditions prove the bounds.
- `graph`: C has no dictionary, so `graph.c` carries the usual hand-written
  open-addressing table (multiplicative hash, grown at 3/4 full), and keeps
  every node's targets in one flat array. Dewy uses the prelude's `dict`,
  which also preserves insertion order, and one `array<int64>` per node.
- `records`: C holds the particles as a flat array of structs. Dewy's
  `array<Particle>` currently holds a reference per record, and each field
  write checks that the array and the record are not shared.
- Memory: the Dewy programs never return storage to the system before exit
  in these workloads; neither do the C ones.

Proof workarounds the ordinary source needed: a string argument is bound to
an `array<uint8>` name before it is looped over (`harness.dewy`), and
counters compared against an `int64` size are `int64` variables rather than
range loops. Nothing is manually tuned; a tuned variant would be recorded
separately.

## Compile latency

The table's compile time is one build with the checked prelude already
cached by an earlier build with the same compiler (the transitional cache
the roadmap describes). The first build after the compiler changes also
checks the prelude; that fresh figure is recorded with each set of results.

## Results

See [`RESULTS.md`](RESULTS.md): the baseline and each later checkpoint, with
the source revision, machine and toolchains.
